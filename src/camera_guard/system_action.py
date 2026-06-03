import platform
import subprocess
import time


def shutdown_computer() -> bool:
    """Issue an OS shutdown command. Returns True when the command is submitted."""
    system = platform.system().lower()

    try:
        if system == "windows":
            subprocess.Popen(["shutdown", "/s", "/t", "0"])
            return True

        if system == "darwin":
            subprocess.Popen(["osascript", "-e", 'tell application "System Events" to shut down'])
            return True

        subprocess.Popen(["shutdown", "-h", "now"])
        return True
    except Exception as exc:
        print("[SHUTDOWN] 自动关机失败:", exc)
        return False


class ShutdownManager:
    def __init__(self, enable: bool = False, delay_seconds: float = 0.0):
        self.enable = bool(enable)
        self.delay_seconds = float(delay_seconds or 0)

    def trigger(self):
        if not self.enable:
            return False
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)
        ok = shutdown_computer()
        if ok:
            print("[SHUTDOWN] 已触发自动关机")
        return ok
