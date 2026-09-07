"""Local transcription worker and command-line entry point."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import tempfile
from contextlib import redirect_stdout
from app_paths import data_root
from sessions import prepare_session, transcript_suffix


def timestamp(seconds, srt=False):
    millis = max(0, round(seconds * 1000))
    hours, millis = divmod(millis, 3600000)
    minutes, millis = divmod(millis, 60000)
    seconds, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02}" + (f",{millis:03}" if srt else "")


def split_text(text, limit=12000):
    """Bound each part without dropping text or splitting ordinary words."""
    while text:
        end = min(limit, len(text))
        if end < len(text):
            boundary = text.rfind(" ", 0, end + 1)
            if boundary > 0:
                end = boundary
        yield text[:end]
        text = text[end:].lstrip()


def emit(kind, **fields):
    print(json.dumps({"kind": kind, **fields}, ensure_ascii=False), flush=True)


def run(audio, output, model_name="base", language=None, *, session_name="", session_dir=None):
    from faster_whisper import WhisperModel

    audio = Path(audio).resolve()
    if not audio.is_file():
        raise ValueError("Choose an existing audio or video file.")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    emit("status", message="Preparing session folder and saving the audio…")
    audio, folder = prepare_session(audio, output, session_name, session_dir)
    suffix = transcript_suffix(folder)
    emit("status", message="Loading speech model (first use downloads it; this may take several minutes).", folder=str(folder), audio=str(audio))
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    emit("status", message="Reading audio and detecting speech…")
    segments, info = model.transcribe(str(audio), language=language, beam_size=5,
                                      vad_filter=True, condition_on_previous_text=False)
    emit("status", message=f"Transcribing • language: {info.language} • {timestamp(info.duration)} of audio")
    texts = []
    # Flush every segment: interrupted jobs retain their partial transcript.
    with (folder / f"transcript{suffix}.partial.txt").open("w", encoding="utf-8") as plain, \
         (folder / f"timestamps{suffix}.partial.txt").open("w", encoding="utf-8") as timed, \
         (folder / f"subtitles{suffix}.partial.srt").open("w", encoding="utf-8") as subtitles:
        count = 0
        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue
            count += 1
            texts.append(text)
            plain.write(text + "\n")
            timed.write(f"[{timestamp(segment.start)} – {timestamp(segment.end)}] {text}\n")
            subtitles.write(f"{count}\n{timestamp(segment.start, True)} --> {timestamp(segment.end, True)}\n{text}\n\n")
            for handle in (plain, timed, subtitles):
                handle.flush()
            emit("segment", text=text, progress=min(99, segment.end / max(info.duration, 1) * 100))
    if not texts:
        raise ValueError("No speech was detected. Try another file or select its language manually.")
    for name in ("transcript.txt", "timestamps.txt", "subtitles.srt"):
        path = Path(name)
        (folder / f"{path.stem}{suffix}.partial{path.suffix}").rename(folder / f"{path.stem}{suffix}{path.suffix}")
    parts = folder / f"AI-parts{suffix}"
    parts.mkdir()
    chunks = list(split_text("\n".join(texts)))
    for i, chunk in enumerate(chunks, 1):
        (parts / f"part-{i:03}.txt").write_text(f"Audio: {audio.name}\nPart {i} of {len(chunks)}\n\n{chunk}\n", encoding="utf-8")
    (folder / f"details{suffix}.json").write_text(json.dumps({"source": str(audio), "model": model_name,
        "language": info.language, "duration_seconds": info.duration, "segments": count}, indent=2), encoding="utf-8")
    emit("done", folder=str(folder), transcript=str(folder / f"transcript{suffix}.txt"))
    return folder


def main(argv=None):
    parser = argparse.ArgumentParser(description="Transcribe audio locally into text, timestamps, subtitles, and AI-sized parts.")
    parser.add_argument("audio", type=Path)
    parser.add_argument("--output", type=Path, default=data_root() / "transcripts")
    parser.add_argument("--model", choices=["tiny", "base", "small", "medium"], default="base")
    parser.add_argument("--language", default=None, help="Language code such as en or fr; omit to detect")
    parser.add_argument("--events-file", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--session-name", default="", help="Folder name for audio and transcript")
    parser.add_argument("--session-dir", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.events_file:
        with args.events_file.open("w", encoding="utf-8", buffering=1) as stream, redirect_stdout(stream):
            return execute(args)
    return execute(args)


def execute(args):
    try:
        run(args.audio, args.output, args.model, args.language, session_name=args.session_name, session_dir=args.session_dir)
    except Exception as exc:
        emit("error", message=str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
