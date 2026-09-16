"""
Encryption-based subscriber ID processor -- pluggable registry.

Ported from chinthakadd7/Demask (backend/providers/encryption_provider.py).
Adapted to read ENCRYPTION_KEY/ENCRYPTION_PROVIDER via os.environ directly
(this app's existing convention in app/main.py) instead of Demask's
standalone config.py Settings class.

HOW TO ADD A NEW PROVIDER:
1. Subclass BaseEncryptionProvider and implement decrypt_series().
2. Register it in ENCRYPTION_REGISTRY with a unique string key.
3. Set ENCRYPTION_KEY and ENCRYPTION_PROVIDER in your .env file.
4. Add the method to the DemaskPage frontend UI if it needs bespoke params.

SECURITY:
- Never hard-code encryption keys.
- Keys are always read from environment variables.
- Do not attempt brute-force or key guessing.
"""

import base64
import hashlib
import hmac
import os
from abc import ABC, abstractmethod
from typing import Dict, Type

import pandas as pd

from .base import BaseProcessor, ProcessingResult


class BaseEncryptionProvider(ABC):
    def __init__(self, key: str):
        self.key = key

    @abstractmethod
    def decrypt_series(self, series: pd.Series) -> pd.Series: ...


class DemoCipherProvider(BaseEncryptionProvider):
    """
    Reversible token cipher using standard library HMAC-SHA256 keystream.
    Zero external C-dependencies, fully reversible, safe on all Python versions.
    """

    def _derive_keystream(self, length: int) -> bytes:
        derived_key = hashlib.sha256(self.key.encode("utf-8")).digest()
        stream = bytearray()
        counter = 0
        while len(stream) < length:
            chunk = hmac.new(
                derived_key,
                f"slt-stream-{counter}".encode("utf-8"),
                hashlib.sha256,
            ).digest()
            stream.extend(chunk)
            counter += 1
        return bytes(stream[:length])

    def decrypt_value(self, val: str) -> str:
        s = str(val).strip()
        if not s:
            return s

        # Support demo token format: ENC_<id>_<tag> (e.g., ENC_94123456789_x8f21 -> 94123456789)
        if s.startswith("ENC_") and "_" in s[4:]:
            parts = s[4:].split("_")
            if parts[0].isdigit() and len(parts[0]) >= 7:
                return parts[0]

        raw_b64 = s[4:] if s.startswith("ENC_") else s
        if "_" in raw_b64:
            raw_b64 = raw_b64.split("_")[0]

        padding = "=" * (-len(raw_b64) % 4)
        try:
            ct = base64.urlsafe_b64decode(raw_b64 + padding)
            ks = self._derive_keystream(len(ct))
            pt = bytes(b ^ ks[i] for i, b in enumerate(ct))
            return pt.decode("utf-8")
        except Exception:
            return s

    def encrypt_value(self, val: str) -> str:
        pt = str(val).encode("utf-8")
        ks = self._derive_keystream(len(pt))
        ct = bytes(b ^ ks[i] for i, b in enumerate(pt))
        token = base64.urlsafe_b64encode(ct).decode("utf-8").rstrip("=")
        return f"ENC_{token}"

    def decrypt_series(self, series: pd.Series) -> pd.Series:
        return series.astype(str).apply(self.decrypt_value)


# -- Registry -- register providers here -------------------------------------
ENCRYPTION_REGISTRY: Dict[str, Type[BaseEncryptionProvider]] = {
    "demo_cipher": DemoCipherProvider,
    "aes_token": DemoCipherProvider,
}

try:
    from cryptography.fernet import Fernet

    class FernetProvider(BaseEncryptionProvider):
        """Real AES-based decryption via the `cryptography` package's Fernet recipe."""

        def __init__(self, key: str):
            super().__init__(key)
            self.cipher = Fernet(key.encode("utf-8"))

        def decrypt_series(self, series: pd.Series) -> pd.Series:
            return series.astype(str).apply(
                lambda val: self.cipher.decrypt(str(val).encode("utf-8")).decode("utf-8")
            )

    ENCRYPTION_REGISTRY["fernet"] = FernetProvider
except ImportError:
    pass


class EncryptionProvider(BaseProcessor):
    def process(self, df: pd.DataFrame, subscriber_id_col: str, encryption_method: str) -> ProcessingResult:
        total = len(df)

        if encryption_method not in ENCRYPTION_REGISTRY:
            available = list(ENCRYPTION_REGISTRY.keys())
            raise NotImplementedError(
                f"Encryption method '{encryption_method}' is not implemented. "
                f"Available: {available or 'none configured'}."
            )

        encryption_key = os.environ.get("ENCRYPTION_KEY", "")
        if not encryption_key:
            raise ValueError("No ENCRYPTION_KEY configured. Set it in your .env file.")

        provider = ENCRYPTION_REGISTRY[encryption_method](key=encryption_key)
        result_df = df.copy()

        try:
            result_df[subscriber_id_col] = provider.decrypt_series(result_df[subscriber_id_col])
        except Exception as exc:
            raise RuntimeError(f"Decryption failed: {exc}") from exc

        return ProcessingResult(dataframe=result_df, total_records=total, processed=total, unprocessed=0, errors=0)
