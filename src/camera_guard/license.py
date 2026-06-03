import base64
import hashlib
import json
import platform
import tkinter as tk
import uuid
from datetime import date
from tkinter import messagebox, simpledialog

import yaml
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAs9UkuIIUyPOTt3QmY8aI
Qz5KQTTuxdLspSmA/KyXG1pQU7/foMYg39CJPXjHnnU/u//nOnoCwAK6WLXhmVdL
4vRstXePvOlDynR8IX0iftr8RAVY/E3w3qtF9tQqBuV8zJ1at7GM+D179LHWirOh
slcDjiG7kvlINGdiH/t6nuhOPFdzsWwNhPzDf2BHtSj2zrd45A6yZOW2iYZ77U0S
RdhKr9lgSyZMz+XP5bqSoULUr+AJTo2KQqvlv1bRNpcMjtPXqXAHBRtEmoZUrb6j
0xB1wqFP4x7TRcpuERzvaUOy6Am8rGiZjnFGsszB8vGJRqvPVzMAzdB+Dprq8B73
WwIDAQAB
-----END PUBLIC KEY-----"""


def _b64url_decode(value: str) -> bytes:
    padding_len = (-len(value)) % 4
    return base64.urlsafe_b64decode(value + ("=" * padding_len))


def _windows_machine_guid() -> str:
    if platform.system().lower() != "windows":
        return ""
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(value)
    except Exception:
        return ""


def get_machine_code() -> str:
    parts = [
        platform.system(),
        platform.node(),
        _windows_machine_guid(),
        str(uuid.getnode()),
    ]
    raw = "|".join(part.strip().lower() for part in parts if part)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()
    return "-".join(digest[i:i + 4] for i in range(0, 20, 4))


def verify_license_code(license_code: str, machine_code: str):
    try:
        payload_part, signature_part = (license_code or "").strip().split(".", 1)
        payload_bytes = _b64url_decode(payload_part)
        signature = _b64url_decode(signature_part)
        public_key = serialization.load_pem_public_key(PUBLIC_KEY_PEM)
        public_key.verify(signature, payload_bytes, padding.PKCS1v15(), hashes.SHA256())
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (ValueError, InvalidSignature, json.JSONDecodeError, TypeError):
        return False, "授权码格式或签名无效"

    if str(payload.get("machine_code", "")).strip().upper() != machine_code:
        return False, "授权码不属于当前电脑"

    expires = str(payload.get("expires", "") or "").strip()
    if expires:
        try:
            if date.fromisoformat(expires) < date.today():
                return False, "授权码已过期"
        except ValueError:
            return False, "授权码过期时间格式无效"

    return True, payload


def has_valid_activation(license_cfg, machine_code: str) -> bool:
    license_code = str(license_cfg.get("code", "") or "").strip()
    if not license_code:
        return False
    ok, _ = verify_license_code(license_code, machine_code)
    return ok


def ensure_authorized(cfg, config_path: str = "config.yaml") -> bool:
    machine_code = get_machine_code()
    license_cfg = cfg.raw.get("license", {})
    if has_valid_activation(license_cfg, machine_code):
        return True

    root = tk.Tk()
    root.withdraw()
    try:
        try:
            root.clipboard_clear()
            root.clipboard_append(machine_code)
        except Exception:
            pass

        prompt = (
            "请输入软件授权码。\n\n"
            f"本机机器码：{machine_code}\n"
            "机器码已复制到剪贴板，请发送给管理员生成授权码。"
        )
        for _ in range(3):
            entered = simpledialog.askstring("CameraGuard 授权", prompt, parent=root)
            if entered is None:
                return False
            ok, info = verify_license_code(entered, machine_code)
            if ok:
                cfg.raw["license"] = {"code": entered.strip()}
                with open(config_path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(cfg.raw, f, allow_unicode=True, sort_keys=False)
                return True
            messagebox.showerror("授权失败", str(info), parent=root)
        return False
    finally:
        root.destroy()
