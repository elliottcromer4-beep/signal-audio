import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
from build_release import SOURCE_FILES, source_archive


class ReleaseTests(unittest.TestCase):
    def test_allowlist_excludes_local_data_and_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in SOURCE_FILES:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("public file")
            for name in ("settings.json", "transcripts/private.txt", "recordings/private.wav", ".env", ".venv/private.txt", "dist/old.zip"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("PRIVATE DO NOT SHIP")
            archive = source_archive(root, root / "source.zip")
            with zipfile.ZipFile(archive) as output:
                self.assertEqual(len(output.namelist()), len(SOURCE_FILES))
                self.assertTrue(all(b"PRIVATE" not in output.read(name) for name in output.namelist()))

    def test_all_source_inputs_exist(self):
        for relative in SOURCE_FILES:
            self.assertTrue((ROOT / relative).is_file(), relative)


if __name__ == "__main__":
    unittest.main()
