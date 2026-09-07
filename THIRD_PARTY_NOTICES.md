# Third-party software

Signal Audio's own code and logo are MIT licensed. Its dependencies retain
their respective licenses. `requirements-lock.txt` lists the runtime versions.

Key components:

- faster-whisper: https://github.com/SYSTRAN/faster-whisper
- CTranslate2: https://github.com/OpenNMT/CTranslate2
- PyAudioWPatch and PortAudio: https://github.com/s0d3s/PyAudioWPatch
- PyAV and its bundled FFmpeg libraries: https://github.com/PyAV-Org/PyAV
- ONNX Runtime: https://github.com/microsoft/onnxruntime
- NumPy: https://numpy.org
- Hugging Face libraries and model hosting: https://huggingface.co
- Python and Tcl/Tk: https://www.python.org and https://www.tcl.tk
- PyInstaller bootloader: https://pyinstaller.org (GPL with the distribution exception)

The release builder includes installed dependency license files under
`licenses/` and a version inventory in `DEPENDENCIES.txt`. FFmpeg sources and
build scripts used by PyAV wheels are available at
https://github.com/PyAV-Org/pyav-ffmpeg. Refer to the bundled PyAV/FFmpeg notices
for their terms; do not assume all dependencies use Signal's license.

Speech model weights are downloaded separately from the model host, not
included in the release ZIP. Model licensing and model cards remain with
their upstream publishers. Signal Audio is an independent audio utility,
unaffiliated with the Signal messaging application.

The PyAV DLLs in this build identify their FFmpeg license as LGPL version 3
or later. The LGPLv3 text, its referenced GPLv3 text, and Tcl's license are
also included under `licenses/upstream` in the portable build and `third_party`
in the source. These texts were obtained from the FFmpeg and Tcl upstream
repositories. Distributors of binary releases must also satisfy upstream
corresponding-source requirements; refer to https://ffmpeg.org/legal.html and
the PyAV wheel/build provenance before publishing binary release assets.
