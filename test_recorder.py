from array import array
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest.mock import patch
import wave
import numpy as np
import av  # Load native modules before temporarily replacing sys.modules entries.

from recorder import record, TimelineWriter, mix_tracks


class CaptureTests(unittest.TestCase):
    def capture(self, folder, source='computer', fail=False, wrong=False):
        stop = threading.Event()
        events, opened = [], []
        pcm = array('h', [1000, -1000] * 800).tobytes()

        class Stream:
            def __init__(self, callback): self.callback = callback
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def start_stream(self):
                self.callback(pcm, 800, {'current_time': 1, 'input_buffer_adc_time': 1}, 0)
                if fail:
                    self.callback(pcm, 800, {'current_time': 1, 'input_buffer_adc_time': 1}, 2)
            def stop_stream(self): pass
            def is_active(self): return True

        class Audio:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def get_device_info_by_index(self, index):
                return {'isLoopbackDevice': index == 1 and not wrong, 'maxInputChannels': 2,
                        'defaultSampleRate': 48000, 'name': f'Device {index}', 'index': index}
            def open(self, **kwargs):
                opened.append(kwargs['input_device_index'])
                return Stream(kwargs['stream_callback'])

        def notify(event):
            events.append(event)
            if event['kind'] == 'recording_started': stop.set()

        module = types.SimpleNamespace(PyAudio=Audio, paInt16=8, paContinue=0, paInputOverflow=2)
        with patch.dict('sys.modules', {'pyaudiowpatch': module}), patch('recorder.time.monotonic', return_value=1):
            record(folder, 1, stop, notify, source=source, microphone_index=2)
        return events[-1], pcm, opened

    def test_computer_mode_never_opens_microphone(self):
        with tempfile.TemporaryDirectory() as folder:
            result, pcm, opened = self.capture(folder)
            self.assertEqual(opened, [1])
            self.assertIsNone(result['error'])
            self.assertTrue(result['has_audio'])
            with wave.open(result['path'], 'rb') as saved:
                self.assertEqual(saved.getnframes(), 800)
                self.assertEqual(saved.readframes(800), pcm)

    def test_microphone_only(self):
        with tempfile.TemporaryDirectory() as folder:
            result, _, opened = self.capture(folder, source='microphone')
            self.assertEqual(opened, [2])
            self.assertIsNone(result['error'])
            self.assertEqual(Path(result['path']).name, 'microphone.wav')

    def test_both_sources_save_originals_and_mix(self):
        with tempfile.TemporaryDirectory() as folder:
            result, _, opened = self.capture(folder, source='both')
            self.assertEqual(opened, [1, 2])
            self.assertIsNone(result['error'])
            path = Path(result['path'])
            self.assertEqual(path.name, 'combined.wav')
            self.assertTrue((path.parent / 'computer.wav').exists())
            self.assertTrue((path.parent / 'microphone.wav').exists())
            with wave.open(str(path), 'rb') as mixed:
                self.assertEqual(mixed.getframerate(), 16000)
                self.assertEqual(mixed.getnchannels(), 1)

    def test_overflow_preserves_recording(self):
        with tempfile.TemporaryDirectory() as folder:
            result, pcm, _ = self.capture(folder, fail=True)
            self.assertIn('overflowed', result['error'])
            with wave.open(result['path'], 'rb') as saved:
                self.assertEqual(saved.readframes(800), pcm)

    def test_wrong_device_type_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            result, _, opened = self.capture(folder, wrong=True)
            self.assertIn('wrong input type', result['error'])
            self.assertEqual(opened, [])
            self.assertIsNone(result['path'])

    def test_timeline_keeps_silence_and_trims_overlap(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'timeline.wav'
            with wave.open(str(path), 'wb') as handle:
                writer = TimelineWriter(handle, 1000, 1)
                writer.write(array('h', [100] * 100).tobytes(), .2)
                writer.write(array('h', [200] * 100).tobytes(), .5)
                writer.write(array('h', [300] * 100).tobytes(), .5)
                writer.pad_to(1000)
            with wave.open(str(path), 'rb') as handle:
                data = array('h', handle.readframes(1000))
            self.assertEqual(len(data), 1000)
            self.assertEqual(list(data[:200]), [0] * 200)
            self.assertEqual(list(data[200:300]), [100] * 100)
            self.assertEqual(list(data[300:500]), [0] * 200)
            self.assertEqual(list(data[500:600]), [200] * 100)

    def test_different_rates_and_full_scale_mix_without_overflow(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = []
            for rate in (44100, 48000):
                path = Path(folder) / f'{rate}.wav'
                paths.append(path)
                with wave.open(str(path), 'wb') as handle:
                    handle.setnchannels(1); handle.setsampwidth(2); handle.setframerate(rate)
                    samples = np.full(rate, 30000, dtype='<i2')
                    samples[rate//2:] = 0
                    handle.writeframes(samples.tobytes())
            path = mix_tracks(paths, Path(folder) / 'mix.wav')
            with wave.open(str(path), 'rb') as handle:
                self.assertAlmostEqual(handle.getnframes(), 16000, delta=2)
                samples = np.frombuffer(handle.readframes(16000), dtype='<i2')
            self.assertGreater(float(samples[100:7900].mean()), 29990)
            self.assertLess(abs(float(samples[8100:].mean())), 1)


if __name__ == '__main__':
    unittest.main()
