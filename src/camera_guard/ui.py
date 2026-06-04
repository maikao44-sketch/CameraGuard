import os
import json
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import cv2
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk, messagebox
import yaml


@dataclass
class RuntimeState:
    latest_frame: Any = None
    latest_result: Dict[str, Any] = field(default_factory=dict)
    suspicious: bool = False
    running: bool = True
    started_at: float = field(default_factory=time.time)
    today_alarm_count: int = 0
    today_evidence_count: int = 0
    last_event: Optional[Dict[str, Any]] = None
    events: List[Dict[str, Any]] = field(default_factory=list)
    computer_name: str = ""
    camera_ok: bool = False


class DashboardUI:
    """CameraGuard 主界面：托盘点开后查看实时画面、预警记录和统计。"""

    def __init__(self, cfg, state: RuntimeState, lock: threading.Lock, on_exit, on_hide):
        self.cfg = cfg
        self.state = state
        self.lock = lock
        self.on_exit = on_exit
        self.on_hide = on_hide
        self.root = tk.Tk()
        self.root.title("CameraGuard 摄像头安全预警系统")
        # 固定主窗口尺寸，避免摄像头画面刷新时反复撑大窗口
        self.root.geometry("1280x780")
        self.root.minsize(1280, 780)
        self.root.maxsize(1280, 780)
        self.root.resizable(False, False)
        self.root.configure(bg="#0f1b2b")
        self.root.protocol("WM_DELETE_WINDOW", self.hide)

        self._img_ref = None
        self._thumb_refs = []
        self._build()
        self.root.after(max(16, int(getattr(self.cfg, "ui_update_interval_ms", 80))), self._refresh)

    def _build(self):
        # 顶栏
        header = tk.Frame(self.root, bg="#0b1422", height=64)
        header.pack(side=tk.TOP, fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="🛡  CameraGuard", fg="#f8fafc", bg="#0b1422", font=("Microsoft YaHei UI", 20, "bold")).pack(side=tk.LEFT, padx=24)
        tk.Label(header, text="摄像头安全预警系统", fg="#94a3b8", bg="#0b1422", font=("Microsoft YaHei UI", 11)).pack(side=tk.LEFT, padx=4, pady=(8, 0))
        tk.Button(header, text="隐藏到托盘", command=self.hide, bg="#1e3a5f", fg="#dbeafe", relief="flat", padx=16, pady=6).pack(side=tk.RIGHT, padx=18)

        body = tk.Frame(self.root, bg="#0f1b2b")
        body.pack(fill=tk.BOTH, expand=True)

        # 左侧导航/状态
        left = tk.Frame(body, bg="#132238", width=220)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)
        self.nav_status = tk.Label(left, text="● 系统运行中", fg="#22c55e", bg="#132238", font=("Microsoft YaHei UI", 12, "bold"))
        self.nav_status.pack(anchor="w", padx=24, pady=(34, 20))
        self.nav_buttons = {}
        nav_items = [
            ("实时监控", self._show_realtime_page),
            ("预警记录", self._open_event_window),
            ("统计分析", self._open_stats_window),
            ("系统设置", self._open_settings_window),
        ]
        for text, command in nav_items:
            color = "#60a5fa" if text == "实时监控" else "#cbd5e1"
            bg = "#1d3b63" if text == "实时监控" else "#132238"
            btn = tk.Button(
                left, text="  " + text, command=command,
                fg=color, bg=bg, activeforeground="#f8fafc", activebackground="#1d3b63",
                font=("Microsoft YaHei UI", 12), anchor="w", height=2,
                relief="flat", bd=0, cursor="hand2"
            )
            btn.pack(fill=tk.X, padx=12, pady=4)
            self.nav_buttons[text] = btn
        tk.Frame(left, bg="#334155", height=1).pack(fill=tk.X, padx=20, pady=28)
        self.left_info = tk.Label(left, text="", fg="#cbd5e1", bg="#132238", justify=tk.LEFT, font=("Microsoft YaHei UI", 10), anchor="nw")
        self.left_info.pack(fill=tk.BOTH, padx=24, pady=8, expand=True)

        main = tk.Frame(body, bg="#0f1b2b")
        main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=18, pady=18)

        # 统计卡片
        cards = tk.Frame(main, bg="#0f1b2b")
        cards.pack(fill=tk.X)
        self.card_alarm = self._card(cards, "今日预警总数", "0 次", "较昨日 --")
        self.card_evi = self._card(cards, "今日截图数量", "0 张", "自动留证")
        self.card_runtime = self._card(cards, "运行时长", "00:00:00", "系统已稳定运行")
        self.card_state = self._card(cards, "当前状态", "监控中", "摄像头监控正常")

        content = tk.Frame(main, bg="#0f1b2b")
        content.pack(fill=tk.BOTH, expand=True, pady=(18, 0))

        # 实时画面
        live_box = self._panel(content, "实时画面    ● 摄像头已连接")
        live_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12))
        # 固定视频显示区域尺寸。不要让 Label 根据图片大小反向撑大窗口。
        self.video_label = tk.Label(live_box, bg="#020617", width=760, height=428)
        self.video_label.pack(fill=tk.BOTH, expand=True, padx=16, pady=(8, 10))
        btns = tk.Frame(live_box, bg="#142238")
        btns.pack(fill=tk.X, padx=16, pady=(0, 14))
        tk.Button(btns, text="打开留证目录", command=lambda: self._open_dir(self.cfg.evidence_dir), bg="#1d4ed8", fg="white", relief="flat", padx=14, pady=7).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(btns, text="打开日志目录", command=lambda: self._open_dir(self.cfg.log_dir), bg="#334155", fg="white", relief="flat", padx=14, pady=7).pack(side=tk.LEFT, padx=8)
        tk.Button(btns, text="退出程序", command=self.exit_app, bg="#7f1d1d", fg="white", relief="flat", padx=14, pady=7).pack(side=tk.RIGHT)

        # 预警记录
        right = self._panel(content, "预警记录（今日）")
        right.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(12, 0))
        right.configure(width=430)
        right.pack_propagate(False)
        self.event_list = tk.Frame(right, bg="#142238")
        self.event_list.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)

        # 底部趋势占位
        bottom = tk.Frame(main, bg="#0f1b2b", height=140)
        bottom.pack(fill=tk.X, pady=(18, 0))
        trend = self._panel(bottom, "预警趋势（近7天）")
        trend.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12))
        self.trend_canvas = tk.Canvas(trend, height=110, bg="#142238", highlightthickness=0)
        self.trend_canvas.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)
        pie = self._panel(bottom, "预警类型分布")
        pie.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(12, 0))
        pie.configure(width=360)
        pie.pack_propagate(False)
        self.type_label = tk.Label(pie, text="疑似手机拍摄行为  100%", fg="#cbd5e1", bg="#142238", font=("Microsoft YaHei UI", 12))
        self.type_label.pack(expand=True)

    def _set_active_nav(self, name):
        for text, btn in getattr(self, "nav_buttons", {}).items():
            if text == name:
                btn.configure(fg="#60a5fa", bg="#1d3b63")
            else:
                btn.configure(fg="#cbd5e1", bg="#132238")

    def _show_realtime_page(self):
        self._set_active_nav("实时监控")
        self.root.lift()
        self.root.focus_force()

    def _open_event_window(self):
        self._set_active_nav("预警记录")
        win = tk.Toplevel(self.root)
        win.title("预警记录 - CameraGuard")
        win.geometry("980x640")
        win.configure(bg="#0f1b2b")
        tk.Label(win, text="预警记录", fg="#f8fafc", bg="#0f1b2b", font=("Microsoft YaHei UI", 18, "bold")).pack(anchor="w", padx=20, pady=(18, 8))
        wrap = tk.Frame(win, bg="#142238", highlightbackground="#26384f", highlightthickness=1)
        wrap.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        canvas = tk.Canvas(wrap, bg="#142238", highlightthickness=0)
        scrollbar = tk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="#142238")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        with self.lock:
            events = list(self.state.events)[::-1]
        if not events:
            tk.Label(inner, text="暂无预警记录", fg="#94a3b8", bg="#142238", font=("Microsoft YaHei UI", 13)).pack(pady=40, padx=20)
            return
        for idx, ev in enumerate(events, 1):
            row = tk.Frame(inner, bg="#172a44", highlightbackground="#2b405c", highlightthickness=1)
            row.pack(fill=tk.X, padx=14, pady=8)
            img_path = ev.get("evidence_image", "")
            if img_path and os.path.exists(img_path):
                try:
                    im = Image.open(img_path)
                    im.thumbnail((150, 90))
                    photo = ImageTk.PhotoImage(im)
                    self._thumb_refs.append(photo)
                    tk.Label(row, image=photo, bg="#172a44").pack(side=tk.LEFT, padx=12, pady=10)
                except Exception:
                    tk.Label(row, text="无图", fg="#94a3b8", bg="#172a44", width=14).pack(side=tk.LEFT, padx=12)
            else:
                tk.Label(row, text="无图", fg="#94a3b8", bg="#172a44", width=14).pack(side=tk.LEFT, padx=12)
            info = tk.Frame(row, bg="#172a44")
            info.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=10)
            tk.Label(info, text=f"#{idx}  疑似手机拍摄行为", fg="#f8fafc", bg="#172a44", font=("Microsoft YaHei UI", 12, "bold"), anchor="w").pack(fill=tk.X)
            tk.Label(info, text="时间：" + ev.get("time", "-"), fg="#cbd5e1", bg="#172a44", font=("Microsoft YaHei UI", 10), anchor="w").pack(fill=tk.X, pady=2)
            tk.Label(info, text="留证图片：" + (img_path or "-"), fg="#94a3b8", bg="#172a44", font=("Microsoft YaHei UI", 9), anchor="w").pack(fill=tk.X)

    def _open_stats_window(self):
        self._set_active_nav("统计分析")
        with self.lock:
            alarm_count = self.state.today_alarm_count
            evi_count = self.state.today_evidence_count
            elapsed = int(time.time() - self.state.started_at)
        win = tk.Toplevel(self.root)
        win.title("统计分析 - CameraGuard")
        win.geometry("760x520")
        win.configure(bg="#0f1b2b")
        tk.Label(win, text="统计分析", fg="#f8fafc", bg="#0f1b2b", font=("Microsoft YaHei UI", 18, "bold")).pack(anchor="w", padx=20, pady=(18, 8))
        box = tk.Frame(win, bg="#142238", highlightbackground="#26384f", highlightthickness=1)
        box.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        h, m, s = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
        text = f"今日预警总数：{alarm_count} 次\n今日截图数量：{evi_count} 张\n运行时长：{h:02d}:{m:02d}:{s:02d}\n主要预警类型：疑似手机拍摄行为"
        tk.Label(box, text=text, fg="#cbd5e1", bg="#142238", justify=tk.LEFT, font=("Microsoft YaHei UI", 13), anchor="nw").pack(anchor="w", padx=24, pady=22)
        c = tk.Canvas(box, height=220, bg="#142238", highlightthickness=0)
        c.pack(fill=tk.X, padx=24, pady=12)
        vals = [max(0, alarm_count - 3), max(0, alarm_count - 2), max(0, alarm_count - 1), alarm_count, max(0, alarm_count - 1), alarm_count, alarm_count]
        mx = max(vals + [1]); w = 680; hh = 180
        pts=[]
        for i,v in enumerate(vals):
            x=30+i*((w-60)/6); y=hh-20-(v/mx)*(hh-50); pts.append((x,y))
        for y in [20, hh/2, hh-20]: c.create_line(20,y,w-20,y,fill="#26384f")
        for i in range(len(pts)-1): c.create_line(*pts[i], *pts[i+1], fill="#ef4444", width=2)
        for x,y in pts: c.create_oval(x-4,y-4,x+4,y+4,fill="#ef4444",outline="")

    def _open_settings_window(self):
        self._set_active_nav("系统设置")
        win = tk.Toplevel(self.root)
        win.title("系统设置 - CameraGuard")
        win.geometry("820x640")
        win.configure(bg="#0f1b2b")
        win.resizable(False, False)
        tk.Label(win, text="系统设置", fg="#f8fafc", bg="#0f1b2b", font=("Microsoft YaHei UI", 18, "bold")).pack(anchor="w", padx=20, pady=(18, 4))
        tk.Label(win, text="修改后点击保存，参数会写入 config.yaml。大部分参数立即生效；重启程序后也会保持。", fg="#94a3b8", bg="#0f1b2b", font=("Microsoft YaHei UI", 10)).pack(anchor="w", padx=20, pady=(0, 12))

        box = tk.Frame(win, bg="#142238", highlightbackground="#26384f", highlightthickness=1)
        box.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        btns = tk.Frame(box, bg="#142238")
        btns.pack(side=tk.BOTTOM, fill=tk.X, padx=24, pady=14)

        scroll_area = tk.Frame(box, bg="#142238")
        scroll_area.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(scroll_area, bg="#142238", highlightthickness=0)
        scrollbar = ttk.Scrollbar(scroll_area, orient=tk.VERTICAL, command=canvas.yview)
        settings_body = tk.Frame(canvas, bg="#142238")
        body_window = canvas.create_window((0, 0), window=settings_body, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def update_scroll_region(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def resize_body(event):
            canvas.itemconfigure(body_window, width=event.width)

        def on_mousewheel(event):
            delta = -1 * int(event.delta / 120) if event.delta else 0
            if delta:
                canvas.yview_scroll(delta, "units")

        settings_body.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", resize_body)
        canvas.bind("<Enter>", lambda _event: canvas.bind_all("<MouseWheel>", on_mousewheel))
        canvas.bind("<Leave>", lambda _event: canvas.unbind_all("<MouseWheel>"))
        win.bind("<Destroy>", lambda event: canvas.unbind_all("<MouseWheel>") if event.widget is win else None)

        def section(parent, title):
            tk.Label(parent, text=title, fg="#f8fafc", bg="#142238", font=("Microsoft YaHei UI", 13, "bold")).pack(anchor="w", padx=24, pady=(18, 8))

        def row(parent, label, var, hint="", width=18):
            frame = tk.Frame(parent, bg="#142238")
            frame.pack(fill=tk.X, padx=24, pady=6)
            tk.Label(frame, text=label, fg="#cbd5e1", bg="#142238", font=("Microsoft YaHei UI", 11), width=20, anchor="w").pack(side=tk.LEFT)
            ent = tk.Entry(frame, textvariable=var, width=width, bg="#0f1b2b", fg="#f8fafc", insertbackground="#f8fafc", relief="flat", font=("Microsoft YaHei UI", 11))
            ent.pack(side=tk.LEFT, padx=(0, 12), ipady=6)
            if hint:
                tk.Label(frame, text=hint, fg="#94a3b8", bg="#142238", font=("Microsoft YaHei UI", 9), anchor="w").pack(side=tk.LEFT)
            return ent

        # 当前值
        confidence_var = tk.StringVar(value=str(getattr(self.cfg, "model_confidence", 0.35)))
        threshold_var = tk.StringVar(value=str(getattr(self.cfg, "suspicious_frame_threshold", 20)))
        cooldown_var = tk.StringVar(value=str(getattr(self.cfg, "cooldown_seconds", 10)))
        save_annotated_var = tk.BooleanVar(value=bool(getattr(self.cfg, "save_annotated_image", True)))
        current_target_fps = float(getattr(self.cfg, "target_fps", 8))
        current_detect_every = max(1, int(getattr(self.cfg, "detect_every_n_frames", 5)))
        detect_frequency_var = tk.StringVar(value=f"{current_target_fps / current_detect_every:.2f}")
        ui_interval_var = tk.StringVar(value=str(getattr(self.cfg, "ui_update_interval_ms", 150)))
        lock_delay_var = tk.StringVar(value=str(getattr(self.cfg, "lock_screen_delay_seconds", 0)))
        action_value = "shutdown" if bool(getattr(self.cfg, "shutdown_enable", False)) else ("lock" if bool(getattr(self.cfg, "lock_screen_enable", False)) else "none")
        alarm_action_var = tk.StringVar(value=action_value)
        camera_index_var = tk.StringVar(value=str(getattr(self.cfg, "camera_index", "auto")))
        prefer_front_var = tk.BooleanVar(value=bool(getattr(self.cfg, "camera_prefer_front", True)))

        section(settings_body, "摄像头参数 camera")
        row(settings_body, "摄像头编号", camera_index_var, "填 auto 默认优先前置；也可填 0、1、2 指定摄像头")
        chk0 = tk.Checkbutton(settings_body, text="自动模式下优先使用前置/内置摄像头", variable=prefer_front_var, fg="#cbd5e1", bg="#142238", activeforeground="#f8fafc", activebackground="#142238", selectcolor="#0f1b2b", font=("Microsoft YaHei UI", 11))
        chk0.pack(anchor="w", padx=24, pady=6)

        section(settings_body, "模型识别参数")
        row(settings_body, "检测置信度 confidence", confidence_var, "建议 0.25–0.50；越高越严格，越低越灵敏")

        section(settings_body, "预警参数 alarm")
        row(settings_body, "连续触发帧数", threshold_var, "建议 15–30；越小越灵敏")
        row(settings_body, "冷却时间/秒", cooldown_var, "一次预警后，多少秒内不重复预警")
        chk1 = tk.Checkbutton(settings_body, text="保存带检测框的留证截图", variable=save_annotated_var, fg="#cbd5e1", bg="#142238", activeforeground="#f8fafc", activebackground="#142238", selectcolor="#0f1b2b", font=("Microsoft YaHei UI", 11))
        chk1.pack(anchor="w", padx=24, pady=6)

        section(settings_body, "性能参数 performance")
        row(settings_body, "检测频率/秒", detect_frequency_var, "老电脑建议 1–2；数值越低越省 CPU")
        row(settings_body, "界面刷新间隔/ms", ui_interval_var, "老电脑建议 150–300；数值越大界面越省资源")

        section(settings_body, "触发后动作")
        for text, value in (
            ("不执行锁屏或关机", "none"),
            ("截图留证后自动锁屏", "lock"),
            ("截图留证后自动关机", "shutdown"),
        ):
            tk.Radiobutton(
                settings_body,
                text=text,
                variable=alarm_action_var,
                value=value,
                fg="#cbd5e1",
                bg="#142238",
                activeforeground="#f8fafc",
                activebackground="#142238",
                selectcolor="#0f1b2b",
                font=("Microsoft YaHei UI", 11),
            ).pack(anchor="w", padx=24, pady=4)
        row(settings_body, "动作延迟/秒", lock_delay_var, "0 表示留证后立即执行")

        info = tk.Label(settings_body, text=f"当前配置文件：{os.path.abspath('config.yaml')}\n留证目录：{getattr(self.cfg, 'evidence_dir', '-')}    日志目录：{getattr(self.cfg, 'log_dir', '-')}", fg="#94a3b8", bg="#142238", justify=tk.LEFT, font=("Microsoft YaHei UI", 9))
        info.pack(anchor="w", padx=24, pady=(10, 18))

        def save_settings():
            try:
                confidence = float(confidence_var.get().strip())
                if not (0.01 <= confidence <= 0.99):
                    raise ValueError("confidence 必须在 0.01 到 0.99 之间")

                threshold = int(threshold_var.get().strip())
                if threshold < 1 or threshold > 300:
                    raise ValueError("连续触发帧数建议设置在 1 到 300 之间")

                cooldown = int(cooldown_var.get().strip())
                if cooldown < 0 or cooldown > 3600:
                    raise ValueError("冷却时间建议设置在 0 到 3600 秒之间")

                camera_index_value = camera_index_var.get().strip() or "auto"
                if camera_index_value.lower() not in ("auto", "front", "default"):
                    camera_index_value = int(camera_index_value)
                    if camera_index_value < 0 or camera_index_value > 20:
                        raise ValueError("摄像头编号建议设置为 auto 或 0–20 之间的数字")

                lock_delay = float(lock_delay_var.get().strip())
                if lock_delay < 0 or lock_delay > 60:
                    raise ValueError("锁屏延迟建议设置在 0 到 60 秒之间")

                detect_frequency = float(detect_frequency_var.get().strip())
                if detect_frequency < 0.2 or detect_frequency > 10:
                    raise ValueError("检测频率建议设置在 0.2 到 10 次/秒之间")

                target_fps = max(5.0, min(12.0, detect_frequency * 5))
                detect_every = max(1, int(round(target_fps / detect_frequency)))

                ui_interval = int(ui_interval_var.get().strip())
                if ui_interval < 16 or ui_interval > 2000:
                    raise ValueError("界面刷新间隔建议设置在 16 到 2000 毫秒之间")

                raw = self.cfg.raw
                raw.setdefault("camera", {})["index"] = camera_index_value
                raw.setdefault("camera", {})["prefer_front"] = bool(prefer_front_var.get())
                raw.setdefault("model", {})["confidence"] = confidence
                raw.setdefault("alarm", {})["suspicious_frame_threshold"] = threshold
                raw.setdefault("alarm", {})["cooldown_seconds"] = cooldown
                raw.setdefault("alarm", {})["save_annotated_image"] = bool(save_annotated_var.get())
                raw.setdefault("performance", {})["target_fps"] = target_fps
                raw.setdefault("performance", {})["detect_every_n_frames"] = detect_every
                raw.setdefault("performance", {})["ui_update_interval_ms"] = ui_interval
                selected_action = alarm_action_var.get()
                raw.setdefault("lock_screen", {})["enable"] = selected_action == "lock"
                raw.setdefault("lock_screen", {})["delay_seconds"] = lock_delay
                raw.setdefault("shutdown", {})["enable"] = selected_action == "shutdown"
                raw.setdefault("shutdown", {})["delay_seconds"] = lock_delay

                with open("config.yaml", "w", encoding="utf-8") as f:
                    yaml.safe_dump(raw, f, allow_unicode=True, sort_keys=False)

                messagebox.showinfo("保存成功", "系统设置已保存到 config.yaml。摄像头编号修改后需要重启程序生效，其余参数会尽快生效。", parent=win)
                win.destroy()
            except Exception as exc:
                messagebox.showerror("保存失败", str(exc), parent=win)

        tk.Button(btns, text="保存设置", command=save_settings, bg="#1d4ed8", fg="white", relief="flat", padx=22, pady=8, font=("Microsoft YaHei UI", 11, "bold")).pack(side=tk.LEFT)
        tk.Button(btns, text="打开留证目录", command=lambda: self._open_dir(self.cfg.evidence_dir), bg="#334155", fg="white", relief="flat", padx=16, pady=8).pack(side=tk.LEFT, padx=10)
        tk.Button(btns, text="打开日志目录", command=lambda: self._open_dir(self.cfg.log_dir), bg="#334155", fg="white", relief="flat", padx=16, pady=8).pack(side=tk.LEFT)
        tk.Button(btns, text="关闭", command=win.destroy, bg="#475569", fg="white", relief="flat", padx=16, pady=8).pack(side=tk.RIGHT)

    def _card(self, parent, title, value, sub):
        f = tk.Frame(parent, bg="#142238", highlightbackground="#26384f", highlightthickness=1, height=92)
        f.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=7)
        f.pack_propagate(False)
        tk.Label(f, text=title, fg="#cbd5e1", bg="#142238", font=("Microsoft YaHei UI", 10)).pack(anchor="w", padx=18, pady=(14, 0))
        val = tk.Label(f, text=value, fg="#f8fafc", bg="#142238", font=("Microsoft YaHei UI", 20, "bold"))
        val.pack(anchor="w", padx=18)
        tk.Label(f, text=sub, fg="#94a3b8", bg="#142238", font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=18)
        f.value_label = val
        return f

    def _panel(self, parent, title):
        f = tk.Frame(parent, bg="#142238", highlightbackground="#26384f", highlightthickness=1)
        tk.Label(f, text=title, fg="#f8fafc", bg="#142238", font=("Microsoft YaHei UI", 13, "bold"), anchor="w").pack(fill=tk.X, padx=16, pady=(14, 4))
        return f

    def _refresh(self):
        with self.lock:
            frame = None if self.state.latest_frame is None else self.state.latest_frame.copy()
            events = list(self.state.events)[-8:][::-1]
            started_at = self.state.started_at
            alarm_count = self.state.today_alarm_count
            evi_count = self.state.today_evidence_count
            running = self.state.running
            camera_ok = self.state.camera_ok
            computer_name = self.state.computer_name
            camera_index = getattr(self.state, "camera_index", "-")

        if frame is not None:
            self._set_video(frame)
        else:
            self.video_label.configure(text="等待摄像头画面...", fg="#94a3b8", font=("Microsoft YaHei UI", 18))

        elapsed = int(time.time() - started_at)
        h, m, s = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
        self.card_alarm.value_label.configure(text=f"{alarm_count} 次")
        self.card_evi.value_label.configure(text=f"{evi_count} 张")
        self.card_runtime.value_label.configure(text=f"{h:02d}:{m:02d}:{s:02d}")
        self.card_state.value_label.configure(text="监控中" if running and camera_ok else "异常")
        self.nav_status.configure(text="● 系统运行中" if running else "● 已停止", fg="#22c55e" if running else "#ef4444")
        self.left_info.configure(text=f"运行时长： {h:02d}:{m:02d}:{s:02d}\n摄像头状态： {'正常' if camera_ok else '异常'}\n当前摄像头： {camera_index}\n本机名称： {computer_name or '-'}\n版本号： v1.1.1")
        self._render_events(events)
        self._draw_trend(alarm_count)
        self.root.after(max(16, int(getattr(self.cfg, "ui_update_interval_ms", 80))), self._refresh)

    def _set_video(self, frame):
        """刷新实时画面。

        这里使用固定画布尺寸，而不是读取 video_label.winfo_width()/winfo_height()
        动态计算图片大小。否则在部分 Windows 机器上，Label 会被图片撑大，
        下一帧又按更大的 Label 尺寸生成更大的图片，导致窗口不断放大。
        """
        target_w, target_h = 760, 428
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        img.thumbnail((target_w, target_h), Image.LANCZOS)

        canvas = Image.new("RGB", (target_w, target_h), (2, 6, 23))
        x = (target_w - img.width) // 2
        y = (target_h - img.height) // 2
        canvas.paste(img, (x, y))

        self._img_ref = ImageTk.PhotoImage(canvas)
        self.video_label.configure(image=self._img_ref, text="", width=target_w, height=target_h)

    def _render_events(self, events):
        for w in self.event_list.winfo_children():
            w.destroy()
        self._thumb_refs = []
        if not events:
            tk.Label(self.event_list, text="暂无预警记录", fg="#94a3b8", bg="#142238", font=("Microsoft YaHei UI", 12)).pack(pady=40)
            return
        for ev in events:
            row = tk.Frame(self.event_list, bg="#172a44", highlightbackground="#2b405c", highlightthickness=1)
            row.pack(fill=tk.X, pady=5)
            img_path = ev.get("evidence_image", "")
            if img_path and os.path.exists(img_path):
                try:
                    im = Image.open(img_path).resize((86, 52))
                    photo = ImageTk.PhotoImage(im)
                    self._thumb_refs.append(photo)
                    tk.Label(row, image=photo, bg="#172a44").pack(side=tk.LEFT, padx=8, pady=8)
                except Exception:
                    tk.Label(row, text="无图", fg="#94a3b8", bg="#172a44", width=10).pack(side=tk.LEFT, padx=8)
            else:
                tk.Label(row, text="无图", fg="#94a3b8", bg="#172a44", width=10).pack(side=tk.LEFT, padx=8)
            info = tk.Frame(row, bg="#172a44")
            info.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=8)
            tk.Label(info, text="● 疑似手机拍摄行为", fg="#f8fafc", bg="#172a44", font=("Microsoft YaHei UI", 10, "bold"), anchor="w").pack(fill=tk.X)
            tk.Label(info, text=ev.get("time", ""), fg="#cbd5e1", bg="#172a44", font=("Microsoft YaHei UI", 10), anchor="w").pack(fill=tk.X)
            tk.Label(row, text="高风险", fg="#93c5fd", bg="#1d4ed8", font=("Microsoft YaHei UI", 9), padx=8, pady=3).pack(side=tk.RIGHT, padx=10)

    def _draw_trend(self, count):
        c = self.trend_canvas
        c.delete("all")
        w = max(1, c.winfo_width())
        h = max(1, c.winfo_height())
        vals = [max(0, count - 3), max(0, count - 2), max(0, count - 1), count, max(0, count - 1), count, count]
        mx = max(vals + [1])
        pts = []
        for i, v in enumerate(vals):
            x = 20 + i * ((w - 40) / 6)
            y = h - 20 - (v / mx) * (h - 40)
            pts.append((x, y))
        for y in [20, h/2, h-20]:
            c.create_line(16, y, w-16, y, fill="#26384f")
        for i in range(len(pts)-1):
            c.create_line(*pts[i], *pts[i+1], fill="#ef4444", width=2)
        for x, y in pts:
            c.create_oval(x-3, y-3, x+3, y+3, fill="#ef4444", outline="")

    def _open_dir(self, path):
        os.makedirs(path, exist_ok=True)
        try:
            os.startfile(os.path.abspath(path))
        except Exception:
            pass

    def show(self):
        self.root.after(0, lambda: (self.root.deiconify(), self.root.lift(), self.root.focus_force()))

    def hide(self):
        self.root.withdraw()
        self.on_hide()

    def exit_app(self):
        self.on_exit()
        self.root.after(100, self.root.destroy)

    def run(self, initially_visible: bool = False):
        if not initially_visible:
            self.root.withdraw()
        self.root.mainloop()
