"""EncryptedConfigCache - 加密配置缓存

使用 AES-256-GCM 加密存储从 Control Plane 拉取的完整配置，
防止敏感信息（如 LLM API Key）被直接读取。
密钥通过 PBKDF2 从节点 API Key 派生。
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger(__name__)

# 默认缓存路径
DEFAULT_CACHE_PATH = Path.home() / ".nanobot" / "config_cache.enc"

# 加密参数
_SALT_SIZE = 16       # 盐值长度（字节）
_NONCE_SIZE = 12      # AES-GCM nonce 长度（字节）
_KEY_SIZE = 32        # AES-256 密钥长度（字节）
_KDF_ITERATIONS = 480_000  # PBKDF2 迭代次数


class EncryptedConfigCache:
    """加密的配置缓存，使用节点 API Key 派生密钥

    文件格式: salt(16) + nonce(12) + ciphertext(变长，含 GCM tag)
    """

    def __init__(self, api_key: str, cache_path: Path = DEFAULT_CACHE_PATH):
        self._api_key = api_key
        self._cache_path = cache_path

    @property
    def path(self) -> Path:
        return self._cache_path

    def save(self, config_data: dict) -> None:
        """加密并保存配置到本地

        Args:
            config_data: 要缓存的完整配置字典
        """
        plaintext = json.dumps(config_data, ensure_ascii=False).encode("utf-8")
        salt = os.urandom(_SALT_SIZE)
        key = self._derive_key(self._api_key, salt)
        nonce = os.urandom(_NONCE_SIZE)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)

        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_bytes(salt + nonce + ciphertext)
        logger.info("加密配置缓存已保存: %s", self._cache_path)

    def load(self) -> dict | None:
        """从本地加载并解密配置

        Returns:
            解密后的配置字典，密钥不匹配或文件无效时返回 None
        """
        if not self._cache_path.exists():
            return None

        try:
            raw = self._cache_path.read_bytes()
            min_size = _SALT_SIZE + _NONCE_SIZE + 1
            if len(raw) < min_size:
                logger.warning("加密缓存文件过小，可能已损坏")
                return None

            salt = raw[:_SALT_SIZE]
            nonce = raw[_SALT_SIZE : _SALT_SIZE + _NONCE_SIZE]
            ciphertext = raw[_SALT_SIZE + _NONCE_SIZE :]

            key = self._derive_key(self._api_key, salt)
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            return json.loads(plaintext.decode("utf-8"))
        except Exception as e:
            logger.warning("加密配置缓存解密失败: %s", e)
            return None

    def exists(self) -> bool:
        """检查加密缓存文件是否存在"""
        return self._cache_path.exists()

    @staticmethod
    def _derive_key(api_key: str, salt: bytes) -> bytes:
        """使用 PBKDF2 从 API Key 派生 AES-256 密钥"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=_KEY_SIZE,
            salt=salt,
            iterations=_KDF_ITERATIONS,
        )
        return kdf.derive(api_key.encode("utf-8"))
