"""
摄像头调用审计占位模块。
第一版主程序通过 OpenCV 主动打开摄像头做视觉检测；
如果后续需要审计“哪些进程正在调用摄像头”，Windows 下可进一步接入 ETW、WMI、Device Manager 或企业 EDR 日志。
"""

import platform
import psutil
from typing import List, Dict


def list_camera_related_processes() -> List[Dict[str, str]]:
    keywords = ["camera", "teams", "wechat", "weixin", "qq", "chrome", "edge", "firefox", "zoom", "meeting"]
    processes = []
    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            name = (proc.info.get("name") or "").lower()
            exe = (proc.info.get("exe") or "").lower()
            if any(k in name or k in exe for k in keywords):
                processes.append({
                    "pid": str(proc.info.get("pid")),
                    "name": proc.info.get("name") or "",
                    "exe": proc.info.get("exe") or "",
                    "platform": platform.system(),
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return processes
