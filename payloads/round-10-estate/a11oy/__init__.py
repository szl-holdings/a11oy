"""a11oy — governed-action core.

Zero third-party dependency doctrine: every module runs on the Python
standard library alone. Where the `cryptography` package is present it is
used for Ed25519 signatures; otherwise receipts fall back to an explicitly
labelled HMAC-SHA256 demo scheme. The scheme in use is always recorded on
the receipt itself — a silent downgrade would be a Zero-Bandaid violation.
"""

__version__ = "0.1.0"
PREDICATE_TYPE = "https://szl.dev/GovernedAction/v1"
INTOTO_STATEMENT = "https://in-toto.io/Statement/v1"
