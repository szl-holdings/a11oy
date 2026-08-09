"""Stable principal authentication for the Governed Delta Workspace.

This services-layer module accepts a secret-managed JSON registry, reduces raw
bearer tokens to fixed-length digests during parsing, accepts exact pre-hashed
token bindings, and returns immutable principal identities. Raw tokens are
never retained by the resulting registry or included in errors and
representations.
"""

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Any, FrozenSet, Iterable, Optional, Tuple, Union


_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
_REGISTRY_KEYS = frozenset({"version", "credentials"})
_CREDENTIAL_KEYS = frozenset(
    {
        "owner_id",
        "namespace",
        "key_id",
        "token",
        "token_sha256",
        "scopes",
        "revoked",
    }
)
_REQUIRED_CREDENTIAL_KEYS = frozenset(
    {"owner_id", "namespace", "key_id", "scopes"}
)
_TOKEN_KEYS = frozenset({"token", "token_sha256"})
_LEGACY_PRINCIPAL_KEYS = frozenset({"token_sha256", "roles"})
_LEGACY_ROLE_SCOPES = {
    "user": frozenset({"session:read", "step:write"}),
    "admin": frozenset(
        {
            "bench:read",
            "integrity:global",
            "integrity:read",
            "metrics:read",
            "session:read",
            "step:write",
        }
    ),
}
_SAFE_AUTH_MESSAGES = {
    "missing_authorization": "bearer authorization is required",
    "invalid_authorization": "bearer authorization is invalid",
    "invalid_bearer_token": "bearer credential is invalid",
    "credential_revoked": "bearer credential is revoked",
    "foreign_namespace": "bearer credential is not valid for this namespace",
    "missing_scopes": "bearer credential lacks required scopes",
}


class AuthConfigurationError(ValueError):
    """Raised when authentication configuration is absent or malformed."""


class AuthenticationError(ValueError):
    """A token-safe authentication failure with a stable machine code."""

    def __init__(self, code: str):
        if code not in _SAFE_AUTH_MESSAGES:
            raise ValueError("unknown authentication error code")
        self.code = code
        super().__init__(_SAFE_AUTH_MESSAGES[code])


@dataclass(frozen=True, slots=True)
class Principal:
    """Stable caller identity, independent of the active credential key."""

    owner_id: str
    namespace: str
    key_id: str
    scopes: Tuple[str, ...]


@dataclass(frozen=True, slots=True, repr=False)
class _Credential:
    owner_id: str
    namespace: str
    key_id: str
    token_digest: bytes
    scopes: FrozenSet[str]
    revoked: bool


class CredentialRegistry:
    """Immutable, token-redacted credential registry."""

    __slots__ = ("_credentials",)

    def __init__(self, credentials: Iterable[_Credential]):
        values = tuple(credentials)
        if not values:
            raise AuthConfigurationError(
                "credential registry must contain at least one credential"
            )
        self._credentials = values

    @property
    def credential_count(self) -> int:
        return len(self._credentials)

    def __repr__(self) -> str:
        return f"CredentialRegistry(credential_count={self.credential_count})"

    def authenticate(
        self,
        authorization: Optional[str],
        *,
        namespace: str,
        required_scopes: Iterable[str] = (),
    ) -> Principal:
        """Authenticate a bearer header without short-circuiting credential scans."""
        canonical_namespace = _validate_identifier("namespace", namespace)
        required = _normalize_scopes(
            required_scopes,
            field_name="required_scopes",
            allow_empty=True,
            require_list=False,
        )
        token = _parse_bearer_header(authorization)
        try:
            supplied_digest = hashlib.sha256(token.encode("utf-8")).digest()
        finally:
            token = None

        matched: Optional[_Credential] = None
        for credential in self._credentials:
            is_match = hmac.compare_digest(
                supplied_digest,
                credential.token_digest,
            )
            if is_match:
                matched = credential

        if matched is None:
            raise AuthenticationError("invalid_bearer_token")
        if matched.revoked:
            raise AuthenticationError("credential_revoked")
        if matched.namespace != canonical_namespace:
            raise AuthenticationError("foreign_namespace")
        if not required.issubset(matched.scopes):
            raise AuthenticationError("missing_scopes")
        return Principal(
            owner_id=matched.owner_id,
            namespace=matched.namespace,
            key_id=matched.key_id,
            scopes=tuple(sorted(matched.scopes)),
        )


def _reject_duplicate_object_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AuthConfigurationError("credential registry has duplicate object keys")
        result[key] = value
    return result


def _validate_identifier(field_name: str, value: Any) -> str:
    if type(value) is not str or not _IDENTIFIER_PATTERN.fullmatch(value):
        raise AuthConfigurationError(
            f"{field_name} must be a canonical lowercase identifier"
        )
    return value


def _normalize_scopes(
    value: Any,
    *,
    field_name: str,
    allow_empty: bool,
    require_list: bool,
) -> FrozenSet[str]:
    if require_list:
        if type(value) is not list:
            raise AuthConfigurationError(f"{field_name} must be a JSON array")
        values = value
    else:
        if isinstance(value, (str, bytes)) or value is None:
            raise AuthConfigurationError(f"{field_name} must be an iterable of scopes")
        try:
            values = list(value)
        except TypeError as exc:
            raise AuthConfigurationError(
                f"{field_name} must be an iterable of scopes"
            ) from exc
    if not values and not allow_empty:
        raise AuthConfigurationError(f"{field_name} must not be empty")
    normalized = tuple(
        _validate_identifier(f"{field_name} item", item) for item in values
    )
    if len(set(normalized)) != len(normalized):
        raise AuthConfigurationError(f"{field_name} must not contain duplicates")
    return frozenset(normalized)


def _digest_registry_token(value: Any) -> bytes:
    token = value
    try:
        if type(token) is not str or not token:
            raise AuthConfigurationError("credential token must be a non-empty string")
        if len(token) > 4096 or any(character.isspace() for character in token):
            raise AuthConfigurationError(
                "credential token must be a bounded bearer token"
            )
        return hashlib.sha256(token.encode("utf-8")).digest()
    finally:
        token = None


def _parse_token_sha256(value: Any) -> bytes:
    if (
        type(value) is not str
        or not re.fullmatch(r"[0-9a-f]{64}", value)
        or value == hashlib.sha256(b"").hexdigest()
    ):
        raise AuthConfigurationError(
            "credential token_sha256 must be a lowercase SHA-256 digest"
        )
    return bytes.fromhex(value)


def _credential_from_mapping(raw: Any, index: int) -> _Credential:
    if type(raw) is not dict:
        raise AuthConfigurationError(
            f"credential registry entry {index} must be an object"
        )

    keys = frozenset(raw)
    unknown = keys - _CREDENTIAL_KEYS
    missing = _REQUIRED_CREDENTIAL_KEYS - keys
    token_keys = keys & _TOKEN_KEYS
    if unknown or missing or len(token_keys) != 1:
        raise AuthConfigurationError(
            f"credential registry entry {index} has an invalid shape"
        )

    token_key = next(iter(token_keys))
    token_value = raw.pop(token_key)
    try:
        token_digest = (
            _digest_registry_token(token_value)
            if token_key == "token"
            else _parse_token_sha256(token_value)
        )
    finally:
        token_value = None

    owner_id = _validate_identifier("owner_id", raw["owner_id"])
    namespace = _validate_identifier("namespace", raw["namespace"])
    key_id = _validate_identifier("key_id", raw["key_id"])
    scopes = _normalize_scopes(
        raw["scopes"],
        field_name="scopes",
        allow_empty=False,
        require_list=True,
    )
    revoked = raw.get("revoked", False)
    if type(revoked) is not bool:
        raise AuthConfigurationError("revoked must be a JSON boolean")
    return _Credential(
        owner_id=owner_id,
        namespace=namespace,
        key_id=key_id,
        token_digest=token_digest,
        scopes=scopes,
        revoked=revoked,
    )


def _registry_from_credentials(
    credentials: Iterable[_Credential],
) -> CredentialRegistry:
    values = []
    token_digests = set()
    key_ids = set()
    for credential in credentials:
        if credential.token_digest in token_digests:
            raise AuthConfigurationError(
                "credential registry contains a duplicate token"
            )
        key_identity = (credential.namespace, credential.key_id)
        if key_identity in key_ids:
            raise AuthConfigurationError(
                "credential registry contains a duplicate namespace/key_id"
            )
        token_digests.add(credential.token_digest)
        key_ids.add(key_identity)
        values.append(credential)
    return CredentialRegistry(values)


def parse_credential_registry(
    registry_json: Union[str, bytes, bytearray],
) -> CredentialRegistry:
    """Parse a strict version-1 JSON registry and immediately redact raw tokens."""
    raw_registry = registry_json
    try:
        if not isinstance(raw_registry, (str, bytes, bytearray)):
            raise AuthConfigurationError("credential registry must be JSON text")
        if not raw_registry:
            raise AuthConfigurationError("credential registry must not be empty")
        try:
            decoded = json.loads(
                raw_registry,
                object_pairs_hook=_reject_duplicate_object_keys,
            )
        except AuthConfigurationError:
            raise
        except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AuthConfigurationError("credential registry is not valid JSON") from exc
    finally:
        raw_registry = None
        registry_json = None

    if type(decoded) is not dict or frozenset(decoded) != _REGISTRY_KEYS:
        raise AuthConfigurationError("credential registry has an invalid top-level shape")
    if type(decoded["version"]) is not int or decoded["version"] != 1:
        raise AuthConfigurationError("credential registry version must be 1")
    raw_credentials = decoded["credentials"]
    if type(raw_credentials) is not list or not raw_credentials:
        raise AuthConfigurationError(
            "credential registry must contain a non-empty credentials array"
        )

    credentials = []
    for index, raw_credential in enumerate(raw_credentials):
        credentials.append(_credential_from_mapping(raw_credential, index))
    return _registry_from_credentials(credentials)


def parse_legacy_principal_registry(
    registry_json: Union[str, bytes, bytearray],
    *,
    namespace: str,
) -> CredentialRegistry:
    """Map the former digest-only principal registry to stable scoped credentials."""
    canonical_namespace = _validate_identifier("namespace", namespace)
    raw_registry = registry_json
    try:
        if not isinstance(raw_registry, (str, bytes, bytearray)):
            raise AuthConfigurationError("principal registry must be JSON text")
        if not raw_registry:
            raise AuthConfigurationError("principal registry must not be empty")
        try:
            decoded = json.loads(
                raw_registry,
                object_pairs_hook=_reject_duplicate_object_keys,
            )
        except AuthConfigurationError:
            raise
        except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AuthConfigurationError("principal registry is not valid JSON") from exc
    finally:
        raw_registry = None
        registry_json = None

    if type(decoded) is not dict or not decoded:
        raise AuthConfigurationError(
            "principal registry must contain at least one principal"
        )

    credentials = []
    for index, (principal_id, raw_record) in enumerate(decoded.items()):
        owner_id = _validate_identifier("principal_id", principal_id)
        if (
            type(raw_record) is not dict
            or frozenset(raw_record) != _LEGACY_PRINCIPAL_KEYS
        ):
            raise AuthConfigurationError(
                f"principal registry entry {index} has an invalid shape"
            )
        roles = raw_record["roles"]
        if type(roles) is not list or not roles:
            raise AuthConfigurationError("principal roles must be a non-empty array")
        if (
            any(type(role) is not str or role not in _LEGACY_ROLE_SCOPES for role in roles)
            or len(set(roles)) != len(roles)
        ):
            raise AuthConfigurationError("principal roles are invalid")
        scopes = frozenset().union(
            *(_LEGACY_ROLE_SCOPES[role] for role in roles)
        )
        key_id = "legacy:" + hashlib.sha256(
            owner_id.encode("utf-8")
        ).hexdigest()[:24]
        credentials.append(
            _Credential(
                owner_id=owner_id,
                namespace=canonical_namespace,
                key_id=key_id,
                token_digest=_parse_token_sha256(raw_record["token_sha256"]),
                scopes=scopes,
                revoked=False,
            )
        )
    return _registry_from_credentials(credentials)


def _legacy_registry(
    *,
    token: Optional[str],
    owner_id: Optional[str],
    namespace: Optional[str],
    key_id: str,
    scopes: Iterable[str],
) -> CredentialRegistry:
    if token is None or owner_id is None or namespace is None:
        raise AuthConfigurationError(
            "legacy authentication requires token, owner_id, and namespace"
        )
    credential = _Credential(
        owner_id=_validate_identifier("legacy owner_id", owner_id),
        namespace=_validate_identifier("legacy namespace", namespace),
        key_id=_validate_identifier("legacy key_id", key_id),
        token_digest=_digest_registry_token(token),
        scopes=_normalize_scopes(
            scopes,
            field_name="legacy scopes",
            allow_empty=False,
            require_list=False,
        ),
        revoked=False,
    )
    token = None
    return CredentialRegistry((credential,))


def load_credential_registry(
    registry_json: Optional[Union[str, bytes, bytearray]],
    *,
    principal_registry_json: Optional[Union[str, bytes, bytearray]] = None,
    principal_registry_namespace: Optional[str] = None,
    legacy_enabled: bool = False,
    legacy_token: Optional[str] = None,
    legacy_owner_id: Optional[str] = None,
    legacy_namespace: Optional[str] = None,
    legacy_key_id: str = "legacy",
    legacy_scopes: Iterable[str] = (),
) -> CredentialRegistry:
    """Load registry JSON or an explicitly enabled, fully bound legacy credential."""
    legacy_scopes = tuple(legacy_scopes)
    configured_registries = sum(
        value is not None for value in (registry_json, principal_registry_json)
    )
    if configured_registries > 1:
        raise AuthConfigurationError(
            "credential registries cannot be configured together"
        )
    legacy_values_present = any(
        value is not None
        for value in (legacy_token, legacy_owner_id, legacy_namespace)
    ) or legacy_key_id != "legacy" or bool(legacy_scopes)
    if registry_json is not None:
        if legacy_enabled is True or legacy_values_present:
            raise AuthConfigurationError(
                "registry and legacy authentication cannot be configured together"
            )
        return parse_credential_registry(registry_json)
    if principal_registry_json is not None:
        if legacy_enabled is True or legacy_values_present:
            raise AuthConfigurationError(
                "registry and legacy authentication cannot be configured together"
            )
        if principal_registry_namespace is None:
            raise AuthConfigurationError(
                "principal registry requires a namespace binding"
            )
        return parse_legacy_principal_registry(
            principal_registry_json,
            namespace=principal_registry_namespace,
        )
    if legacy_enabled is not True:
        if legacy_values_present:
            raise AuthConfigurationError("legacy authentication is not enabled")
        raise AuthConfigurationError("credential registry is not configured")
    return _legacy_registry(
        token=legacy_token,
        owner_id=legacy_owner_id,
        namespace=legacy_namespace,
        key_id=legacy_key_id,
        scopes=legacy_scopes,
    )


def _parse_bearer_header(authorization: Optional[str]) -> str:
    if authorization is None:
        raise AuthenticationError("missing_authorization")
    if type(authorization) is not str:
        raise AuthenticationError("invalid_authorization")
    scheme, separator, token = authorization.partition(" ")
    if (
        not separator
        or scheme.lower() != "bearer"
        or not token
        or len(token) > 4096
        or any(character.isspace() for character in token)
    ):
        token = None
        raise AuthenticationError("invalid_authorization")
    return token


def authenticate_bearer(
    authorization: Optional[str],
    registry: CredentialRegistry,
    *,
    namespace: str,
    required_scopes: Iterable[str] = (),
) -> Principal:
    """Authenticate through a parsed registry and return an immutable principal."""
    if not isinstance(registry, CredentialRegistry):
        raise AuthConfigurationError("registry must be a CredentialRegistry")
    return registry.authenticate(
        authorization,
        namespace=namespace,
        required_scopes=required_scopes,
    )
