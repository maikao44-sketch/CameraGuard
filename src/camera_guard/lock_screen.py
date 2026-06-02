import os
import platform
import subprocess
import time


def lock_workstation() -> bool:
    """Lock the current workstation. Returns True when the lock command is issued."""
    system = platform.system().lower()

    try:
        if system == "windows":
            import ctypes
            return bool(ctypes.windll.user32.LockWorkStation())

        if system == "darwin":
            subprocess.Popen([
                "osascript",
                "-e",
                'tell application "System Events" to keystroke "q" using {control down, command down}',
            ])
            return True

        # Linux fallback. This is mainly for development; delivery target is Windows.
        for cmd in (["loginctl", "lock-session"], ["xdg-screensaver", "lock"], ["gnome-screensaver-command", "-l"]):
            try:
                subprocess.Popen(cmd)
                return True
            except Exception:
                continue
    except Exception as exc:
        print("[LOCK] 锁屏失败:", exc)
        return False

    print("[LOCK] 当前系统暂不支持自动锁屏")
    return False


class LockScreenManager:
    def __init__(self, enable: bool = False, delay_seconds: float = 0.0):
        self.enable = bool(enable)
        self.delay_seconds = float(delay_seconds or 0)

    def trigger(self):
        if not self.enable:
            return False
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)
        ok = lock_workstation()
        if ok:
            print("[LOCK] 已触发自动锁屏")
        return ok
