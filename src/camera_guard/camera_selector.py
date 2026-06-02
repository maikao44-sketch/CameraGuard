import cv2


def _try_open_camera(index: int):
    """尝试打开摄像头。Windows 下优先使用 DirectShow，失败再用默认后端。"""
    backends = []
    if hasattr(cv2, "CAP_DSHOW"):
        backends.append(cv2.CAP_DSHOW)
    if hasattr(cv2, "CAP_MSMF"):
        backends.append(cv2.CAP_MSMF)
    backends.append(0)

    for backend in backends:
        try:
            cap = cv2.VideoCapture(index, backend) if backend else cv2.VideoCapture(index)
            if cap.isOpened():
                ok, _ = cap.read()
                cap.release()
                if ok:
                    return True
            cap.release()
        except Exception:
            try:
                cap.release()
            except Exception:
                pass
    return False


def select_camera_index(camera_index, prefer_front: bool = True, probe_max_index: int = 5) -> int:
    """选择摄像头编号。

    - camera.index 为数字时：使用用户指定的编号。
    - camera.index 为 auto/front/default 时：自动扫描可用摄像头。

    在大多数 Windows 笔记本/一体机上，内置前置摄像头通常是 0，
    外接 USB 摄像头通常是 1 或更后。因此 prefer_front=True 时会优先使用 0。
    如果 0 不可用，再依次尝试 1、2、3……
    """
    if isinstance(camera_index, int):
        return camera_index

    order = list(range(max(1, int(probe_max_index))))
    if not prefer_front:
        order = order[1:] + [0] if len(order) > 1 else order

    for idx in order:
        if _try_open_camera(idx):
            print(f"[CameraGuard] 自动选择摄像头 index={idx}")
            return idx

    print("[CameraGuard] 未扫描到可用摄像头，回退使用 index=0")
    return 0
