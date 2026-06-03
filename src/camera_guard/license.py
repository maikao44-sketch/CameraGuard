import hashlib
import tkinter as tk
from tkinter import messagebox, simpledialog

import yaml


AUTHORIZED_CODE_HASHES = {
    "bce040e2414c56e5875c6c246abd91b81b7386bd628c6bbc6cecad23ece4f271",
}


def hash_code(code: str) -> str:
    return hashlib.sha256((code or "").strip().encode("utf-8")).hexdigest()


def is_authorized_code(code: str) -> bool:
    normalized = (code or "").strip()
    if not normalized:
        return False
    return hash_code(normalized) in AUTHORIZED_CODE_HASHES


def has_valid_activation(license_cfg) -> bool:
    code_hash = str(license_cfg.get("code_hash", "") or "").strip()
    if code_hash in AUTHORIZED_CODE_HASHES:
        return True

    legacy_code = str(license_cfg.get("code", "") or "").strip()
    return is_authorized_code(legacy_code)


def ensure_authorized(cfg, config_path: str = "config.yaml") -> bool:
    license_cfg = cfg.raw.get("license", {})
    if has_valid_activation(license_cfg):
        return True

    root = tk.Tk()
    root.withdraw()
    try:
        for _ in range(3):
            entered = simpledialog.askstring("CameraGuard 授权", "请输入软件授权码：", parent=root)
            if entered is None:
                return False
            if is_authorized_code(entered):
                cfg.raw["license"] = {"code_hash": hash_code(entered)}
                with open(config_path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(cfg.raw, f, allow_unicode=True, sort_keys=False)
                return True
            messagebox.showerror("授权失败", "授权码不正确，请重新输入。", parent=root)
        return False
    finally:
        root.destroy()
