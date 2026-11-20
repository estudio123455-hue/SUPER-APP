"""Cryptographic HMAC-SHA256 verification for external Payment Gateway Webhooks (Nequi / PSE / Wompi)."""

import hashlib
import hmac

from app.core.config import get_settings


def compute_payment_webhook_signature(
    raw_body: bytes,
    secret: str | None = None,
) -> str:
    """Computes the hex-encoded HMAC-SHA256 signature for a webhook payload."""
    effective_secret = secret or get_settings().payment_webhook_secret
    return hmac.new(
        effective_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()


def verify_payment_webhook_signature(
    raw_body: bytes,
    provided_signature: str | None,
    canonical_payload: str | None = None,
    secret: str | None = None,
) -> bool:
    """Constant-time verification of X-Webhook-Signature using hmac.compare_digest."""
    if not provided_signature or not provided_signature.strip():
        return False

    cleaned_sig = provided_signature.strip().removeprefix("sha256=").strip().lower()
    if not cleaned_sig:
        return False

    expected_raw_sig = compute_payment_webhook_signature(raw_body, secret=secret).lower()
    if hmac.compare_digest(expected_raw_sig, cleaned_sig):
        return True

    if canonical_payload is not None:
        expected_canonical_sig = compute_payment_webhook_signature(
            canonical_payload.encode("utf-8"),
            secret=secret,
        ).lower()
        if hmac.compare_digest(expected_canonical_sig, cleaned_sig):
            return True

    return False
