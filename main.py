import os
import sys


def _set_working_dir():
    """保证双击 exe 时，配置、模型、日志都从程序所在目录读取。"""
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)


_set_working_dir()

from src.camera_guard.app import main


if __name__ == "__main__":
    main()
