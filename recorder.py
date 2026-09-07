"""Windows WASAPI capture with time-aligned computer and microphone tracks."""
from array import array
from contextlib import ExitStack
from datetime import datetime
import json
from pathlib import Path
import queue
import tempfile
import threading
import time
import wave
from sessions import create_session

SOURCES = {"Computer audio": "computer", "Microphone": "microphone", "Computer + microphone": "both"}
MAX_BYTES = 3_500_000_000


def list_devices():
    """WASAPI input devices only, avoiding duplicates from other Windows APIs."""
    import pyaudiowpatch as pa
    with pa.PyAudio() as audio:
        host = audio.get_host_api_info_by_type(pa.paWASAPI)
        devices = list(audio.get_device_info_generator())
        outputs = [d for d in devices if d.get("isLoopbackDevice")]
        microphones = [d for d in devices if d["hostApi"] == host["index"]
                       and d["maxInputChannels"] > 0 and not d.get("isLoopbackDevice")]
        try:
            default_output = audio.get_default_wasapi_loopback()["index"]
        except OSError:
            default_output = None
        return outputs, default_output, microphones, host.get("defaultInputDevice")


def playback_devices():
    outputs, default, _, _ = list_devices()
    return outputs, default


class TimelineWriter:
    """Place PCM on a common timeline; retain silence during source gaps."""
    def __init__(self, handle, rate, channels):
        self.handle, self.rate, self.channels = handle, rate, channels
        self.frames = 0
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(rate)

    def pad_to(self, target):
        while self.frames < target:
            count = min(8192, target - self.frames)
            self.handle.writeframes(b"\0" * count * self.channels * 2)
            self.frames += count

    def write(self, data, seconds):
        target = max(0, round(seconds * self.rate))
        # Ignore scheduling jitter; re-align gaps and clock drift beyond 50 ms.
        if not self.frames or abs(target - self.frames) > self.rate * .05:
            self.pad_to(target)
            if target < self.frames:
                data = data[(self.frames - target) * self.channels * 2:]
        self.handle.writeframes(data)
        self.frames += len(data) // (self.channels * 2)


def mono_blocks(path, rate=16000, block_size=8192):
    """Bounded-memory resampling of different native sample rates."""
    import av
    import numpy as np
    pending = np.empty(0, dtype=np.int16)
    with av.open(str(path)) as source:
        resampler = av.AudioResampler(format="s16", layout="mono", rate=rate)
        for frame in source.decode(audio=0):
            for converted in resampler.resample(frame):
                pending = np.concatenate((pending, converted.to_ndarray().reshape(-1)))
                while len(pending) >= block_size:
                    yield pending[:block_size]
                    pending = pending[block_size:]
        for converted in resampler.resample(None):
            pending = np.concatenate((pending, converted.to_ndarray().reshape(-1)))
        while len(pending):
            yield pending[:block_size]
            pending = pending[block_size:]


def mix_tracks(paths, destination):
    """Average sources with headroom; never concatenate or overflow int16."""
    import numpy as np
    from itertools import zip_longest
    destination = Path(destination)
    partial = destination.with_name(destination.stem + ".partial.wav")
    with wave.open(str(partial), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        for blocks in zip_longest(*(mono_blocks(path) for path in paths)):
            length = max(len(block) for block in blocks if block is not None)
            total = np.zeros(length, dtype=np.int32)
            for block in blocks:
                if block is not None:
                    total[:len(block)] += block.astype(np.int32)
            mixed = np.clip(total / len(paths), -32768, 32767).astype("<i2")
            output.writeframes(mixed.tobytes())
    partial.replace(destination)
    return destination


def record(output, device_index, stop, notify, *, source="computer", microphone_index=None, session_name=""):
    """Capture selected sources; computer-only mode never opens a microphone."""
    import pyaudiowpatch as pa
    folder = None
    tracks = []
    error = None
    reason = ""
    path = None
    total_frames = 0
    peaks = {}
    started = None
    duration = 0
    try:
        if source not in SOURCES.values():
            raise ValueError("Unknown recording source.")
        requested = []
        if source in ("computer", "both"):
            requested.append(("computer", device_index, True))
        if source in ("microphone", "both"):
            requested.append(("microphone", microphone_index, False))
        with pa.PyAudio() as audio, ExitStack() as stack:
            for name, index, loopback in requested:
                if index is None:
                    raise ValueError(f"Select a {name} device first.")
                device = audio.get_device_info_by_index(index)
                if bool(device.get("isLoopbackDevice")) != loopback or device["maxInputChannels"] < 1:
                    raise ValueError(f"The selected {name} device has the wrong input type.")
                tracks.append({"name": name, "device": device})
            folder = create_session(output, session_name)
            packets = queue.Queue(maxsize=512)
            overflow = threading.Event()

            def callback_for(name, rate):
                def callback(data, frame_count, timing, flags):
                    now = time.monotonic()
                    current, adc = timing.get("current_time", 0), timing.get("input_buffer_adc_time", 0)
                    delay = current - adc
                    if not adc or not 0 <= delay <= 5:
                        delay = frame_count / rate
                    try:
                        packets.put_nowait((name, data, now - delay, flags))
                    except queue.Full:
                        overflow.set()
                    return (None, pa.paContinue)
                return callback

            for track in tracks:
                device = track["device"]
                rate, channels = int(device["defaultSampleRate"]), int(device["maxInputChannels"])
                track["path"] = folder / (track["name"] + ".wav")
                handle = stack.enter_context(wave.open(str(track["path"]), "wb"))
                track["writer"] = TimelineWriter(handle, rate, channels)
                track["stream"] = stack.enter_context(audio.open(
                    format=pa.paInt16, channels=channels, rate=rate, input=True,
                    input_device_index=device["index"], frames_per_buffer=1024, start=False,
                    stream_callback=callback_for(track["name"], rate)))
                peaks[track["name"]] = 0
            lookup = {track["name"]: track for track in tracks}
            path = tracks[0]["path"]
            started = last_update = time.monotonic()
            levels = dict(peaks)
            for track in tracks:
                track["stream"].start_stream()
            notify({"kind": "recording_started", "path": str(path), "source": source,
                    "device": " + ".join(t["device"]["name"] for t in tracks)})

            def consume(packet):
                name, data, capture_time, flags = packet
                if flags & pa.paInputOverflow:
                    raise RuntimeError("Audio capture overflowed. Partial tracks are saved; close busy apps and retry.")
                track = lookup[name]
                seconds = capture_time - started
                if seconds < 0:
                    trim = round(-seconds * track["writer"].rate) * track["writer"].channels * 2
                    data, seconds = data[trim:], 0
                track["writer"].write(data, seconds)
                peak = max((abs(value) for value in array("h", data)), default=0)
                peaks[name] = max(peaks[name], peak)
                levels[name] = max(levels[name], peak)

            try:
                while not stop.is_set():
                    try:
                        consume(packets.get(timeout=.05))
                    except queue.Empty:
                        pass
                    now = time.monotonic()
                    if overflow.is_set():
                        raise RuntimeError("The recording queue filled up. Partial tracks are saved.")
                    if now - last_update >= .25:
                        notify({"kind": "recording_level", "seconds": now - started,
                                "level": max(levels.values(), default=0) / 32768 * 100,
                                "levels": {k: v / 32768 * 100 for k, v in levels.items()}})
                        levels = {name: 0 for name in levels}
                        last_update = now
                        for track in tracks:
                            writer = track["writer"]
                            if (now - started) * writer.rate * writer.channels * 2 >= MAX_BYTES:
                                reason = "Recording reached the WAV size limit and was saved automatically."
                                stop.set()
                    if any(not t["stream"].is_active() for t in tracks):
                        raise RuntimeError("An audio device stopped. Partial tracks are saved.")
            finally:
                duration = time.monotonic() - started
                for track in tracks:
                    track["stream"].stop_stream()
            while not packets.empty():
                consume(packets.get_nowait())
            for track in tracks:
                writer = track["writer"]
                writer.pad_to(round(duration * writer.rate))
                total_frames += writer.frames
        if source == "both":
            notify({"kind": "recording_processing", "message": "Saving mixed audio. Your original tracks are already saved."})
            path = mix_tracks([t["path"] for t in tracks], folder / "combined.wav")
    except Exception as exc:
        error = str(exc)
    if folder:
        try:
            (folder / "capture.json").write_text(json.dumps({
                "source": source, "duration_seconds": duration, "error": error,
                "tracks": [{"file": t["path"].name, "device": t["device"]["name"],
                            "sample_rate": t["writer"].rate, "peak": peaks.get(t["name"], 0)}
                           for t in tracks if "writer" in t]}, indent=2), encoding="utf-8")
        except OSError as exc:
            error = error or f"Could not save recording details: {exc}"
    notify({"kind": "recording_finished", "path": str(path) if path and path.exists() else None,
            "frames": total_frames, "has_audio": max(peaks.values(), default=0) > 32,
            "silent_sources": [k for k, v in peaks.items() if v <= 32],
            "error": error, "reason": reason})
