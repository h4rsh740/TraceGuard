"""Cryptographic hash chain utilities for tamper-evident event logging."""

import hashlib
import json
from typing import Any

GENESIS_PREV_HASH = "0" * 64


def canonical_json(data: Any) -> str:
    """Serialize data into a deterministic, canonical JSON string (RFC 8785 style).

    - Sorted keys
    - Minimal separators (no extra whitespace)
    - UTF-8 encoding
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def compute_event_hash(prev_hash: str | None, normalized_event: dict[str, Any]) -> str:
    """Compute SHA-256 hash for an event chained to the previous event hash.

    event_hash = SHA256(prev_hash + canonical_json(normalized_event))
    """
    effective_prev = prev_hash if prev_hash else GENESIS_PREV_HASH
    payload_str = canonical_json(normalized_event)
    combined = f"{effective_prev}{payload_str}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()
