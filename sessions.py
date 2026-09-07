"""Named library folders shared by recordings and their transcripts."""
from datetime import datetime
import json
from pathlib import Path
import re
import shutil


def safe_name(name):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", name).strip(" .")[:80].rstrip(" .")
    if not name:
        name = datetime.now().strftime("Recording %Y-%m-%d %H-%M-%S")
    if name.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        name = "Session " + name
    return name


def create_session(library, name=""):
    library = Path(library).resolve()
    library.mkdir(parents=True, exist_ok=True)
    name = safe_name(name)
    number = 1
    while True:
        folder = library / (name if number == 1 else f"{name} ({number})")
        try:
            folder.mkdir()
            break
        except FileExistsError:
            number += 1
    (folder / "session.json").write_text(json.dumps({"name": folder.name, "created": datetime.now().isoformat(timespec="seconds")}, indent=2), encoding="utf-8")
    return folder


def prepare_session(audio, library, name="", existing=None):
    audio = Path(audio).resolve()
    if existing:
        folder = Path(existing).resolve()
        if not (folder / "session.json").is_file() or audio.parent != folder:
            raise ValueError("The recording must belong to the selected session folder.")
        return audio, folder
    folder = create_session(library, name or audio.stem)
    # Copy imports in the worker so large files do not freeze the interface.
    target = folder / ("recording" + audio.suffix.lower())
    partial = target.with_name(target.name + ".copying")
    shutil.copy2(audio, partial)
    partial.replace(target)
    return target, folder


def transcript_suffix(folder):
    """A retry preserves prior complete and partial results."""
    number = 1
    while True:
        suffix = "" if number == 1 else f"-{number}"
        names = [f"{stem}{suffix}{extension}" for stem, extension in
                 (("transcript", ".txt"), ("transcript", ".partial.txt"),
                  ("timestamps", ".txt"), ("timestamps", ".partial.txt"),
                  ("subtitles", ".srt"), ("subtitles", ".partial.srt"),
                  ("details", ".json"), ("AI-parts", ""))]
        if not any((Path(folder) / name).exists() for name in names):
            try:
                with (Path(folder) / f"details{suffix}.json").open("x", encoding="utf-8") as reservation:
                    json.dump({"status": "reserved"}, reservation)
                return suffix
            except FileExistsError:
                pass
        number += 1
