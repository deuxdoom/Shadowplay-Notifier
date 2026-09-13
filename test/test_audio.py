import ctypes
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from component.audio import (GUID, WAVEFORMATEX, WAVEFORMATEXTENSIBLE,
                             WAVE_FORMAT_EXTENSIBLE, WAVE_FORMAT_PCM,
                             _sample_kind)


class AudioFormatTests(unittest.TestCase):
    def test_windows_wave_structure_sizes(self):
        self.assertEqual(ctypes.sizeof(WAVEFORMATEX), 18)
        self.assertEqual(ctypes.sizeof(WAVEFORMATEXTENSIBLE), 40)

    def test_float_extensible_and_pcm16_are_recognized(self):
        extended = WAVEFORMATEXTENSIBLE()
        extended.Format.wFormatTag = WAVE_FORMAT_EXTENSIBLE
        extended.Format.wBitsPerSample = 32
        extended.Format.cbSize = 22
        extended.SubFormat = GUID("{00000003-0000-0010-8000-00AA00389B71}")
        pointer = ctypes.cast(ctypes.pointer(extended), ctypes.POINTER(WAVEFORMATEX))
        self.assertEqual(_sample_kind(pointer), "float32")

        pcm = WAVEFORMATEX()
        pcm.wFormatTag = WAVE_FORMAT_PCM
        pcm.wBitsPerSample = 16
        self.assertEqual(_sample_kind(ctypes.pointer(pcm)), "pcm16")

    def test_unsupported_format_is_rejected(self):
        fmt = WAVEFORMATEX()
        fmt.wFormatTag = WAVE_FORMAT_PCM
        fmt.wBitsPerSample = 24
        with self.assertRaises(OSError):
            _sample_kind(ctypes.pointer(fmt))


if __name__ == "__main__":
    unittest.main(verbosity=2)
