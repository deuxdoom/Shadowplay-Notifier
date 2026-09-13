"""자체 임시 레지스트리 키로 자동 실행 등록을 검사합니다. 실제 Run 키는 쓰지 않습니다."""

import ctypes
import sys
import unittest
import uuid
import winreg
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from component import startup


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.key = "Software\\ShadowPlayNotifierTests\\" + uuid.uuid4().hex
        self.registry_patch = patch.object(startup, "RUN_KEY", self.key)
        self.registry_patch.start()

    def tearDown(self):
        self.registry_patch.stop()
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, self.key)
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\ShadowPlayNotifierTests")
        except FileNotFoundError:
            pass
        except OSError:
            pass  # 다른 검사가 쓰는 상위 키는 남깁니다.

    def test_register_replace_and_remove_preserve_other_values(self):
        self.assertFalse(startup.is_enabled())
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.key) as key:
            winreg.SetValueEx(key, "OtherApp", 0, winreg.REG_SZ, "untouched")
        startup.set_enabled(True)
        self.assertTrue(startup.is_enabled())
        with patch.object(startup, "command", return_value='"C:\\Moved App\\Notifier.exe"'):
            self.assertFalse(startup.is_enabled())
            startup.set_enabled(True)
            self.assertTrue(startup.is_enabled())
        startup.set_enabled(False)
        startup.set_enabled(False)
        self.assertFalse(startup.is_enabled())
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.key) as key:
            self.assertEqual(winreg.QueryValueEx(key, "OtherApp")[0], "untouched")

    def test_frozen_command_round_trips_spaces_and_unicode(self):
        executable = r"C:\Program Files\달 시계\ShadowPlayNotifier.exe"
        with patch.object(sys, "executable", executable), patch.object(sys, "frozen", True, create=True):
            command = startup.command()
        shell = ctypes.windll.shell32
        shell.CommandLineToArgvW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
        shell.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)
        ctypes.windll.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        count = ctypes.c_int()
        args = shell.CommandLineToArgvW(command, ctypes.byref(count))
        try:
            self.assertEqual([args[i] for i in range(count.value)], [executable])
        finally:
            ctypes.windll.kernel32.LocalFree(args)

    def test_source_command_uses_absolute_pythonw_and_entrypoint(self):
        with patch.object(sys, "frozen", False, create=True):
            command = startup.command()
        self.assertIn(str(Path(sys.executable).with_name("pythonw.exe")), command)
        self.assertIn(str(Path(__file__).resolve().parents[1] / "ShadowPlayNotifier.py"), command)

    def test_long_command_is_rejected_without_registry_write(self):
        with patch.object(startup, "command", return_value='"C:\\' + 'a' * 260 + '.exe"'):
            with self.assertRaises(ValueError):
                startup.set_enabled(True)
        with self.assertRaises(FileNotFoundError):
            winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.key)

    def test_write_failure_preserves_registered_command(self):
        startup.set_enabled(True)
        with patch.object(winreg, "SetValueEx", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                startup.set_enabled(True)
        self.assertTrue(startup.is_enabled())


if __name__ == "__main__":
    unittest.main(verbosity=2)
