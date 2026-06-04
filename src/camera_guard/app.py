import time
import cv2
import threading
import socket

from .config import load_config
from .detector import PhoneDetector
from .rules import is_suspicious_phone_recording
from .drawing import draw_detection
from .alarm import AlarmManager
from .reporter import Reporter
from .lock_screen import LockScreenManager
from .system_action import ShutdownManager
from .license import ensure_authorized
from .camera_audit import list_camera_related_processes
from .camera_selector import select_camera_index
from .tray import TrayManager
from .ui import DashboardUI, RuntimeState


def _detection_worker(cfg, state, lock, exit_requested):
    detector = PhoneDetector(
        cfg.model_path,
        cfg.model_confidence,
        backend=cfg.model_backend,
        iou_threshold=cfg.model_iou_threshold,
        imgsz=cfg.model_imgsz,
    )
    alarm_manager = AlarmManager(cfg.evidence_dir, cfg.log_dir)
    reporter = Reporter(cfg.report_enable, cfg.report_url, cfg.report_timeout_seconds)
    lock_screen_manager = LockScreenManager(cfg.lock_screen_enable, cfg.lock_screen_delay_seconds)
    shutdown_manager = ShutdownManager(cfg.shutdown_enable, cfg.shutdown_delay_seconds)

    selected_camera_index = select_camera_index(cfg.camera_index, cfg.camera_prefer_front, cfg.camera_probe_max_index)
    with lock:
        state.camera_index = selected_camera_index

    cap = cv2.VideoCapture(selected_camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(selected_camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.camera_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.camera_height)

    if not cap.isOpened():
        print("摄像头打开失败，请检查摄像头是否存在或被占用。")
        print("可能相关进程：", list_camera_related_processes())
        with lock:
            state.camera_ok = False
            state.running = False
        return

    with lock:
        state.camera_ok = True
        state.running = True
        state.computer_name = socket.gethostname()

    suspicious_count = 0
    last_alarm_time = 0.0
    frame_index = 0
    last_result = {
        "has_person": False,
        "has_phone": False,
        "persons": [],
        "phones": [],
    }
    last_suspicious = False
    last_state_update = 0.0

    while not exit_requested.is_set():
        loop_started = time.time()
        frame_interval = 1.0 / cfg.target_fps
        ui_update_interval = cfg.ui_update_interval_ms / 1000.0
        ret, frame = cap.read()
        if not ret:
            with lock:
                state.camera_ok = False
            time.sleep(0.2)
            continue

        height, width = frame.shape[:2]
        detector.confidence = cfg.model_confidence
        detector.iou_threshold = cfg.model_iou_threshold

        should_detect = frame_index % cfg.detect_every_n_frames == 0
        if should_detect:
            last_result = detector.detect(frame)
            last_suspicious = is_suspicious_phone_recording(last_result, (width, height), cfg.raw.get("rule", {}))
        result = last_result
        suspicious = last_suspicious

        if suspicious:
            suspicious_count += 1
        else:
            suspicious_count = 0

        display_frame = frame.copy()
        draw_detection(display_frame, result, suspicious=suspicious)

        event = None
        if suspicious_count >= cfg.suspicious_frame_threshold:
            now = time.time()
            if now - last_alarm_time >= cfg.cooldown_seconds:
                evidence_frame = display_frame if cfg.save_annotated_image else frame
                event = alarm_manager.trigger(evidence_frame, result)
                reporter.report(event)
                lock_screen_manager.enable = cfg.lock_screen_enable
                lock_screen_manager.delay_seconds = cfg.lock_screen_delay_seconds
                shutdown_manager.enable = cfg.shutdown_enable
                shutdown_manager.delay_seconds = cfg.shutdown_delay_seconds
                if cfg.shutdown_enable:
                    shutdown_manager.trigger()
                else:
                    lock_screen_manager.trigger()
                last_alarm_time = now
            suspicious_count = 0

        now = time.time()
        if event or now - last_state_update >= ui_update_interval:
            with lock:
                state.latest_frame = display_frame
                state.latest_result = result
                state.suspicious = suspicious
                state.camera_ok = True
                if event:
                    state.last_event = event
                    state.events.append(event)
                    state.today_alarm_count += 1
                    state.today_evidence_count += 1
                    state.events = state.events[-50:]
            last_state_update = now

        frame_index += 1
        elapsed = time.time() - loop_started
        sleep_seconds = frame_interval - elapsed
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    cap.release()
    with lock:
        state.running = False


def main():
    config_path = "config.yaml"
    cfg = load_config(config_path)
    if not ensure_authorized(cfg, config_path):
        print("授权失败，程序已退出。")
        return
    state = RuntimeState(computer_name=socket.gethostname())
    lock = threading.Lock()
    exit_requested = threading.Event()

    ui_holder = {"ui": None}

    def show_window():
        ui = ui_holder.get("ui")
        if ui:
            ui.show()
            tray.set_window_visible(True)

    def hide_window():
        tray.set_window_visible(False)

    def on_exit():
        exit_requested.set()
        try:
            tray.stop()
        except Exception:
            pass

    tray = TrayManager(
        on_show_window=show_window,
        on_exit=on_exit,
        title="CameraGuard",
    )
    tray_thread = threading.Thread(target=tray.start, daemon=True)
    tray_thread.start()

    worker = threading.Thread(target=_detection_worker, args=(cfg, state, lock, exit_requested), daemon=True)
    worker.start()

    ui = DashboardUI(cfg, state, lock, on_exit=on_exit, on_hide=hide_window)
    ui_holder["ui"] = ui
    print("CameraGuard 已启动，可通过右下角托盘图标打开预警看板。")
    ui.run(initially_visible=cfg.show_window)

    exit_requested.set()
    try:
        tray.stop()
    except Exception:
        pass
