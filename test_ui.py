import os
from pathlib import Path
import queue
import sys
import tempfile
import unittest
from unittest.mock import patch

from app import App


@unittest.skipUnless(sys.platform == "win32", "Windows desktop interface")
class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"SIGNAL_DATA_DIR": self.folder.name})
        self.env.start()
        self.devices = patch("app.list_devices", return_value=(
            [{"name": "Test output [Loopback]", "index": 1}], 1,
            [{"name": "Test microphone", "index": 2}], 2))
        self.devices.start()
        self.app = App()
        self.app.withdraw()

    def tearDown(self):
        self.app.close()
        self.devices.stop()
        self.env.stop()
        self.folder.cleanup()

    def test_source_preference_round_trip(self):
        self.app.source_name.set("Computer + microphone")
        self.app.source_changed()
        self.assertTrue(self.app.can_record())
        self.app.save_settings()
        saved = self.app.read_settings()
        self.assertEqual(saved["source"], "Computer + microphone")
        self.assertEqual(saved["microphone"], "Test microphone")

    def test_no_microphone_disables_only_modes_that_need_it(self):
        self.app.microphones = []
        self.app.source_name.set("Computer audio")
        self.assertTrue(self.app.can_record())
        for mode in ("Microphone", "Computer + microphone"):
            self.app.source_name.set(mode)
            self.assertFalse(self.app.can_record())

    def test_search_and_export_preserve_unicode(self):
        self.app.preview.configure(state="normal")
        self.app.preview.insert("1.0", "A café conversation.\nSecond line.")
        self.app.preview.configure(state="disabled")
        self.app.search_text.set("café")
        self.app.find_text()
        self.assertTrue(self.app.preview.tag_ranges("match"))
        export = Path(self.folder.name) / "export.txt"
        with patch("app.filedialog.asksaveasfilename", return_value=str(export)):
            self.app.export_text()
        self.assertEqual(export.read_text(encoding="utf-8"), "A café conversation.\nSecond line.")

    def test_worker_drains_final_events(self):
        path = Path(self.folder.name) / "events.jsonl"
        path.write_text('{"kind":"segment","text":"café","progress":99}\n{"kind":"done","folder":"test"}\n', encoding="utf-8")
        process = unittest.mock.Mock()
        process.poll.return_value = 0
        process.wait.return_value = 0
        self.app.read_worker(process, path)
        self.assertEqual([self.app.events.get()["kind"] for _ in range(3)], ["segment", "done", "exit"])
        self.assertFalse(path.exists())

    def test_named_session_destination_and_small_window(self):
        self.app.session_name.set("Team discussion")
        self.assertIn("Team discussion", self.app.session_path.get())
        self.app.geometry("1020x760")
        self.app.deiconify()
        self.app.update()
        self.assertGreaterEqual(self.app.cancel_button.winfo_height(), self.app.cancel_button.winfo_reqheight())
        self.assertLessEqual(self.app.cancel_button.winfo_rooty() + self.app.cancel_button.winfo_height(),
                             self.app.winfo_rooty() + self.app.winfo_height())


if __name__ == "__main__":
    unittest.main()
