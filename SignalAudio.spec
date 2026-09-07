# Build on Windows with Python 3.11: python -m PyInstaller SignalAudio.spec
from PyInstaller.utils.hooks import collect_all, copy_metadata

datas = [("assets", "assets")]
binaries = []
hiddenimports = ["transcribe", "recorder", "ui", "app_paths"]
for package in ("faster_whisper", "ctranslate2", "onnxruntime", "av", "pyaudiowpatch", "tokenizers", "hf_xet"):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h
for package in ("faster-whisper", "huggingface-hub", "tqdm", "numpy", "tokenizers", "packaging", "filelock", "fsspec", "pyyaml", "httpx", "hf-xet"):
    datas += copy_metadata(package)

a = Analysis(["app.py"], pathex=[], binaries=binaries, datas=datas, hiddenimports=hiddenimports,
             hookspath=[], runtime_hooks=[], excludes=["pytest", "IPython", "matplotlib", "torch", "tensorflow"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="SignalAudio", console=False,
          debug=False, strip=False, upx=False, icon="assets/signal.ico")
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="SignalAudio")
