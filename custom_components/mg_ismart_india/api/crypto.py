from __future__ import annotations
import hashlib
import hmac
import re
from binascii import unhexlify
from typing import Any
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad


class MgIndiaApiError(Exception):
    pass


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) >= 10:
        digits = digits[-10:]
    if len(digits) != 10:
        raise MgIndiaApiError("Use the 10 digit India mobile number")
    return digits


def make_device_id(phone: str) -> str:
    return "ha-india-" + \
        hashlib.sha256(normalize_phone(phone).encode()).hexdigest()[:40]


def md5_hex(value: str) -> str:
    return hashlib.md5(value.encode()).hexdigest()  # noqa: S324 - MG India protocol compatibility


def tap_signature(body: str) -> str:
    key = md5_hex(body[1: len(body) // 2])
    return hmac.new(key.encode(), body.encode(), hashlib.sha256).hexdigest()


def gateway_signature(
        path: str,
        timestamp: str,
        content_type: str = "application/json") -> str:
    part1 = md5_hex(path)
    part2 = md5_hex(part1 + timestamp + "1" + content_type)
    key = md5_hex(part2 + timestamp)
    return hmac.new(
        key.encode(),
        (path + timestamp + "1" + content_type).encode(),
        hashlib.sha256).hexdigest()


def hash_control_pin(pin: str) -> str:
    if not re.fullmatch(r"\d{4,8}", pin or ""):
        raise MgIndiaApiError("Control PIN must be 4 to 8 digits")
    normalized = pin if len(pin) == 6 else f"{pin}00"
    return md5_hex(normalized).upper()


def decrypt_gateway_body(encrypted: str, headers: Any) -> str:
    timestamp = headers.get(
        "APP-TIMESTAMP") or headers.get("app-timestamp") or ""
    key = md5_hex(timestamp)[:16].encode()
    return unpad(
        AES.new(
            key,
            AES.MODE_CBC,
            key).decrypt(
            unhexlify(encrypted)),
        AES.block_size).decode()
