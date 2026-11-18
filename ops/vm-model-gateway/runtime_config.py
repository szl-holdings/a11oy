#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Shared, loopback-only transport selection for the proposal gateway."""

import json
import pathlib
import re
import socket
from dataclasses import dataclass

LOOPBACK_HOST = "127.0.0.1"
GATEWAY_PORT = 4000
GATEWAY_PORT_ENV = "SZL_VM_GATEWAY_PORT"
DEFAULT_TUNNEL_PORT = 19483
REMOTE_MODEL_PORT = 8080
TUNNEL_PORT_ENV = "SZL_VM_GATEWAY_TUNNEL_PORT"
CONFIG_SCHEMA = "szl.vm-model-transport/v1"


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_transport_configuration_field")
        result[key] = value
    return result


@dataclass(frozen=True)
class LocalTransport:
    tunnel_port: int = DEFAULT_TUNNEL_PORT
    gateway_port: int = GATEWAY_PORT

    def __post_init__(self):
        if (type(self.gateway_port) is not int
                or not 1024 <= self.gateway_port <= 65535
                or self.gateway_port in (DEFAULT_TUNNEL_PORT, REMOTE_MODEL_PORT)):
            raise ValueError("invalid_local_gateway_port")
        if (type(self.tunnel_port) is not int
                or not 1024 <= self.tunnel_port <= 65535
                or self.tunnel_port in (GATEWAY_PORT, REMOTE_MODEL_PORT)
                or self.tunnel_port == self.gateway_port):
            raise ValueError("invalid_local_tunnel_port")

    @classmethod
    def from_environment(cls, environ):
        raw = environ.get(TUNNEL_PORT_ENV, str(DEFAULT_TUNNEL_PORT))
        if not isinstance(raw, str) or re.fullmatch(r"[1-9][0-9]{3,4}", raw) is None:
            raise ValueError("invalid_local_tunnel_port")
        selected = environ.get(GATEWAY_PORT_ENV, str(GATEWAY_PORT))
        if (not isinstance(selected, str)
                or re.fullmatch(r"[1-9][0-9]{3,4}", selected) is None):
            raise ValueError("invalid_local_gateway_port")
        return cls(int(raw), int(selected))

    @classmethod
    def from_file(cls, path):
        """Load only the operator's local port; never a host or remote target."""
        path = pathlib.Path(path)
        if path.is_symlink():
            raise ValueError("transport_configuration_symlink")
        if not path.exists():
            return cls()
        if not path.is_file():
            raise ValueError("transport_configuration_not_file")
        with path.open("rb") as source:
            raw = source.read(1025)
        if len(raw) > 1024:
            raise ValueError("transport_configuration_too_large")
        config = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_fields)
        if (not isinstance(config, dict)
                or set(config) not in (
                    {"schema", "local_tunnel_port"},
                    {"schema", "local_tunnel_port", "local_gateway_port"},
                ) or config["schema"] != CONFIG_SCHEMA):
            raise ValueError("invalid_transport_configuration")
        return cls(config["local_tunnel_port"], config.get("local_gateway_port", GATEWAY_PORT))

    @property
    def upstream(self):
        return f"{LOOPBACK_HOST}:{self.tunnel_port}"

    @property
    def health_url(self):
        return f"http://{self.upstream}/health"

    @property
    def ssh_forward(self):
        return f"{self.upstream}:{LOOPBACK_HOST}:{REMOTE_MODEL_PORT}"

    @property
    def gateway_bind(self):
        return f"{LOOPBACK_HOST}:{self.gateway_port}"

    @property
    def gateway_health_url(self):
        return f"http://{self.gateway_bind}/health"

    @property
    def gateway_environment(self):
        return {TUNNEL_PORT_ENV: str(self.tunnel_port),
                GATEWAY_PORT_ENV: str(self.gateway_port)}

    def require_free_ports(self, socket_factory=socket.socket):
        """Refuse existing listeners without adopting or terminating them."""
        for port in (self.gateway_port, self.tunnel_port):
            with socket_factory() as sock:
                sock.settimeout(1)
                if sock.connect_ex((LOOPBACK_HOST, port)) == 0:
                    raise SystemExit("Existing listener preserved; startup refused")
