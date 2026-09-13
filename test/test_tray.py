"""실제 알림 영역 등록·복원 메시지·메뉴 명령·종료 자원을 검사합니다."""

import sys
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from component import instance
from component.tray import (TrayIcon, RESTORE_MESSAGE, CALLBACK_MESSAGE,
                            user32, shell32, ctypes)


class TrayTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.calls = []
        self.state = {"mode": "auto", "recording": False}
        self.tray = TrayIcon(self.root, {
            action: lambda action=action: self.calls.append(action)
            for action in TrayIcon.COMMANDS.values()}, lambda: self.state)
        self.assertTrue(self.tray.available)

    def tearDown(self):
        self.tray.close()
        self.root.destroy()

    def pump(self):
        until = time.perf_counter() + .25
        while time.perf_counter() < until:
            self.root.update()
            time.sleep(.01)

    def test_registered_messages_restore_hidden_app(self):
        self.assertTrue(instance.focus_existing("a hidden application"))
        self.pump()
        self.assertIn("show", self.calls)
        user32.PostMessageW(self.tray.hwnd, CALLBACK_MESSAGE, 0, (1 << 16) | 0x401)
        self.pump()
        self.assertGreaterEqual(self.calls.count("show"), 2)

    def test_native_menu_all_commands_and_checkmarks(self):
        for command, action in TrayIcon.COMMANDS.items():
            with patch.object(user32, "TrackPopupMenu", return_value=command):
                self.tray._show_menu()
            self.assertEqual(self.calls[-1], action)
        for mode, command in (("wallpaper", 2), ("monitor", 3), ("auto", 4)):
            self.state["mode"] = mode
            checked = [item[0] for item in self.tray.menu_entries() if item[2] == 8]
            self.assertEqual(checked, [command])

    def test_explorer_restart_readds_icon(self):
        shell32.Shell_NotifyIconW(2, ctypes.byref(self.tray._data))
        user32.PostMessageW(self.tray.hwnd, self.tray._taskbar_created, 0, 0)
        self.pump()
        self.assertTrue(self.tray.available)

    def test_command_exit_and_cleanup_are_idempotent(self):
        user32.PostMessageW(self.tray.hwnd, 0x111, 7, 0)
        self.pump()
        self.assertEqual(self.calls, ["quit"])
        self.tray.close()
        self.tray.close()
        self.assertIsNone(self.tray.hwnd)
        self.assertIsNone(self.tray._icon)
        self.assertFalse(self.tray._registered)
        self.assertEqual(len(self.root.tk.call("after", "info")), 0)
        # 같은 프로세스에서 다시 만들어도 등록·핸들이 남아 있지 않습니다.
        self.tray = TrayIcon(self.root, {}, lambda: self.state)
        self.assertTrue(self.tray.available)


if __name__ == "__main__":
    unittest.main(verbosity=2)
