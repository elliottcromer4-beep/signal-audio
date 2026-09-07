<p align="center"><img src="assets/signal.svg" width="80" alt="Signal Audio waveform logo"></p>
<h1 align="center">Signal Audio</h1>
<p align="center">Capture audio. Turn it into words. Keep it local.</p>

A dark Windows desktop app for recording computer audio, a microphone, or both,
and turning speech into text you can search, save, or give to an AI.

## Features

- **Three capture modes:** computer playback, microphone input, or both together.
- **Separate original tracks and a mixed file** when capturing both sources.
- **Local transcription** with faster-whisper; no API key or subscription.
- **Import audio/video:** MP3, WAV, M4A, MP4, FLAC, OGG, and other supported media.
- **Text, timestamps, subtitles, and AI-sized parts** in one results folder.
- Recording timer, activity indicators, record-only mode, transcript search,
  word count, recent transcripts, and remembered settings.

## Run the portable Windows app

1. Download and extract `signal-audio-0.3.0-windows-x64.zip` from the repository's
   release assets. Keep the whole extracted folder, including `_internal`.
2. Run **SignalAudio.exe**. Python is not required.
3. The first transcription downloads the selected speech model. Models are
   cached for later use; transcription can then run offline.

Requires Windows 10/11 x64. This release is unsigned. There is no auto-updater.
Model weights are not included in the ZIP. Recognition runs on the CPU; long
recordings and larger models can take substantial time and memory.

## Named sessions

Enter a **Session name** at the top of the window, such as `Interview with Alex`.
The destination shown underneath contains both the audio and transcript.
Use **Save location…** to choose the parent library folder, and **Open session
folder ↗** to open the actual session once it has been created.

```text
Your library/
  Interview with Alex/
    microphone.wav
    transcript.txt
    timestamps.txt
    subtitles.srt
    AI-parts/
    session.json
```

Computer recordings use `computer.wav`; combined mode also adds `combined.wav`.
Imported media is copied as `recording.mp3` (or its original extension), so the
source stays unchanged. Leave the name blank for an automatic recording name.
A duplicate folder name becomes `Interview with Alex (2)`. Transcribing audio
again within a session preserves the previous files and creates `transcript-2.txt`,
`timestamps-2.txt`, and so on. Renaming the field before importing/transcribing
creates a new session rather than renaming an existing folder. Old libraries
are not moved or reorganized automatically.

## Record audio

1. Select **Record audio**, then choose a source:

   | Source | What gets captured |
   | --- | --- |
   | Computer audio | All applications on the chosen speakers/headphones; microphone stays off. |
   | Microphone | Only the selected microphone/input device. |
   | Computer + microphone | Both selected sources, with separate originals and a combined recording. |

2. Choose the playback device and/or microphone. Use **↻** to refresh after
   connecting a new device. Selected devices stay fixed during a recording.
3. Click **Start recording**, then play audio or speak. The footer reports
   activity for each source; the meter shows the highest source level.
4. Click **Stop & transcribe**. The original audio is saved before recognition
   starts. In combined mode, a mixed track is created first.
5. Use **Copy text**, **Save as…**, or **Files ↗** to use the result.

Uncheck **Transcribe when recording stops** to save audio without immediately
transcribing. The recording is selected in **Import file** for later use.
**Text is generated after capture stops; this is not live captioning.**

Use headphones when recording both sources to avoid the microphone picking up
speaker audio a second time. There is no echo cancellation, speaker labeling,
per-application isolation, or cloud processing. Record only where you have
permission. Keep the selected devices connected and the computer awake.

## Import an existing recording

Choose **Import file**, select an audio or video file, and click
**Transcribe file →**. Webpage and streaming-service links are not media files.
Use computer capture to record local playback instead.

| Quality | Model | Tradeoff |
| --- | --- | --- |
| Fast | tiny | Fastest; lower accuracy |
| Balanced | base | Default balance of speed and accuracy |
| Detailed | small | Better accuracy; slower |
| Maximum | medium | Largest available in this app; slowest |

Language is detected automatically, or enter a language code such as `en` or
`fr`. Automatic transcripts can mishear names and overlapping speech; review
important passages against the audio.

## Files and privacy

The portable app keeps settings and the default library under
`%LOCALAPPDATA%\SignalAudio`. Source runs use the project directory. Use
**Save location…** to select another library, or **Open library ↗** to find it.
Advanced users and tests can set `SIGNAL_DATA_DIR` to choose a different data
root. Existing source-run recordings/settings are not moved automatically
when switching to the portable application.

Every capture gets its own named session folder directly inside the library:

- `computer.wav` and/or `microphone.wav`: original native-rate captures.
- `combined.wav`: mixed 16 kHz mono audio when both sources are selected.
- `capture.json`: selected device names, timing, levels, and any capture error.
- `session.json`: session name and creation time.

The mixed track uses an equal blend with headroom to avoid clipping. Source
tracks are aligned using driver timing and padded during gaps. Timing is
suitable for speech, not sample-accurate studio recording. Devices with weak
timestamps can have small offsets; keep the originals for later editing.
At 48 kHz stereo, each source uses roughly 690 MB per hour. Capture stops
before any original WAV reaches 3.5 GB (about five hours at that format).

The transcript is saved in that same session folder, alongside its audio:

- `transcript.txt`: plain text.
- `timestamps.txt`: text with segment times.
- `subtitles.srt`: subtitles.
- `AI-parts/part-001.txt`, etc.: up to 12,000 transcript characters per part,
  plus a header. AI limits vary; these parts are a convenience, not a guarantee.
- `details.json`: source path, selected model, detected language, and duration.

Failed or cancelled transcription keeps generated text in `.partial` files.
Restarting begins again rather than resuming. A recording error preserves
tracks already written. Closing during capture saves it without starting
recognition. If closing during mixing, the app finishes saving before exiting.
No recordings or transcripts are uploaded by the app. Initial model downloads
contact Hugging Face. No account or token is required.

## Useful controls

- **Recent transcripts:** reopen up to 12 completed transcripts.
- **Search / Find next:** search without changing the transcript.
- **Ctrl+O:** import a file. **Ctrl+F:** search. **Ctrl+Shift+C:** copy text.
- Output folder, source, devices, quality, language, and auto-transcribe choice
  are remembered in local settings.

## Run from source

Install Python **3.11 x64** with Tcl/Tk from python.org. Extract the source ZIP
and double-click **Start Signal.cmd**. The launcher creates `.venv` and installs
the pinned dependencies on first launch. Internet is required for setup.

Or run these commands from the extracted project folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe app.py
```

CLI transcription:

```powershell
.\.venv\Scripts\python.exe transcribe.py "C:\audio\recording.mp3" --model base --language en
```

Optional: `--output "C:\audio\transcripts"`. CLI progress is emitted as JSON
lines. `Start Transcriber.cmd` remains as a compatible launcher.

## Troubleshooting

- **No microphone / access denied:** check Windows microphone access for
  desktop apps and select the correct input. Signal does not change permissions.
- **Computer source is quiet:** verify playback is on this computer, the chosen
  output is correct, and the application/device is not muted.
- **Only one source has sound:** check both activity indicators, device choices,
  and volumes. A quiet source is kept as silence; it does not block the other.
- **Echo:** use headphones or choose a single source.
- **Device changed/disconnected:** stop, refresh devices, and record again.
- **Overflow or slow disk:** close busy apps and use a local disk; partial tracks
  are retained. Do not record directly to an unreliable network location.
- **Slow transcription:** choose Fast or Balanced.
- **Model download failed:** check internet access and retry.
- **DLL error:** the speech engine may require Microsoft's Visual C++
  Redistributable for x64.

## Development and releases

See [CONTRIBUTING.md](CONTRIBUTING.md) for tests and build instructions,
[CHANGELOG.md](CHANGELOG.md) for changes, and [GITHUB_UPLOAD.md](GITHUB_UPLOAD.md)
for publishing the prepared source and release archives.

Tests use synthetic audio and mocked devices; normal tests do not record your
microphone or download model weights. GitHub Actions runs Windows checks on
pushes and pull requests. A manual workflow run also builds downloadable ZIPs.

## License

Signal Audio code and the waveform logo are [MIT licensed](LICENSE).
Dependencies retain their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
and the release's `licenses` folder. This project is unrelated to the Signal
messaging application.
