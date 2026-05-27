from __future__ import annotations

import hashlib
import hmac
from typing import Any

from loguru import logger

from app.config import settings


class FeishuAuth:
    """Feishu webhook signature verification.

    When the bot operates in webhook mode (backup to WebSocket),
    Feishu signs every request with an HMAC-SHA256 of the timestamp + body.
    """

    def __init__(
        self,
        verification_token: str | None = None,
        encrypt_key: str | None = None,
    ):
        self.verification_token = verification_token or settings.feishu_verification_token
        self.encrypt_key = encrypt_key or settings.feishu_encrypt_key

    def verify_signature(self, timestamp: str, nonce: str, body: str, signature: str) -> bool:
        """Verify the X-Lark-Signature header.

        Feishu computes: base64(HMAC-SHA256(encrypt_key, timestamp + nonce + body))
        """
        if not self.encrypt_key:
            logger.warning("Feishu encrypt_key not configured, skipping signature verification")
            return True

        sign_base = f"{timestamp}{nonce}{body}"
        computed = hmac.new(
            self.encrypt_key.encode("utf-8"),
            sign_base.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # Feishu sends signature as hex, but we compare in a timing-safe way
        expected = computed
        if isinstance(signature, str):
            result = hmac.compare_digest(expected, signature)
        else:
            result = False

        if not result:
            logger.warning("Feishu signature verification failed")
        return result

    def verify_token(self, token: str) -> bool:
        """Verify the verification token from the URL challenge or event payload."""
        if not self.verification_token:
            return True
        return hmac.compare_digest(token, self.verification_token)

    def handle_url_verification(self, challenge: str, token: str) -> dict[str, Any]:
        """Handle the Feishu URL verification handshake.

        When first configuring a webhook, Feishu sends a challenge request.
        We must echo back the challenge value.
        """
        if not self.verify_token(token):
            logger.warning("URL verification token mismatch")
            return {"error": "token mismatch"}
        return {"challenge": challenge}
