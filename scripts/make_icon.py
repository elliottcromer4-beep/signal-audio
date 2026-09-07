"""Render Signal's geometric waveform as a Windows icon without extra libraries."""
from pathlib import Path
import struct


def make_icon(path):
    size = 64
    background, accent = (12, 16, 23), (103, 232, 194)
    pixels = bytearray()
    bars = [(12, 12), (22, 28), (32, 44), (42, 28), (52, 12)]
    for y in reversed(range(size)):
        for x in range(size):
            color = accent if any(abs(x - bx) <= 2 and abs(y - 32) <= height / 2 for bx, height in bars) else background
            r, g, b = color
            pixels.extend((b, g, r, 255))
    dib = struct.pack('<IiiHHIIiiII', 40, size, size * 2, 1, 32, 0, len(pixels), 0, 0, 0, 0)
    body = dib + pixels + b'\0' * (size * size // 8)
    entry = struct.pack('<BBBBHHII', size, size, 0, 0, 1, 32, len(body), 22)
    Path(path).write_bytes(struct.pack('<HHH', 0, 1, 1) + entry + body)


if __name__ == '__main__':
    make_icon(Path(__file__).resolve().parents[1] / 'assets' / 'signal.ico')
