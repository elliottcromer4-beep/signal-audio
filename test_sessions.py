import contextlib
import io
import tempfile
from pathlib import Path
import types
import unittest
from unittest.mock import patch

from sessions import create_session, prepare_session, safe_name
from transcribe import run


class SessionTests(unittest.TestCase):
    def test_names_stay_inside_library_and_collisions_preserve_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = create_session(root, "Meeting notes")
            (first / "important.txt").write_text("keep")
            second = create_session(root, "Meeting notes")
            self.assertEqual(second.name, "Meeting notes (2)")
            self.assertEqual((first / "important.txt").read_text(), "keep")
            for name in ("../../outside", "C:\\escape", "CON", "..", "bad:name?", "NUL.txt"):
                folder = create_session(root, name)
                self.assertEqual(folder.parent, root.resolve())
                self.assertTrue(folder.name)

    def test_import_copies_audio_into_named_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "source.mp3"
            original.write_bytes(b"audio sample")
            saved, folder = prepare_session(original, root / "library", "My interview")
            self.assertEqual(folder.name, "My interview")
            self.assertEqual(saved.parent, folder)
            self.assertEqual(saved.read_bytes(), original.read_bytes())
            self.assertTrue(original.exists())

    def test_audio_and_repeated_transcripts_stay_together(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = create_session(root, "Discussion")
            audio = folder / "computer.wav"
            audio.write_bytes(b"original")
            model = types.SimpleNamespace(transcribe=lambda *a, **k: (
                iter([types.SimpleNamespace(text="Useful ideas.", start=0, end=2)]),
                types.SimpleNamespace(language="en", duration=2)))
            module = types.SimpleNamespace(WhisperModel=lambda *a, **k: model)
            with patch.dict("sys.modules", {"faster_whisper": module}), contextlib.redirect_stdout(io.StringIO()):
                first = run(audio, root, session_dir=folder)
                second = run(audio, root, session_dir=folder)
            self.assertEqual(first, folder)
            self.assertEqual(second, folder)
            self.assertEqual(audio.read_bytes(), b"original")
            self.assertTrue((folder / "transcript.txt").is_file())
            self.assertTrue((folder / "transcript-2.txt").is_file())
            self.assertEqual(len(list(root.iterdir())), 1)

    def test_existing_session_rejects_unrelated_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = create_session(root, "Session")
            audio = root / "unrelated.wav"
            audio.touch()
            with self.assertRaises(ValueError):
                prepare_session(audio, root, existing=folder)


if __name__ == "__main__":
    unittest.main()
