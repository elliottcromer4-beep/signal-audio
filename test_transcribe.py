import contextlib
import io
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from transcribe import run, split_text, timestamp


class TranscriptTests(unittest.TestCase):
    def test_parts_preserve_words_and_bound_size(self):
        text = "A podcast with names, punctuation, and café.\n" * 1500
        parts = list(split_text(text))
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(part) <= 12000 for part in parts))
        self.assertEqual(" ".join(text.split()), " ".join(" ".join(parts).split()))

    def test_timestamp_carry(self):
        self.assertEqual(timestamp(3599.9996, srt=True), "01:00:00,000")

    def transcribe_fixture(self, root, fail=False):
        audio = root / "episode.wav"
        audio.touch()

        def segments():
            yield types.SimpleNamespace(start=0, end=1.2, text=" Hello café.")
            if fail:
                raise RuntimeError("interrupted")
            yield types.SimpleNamespace(start=1.2, end=2.5, text=" Second sentence.")

        model = types.SimpleNamespace(transcribe=lambda *a, **k: (segments(), types.SimpleNamespace(language="en", duration=3)))
        module = types.SimpleNamespace(WhisperModel=lambda *a, **k: model)
        with patch.dict("sys.modules", {"faster_whisper": module}), contextlib.redirect_stdout(io.StringIO()):
            return run(audio, root / "out")

    def test_export_and_unique_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self.transcribe_fixture(root)
            second = self.transcribe_fixture(root)
            self.assertNotEqual(first, second)
            self.assertEqual((first / "transcript.txt").read_text(encoding="utf-8"), "Hello café.\nSecond sentence.\n")
            self.assertIn("00:00:01,200 --> 00:00:02,500", (first / "subtitles.srt").read_text())
            self.assertTrue((first / "AI-parts" / "part-001.txt").is_file())
            self.assertFalse(list(first.glob("*.partial.*")))

    def test_failure_retains_partial_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                self.transcribe_fixture(root, fail=True)
            partial = next((root / "out").glob("*/transcript.partial.txt"))
            self.assertEqual(partial.read_text(encoding="utf-8"), "Hello café.\n")
            self.assertFalse(list((root / "out").glob("*/transcript.txt")))


if __name__ == "__main__":
    unittest.main()
