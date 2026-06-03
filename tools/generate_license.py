import argparse
import base64
import json
from datetime import date

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def main():
    parser = argparse.ArgumentParser(description="Generate a CameraGuard machine-bound license code.")
    parser.add_argument("machine_code", help="Machine code shown by CameraGuard.")
    parser.add_argument("--customer", default="", help="Optional customer name.")
    parser.add_argument("--expires", default="", help="Optional expiry date, YYYY-MM-DD.")
    parser.add_argument("--private-key", default="license_private_key.pem", help="RSA private key PEM path.")
    args = parser.parse_args()

    if args.expires:
        date.fromisoformat(args.expires)

    payload = {
        "machine_code": args.machine_code.strip().upper(),
        "customer": args.customer.strip(),
        "expires": args.expires.strip(),
    }
    payload_bytes = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

    with open(args.private_key, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)

    signature = private_key.sign(payload_bytes, padding.PKCS1v15(), hashes.SHA256())
    print(f"{b64url(payload_bytes)}.{b64url(signature)}")


if __name__ == "__main__":
    main()
