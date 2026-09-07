"""Desktop UI. Speech recognition runs in a cancellable child process."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tempfile
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from recorder import list_devices, record, SOURCES
from ui import SignalUI
from app_paths import ROOT, data_root
from sessions import safe_name

class App(SignalUI, tk.Tk):
    def __init__(self):
        super().__init__()
        self.process = None
        self.events = queue.Queue()
        self.result_folder = None
        self.cancelled = False
        self.completed = False
        self.recording_thread = None
        self.recording_stop = threading.Event()
        self.closing = False
        self.devices = []
        self.microphones = []
        self.device_name = tk.StringVar()
        self.microphone_name = tk.StringVar()
        self.audio = tk.StringVar()
        self.session_name = tk.StringVar()
        self.session_path = tk.StringVar()
        self.session_dir = None
        self.data_root = data_root()
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.output = tk.StringVar(value=str(self.data_root / "transcripts"))
        self.model = tk.StringVar(value="base")
        self.language = tk.StringVar(value="Auto detect")
        self.settings_path = self.data_root / "settings.json"
        self.settings = self.read_settings()
        self.sources = SOURCES
        saved_source = self.settings.get("source", "Computer audio")
        self.source_name = tk.StringVar(value=saved_source if saved_source in SOURCES else "Computer audio")
        self.output.set(self.settings.get("output", str(self.data_root / "transcripts")))
        self.qualities = {"Fast": "tiny", "Balanced": "base", "Detailed": "small", "Maximum": "medium"}
        saved_model = self.settings.get("model", "base")
        self.model.set(saved_model if saved_model in self.qualities.values() else "base")
        self.quality_name = tk.StringVar(value=next(k for k, v in self.qualities.items() if v == self.model.get()))
        self.language.set(self.settings.get("language", "Auto detect"))
        self.auto_transcribe = tk.BooleanVar(value=self.settings.get("auto_transcribe", True))
        self.recent_name = tk.StringVar(value="Recent transcripts")
        self.search_text = tk.StringVar()
        self.search_position = "1.0"
        self.word_count = 0
        self.status = tk.StringVar(value="Capture audio, then turn it into text. Everything stays on this computer.")
        self.build_ui()
        self.refresh_devices()
        self.refresh_recent()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(150, self.poll)

    def read_settings(self):
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def save_settings(self):
        self.settings.update(output=self.output.get(), model=self.model.get(), language=self.language.get(),
                             auto_transcribe=self.auto_transcribe.get(), device=self.device_name.get(),
                             source=self.source_name.get(), microphone=self.microphone_name.get())
        try:
            temporary = self.settings_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(self.settings, indent=2), encoding="utf-8")
            temporary.replace(self.settings_path)
        except OSError:
            pass

    def quality_changed(self, event=None):
        self.model.set(self.qualities[self.quality_name.get()])
        hints = {"tiny": "Fastest results; lower accuracy", "base": "Balanced speed and accuracy",
                 "small": "Better accuracy; takes longer", "medium": "Most detailed; slowest on this computer"}
        self.quality_hint.configure(text=hints[self.model.get()])

    def update_output_label(self):
        path = self.output.get()
        self.output_label.configure(text=path if len(path) < 70 else "…" + path[-67:])
        self.update_session_preview()

    def update_session_preview(self, *args):
        if self.session_dir and self.session_name.get() == Path(self.session_dir).name:
            target = Path(self.session_dir)
        else:
            target = Path(self.output.get()) / safe_name(self.session_name.get())
        self.session_path.set("Audio + transcript → " + str(target))
        self.session_open_button.configure(state="normal" if self.session_dir and self.session_name.get() == Path(self.session_dir).name else "disabled")

    def open_session(self):
        if self.session_dir and Path(self.session_dir).is_dir():
            try:
                os.startfile(str(self.session_dir))
            except OSError as exc:
                messagebox.showerror("Cannot open session", str(exc))

    def set_session(self, folder):
        self.session_dir = Path(folder)
        self.session_name.set(self.session_dir.name)
        self.session_open_button.configure(state="normal")
        self.update_session_preview()

    def open_library(self):
        try:
            Path(self.output.get()).mkdir(parents=True, exist_ok=True)
            os.startfile(self.output.get())
        except OSError as exc:
            messagebox.showerror("Cannot open library", str(exc))

    def refresh_recent(self):
        saved = [p for p in self.settings.get("recent", []) if isinstance(p, str) and Path(p).is_file()]
        try:
            found = sorted((p for p in Path(self.output.get()).glob("*/transcript*.txt") if ".partial." not in p.name), key=lambda p: p.stat().st_mtime, reverse=True)
            saved += [str(p) for p in found if str(p) not in saved]
        except OSError:
            pass
        self.recents = saved[:12]
        self.recent_box.configure(values=[f"{i+1}. {Path(p).parent.name}" for i, p in enumerate(self.recents)])
        self.recent_name.set("Recent transcripts" if self.recents else "No recent transcripts yet")

    def load_recent(self, event=None):
        if self.process or self.recording_thread:
            return
        i = self.recent_box.current()
        if i < 0 or i >= len(self.recents):
            return
        path = Path(self.recents[i])
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            self.status.set(f"Cannot load transcript: {exc}")
            return
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")
        self.empty_label.place_forget()
        self.word_count = len(text.split())
        self.word_label.configure(text=f"{self.word_count:,} words")
        self.copy_button.configure(state="normal")
        self.export_button.configure(state="normal")
        self.result_folder = str(path.parent)
        self.set_session(path.parent)
        if (path.parent / "session.json").is_file():
            candidates = [path.parent / name for name in ("combined.wav", "computer.wav", "microphone.wav")]
            candidates += list(path.parent.glob("recording.*"))
            selected = next((p for p in candidates if p.is_file() and p.suffix != ".copying"), None)
            if selected:
                self.audio.set(str(selected))
        self.folder_button.configure(state="normal")
        self.search_position = "1.0"
        self.status.set("Loaded a saved transcript.")

    def find_text(self, event=None):
        query = self.search_text.get().strip()
        self.preview.tag_remove("match", "1.0", "end")
        if not query:
            return
        at = self.preview.search(query, self.search_position, stopindex="end", nocase=True)
        if not at:
            at = self.preview.search(query, "1.0", stopindex="end", nocase=True)
        if at:
            end = f"{at}+{len(query)}c"
            self.preview.tag_add("match", at, end)
            self.preview.see(at)
            self.search_position = self.preview.index(end)
        else:
            self.status.set("No matching text found.")

    def export_text(self):
        text = self.preview.get("1.0", "end-1c")
        if not text.strip():
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="transcript.txt", filetypes=[("Text", "*.txt")])
        if path:
            try:
                Path(path).write_text(text, encoding="utf-8")
                self.status.set("Transcript exported.")
            except OSError as exc:
                messagebox.showerror("Cannot save transcript", str(exc))

    def refresh_devices(self):
        try:
            self.devices, default, self.microphones, default_mic = list_devices()
            labels = [d['name'].replace(' [Loopback]', '') for d in self.devices]
            self.device_box.configure(values=labels)
            selected = next((i for i, d in enumerate(self.devices) if d["index"] == default), 0)
            if self.settings.get("device") in labels:
                selected = labels.index(self.settings["device"])
            self.device_name.set(labels[selected] if labels else "No playback devices available")
            mic_labels = [d["name"] for d in self.microphones]
            self.microphone_box.configure(values=mic_labels)
            selected_mic = next((i for i, d in enumerate(self.microphones) if d["index"] == default_mic), 0)
            if self.settings.get("microphone") in mic_labels:
                selected_mic = mic_labels.index(self.settings["microphone"])
            self.microphone_name.set(mic_labels[selected_mic] if mic_labels else "No microphone available")
            self.source_changed()
        except Exception as exc:
            self.devices = []
            self.microphones = []
            self.record_button.configure(state="disabled")
            self.status.set(f"Audio devices unavailable: {exc}")

    def can_record(self):
        source = self.sources[self.source_name.get()]
        return ((source == "microphone" or bool(self.devices)) and
                (source == "computer" or bool(self.microphones)))

    def source_changed(self, event=None):
        source = self.sources[self.source_name.get()]
        self.device_section.pack_forget()
        self.microphone_section.pack_forget()
        if source in ("computer", "both"):
            self.device_section.pack(fill="x", before=self.timer_label)
        if source in ("microphone", "both"):
            self.microphone_section.pack(fill="x", before=self.timer_label)
        hints = {"computer": "Captures all apps on the selected output. Microphone is off.",
                 "microphone": "Records only the selected microphone. Computer audio is off.",
                 "both": "Records both sources. Use headphones to avoid echo. Separate tracks are also saved."}
        self.source_hint.configure(text=hints[source])
        self.record_button.configure(state="normal" if self.can_record() else "disabled")
        if event:
            self.save_settings()

    def start_recording(self):
        if self.process or self.recording_thread:
            return
        selection = self.device_box.current()
        microphone = self.microphone_box.current()
        source = self.sources[self.source_name.get()]
        if (not self.can_record() or not self.output.get().strip()
                or (source != "microphone" and selection < 0)
                or (source != "computer" and microphone < 0)):
            messagebox.showerror("Choose audio devices", "Select the required recording devices and an output folder.")
            return
        self.recording_stop.clear()
        self.session_dir = None
        self.session_open_button.configure(state="disabled")
        self.save_settings()
        self.timer_label.configure(text="00:00:00")
        self.meter_values = [0] * 44
        self.draw_meter()
        self.capture_hint.configure(text="OPENING AUDIO DEVICE")
        self.state_label.configure(text="● RECORDING", fg="#ffb1bf")
        self.busy(True)
        self.cancel_button.configure(state="disabled")
        self.record_button.pack_forget()
        self.stop_button.configure(state="normal", text="■  Stop & transcribe" if self.auto_transcribe.get() else "■  Save recording")
        self.stop_button.pack(fill="x", before=self.auto_check)
        self.status.set("Opening the playback device…")
        self.recording_thread = threading.Thread(target=record,
            args=(self.output.get(), self.devices[selection]["index"] if source != "microphone" else None,
                  self.recording_stop, self.events.put),
            kwargs={"source": source, "microphone_index": self.microphones[microphone]["index"] if source != "computer" else None,
                    "session_name": self.session_name.get()}, daemon=True)
        self.recording_thread.start()

    def stop_recording(self):
        self.recording_stop.set()
        self.stop_button.configure(state="disabled")
        self.status.set("Saving your recording…")

    def choose_audio(self):
        path = filedialog.askopenfilename(filetypes=[("Audio and video", "*.mp3 *.wav *.m4a *.mp4 *.flac *.ogg *.opus *.aac *.wma *.webm *.mkv"), ("All files", "*.*")])
        if path:
            self.session_dir = None
            self.session_open_button.configure(state="disabled")
            self.audio.set(path)
            self.session_name.set(Path(path).stem)
            if (Path(path).parent / "session.json").is_file():
                self.set_session(Path(path).parent)
            self.set_mode("file")

    def choose_output(self):
        path = filedialog.askdirectory()
        if path:
            self.output.set(path)
            self.session_dir = None
            self.session_open_button.configure(state="disabled")
            self.update_output_label()
            self.save_settings()
            self.refresh_recent()

    def busy(self, value):
        for control, idle_state in self.controls:
            control.configure(state="disabled" if value else idle_state)
        self.start_button.configure(state="disabled" if value else "normal")
        self.cancel_button.configure(state="normal" if value else "disabled")
        self.record_button.configure(state="disabled" if value or not self.can_record() else "normal")
        self.refresh_button.configure(state="disabled" if value else "normal")
        self.device_box.configure(state="disabled" if value else "readonly")
        self.microphone_box.configure(state="disabled" if value else "readonly")
        self.recent_box.configure(state="disabled" if value else "readonly")

    def start(self):
        if self.process or self.recording_thread:
            return
        if not Path(self.audio.get()).is_file() or not self.output.get().strip():
            messagebox.showerror("Choose a file", "Choose an existing audio file and an output folder.")
            return
        self.result_folder = None
        self.save_settings()
        self.cancelled = self.completed = False
        self.word_count = 0
        self.word_label.configure(text="0 words")
        self.search_position = "1.0"
        self.empty_label.place_forget()
        self.state_label.configure(text="● TRANSCRIBING", fg="#67e8c2")
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.configure(state="disabled")
        self.copy_button.configure(state="disabled")
        self.export_button.configure(state="disabled")
        self.folder_button.configure(state="disabled")
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self.status.set("Starting transcription…")
        self.busy(True)
        if getattr(sys, "frozen", False):
            command = [sys.executable, "--transcribe"]
        else:
            command = [sys.executable, "-u", str(ROOT / "transcribe.py")]
        command += [self.audio.get(), "--output", self.output.get(), "--model", self.model.get()]
        command += ["--session-name", self.session_name.get()]
        if (self.session_dir and (Path(self.session_dir) / "session.json").is_file()
                and Path(self.audio.get()).resolve().parent == Path(self.session_dir).resolve()
                and self.session_name.get() == Path(self.session_dir).name):
            command += ["--session-dir", str(self.session_dir)]
        language = self.language.get().strip()
        if language and language != "Auto detect":
            command.extend(["--language", language])
        try:
            with tempfile.NamedTemporaryFile(prefix="signal-events-", suffix=".jsonl", delete=False) as temporary:
                events_path = Path(temporary.name)
            command.extend(["--events-file", str(events_path)])
            env = dict(os.environ, PYTHONIOENCODING="utf-8")
            self.process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        except Exception as exc:
            if "events_path" in locals():
                events_path.unlink(missing_ok=True)
            self.progress.stop()
            self.busy(False)
            self.status.set(f"Could not start: {exc}")
            self.state_label.configure(text="● ERROR", fg="#ffb1bf")
            return
        threading.Thread(target=self.read_worker, args=(self.process, events_path), daemon=True).start()

    def read_worker(self, process, events_path):
        pending = b""
        try:
            with events_path.open("rb") as stream:
                while True:
                    # Check exit before reading, so the final read drains all flushed events.
                    finished = process.poll() is not None
                    pending += stream.read()
                    while b"\n" in pending:
                        line, pending = pending.split(b"\n", 1)
                        try:
                            event = json.loads(line)
                            if isinstance(event, dict) and "kind" in event:
                                self.events.put(event)
                        except (ValueError, UnicodeError):
                            pass
                    if finished:
                        break
                    time.sleep(.1)
            self.events.put({"kind": "exit", "code": process.wait(), "detail": "Check that the app dependencies are installed if this persists."})
        except OSError as exc:
            if process.poll() is None:
                process.terminate()
            self.events.put({"kind": "exit", "code": process.wait() or 1, "detail": str(exc)})
        finally:
            events_path.unlink(missing_ok=True)

    def poll(self):
        while not self.events.empty():
            event = self.events.get_nowait()
            kind = event["kind"]
            if kind == "recording_started":
                self.audio.set(event["path"])
                self.set_session(Path(event["path"]).parent)
                self.capture_hint.configure(text="RECORDING " + self.source_name.get().upper())
                self.status.set("Recording selected sources. Text is generated after capture stops.")
            elif kind == "recording_processing":
                self.status.set(event["message"])
            elif kind == "recording_level":
                self.draw_meter(event["level"])
                seconds = int(event["seconds"])
                self.timer_label.configure(text=f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}")
                hint = "AUDIO DETECTED" if event["level"] > .1 else "WAITING FOR SOUND"
                self.capture_hint.configure(text=hint)
                levels = event.get("levels", {})
                self.status.set(" · ".join(f"{name.title()}: {'audio detected' if value > .1 else 'quiet'}" for name, value in levels.items()))
            elif kind == "recording_finished":
                self.recording_thread = None
                self.stop_button.configure(state="disabled")
                self.stop_button.pack_forget()
                self.record_button.pack(fill="x", before=self.auto_check)
                self.capture_hint.configure(text="CAPTURE SAVED")
                self.state_label.configure(text="● READY", fg="#67e8c2")
                self.busy(False)
                if event["path"]:
                    self.audio.set(event["path"])
                    self.set_session(Path(event["path"]).parent)
                    self.result_folder = str(Path(event["path"]).parent)
                    self.folder_button.configure(state="normal")
                if self.closing:
                    self.save_settings()
                    self.destroy()
                    return
                if event["error"]:
                    if event["path"]:
                        self.set_mode("file")
                    self.status.set("Recording stopped: " + event["error"] + " Any captured audio is in the selected file; click Transcribe to process it.")
                elif not event["has_audio"]:
                    self.status.set("No audible sound captured. Check playback, volume, and your selected output device.")
                else:
                    if event.get("silent_sources") and len(event["silent_sources"]) == 1 and self.sources[self.source_name.get()] == "both":
                        self.capture_hint.configure(text="ONE SOURCE WAS SILENT — CHECK DEVICES")
                    if event["reason"]:
                        messagebox.showinfo("Recording saved", event["reason"])
                    if self.auto_transcribe.get():
                        self.start()
                    else:
                        self.set_mode("file")
                        self.status.set("Recording saved. Transcribe it now, or find the audio in your library later.")
            elif kind == "status":
                self.status.set(event["message"])
                if "audio" in event:
                    self.audio.set(event["audio"])
                if "folder" in event:
                    self.result_folder = event["folder"]
                    self.set_session(event["folder"])
                    self.folder_button.configure(state="normal")
            elif kind == "segment":
                self.progress.stop()
                self.progress.configure(mode="determinate", value=event["progress"])
                self.preview.configure(state="normal")
                self.preview.insert("end", event["text"] + "\n")
                self.preview.see("end")
                self.preview.configure(state="disabled")
                self.word_count += len(event["text"].split())
                self.word_label.configure(text=f"{self.word_count:,} words")
                self.copy_button.configure(state="normal")
                self.export_button.configure(state="normal")
            elif kind == "done":
                self.completed = True
                self.progress.stop()
                self.progress.configure(mode="determinate", value=100)
                self.status.set("Done. Copy the text, or open results for the transcript, timestamps, subtitles, and AI-parts.")
                self.state_label.configure(text="● COMPLETE", fg="#67e8c2")
                transcript = event.get("transcript", str(Path(event["folder"]) / "transcript.txt"))
                self.settings["recent"] = [transcript] + [p for p in self.settings.get("recent", []) if p != transcript][:11]
                self.save_settings()
                self.refresh_recent()
            elif kind == "error":
                self.status.set("Transcription failed: " + event["message"])
                self.state_label.configure(text="● ERROR", fg="#ffb1bf")
            elif kind == "exit":
                self.process = None
                self.progress.stop()
                self.busy(False)
                if self.cancelled and not self.completed:
                    self.state_label.configure(text="● CANCELLED", fg="#93a5b9")
                    self.status.set("Cancelled. Any text already transcribed is saved in files marked .partial.")
                elif event["code"] and not self.status.get().startswith("Transcription failed:"):
                    self.state_label.configure(text="● ERROR", fg="#ffb1bf")
                    self.status.set("Transcription failed. " + (event["detail"][-500:] or "The worker exited unexpectedly."))
        self.after(150, self.poll)

    def cancel(self):
        if self.process and self.process.poll() is None:
            self.cancelled = True
            self.process.terminate()
            self.cancel_button.configure(state="disabled")
            self.status.set("Cancelling…")

    def copy(self):
        if not self.preview.get("1.0", "end-1c").strip():
            return
        self.clipboard_clear()
        self.clipboard_append(self.preview.get("1.0", "end-1c"))
        self.status.set("Text copied. Paste it into your AI conversation.")

    def open_results(self):
        if self.result_folder:
            try:
                os.startfile(self.result_folder)
            except OSError as exc:
                messagebox.showerror("Cannot open folder", str(exc))

    def close(self):
        self.save_settings()
        if self.recording_thread:
            self.closing = True
            self.stop_recording()
            return
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=5)
        self.destroy()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--transcribe":
        from transcribe import main
        raise SystemExit(main(sys.argv[2:]))
    App().mainloop()
