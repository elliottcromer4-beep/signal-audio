"""Build source and portable archives from explicit inputs; never package user data."""
import argparse
import hashlib
from importlib import metadata
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app_paths import VERSION
from make_icon import make_icon

SOURCE_FILES = (
    "app.py", "ui.py", "app_paths.py", "recorder.py", "transcribe.py", "sessions.py",
    "test_recorder.py", "test_transcribe.py", "test_ui.py", "test_release.py", "test_sessions.py",
    "requirements.txt", "requirements-lock.txt", "requirements-build.txt",
    "Start Signal.cmd", "Start Transcriber.cmd", "SignalAudio.spec",
    "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "CONTRIBUTING.md",
    "CHANGELOG.md", "GITHUB_UPLOAD.md", ".gitignore", ".gitattributes",
    "assets/signal.svg", "assets/signal.ico",
    "third_party/ffmpeg/COPYING.LGPLv3", "third_party/ffmpeg/COPYING.GPLv3",
    "third_party/tcl/license.terms",
    "scripts/build_release.py", "scripts/make_icon.py",
    ".github/workflows/checks.yml",
)


def source_archive(root, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for relative in SOURCE_FILES:
            source = Path(root) / relative
            if not source.is_file() or source.is_symlink():
                raise ValueError(f"Missing or unsafe release input: {relative}")
            archive.write(source, f"signal-audio-{VERSION}/{relative}")
    return destination


def dependency_notices(destination):
    shutil.copytree(ROOT / "third_party", destination / "licenses" / "upstream", dirs_exist_ok=True)
    inventory = ["Signal Audio dependency inventory", "", f"Python {sys.version}", ""]
    names = [line.split("==")[0] for line in (ROOT / "requirements-lock.txt").read_text(encoding="utf-8-sig").splitlines() if "==" in line]
    names += ["pyinstaller"]
    for name in names:
        package = metadata.distribution(name)
        license_text = package.metadata.get("License-Expression") or package.metadata.get("License") or "See upstream license files"
        inventory.append(f"{package.metadata['Name']} {package.version}\n{license_text}\n")
        for item in package.files or []:
            filename = Path(str(item))
            if any(word in filename.name.lower() for word in ("license", "copying", "notice")):
                origin = Path(package.locate_file(item))
                if origin.is_file():
                    # Wheel paths are sometimes ../../...; use a flat safe basename.
                    target = destination / "licenses" / name / filename.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.exists() and target.read_bytes() != origin.read_bytes():
                        target = target.with_name(hashlib.sha256(str(item).encode()).hexdigest()[:8] + "-" + target.name)
                    shutil.copy2(origin, target)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.exists():
        target = destination / "licenses" / "Python"
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(python_license, target / "LICENSE.txt")
    (destination / "DEPENDENCIES.txt").write_text("\n".join(inventory), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    make_icon(ROOT / "assets" / "signal.ico")
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-v"], cwd=ROOT, check=True)
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    archives = [source_archive(ROOT, dist / f"signal-audio-{VERSION}-source.zip")]
    if not args.source_only:
        if sys.platform != "win32":
            raise SystemExit("Build the portable Windows application on Windows x64.")
        subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "SignalAudio.spec"], cwd=ROOT, check=True)
        folder = dist / "SignalAudio"
        for name in ("README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "CHANGELOG.md"):
            shutil.copy2(ROOT / name, folder / name)
        dependency_notices(folder)
        archive = dist / f"signal-audio-{VERSION}-windows-x64.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
            for path in sorted(folder.rglob("*")):
                if path.is_file():
                    output.write(path, "SignalAudio/" + path.relative_to(folder).as_posix())
        archives.append(archive)
    lines = []
    for path in archives:
        with path.open("rb") as stream:
            lines.append(hashlib.file_digest(stream, "sha256").hexdigest() + "  " + path.name)
    (dist / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\nRelease artifacts:")
    for path in archives:
        print(path)


if __name__ == "__main__":
    main()
