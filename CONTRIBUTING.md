# Contributing

Use Windows 10/11 x64 and Python 3.11 x64 with Tcl/Tk.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m unittest discover -v
.\.venv\Scripts\python.exe app.py
```

Use a separate output folder while testing. Never add real recordings,
transcripts, model downloads, credentials, or local settings to a commit.
Tests generate synthetic audio in temporary directories and mock hardware;
ordinary test runs do not record a microphone or download a speech model.

For device-related changes, additionally test the three capture modes on real
Windows devices. Check stop, quiet inputs, device removal, and different input
sample rates. Combined capture aligns driver timestamps with the recording
clock, corrects gaps/drift beyond 50 ms, and is intended for speech rather
than sample-accurate studio recording. It does not implement echo cancellation.

## Release

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe scripts/build_release.py
```

The builder runs tests, creates an explicit-allowlist source ZIP, builds the
Windows folder with PyInstaller, collects dependency license files, creates
a portable ZIP, and writes SHA256 checksums. Runtime model weights and user
data are excluded. Do not add the build directories to Git.

Before publishing, extract the portable ZIP into a new folder and check
`SignalAudio.exe`, microphone capture, combined capture, and transcription.
First use of a speech model requires internet access. Update `app_paths.py`
and `CHANGELOG.md` for new versions. Release binaries are unsigned unless
you separately sign them with your own certificate.
