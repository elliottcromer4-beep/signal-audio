"""Writable user data is separate from a frozen application's installed files."""
import os
from pathlib import Path
import sys

VERSION = "0.3.0"
ROOT = Path(__file__).resolve().parent


def data_root():
    if os.environ.get("SIGNAL_DATA_DIR"):
        return Path(os.environ["SIGNAL_DATA_DIR"]).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SignalAudio"
    return ROOT
