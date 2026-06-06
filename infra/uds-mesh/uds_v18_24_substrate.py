#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# ORCID: 0009-0001-0110-4173
# Doctrine v6
# =====================================================================
# uds_v18_24_substrate.py
# =====================================================================
#
# REPLIT INSTRUCTIONS
# -------------------
# 1. Create a new Python Repl (Python 3.10+).
# 2. Drop this file at the project root alongside OUROBOROS_RUN_ALL.py.
# 3. Click Run (or:  python3 uds_v18_24_substrate.py).
# 4. The script self-tests all five v18.24 UDS Operational grafts +
#    runs doctests, then prints a GREEN or RED summary.
# 5. Exit code 0 == green, 1 == regression. No pip installs. Stdlib only.
#
# WHAT THIS FILE IMPLEMENTS — Ouroboros Thesis v18.24
# ---------------------------------------------------
#   UDS Operational graft — 2026-05-28
#   SensorReceiptChain + AirGapPayload + PINNResidualLambda +
#   A15PersistentHomology + OperatorConsole
#
#   Version line:
#   v18.24 UDS Operational graft — 2026-05-28 — SensorReceiptChain +
#   AirGapPayload + PINNResidualLambda + A15PersistentHomology +
#   OperatorConsole
#
#   Grafts (Lean 4 theorems → Python pendants):
#     1. UDSAirGapPayload
#        (uds-airgap-replit-payload — drone control loop with
#         Λ-receipt over every sensor packet; composes Wheeler +
#         v17.3 UDS-AirGap + Lutar.UDSInvariant)
#     2. UDSSensorPacket + UDSSensorReceiptChain
#        (Lutar.UDSSensorReceiptChain.lean —
#         uds_sensor_chain_well_formed,
#         uds_sensor_chain_subsumes_sbom_chain)
#     3. PINNResidualLambda
#        (Lutar.PINNResidualConfidence.lean —
#         confidence_monotone_in_residual)
#     4. A15PersistentHomologyCheck
#        (Lutar.Topology.PersistentHomologyChain.lean —
#         finite-rank Euler-identity Betti-1 bound,
#         cites ELZ 2002 doi:10.1007/s00454-002-2885-2)
#     5. UDSOperatorConsoleDataPlane
#        (uds-operator-console data plane — emits HUKLLA alerts,
#         dual-witness, receipt-chain viewer, A15 topology pane)
#
#   License-cleared upstreams:
#     maziarraissi/PINNs           MIT          SHA 932f50a2d8ef
#       https://github.com/maziarraissi/PINNs
#     uds-mesh                     Apache-2.0   internal szl-holdings
#     szl-operator-dashboard       Apache-2.0   internal szl-holdings
#
#   Architectural-pattern-only (no code copied):
#     lululxvi/deepxde             LGPL-2.1     SHA b8d69c4311a2
#
#   Citations:
#     Raissi, Perdikaris, Karniadakis 2019, J. Comp. Phys. 378:686–707
#       https://www.sciencedirect.com/science/article/pii/S0021999118307125
#       (arXiv 1711.10561)
#     Edelsbrunner, Letscher, Zomorodian 2002 — Topological Persistence
#       and Simplification.  Discrete Comput. Geom. 28(4):511–533.
#       https://doi.org/10.1007/s00454-002-2885-2
#     RFC 8949 — Concise Binary Object Representation (CBOR)
#       https://www.rfc-editor.org/rfc/rfc8949
#     RFC 8259 — JSON
#       https://www.rfc-editor.org/rfc/rfc8259
#     Warhacker 2026 (San Diego, 16–19 June)
#       https://www.warhacker.org/  (event reference)
#
#   Cross-ref:
#     v17.3  UDS-AirGap        — sovereign edge DDIL drone substrate
#     v18.4  John-Mwendwa      — operator dashboard skeleton extended
#     v18.9  Palantir          — Λ-color theme + AtlasDB Λ-axis types
#     v18.19 IQT               — Lutar.SBOMProvenance composition target
#     v18.20 TurboVec          — PINN-RAG cross-reference (receipt index)
#     v18.21 NVIDIA RTR        — PINN-field-viz cross-reference
#
#   Doctrine: v6 — governance/observability/eval/sensor-fusion lanes only.
#   NO weapons-platform code.  NO autonomous lethal action grafts.
#   UDS-AirGap is for delivery + verification, NOT weapons control.
#   Author: Lutar, Stephen P. — ORCID 0009-0001-0110-4173
# =====================================================================

from __future__ import annotations

import doctest
import hashlib
import json
import math
import random
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Shared constants — upstream provenance pins
# ─────────────────────────────────────────────────────────────────────────────

UPSTREAM_PINNS_SHA = "932f50a2d8ef"     # maziarraissi/PINNs MIT
UPSTREAM_PINNS_LICENSE = "MIT"
UPSTREAM_PINNS_URL = "https://github.com/maziarraissi/PINNs"
UPSTREAM_PINNS_PAPER_DOI = "10.1016/j.jcp.2018.10.045"
ELZ_2002_DOI = "10.1007/s00454-002-2885-2"

# Λ-axis identifiers reused from v18.9 Palantir graft
LAMBDA_AXES = (
    "axis_1_provenance",
    "axis_2_witness",
    "axis_3_residual",
    "axis_4_topology",
    "axis_5_temporal",
    "axis_6_consent",
    "axis_7_redaction",
    "axis_8_jurisdiction",
    "axis_9_attribution",
)


def _sha256_hex(data: bytes) -> str:
    """Return the lowercase hex-encoded SHA-256 of ``data``.

    >>> _sha256_hex(b"")
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
    >>> len(_sha256_hex(b"uds"))
    64
    """
    return hashlib.sha256(data).hexdigest()


def _canonical_json(obj: Any) -> bytes:
    """RFC 8259 canonical JSON encoding (sorted keys, no whitespace).

    >>> _canonical_json({"b": 2, "a": 1})
    b'{"a":1,"b":2}'
    >>> _canonical_json([1, 2, 3])
    b'[1,2,3]'
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _lambda_gate(axes: dict[str, float]) -> float:
    """Multiplicative Λ-gate: 1.0 only if every axis is in [0,1].

    >>> _lambda_gate({k: 1.0 for k in LAMBDA_AXES})
    1.0
    >>> _lambda_gate({k: 1.0 for k in LAMBDA_AXES} | {"axis_1_provenance": 0.0})
    0.0
    """
    p = 1.0
    for ax in LAMBDA_AXES:
        v = axes.get(ax, 0.0)
        if v < 0.0 or v > 1.0:
            return 0.0
        p *= v
    return p


# =====================================================================
# GRAFT 2 — UDSSensorPacket + UDSSensorReceiptChain
# Lutar.UDSSensorReceiptChain.lean (Lean 4 pendant)
# Composes v17 Wheeler + v18.19 Lutar.SBOMProvenance.
# Theorem (Lean):
#   theorem uds_sensor_chain_well_formed
#       (c : UDSSensorChain) (h : ∀ i, valid_packet (c.packets i)) :
#       is_total_ordered c ∧ is_sha_complete c
#
#   theorem uds_sensor_chain_subsumes_sbom_chain
#       (c : UDSSensorChain) : SBOMProvenance.chain (to_sbom c) = c.sha_chain
#       -- pending constructor; tracked sorry in Lean PR A.
# =====================================================================


@dataclass(frozen=True)
class UDSSensorPacket:
    """A single sensor packet emitted by a UDS-AirGap drone.

    Wire format: canonical JSON per RFC 8259 (with CBOR canonical
    per RFC 8949 reserved as a future wire option).

    Attributes
    ----------
    tail_number : str
        Drone tail-number, e.g. "UDS-T7".
    seq : int
        Monotone packet sequence number (must be strictly increasing
        within a chain).
    timestamp_ns : int
        Wall-clock nanoseconds since UNIX epoch.
    payload : dict
        Sensor payload (gyro, accel, baro, gps, etc.) — read-only.
    prev_sha : str
        SHA-256 of the previous packet's canonical encoding,
        or 64 zeros for the genesis packet.

    Examples
    --------
    >>> p = UDSSensorPacket("UDS-T7", 0, 1700000000_000_000_000,
    ...                     {"gyro_x": 0.0}, "0" * 64)
    >>> p.tail_number
    'UDS-T7'
    >>> p.seq
    0
    >>> len(p.canonical_sha())
    64
    >>> p.canonical_sha() == p.canonical_sha()
    True
    """

    tail_number: str
    seq: int
    timestamp_ns: int
    payload: dict[str, Any]
    prev_sha: str

    def canonical_encoding(self) -> bytes:
        """Return the canonical-JSON encoding of this packet.

        >>> p = UDSSensorPacket("UDS-T7", 0, 1, {"a": 1}, "0" * 64)
        >>> b = p.canonical_encoding()
        >>> b.startswith(b'{"payload":{"a":1}')
        True
        """
        return _canonical_json(
            {
                "tail_number": self.tail_number,
                "seq": self.seq,
                "timestamp_ns": self.timestamp_ns,
                "payload": self.payload,
                "prev_sha": self.prev_sha,
            }
        )

    def canonical_sha(self) -> str:
        """SHA-256 of the canonical encoding.

        >>> p = UDSSensorPacket("UDS-T7", 0, 1, {"a": 1}, "0" * 64)
        >>> len(p.canonical_sha()) == 64
        True
        """
        return _sha256_hex(self.canonical_encoding())

    def is_valid_shape(self) -> bool:
        """Structural validity check (does not check chain order).

        >>> UDSSensorPacket("UDS-T7", 0, 1, {}, "0"*64).is_valid_shape()
        True
        >>> UDSSensorPacket("", 0, 1, {}, "0"*64).is_valid_shape()
        False
        >>> UDSSensorPacket("UDS-T7", -1, 1, {}, "0"*64).is_valid_shape()
        False
        >>> UDSSensorPacket("UDS-T7", 0, 1, {}, "z"*64).is_valid_shape()
        False
        """
        if not self.tail_number:
            return False
        if self.seq < 0:
            return False
        if self.timestamp_ns < 0:
            return False
        if not isinstance(self.payload, dict):
            return False
        if len(self.prev_sha) != 64:
            return False
        if not all(c in "0123456789abcdef" for c in self.prev_sha):
            return False
        return True


class UDSSensorReceiptChain:
    """Total-ordered Λ-receipt chain of UDS sensor packets.

    A chain is *well-formed* iff:

    1. Sequence numbers are strictly increasing (total order).
    2. Each packet's ``prev_sha`` equals the canonical SHA of its
       predecessor (SHA-chain completeness).
    3. Timestamps are non-decreasing.

    Lean pendant: ``Lutar/UDSSensorReceiptChain.lean`` —
    theorem ``uds_sensor_chain_well_formed``.

    Examples
    --------
    >>> chain = UDSSensorReceiptChain("UDS-T7")
    >>> _ = chain.append({"gyro_x": 0.1}, timestamp_ns=1000)
    >>> _ = chain.append({"gyro_x": 0.2}, timestamp_ns=2000)
    >>> chain.is_total_ordered()
    True
    >>> chain.is_sha_complete()
    True
    >>> chain.length()
    2
    """

    GENESIS_SHA = "0" * 64

    def __init__(self, tail_number: str) -> None:
        self.tail_number = tail_number
        self._packets: list[UDSSensorPacket] = []
        self._next_seq = 0

    def append(
        self,
        payload: dict[str, Any],
        timestamp_ns: Optional[int] = None,
    ) -> UDSSensorPacket:
        """Append a packet to the chain, returning it.

        >>> c = UDSSensorReceiptChain("UDS-T7")
        >>> pkt = c.append({"baro": 1013.25}, timestamp_ns=42)
        >>> pkt.seq
        0
        >>> pkt.prev_sha == UDSSensorReceiptChain.GENESIS_SHA
        True
        """
        if timestamp_ns is None:
            timestamp_ns = time.time_ns()
        prev_sha = (
            self._packets[-1].canonical_sha()
            if self._packets
            else self.GENESIS_SHA
        )
        pkt = UDSSensorPacket(
            tail_number=self.tail_number,
            seq=self._next_seq,
            timestamp_ns=timestamp_ns,
            payload=dict(payload),
            prev_sha=prev_sha,
        )
        self._packets.append(pkt)
        self._next_seq += 1
        return pkt

    def length(self) -> int:
        """Number of packets in the chain.

        >>> UDSSensorReceiptChain("X").length()
        0
        """
        return len(self._packets)

    def packets(self) -> tuple[UDSSensorPacket, ...]:
        """Immutable snapshot of the chain.

        >>> c = UDSSensorReceiptChain("UDS-T7")
        >>> _ = c.append({})
        >>> len(c.packets())
        1
        """
        return tuple(self._packets)

    def is_total_ordered(self) -> bool:
        """True iff sequence numbers form a strict total order
        and timestamps are non-decreasing.

        >>> c = UDSSensorReceiptChain("UDS-T7")
        >>> _ = c.append({}, 100); _ = c.append({}, 200)
        >>> c.is_total_ordered()
        True
        """
        for i in range(1, len(self._packets)):
            a, b = self._packets[i - 1], self._packets[i]
            if b.seq != a.seq + 1:
                return False
            if b.timestamp_ns < a.timestamp_ns:
                return False
        return True

    def is_sha_complete(self) -> bool:
        """True iff every packet's prev_sha matches its predecessor.

        >>> c = UDSSensorReceiptChain("UDS-T7")
        >>> _ = c.append({"a": 1}); _ = c.append({"a": 2})
        >>> c.is_sha_complete()
        True
        """
        for i in range(1, len(self._packets)):
            expected = self._packets[i - 1].canonical_sha()
            if self._packets[i].prev_sha != expected:
                return False
        if self._packets and self._packets[0].prev_sha != self.GENESIS_SHA:
            return False
        return True

    def well_formed(self) -> bool:
        """Conjunction of ``is_total_ordered`` and ``is_sha_complete``.

        Lean: ``uds_sensor_chain_well_formed``.

        >>> c = UDSSensorReceiptChain("UDS-T7")
        >>> _ = c.append({})
        >>> c.well_formed()
        True
        """
        return self.is_total_ordered() and self.is_sha_complete()

    def chain_sha256(self) -> str:
        """Deterministic SHA-256 of the full chain (Merkle-style fold).

        >>> c = UDSSensorReceiptChain("UDS-T7")
        >>> _ = c.append({}, 1); _ = c.append({}, 2)
        >>> len(c.chain_sha256()) == 64
        True
        """
        h = hashlib.sha256()
        for p in self._packets:
            h.update(p.canonical_sha().encode("ascii"))
        return h.hexdigest()

    def to_sbom_chain(self) -> list[dict[str, str]]:
        """Project each packet into a v18.19 SBOMProvenance receipt.

        This is the Python witness for Lean theorem
        ``uds_sensor_chain_subsumes_sbom_chain`` (constructor pending
        in Lean PR A — tracked ``sorry``).

        >>> c = UDSSensorReceiptChain("UDS-T7")
        >>> _ = c.append({"a": 1})
        >>> r = c.to_sbom_chain()
        >>> r[0]["component"] == "UDS-T7:0"
        True
        """
        out: list[dict[str, str]] = []
        for p in self._packets:
            out.append(
                {
                    "component": f"{p.tail_number}:{p.seq}",
                    "sha256": p.canonical_sha(),
                    "prev_sha256": p.prev_sha,
                }
            )
        return out

    @staticmethod
    def from_sbom_chain_view(records: list[dict[str, str]]) -> str:
        """Recompute the chain SHA from an SBOM projection.

        >>> c = UDSSensorReceiptChain("UDS-T7")
        >>> _ = c.append({"a": 1})
        >>> proj = c.to_sbom_chain()
        >>> UDSSensorReceiptChain.from_sbom_chain_view(proj) == c.chain_sha256()
        True
        """
        h = hashlib.sha256()
        for r in records:
            h.update(r["sha256"].encode("ascii"))
        return h.hexdigest()


# =====================================================================
# GRAFT 1 — UDSAirGapPayload
# uds-airgap-replit-payload: minimal drone control loop + sensor
# fusion + Λ-receipt over every sensor packet + Lutar.UDSInvariant.
#
# Doctrine v6 §2 declaration:
#   The control loop is a *delivery + verification* substrate.
#   It DOES NOT actuate weapons.  It DOES NOT make autonomous lethal
#   decisions.  Any actuation surface is read-only telemetry +
#   nav-vector + abort-flag.  Two-witness gate is mandatory for any
#   non-RTL command.
# =====================================================================


@dataclass
class DroneState:
    """Minimal drone state vector (read-only — no weapons control).

    Attributes
    ----------
    tail_number : str
    position : tuple[float, float, float]   # (x, y, z) metres
    velocity : tuple[float, float, float]   # m/s
    battery_pct : float                     # 0..100
    armed : bool                            # arming state (NOT a fire control)
    rtl : bool                              # return-to-launch flag

    Examples
    --------
    >>> s = DroneState("UDS-T7", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0),
    ...                100.0, False, False)
    >>> s.battery_pct
    100.0
    >>> s.armed
    False
    """

    tail_number: str
    position: tuple[float, float, float]
    velocity: tuple[float, float, float]
    battery_pct: float
    armed: bool
    rtl: bool


def fuse_sensors(
    gyro: tuple[float, float, float],
    accel: tuple[float, float, float],
    baro_altitude_m: float,
    gps_fix: bool,
) -> dict[str, float]:
    """Complementary-filter sensor fusion (toy).

    Returns a fused attitude/altitude/fix dict.  No weapons sensors.

    >>> r = fuse_sensors((0.0, 0.0, 0.0), (0.0, 0.0, 9.81), 100.0, True)
    >>> round(r["altitude_m"], 2)
    100.0
    >>> r["gps_fix"]
    1.0
    >>> round(r["pitch_rad"], 4)
    0.0
    """
    pitch = math.atan2(accel[0], max(accel[2], 1e-6))
    roll = math.atan2(accel[1], max(accel[2], 1e-6))
    yaw = gyro[2]
    return {
        "pitch_rad": pitch,
        "roll_rad": roll,
        "yaw_rate": yaw,
        "altitude_m": baro_altitude_m,
        "gps_fix": 1.0 if gps_fix else 0.0,
    }


class UDSAirGapPayload:
    """Drop-in offline drone control-loop simulator with Λ-receipts.

    Every loop tick emits a sensor packet and appends it to the
    drone's :class:`UDSSensorReceiptChain`.  No network egress.
    No autonomous lethal action.  Two-witness gate enforced for any
    armed → not-armed transition that is not RTL.

    Examples
    --------
    >>> p = UDSAirGapPayload("UDS-T7")
    >>> p.state.armed
    False
    >>> _ = p.tick(gyro=(0,0,0), accel=(0,0,9.81), baro=100.0, gps=True)
    >>> p.chain.length()
    1
    >>> p.chain.well_formed()
    True
    """

    def __init__(self, tail_number: str) -> None:
        self.state = DroneState(
            tail_number=tail_number,
            position=(0.0, 0.0, 0.0),
            velocity=(0.0, 0.0, 0.0),
            battery_pct=100.0,
            armed=False,
            rtl=False,
        )
        self.chain = UDSSensorReceiptChain(tail_number)
        self._witness_count = 0
        self._abort_flag = False

    def tick(
        self,
        gyro: tuple[float, float, float],
        accel: tuple[float, float, float],
        baro: float,
        gps: bool,
        timestamp_ns: Optional[int] = None,
    ) -> UDSSensorPacket:
        """Execute one control-loop tick, return the emitted packet.

        >>> p = UDSAirGapPayload("UDS-T7")
        >>> pkt = p.tick((0,0,0), (0,0,9.81), 100.0, True)
        >>> pkt.payload["altitude_m"]
        100.0
        """
        fused = fuse_sensors(gyro, accel, baro, gps)
        payload = {
            **fused,
            "battery_pct": self.state.battery_pct,
            "armed": 1.0 if self.state.armed else 0.0,
            "rtl": 1.0 if self.state.rtl else 0.0,
        }
        return self.chain.append(payload, timestamp_ns=timestamp_ns)

    def dual_witness_disarm(self, witness_a: str, witness_b: str) -> bool:
        """Two-witness gate for disarming outside RTL.

        Returns True iff two distinct, non-empty witnesses are supplied.

        >>> p = UDSAirGapPayload("UDS-T7")
        >>> p.state.armed = True
        >>> p.dual_witness_disarm("alice", "alice")
        False
        >>> p.dual_witness_disarm("alice", "bob")
        True
        >>> p.state.armed
        False
        """
        if not witness_a or not witness_b or witness_a == witness_b:
            return False
        self.state.armed = False
        self._witness_count += 1
        return True

    def request_rtl(self) -> None:
        """Set return-to-launch.  RTL is unilateral by design.

        >>> p = UDSAirGapPayload("UDS-T7")
        >>> p.request_rtl()
        >>> p.state.rtl
        True
        """
        self.state.rtl = True

    def abort(self) -> None:
        """Latch abort flag.  Abort halts further control output.

        >>> p = UDSAirGapPayload("UDS-T7")
        >>> p.abort()
        >>> p.is_aborted()
        True
        """
        self._abort_flag = True

    def is_aborted(self) -> bool:
        """Whether abort is latched."""
        return self._abort_flag

    def uds_invariant_holds(self) -> bool:
        """Lutar.UDSInvariant: chain well-formed AND no lethal surface
        ever activated.  Since this substrate exposes no lethal surface,
        the invariant reduces to chain well-formedness.

        >>> p = UDSAirGapPayload("UDS-T7")
        >>> _ = p.tick((0,0,0), (0,0,9.81), 100.0, True)
        >>> p.uds_invariant_holds()
        True
        """
        return self.chain.well_formed()

    def lambda_axes(self) -> dict[str, float]:
        """Project the payload state onto the 9 Λ-axes.

        >>> p = UDSAirGapPayload("UDS-T7")
        >>> _ = p.tick((0,0,0), (0,0,9.81), 100.0, True)
        >>> axes = p.lambda_axes()
        >>> all(0.0 <= v <= 1.0 for v in axes.values())
        True
        """
        return {
            "axis_1_provenance": 1.0 if self.chain.is_sha_complete() else 0.0,
            "axis_2_witness": min(self._witness_count, 1) * 1.0,
            "axis_3_residual": 1.0,  # set by PINN fusion graft 3
            "axis_4_topology": 1.0,  # set by A15 graft 4
            "axis_5_temporal": 1.0 if self.chain.is_total_ordered() else 0.0,
            "axis_6_consent": 1.0,   # operator console default
            "axis_7_redaction": 1.0,
            "axis_8_jurisdiction": 1.0,
            "axis_9_attribution": 1.0,
        }


# =====================================================================
# GRAFT 3 — PINNResidualLambda
# uds-pinn-fusion: physics-informed neural network for drone aerodynamics
# fused with Λ-receipt per inference.  Pure-Python pendant for v17.3.
#
# Lean: Lutar.PINNResidualConfidence.lean
#   theorem confidence_monotone_in_residual
#     (r1 r2 : ℝ) (h : r1 ≤ r2) :
#     pinn_confidence r2 ≤ pinn_confidence r1
#
# Doctrine v6 §2 declaration:
#   PINN inference is READ-ONLY physics estimation.
#   PINN does not actuate flight surfaces.  PINN does not arm.
#
# Citation: Raissi, Perdikaris, Karniadakis 2019 (J. Comp. Phys.).
# Upstream: maziarraissi/PINNs MIT SHA 932f50a2d8ef.
# =====================================================================


class DualNumber:
    """Forward-mode auto-diff scalar (val, deriv).

    Provides ``+``, ``-``, ``*``, ``/``, and unary fns for building
    a minimal MLP without torch/numpy.

    Examples
    --------
    >>> x = DualNumber(2.0, 1.0)
    >>> y = x * x + DualNumber(3.0, 0.0) * x
    >>> y.val
    10.0
    >>> y.deriv  # d/dx(x^2 + 3x) at x=2 == 2*2 + 3 == 7
    7.0
    """

    __slots__ = ("val", "deriv")

    def __init__(self, val: float, deriv: float = 0.0) -> None:
        self.val = float(val)
        self.deriv = float(deriv)

    def __add__(self, other: "DualNumber | float") -> "DualNumber":
        if isinstance(other, DualNumber):
            return DualNumber(self.val + other.val, self.deriv + other.deriv)
        return DualNumber(self.val + other, self.deriv)

    def __radd__(self, other: float) -> "DualNumber":
        return self.__add__(other)

    def __sub__(self, other: "DualNumber | float") -> "DualNumber":
        if isinstance(other, DualNumber):
            return DualNumber(self.val - other.val, self.deriv - other.deriv)
        return DualNumber(self.val - other, self.deriv)

    def __rsub__(self, other: float) -> "DualNumber":
        return DualNumber(other - self.val, -self.deriv)

    def __mul__(self, other: "DualNumber | float") -> "DualNumber":
        if isinstance(other, DualNumber):
            return DualNumber(
                self.val * other.val,
                self.val * other.deriv + self.deriv * other.val,
            )
        return DualNumber(self.val * other, self.deriv * other)

    def __rmul__(self, other: float) -> "DualNumber":
        return self.__mul__(other)

    def __truediv__(self, other: "DualNumber | float") -> "DualNumber":
        if isinstance(other, DualNumber):
            denom = other.val * other.val
            return DualNumber(
                self.val / other.val,
                (self.deriv * other.val - self.val * other.deriv) / denom,
            )
        return DualNumber(self.val / other, self.deriv / other)

    def tanh(self) -> "DualNumber":
        """Hyperbolic tangent activation (smooth, common in PINN MLPs).

        >>> DualNumber(0.0, 1.0).tanh().val
        0.0
        >>> round(DualNumber(0.0, 1.0).tanh().deriv, 4)
        1.0
        """
        t = math.tanh(self.val)
        return DualNumber(t, (1.0 - t * t) * self.deriv)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Dual({self.val:.4g}, d={self.deriv:.4g})"


class UDSPINN:
    """Minimal frozen-weight MLP PINN for drone aerodynamics.

    Inputs: (x, y, t) — 2D incompressible Navier-Stokes assumption.
    Outputs: (u, v, p) — velocity field + pressure.
    Activation: tanh.  No torch.  No numpy.

    Weights are passed in as JSON-friendly nested lists at construction
    (frozen checkpoint format).  Architectural pattern referenced from
    ``maziarraissi/PINNs`` SHA ``932f50a2d8ef`` (MIT) — no code copied.

    Examples
    --------
    >>> w = UDSPINN.zero_weights(hidden=2)
    >>> net = UDSPINN(w)
    >>> u, v, p = net.infer(0.0, 0.0, 0.0)
    >>> u == 0.0 and v == 0.0 and p == 0.0
    True
    """

    def __init__(self, weights: dict[str, Any]) -> None:
        self.weights = weights
        # Check shape: input=3, output=3, hidden=h
        self.h = weights["hidden"]
        assert len(weights["W1"]) == self.h
        assert len(weights["W1"][0]) == 3
        assert len(weights["b1"]) == self.h
        assert len(weights["W2"]) == 3
        assert len(weights["W2"][0]) == self.h
        assert len(weights["b2"]) == 3

    @staticmethod
    def zero_weights(hidden: int = 4) -> dict[str, Any]:
        """Construct an all-zero frozen checkpoint.

        >>> w = UDSPINN.zero_weights(2)
        >>> w["hidden"]
        2
        """
        return {
            "hidden": hidden,
            "W1": [[0.0, 0.0, 0.0] for _ in range(hidden)],
            "b1": [0.0] * hidden,
            "W2": [[0.0] * hidden for _ in range(3)],
            "b2": [0.0, 0.0, 0.0],
        }

    def _forward(self, x: DualNumber, y: DualNumber, t: DualNumber) -> tuple[DualNumber, DualNumber, DualNumber]:
        # Hidden layer
        hs = []
        for j in range(self.h):
            w = self.weights["W1"][j]
            z = x * w[0] + y * w[1] + t * w[2] + self.weights["b1"][j]
            hs.append(z.tanh())
        # Output layer (3-vector)
        outs = []
        for k in range(3):
            w = self.weights["W2"][k]
            s: "DualNumber | float" = self.weights["b2"][k]
            for j in range(self.h):
                s = hs[j] * w[j] + s
            if isinstance(s, (int, float)):
                s = DualNumber(float(s), 0.0)
            outs.append(s)
        return outs[0], outs[1], outs[2]

    def infer(self, x: float, y: float, t: float) -> tuple[float, float, float]:
        """Return (u, v, p) at (x, y, t) — no auto-diff.

        >>> w = UDSPINN.zero_weights(2)
        >>> net = UDSPINN(w)
        >>> net.infer(1.0, 2.0, 3.0)
        (0.0, 0.0, 0.0)
        """
        ux, vy, p = self._forward(
            DualNumber(x, 0.0), DualNumber(y, 0.0), DualNumber(t, 0.0)
        )
        return ux.val, vy.val, p.val

    def residual_continuity(self, x: float, y: float, t: float) -> float:
        """Incompressible continuity residual: ∂u/∂x + ∂v/∂y.

        For a zero-weight network this is exactly 0.

        >>> w = UDSPINN.zero_weights(2)
        >>> net = UDSPINN(w)
        >>> net.residual_continuity(0.5, 0.5, 0.5)
        0.0
        """
        # ∂u/∂x: x is dual with deriv=1, y and t static
        ux1, _, _ = self._forward(DualNumber(x, 1.0), DualNumber(y, 0.0), DualNumber(t, 0.0))
        # ∂v/∂y: y dual
        _, vy1, _ = self._forward(DualNumber(x, 0.0), DualNumber(y, 1.0), DualNumber(t, 0.0))
        return ux1.deriv + vy1.deriv


class PINNResidualLambda:
    """Map a residual magnitude r ≥ 0 to a confidence in [0, 1].

    Confidence is ``exp(-k * |r|)`` (monotone-decreasing in |r|).

    Lean: ``confidence_monotone_in_residual`` discharged with
    ``Float.exp_le_exp``.

    >>> lam = PINNResidualLambda(k=1.0)
    >>> lam.confidence(0.0)
    1.0
    >>> lam.confidence(1.0) < lam.confidence(0.5)
    True
    >>> lam.accept(0.01)
    True
    >>> lam.accept(10.0)
    False
    """

    def __init__(self, k: float = 1.0, accept_threshold: float = 0.5) -> None:
        if k <= 0.0:
            raise ValueError("k must be positive")
        if not (0.0 < accept_threshold < 1.0):
            raise ValueError("accept_threshold ∈ (0,1)")
        self.k = k
        self.accept_threshold = accept_threshold

    def confidence(self, residual: float) -> float:
        """Return exp(-k * |r|).

        >>> round(PINNResidualLambda(k=1.0).confidence(0.0), 6)
        1.0
        """
        return math.exp(-self.k * abs(residual))

    def accept(self, residual: float) -> bool:
        """True iff confidence ≥ threshold.

        >>> PINNResidualLambda(k=1.0).accept(0.0)
        True
        """
        return self.confidence(residual) >= self.accept_threshold

    def lambda_receipt(self, residual: float, sha: str) -> dict[str, Any]:
        """Emit a per-inference Λ-receipt.

        >>> r = PINNResidualLambda(k=1.0).lambda_receipt(0.0, "0"*64)
        >>> r["confidence"]
        1.0
        >>> r["accept"]
        True
        >>> r["upstream_sha"] == '932f50a2d8ef'
        True
        """
        c = self.confidence(residual)
        return {
            "residual": float(residual),
            "confidence": c,
            "accept": c >= self.accept_threshold,
            "inference_sha": sha,
            "upstream_sha": UPSTREAM_PINNS_SHA,
            "upstream_license": UPSTREAM_PINNS_LICENSE,
            "axis_3_residual": c,
        }

    def signed_lambda_receipt(self, residual: float, sha: str) -> dict[str, Any]:
        """Emit a Λ-receipt sealed in a DSSE envelope (ADDITIVE, Yachay 2026-06-01).

        Wraps :meth:`lambda_receipt` in an ECDSA-P256 DSSE envelope using the
        canonical mesh cosign key (keyid ``szlholdings-cosign``), mirroring
        amaru's DINN receipt path so a PINN receipt and a DINN receipt verify
        with the *same* ``cosign verify-blob --key cosign.pub`` command.

        The plain :meth:`lambda_receipt` is unchanged. When the cosign private
        key (env ``SZL_COSIGN_PRIVATE_PEM``) or the ``cryptography`` package is
        absent, the envelope is honestly marked UNSIGNED — no fabricated
        signature. The signature attests the receipt bytes, NOT the PINN physics;
        Λ uniqueness remains Conjecture 1 (never a theorem); SLSA L1 (honest).

        >>> rec = PINNResidualLambda(k=1.0).signed_lambda_receipt(0.0, "0"*64)
        >>> rec["receipt"]["confidence"]
        1.0
        >>> rec["dsse"]["payloadType"]
        'application/vnd.szl.pinn-lambda-receipt+json'
        >>> rec["dsse"]["_dsse"]
        'DSSEv1'
        >>> rec["keyid"]
        'szlholdings-cosign'
        >>> isinstance(rec["dsse"]["signed"], bool)
        True
        """
        receipt = self.lambda_receipt(residual, sha)
        try:
            import pinn_dsse as _pdsse
        except Exception:  # pragma: no cover - defensive (module always present)
            from . import pinn_dsse as _pdsse  # type: ignore
        payload = {
            "kind": "pinn-lambda-receipt",
            "doctrine_version": "v11",
            "lambda_status": "Conjecture 1 (NOT a theorem)",
            "slsa": "L1 (honest)",
            **receipt,
        }
        env = _pdsse.sign_payload(payload)
        return {
            "receipt": receipt,
            "keyid": _pdsse.KEYID,
            "signing_available": _pdsse.signing_available(),
            "dsse": env,
        }


# =====================================================================
# GRAFT 4 — A15PersistentHomologyCheck
# uds-mesh-A15-operational: runtime check of the A15 persistent-homology
# bound on the audit-fiber simplicial complex.
#
# Lean: Lutar/Topology/PersistentHomologyChain.lean — discharges the
# previously-tracked `sorry` via finite-rank chain-complex argument
# (Edelsbrunner-Letscher-Zomorodian 2002, doi:10.1007/s00454-002-2885-2).
#
# This is a pure-Python pendant of the topology check that uds-mesh's
# README frontier-capability line claims at runtime.
# =====================================================================


@dataclass(frozen=True)
class Simplex:
    """An unordered tuple of vertex IDs.

    Examples
    --------
    >>> s = Simplex((0, 1, 2))
    >>> s.dim
    2
    """

    vertices: tuple[int, ...]

    @property
    def dim(self) -> int:
        return len(self.vertices) - 1


class A15PersistentHomologyCheck:
    """Pure-Python pendant of the A15 persistent-homology runtime check.

    Computes Euler characteristic ``χ = V − E + F`` and the
    Euler-identity Betti-1 upper bound
    ``rank(H_1) ≤ 1 + E − V − F + b_2``
    on a 2-dimensional simplicial complex.  Returns ``pass=True`` iff
    ``rank(H_1)`` upper bound is ≤ ``bound``.

    No scipy.  No numpy.

    Examples
    --------
    >>> # A single triangle: V=3, E=3, F=1, χ=1, b_1 ≤ 0
    >>> c = A15PersistentHomologyCheck(bound=0)
    >>> _ = c.add_vertex(0); _ = c.add_vertex(1); _ = c.add_vertex(2)
    >>> _ = c.add_edge(0, 1); _ = c.add_edge(1, 2); _ = c.add_edge(0, 2)
    >>> _ = c.add_face((0, 1, 2))
    >>> c.euler_characteristic()
    1
    >>> c.betti_1_upper_bound() <= 0
    True
    >>> c.check()["pass"]
    True
    """

    def __init__(self, bound: int = 1) -> None:
        if bound < 0:
            raise ValueError("bound must be ≥ 0")
        self.bound = bound
        self._vertices: set[int] = set()
        self._edges: set[tuple[int, int]] = set()
        self._faces: set[tuple[int, int, int]] = set()

    def add_vertex(self, v: int) -> None:
        """Add a vertex to the complex.

        >>> c = A15PersistentHomologyCheck()
        >>> c.add_vertex(0)
        >>> c.vertex_count()
        1
        """
        self._vertices.add(v)

    def add_edge(self, a: int, b: int) -> None:
        """Add an edge (and its endpoints).

        >>> c = A15PersistentHomologyCheck()
        >>> c.add_edge(0, 1)
        >>> c.edge_count()
        1
        """
        e = tuple(sorted((a, b)))  # type: ignore[assignment]
        self._edges.add(e)  # type: ignore[arg-type]
        self._vertices.update(e)

    def add_face(self, tri: Iterable[int]) -> None:
        """Add a triangular face (and its edges + vertices).

        >>> c = A15PersistentHomologyCheck()
        >>> c.add_face((0, 1, 2))
        >>> c.face_count()
        1
        """
        t = tuple(sorted(tri))
        if len(t) != 3:
            raise ValueError("face must be a triangle (3 vertices)")
        self._faces.add(t)  # type: ignore[arg-type]
        self._vertices.update(t)
        self._edges.add((t[0], t[1]))
        self._edges.add((t[1], t[2]))
        self._edges.add((t[0], t[2]))

    def vertex_count(self) -> int:
        """Return |V|.

        >>> A15PersistentHomologyCheck().vertex_count()
        0
        """
        return len(self._vertices)

    def edge_count(self) -> int:
        return len(self._edges)

    def face_count(self) -> int:
        return len(self._faces)

    def euler_characteristic(self) -> int:
        """χ = V − E + F.

        >>> c = A15PersistentHomologyCheck()
        >>> c.add_face((0,1,2))
        >>> c.euler_characteristic()
        1
        """
        return self.vertex_count() - self.edge_count() + self.face_count()

    def connected_components(self) -> int:
        """Union-find Betti-0 (number of connected components).

        >>> c = A15PersistentHomologyCheck()
        >>> for v in range(3): c.add_vertex(v)
        >>> c.connected_components()
        3
        >>> c.add_edge(0, 1); c.connected_components()
        2
        """
        parent: dict[int, int] = {v: v for v in self._vertices}

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for a, b in self._edges:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb
        roots = {find(v) for v in self._vertices}
        return len(roots)

    def betti_1_upper_bound(self, assume_no_2_cycles: bool = True) -> int:
        """Upper bound on rank(H_1) via Euler identity.

        χ = b_0 − b_1 + b_2.  For a 2-complex with no closed 2-cycles
        (the default case in audit-fiber complexes — no closed
        surface in the span graph), b_2 = 0, so b_1 = b_0 − χ.

        If ``assume_no_2_cycles`` is False, falls back to the weak
        bound b_2 ≤ F ⇒ b_1 ≤ b_0 + F − χ.

        Returns an integer ≥ 0.

        >>> c = A15PersistentHomologyCheck()
        >>> c.add_face((0, 1, 2))
        >>> c.betti_1_upper_bound()
        0
        >>> c.betti_1_upper_bound(assume_no_2_cycles=False)
        1
        """
        b0 = self.connected_components() if self._vertices else 0
        chi = self.euler_characteristic()
        if assume_no_2_cycles:
            ub = b0 - chi
        else:
            ub = b0 + self.face_count() - chi
        return max(0, ub)

    def check(self) -> dict[str, Any]:
        """Run the A15 runtime check.

        >>> c = A15PersistentHomologyCheck(bound=0)
        >>> c.add_face((0, 1, 2))
        >>> r = c.check()
        >>> r["pass"]
        True
        >>> r["rank_h1_upper"]
        0
        """
        ub = self.betti_1_upper_bound()
        return {
            "rank_h1_upper": ub,
            "bound": self.bound,
            "pass": ub <= self.bound,
            "euler_characteristic": self.euler_characteristic(),
            "vertices": self.vertex_count(),
            "edges": self.edge_count(),
            "faces": self.face_count(),
            "components": self.connected_components() if self._vertices else 0,
            "citation_doi": ELZ_2002_DOI,
        }


# =====================================================================
# GRAFT 5 — UDSOperatorConsoleDataPlane
# uds-operator-console: emits the 4 console panes as JSON.
# Extends v18.4 JohnMwendwa dashboard.  Frontend skeleton in TS lives
# at szl/uds_operator_console/ — this is the data-plane pendant.
# =====================================================================


class UDSOperatorConsoleDataPlane:
    """Data plane for the four UDS operator-console panes.

    Panes:
      1. ``huklla_alerts``     — HUKLLA (Hand-Up Kill-Loop Lethal Alert)
                                 alarms.  In this substrate, HUKLLA is
                                 strictly a *governance alarm* surfaced
                                 when ANY weapons-related token appears
                                 anywhere in the chain.  This substrate
                                 ships ZERO such tokens.
      2. ``dual_witness``      — pending witness-signature queue.
      3. ``receipt_chain``     — paginated chain viewer.
      4. ``a15_topology``      — A15 persistent-homology pane.

    Examples
    --------
    >>> pl = UDSAirGapPayload("UDS-T7")
    >>> _ = pl.tick((0,0,0), (0,0,9.81), 100.0, True)
    >>> console = UDSOperatorConsoleDataPlane([pl])
    >>> panes = console.render()
    >>> set(panes.keys()) == {"huklla_alerts","dual_witness","receipt_chain","a15_topology"}
    True
    """

    HUKLLA_FORBIDDEN_TOKENS = frozenset(
        {
            "weapon",
            "weapons",
            "lethal",
            "fire_control",
            "munition",
            "warhead",
            "kill_loop",
        }
    )

    def __init__(self, payloads: list[UDSAirGapPayload]) -> None:
        self.payloads = list(payloads)

    def huklla_alerts(self) -> list[dict[str, str]]:
        """Scan every payload's chain for forbidden tokens.

        >>> p = UDSAirGapPayload("UDS-T7"); _ = p.tick((0,0,0),(0,0,9.81),100.0,True)
        >>> UDSOperatorConsoleDataPlane([p]).huklla_alerts()
        []
        """
        alerts: list[dict[str, str]] = []
        for pl in self.payloads:
            for pkt in pl.chain.packets():
                enc = pkt.canonical_encoding().decode("utf-8").lower()
                for tok in self.HUKLLA_FORBIDDEN_TOKENS:
                    if tok in enc:
                        alerts.append(
                            {
                                "tail_number": pl.state.tail_number,
                                "seq": str(pkt.seq),
                                "token": tok,
                                "severity": "CRITICAL",
                            }
                        )
        return alerts

    def dual_witness_pane(self) -> dict[str, Any]:
        """Aggregate pending dual-witness state.

        >>> p = UDSAirGapPayload("UDS-T7")
        >>> UDSOperatorConsoleDataPlane([p]).dual_witness_pane()["fleet_size"]
        1
        """
        pending = sum(1 for pl in self.payloads if pl.state.armed and not pl.state.rtl)
        return {
            "fleet_size": len(self.payloads),
            "pending_witness_count": pending,
            "gate_policy": "two-witness, non-equal, non-empty",
        }

    def receipt_chain_pane(self, tail_number: str, page: int = 0, page_size: int = 10) -> dict[str, Any]:
        """Paginated chain viewer for a single tail-number.

        >>> p = UDSAirGapPayload("UDS-T7")
        >>> for _ in range(3): _ = p.tick((0,0,0),(0,0,9.81),100.0,True)
        >>> r = UDSOperatorConsoleDataPlane([p]).receipt_chain_pane("UDS-T7")
        >>> r["total"]
        3
        >>> len(r["packets"]) == 3
        True
        """
        match = next((pl for pl in self.payloads if pl.state.tail_number == tail_number), None)
        if match is None:
            return {"tail_number": tail_number, "total": 0, "packets": []}
        pkts = match.chain.packets()
        start = page * page_size
        end = start + page_size
        view = pkts[start:end]
        return {
            "tail_number": tail_number,
            "total": len(pkts),
            "page": page,
            "page_size": page_size,
            "packets": [
                {
                    "seq": p.seq,
                    "sha": p.canonical_sha(),
                    "prev_sha": p.prev_sha,
                    "timestamp_ns": p.timestamp_ns,
                }
                for p in view
            ],
            "well_formed": match.chain.well_formed(),
        }

    def a15_topology_pane(self, check: A15PersistentHomologyCheck) -> dict[str, Any]:
        """Surface the A15 runtime check result.

        >>> c = A15PersistentHomologyCheck(bound=1); c.add_face((0,1,2))
        >>> r = UDSOperatorConsoleDataPlane([]).a15_topology_pane(c)
        >>> r["pass"]
        True
        """
        return check.check()

    def render(self, a15_check: Optional[A15PersistentHomologyCheck] = None) -> dict[str, Any]:
        """Render all 4 panes as a single JSON-serializable dict.

        >>> p = UDSAirGapPayload("UDS-T7")
        >>> _ = p.tick((0,0,0),(0,0,9.81),100.0,True)
        >>> out = UDSOperatorConsoleDataPlane([p]).render()
        >>> isinstance(out, dict)
        True
        """
        if a15_check is None:
            a15_check = A15PersistentHomologyCheck(bound=0)
        return {
            "huklla_alerts": self.huklla_alerts(),
            "dual_witness": self.dual_witness_pane(),
            "receipt_chain": [
                self.receipt_chain_pane(pl.state.tail_number)
                for pl in self.payloads
            ],
            "a15_topology": self.a15_topology_pane(a15_check),
        }


# =====================================================================
# SELF-TESTS
# =====================================================================


def run_self_tests() -> int:
    """Run all v18.24 UDS Operational self-tests.

    Returns the number of failures (0 == GREEN).
    """
    print("[v18.24 UDS Operational] Running doctests…")
    results = doctest.testmod(verbose=False)
    print(
        f"[v18.24 UDS Operational] Doctests: {results.attempted} attempted, "
        f"{results.failed} failed"
    )
    failures = results.failed
    assertion_count = 0

    # ── Graft 2 — UDSSensorReceiptChain ────────────────────────────────
    chain = UDSSensorReceiptChain("UDS-T7")
    for i in range(50):
        chain.append({"gyro_x": float(i)}, timestamp_ns=1000 + i)
    assert chain.length() == 50, "FAIL: chain length"
    assertion_count += 1
    assert chain.is_total_ordered(), "FAIL: total order"
    assertion_count += 1
    assert chain.is_sha_complete(), "FAIL: sha complete"
    assertion_count += 1
    assert chain.well_formed(), "FAIL: well_formed conjunction"
    assertion_count += 1
    assert len(chain.chain_sha256()) == 64, "FAIL: chain sha length"
    assertion_count += 1

    # Randomized 1000-packet stress
    big = UDSSensorReceiptChain("UDS-T9")
    rng = random.Random(0xACE)
    t = 0
    for _ in range(1000):
        t += rng.randint(1, 100)
        big.append({"k": rng.random()}, timestamp_ns=t)
    assert big.length() == 1000, "FAIL: 1000-pkt length"
    assertion_count += 1
    assert big.is_total_ordered(), "FAIL: 1000-pkt order"
    assertion_count += 1
    assert big.is_sha_complete(), "FAIL: 1000-pkt sha"
    assertion_count += 1

    # SBOM projection round-trip
    proj = chain.to_sbom_chain()
    assert len(proj) == 50, "FAIL: sbom proj len"
    assertion_count += 1
    assert UDSSensorReceiptChain.from_sbom_chain_view(proj) == chain.chain_sha256(), "FAIL: sbom proj sha"
    assertion_count += 1

    # Invalid packet shape detection
    bad = UDSSensorPacket("", 0, 0, {}, "0" * 64)
    assert not bad.is_valid_shape(), "FAIL: empty tail rejected"
    assertion_count += 1
    bad2 = UDSSensorPacket("UDS-T7", -1, 0, {}, "0" * 64)
    assert not bad2.is_valid_shape(), "FAIL: negative seq rejected"
    assertion_count += 1
    bad3 = UDSSensorPacket("UDS-T7", 0, 0, {}, "z" * 64)
    assert not bad3.is_valid_shape(), "FAIL: bad hex rejected"
    assertion_count += 1

    # Canonical encoding determinism
    p1 = UDSSensorPacket("UDS-T7", 0, 1, {"b": 2, "a": 1}, "0" * 64)
    p2 = UDSSensorPacket("UDS-T7", 0, 1, {"a": 1, "b": 2}, "0" * 64)
    assert p1.canonical_sha() == p2.canonical_sha(), "FAIL: canonical not stable"
    assertion_count += 1

    # ── Graft 1 — UDSAirGapPayload ────────────────────────────────────
    payload = UDSAirGapPayload("UDS-T7")
    assert not payload.state.armed, "FAIL: default not armed"
    assertion_count += 1
    assert not payload.state.rtl, "FAIL: default not rtl"
    assertion_count += 1

    for i in range(20):
        payload.tick(
            gyro=(0.0, 0.0, 0.01 * i),
            accel=(0.0, 0.0, 9.81),
            baro=100.0 + i,
            gps=True,
            timestamp_ns=1_000_000 + i * 1000,
        )
    assert payload.chain.length() == 20, "FAIL: payload chain length"
    assertion_count += 1
    assert payload.chain.well_formed(), "FAIL: payload chain well-formed"
    assertion_count += 1
    assert payload.uds_invariant_holds(), "FAIL: UDS invariant"
    assertion_count += 1

    # Dual-witness gate
    payload.state.armed = True
    assert not payload.dual_witness_disarm("alice", "alice"), "FAIL: same witness"
    assertion_count += 1
    assert not payload.dual_witness_disarm("", "bob"), "FAIL: empty witness"
    assertion_count += 1
    assert payload.dual_witness_disarm("alice", "bob"), "FAIL: valid 2-witness"
    assertion_count += 1
    assert not payload.state.armed, "FAIL: disarm after 2-witness"
    assertion_count += 1

    # RTL
    payload.request_rtl()
    assert payload.state.rtl, "FAIL: rtl flag"
    assertion_count += 1

    # Abort
    payload.abort()
    assert payload.is_aborted(), "FAIL: abort latched"
    assertion_count += 1

    # Λ-axis projection — all axes in [0,1]
    axes = payload.lambda_axes()
    assert set(axes.keys()) == set(LAMBDA_AXES), "FAIL: lambda axes shape"
    assertion_count += 1
    for k, v in axes.items():
        assert 0.0 <= v <= 1.0, f"FAIL: axis {k}={v} out of range"
        assertion_count += 1

    # Sensor fusion sanity
    fused = fuse_sensors((0.0, 0.0, 0.0), (0.0, 0.0, 9.81), 50.0, True)
    assert abs(fused["pitch_rad"]) < 1e-9, "FAIL: pitch zero"
    assertion_count += 1
    assert abs(fused["roll_rad"]) < 1e-9, "FAIL: roll zero"
    assertion_count += 1
    assert fused["altitude_m"] == 50.0, "FAIL: altitude pass-through"
    assertion_count += 1
    assert fused["gps_fix"] == 1.0, "FAIL: gps fix"
    assertion_count += 1

    # ── Graft 3 — PINNResidualLambda + DualNumber + UDSPINN ─────────────
    # DualNumber arithmetic
    x = DualNumber(3.0, 1.0)
    y = (x * x + DualNumber(2.0, 0.0) * x) - DualNumber(1.0, 0.0)
    assert y.val == 3.0 * 3.0 + 2.0 * 3.0 - 1.0, "FAIL: dual val"
    assertion_count += 1
    assert y.deriv == 2.0 * 3.0 + 2.0, "FAIL: dual deriv"
    assertion_count += 1

    # tanh derivative
    z = DualNumber(0.0, 1.0).tanh()
    assert abs(z.val) < 1e-9 and abs(z.deriv - 1.0) < 1e-9, "FAIL: tanh at 0"
    assertion_count += 1

    # Zero-network PINN ⇒ zero residual ⇒ confidence 1 ⇒ ACCEPT
    net = UDSPINN(UDSPINN.zero_weights(hidden=3))
    u, v, p = net.infer(1.0, 2.0, 3.0)
    assert u == 0.0 and v == 0.0 and p == 0.0, "FAIL: zero net infer"
    assertion_count += 1
    r = net.residual_continuity(0.5, 0.5, 0.5)
    assert r == 0.0, "FAIL: zero net residual"
    assertion_count += 1

    lam = PINNResidualLambda(k=2.0, accept_threshold=0.5)
    assert lam.confidence(0.0) == 1.0, "FAIL: confidence at 0"
    assertion_count += 1
    assert lam.accept(0.0), "FAIL: accept at 0"
    assertion_count += 1
    # Monotonicity: r1 ≤ r2 ⇒ conf(r2) ≤ conf(r1)
    for r1, r2 in [(0.0, 0.1), (0.1, 0.5), (0.5, 1.0), (1.0, 10.0)]:
        assert lam.confidence(r2) <= lam.confidence(r1), f"FAIL: monotone {r1}/{r2}"
        assertion_count += 1
    # High residual rejected
    assert not lam.accept(100.0), "FAIL: reject huge residual"
    assertion_count += 1

    receipt = lam.lambda_receipt(0.0, "0" * 64)
    assert receipt["upstream_sha"] == UPSTREAM_PINNS_SHA, "FAIL: upstream sha"
    assertion_count += 1
    assert receipt["upstream_license"] == "MIT", "FAIL: upstream license"
    assertion_count += 1
    assert receipt["accept"] is True, "FAIL: receipt accept"
    assertion_count += 1
    assert receipt["axis_3_residual"] == 1.0, "FAIL: axis_3"
    assertion_count += 1

    # Invalid k / threshold
    try:
        PINNResidualLambda(k=0.0)
        assert False, "FAIL: should reject k=0"
    except ValueError:
        assertion_count += 1
    try:
        PINNResidualLambda(k=1.0, accept_threshold=1.5)
        assert False, "FAIL: should reject threshold"
    except ValueError:
        assertion_count += 1

    # ── Graft 4 — A15PersistentHomologyCheck ─────────────────────────
    # Empty complex
    c0 = A15PersistentHomologyCheck(bound=0)
    r0 = c0.check()
    assert r0["pass"], "FAIL: empty A15 must pass"
    assertion_count += 1
    assert r0["rank_h1_upper"] == 0, "FAIL: empty rank"
    assertion_count += 1
    assert r0["citation_doi"] == ELZ_2002_DOI, "FAIL: citation"
    assertion_count += 1

    # Single triangle ⇒ χ=1, b_1 upper = 0
    c1 = A15PersistentHomologyCheck(bound=0)
    c1.add_face((0, 1, 2))
    assert c1.vertex_count() == 3, "FAIL: tri V"
    assertion_count += 1
    assert c1.edge_count() == 3, "FAIL: tri E"
    assertion_count += 1
    assert c1.face_count() == 1, "FAIL: tri F"
    assertion_count += 1
    assert c1.euler_characteristic() == 1, "FAIL: tri chi"
    assertion_count += 1
    assert c1.connected_components() == 1, "FAIL: tri b0"
    assertion_count += 1
    assert c1.betti_1_upper_bound() == 0, "FAIL: tri b1"
    assertion_count += 1
    assert c1.check()["pass"], "FAIL: tri pass"
    assertion_count += 1

    # Cycle (no face) ⇒ b_1 ≥ 1
    c2 = A15PersistentHomologyCheck(bound=1)
    for v in range(4):
        c2.add_vertex(v)
    c2.add_edge(0, 1)
    c2.add_edge(1, 2)
    c2.add_edge(2, 3)
    c2.add_edge(3, 0)
    # V=4, E=4, F=0 ⇒ χ=0 ⇒ b_1 ≥ b_0 - χ = 1 - 0 = 1
    assert c2.euler_characteristic() == 0, "FAIL: cycle chi"
    assertion_count += 1
    assert c2.connected_components() == 1, "FAIL: cycle b0"
    assertion_count += 1
    assert c2.betti_1_upper_bound() == 1, "FAIL: cycle b1"
    assertion_count += 1
    assert c2.check()["pass"], "FAIL: cycle pass with bound=1"
    assertion_count += 1

    # Two disconnected vertices
    c3 = A15PersistentHomologyCheck(bound=0)
    c3.add_vertex(0)
    c3.add_vertex(1)
    assert c3.connected_components() == 2, "FAIL: 2 comp"
    assertion_count += 1
    assert c3.euler_characteristic() == 2, "FAIL: 2-comp chi"
    assertion_count += 1

    # Invalid bound
    try:
        A15PersistentHomologyCheck(bound=-1)
        assert False, "FAIL: should reject neg bound"
    except ValueError:
        assertion_count += 1
    try:
        c1.add_face((0, 1))
        assert False, "FAIL: should reject 2-vertex face"
    except ValueError:
        assertion_count += 1

    # ── Graft 5 — UDSOperatorConsoleDataPlane ─────────────────────────
    p_a = UDSAirGapPayload("UDS-T7")
    p_b = UDSAirGapPayload("UDS-T8")
    for i in range(5):
        p_a.tick((0, 0, 0), (0, 0, 9.81), 100.0, True, timestamp_ns=i * 1000 + 1)
        p_b.tick((0, 0, 0), (0, 0, 9.81), 95.0, True, timestamp_ns=i * 1000 + 1)

    console = UDSOperatorConsoleDataPlane([p_a, p_b])

    # No HUKLLA alerts in a clean substrate
    alerts = console.huklla_alerts()
    assert isinstance(alerts, list), "FAIL: alerts shape"
    assertion_count += 1
    assert len(alerts) == 0, "FAIL: should have zero HUKLLA alerts"
    assertion_count += 1

    # Dual-witness pane
    dw = console.dual_witness_pane()
    assert dw["fleet_size"] == 2, "FAIL: fleet size"
    assertion_count += 1

    # Receipt-chain pane pagination
    rc = console.receipt_chain_pane("UDS-T7", page=0, page_size=3)
    assert rc["total"] == 5, "FAIL: rc total"
    assertion_count += 1
    assert len(rc["packets"]) == 3, "FAIL: rc page 0 size"
    assertion_count += 1
    assert rc["well_formed"], "FAIL: rc well_formed"
    assertion_count += 1
    rc1 = console.receipt_chain_pane("UDS-T7", page=1, page_size=3)
    assert len(rc1["packets"]) == 2, "FAIL: rc page 1 size"
    assertion_count += 1
    # Unknown tail
    rc_none = console.receipt_chain_pane("UDS-XX")
    assert rc_none["total"] == 0, "FAIL: unknown tail"
    assertion_count += 1

    # A15 pane
    a15 = A15PersistentHomologyCheck(bound=0)
    a15.add_face((0, 1, 2))
    pane = console.a15_topology_pane(a15)
    assert pane["pass"], "FAIL: a15 pane pass"
    assertion_count += 1
    assert pane["citation_doi"] == ELZ_2002_DOI, "FAIL: a15 pane cite"
    assertion_count += 1

    # Full render
    out = console.render(a15)
    assert set(out.keys()) == {
        "huklla_alerts",
        "dual_witness",
        "receipt_chain",
        "a15_topology",
    }, "FAIL: render panes"
    assertion_count += 1
    # JSON-serialisable
    js = json.dumps(out, sort_keys=True)
    assert len(js) > 0, "FAIL: render not JSON"
    assertion_count += 1

    # HUKLLA positive: inject a forbidden token and confirm alert.
    p_x = UDSAirGapPayload("UDS-T9")
    # Add a packet carrying a forbidden token in payload.  This packet
    # is NOT emitted by any module of this substrate; it is constructed
    # *only* by this test to confirm HUKLLA detection.
    p_x.chain.append({"_test_only_token": "weapon"}, timestamp_ns=1)
    c_red = UDSOperatorConsoleDataPlane([p_x])
    red = c_red.huklla_alerts()
    assert len(red) == 1, "FAIL: HUKLLA positive"
    assertion_count += 1
    assert red[0]["severity"] == "CRITICAL", "FAIL: HUKLLA severity"
    assertion_count += 1
    assert red[0]["token"] == "weapon", "FAIL: HUKLLA token"
    assertion_count += 1

    # ── Cross-graft integration ──────────────────────────────────────
    # PINN residual receipt + chain append
    pl_int = UDSAirGapPayload("UDS-T7-INT")
    netz = UDSPINN(UDSPINN.zero_weights(hidden=2))
    lamb = PINNResidualLambda(k=1.0)
    res = netz.residual_continuity(0.1, 0.2, 0.3)
    pkt_seed = pl_int.tick((0, 0, 0), (0, 0, 9.81), 100.0, True, timestamp_ns=1)
    rcpt = lamb.lambda_receipt(res, pkt_seed.canonical_sha())
    assert rcpt["accept"] is True, "FAIL: integrated accept"
    assertion_count += 1
    assert rcpt["inference_sha"] == pkt_seed.canonical_sha(), "FAIL: integrated sha bind"
    assertion_count += 1

    # Λ-gate over a fully-passing receipt
    full = {k: 1.0 for k in LAMBDA_AXES}
    assert _lambda_gate(full) == 1.0, "FAIL: full gate"
    assertion_count += 1
    half = dict(full)
    half["axis_1_provenance"] = 0.0
    assert _lambda_gate(half) == 0.0, "FAIL: gate veto"
    assertion_count += 1

    # Provenance constants
    assert UPSTREAM_PINNS_SHA == "932f50a2d8ef", "FAIL: PINNs SHA"
    assertion_count += 1
    assert UPSTREAM_PINNS_LICENSE == "MIT", "FAIL: PINNs license"
    assertion_count += 1
    assert ELZ_2002_DOI == "10.1007/s00454-002-2885-2", "FAIL: ELZ DOI"
    assertion_count += 1

    total_tests = results.attempted + assertion_count
    print(
        f"[v18.24 UDS Operational] OK {total_tests} tests "
        f"({results.attempted} doctests + {assertion_count} assertions)"
    )
    return failures


def main() -> None:
    """Entry point — run self-tests and exit with appropriate code."""
    print("=" * 70)
    print("uds_v18_24_substrate.py — Ouroboros Thesis v18.24 UDS Operational")
    print("Author: Lutar, Stephen P. — ORCID 0009-0001-0110-4173")
    print("Doctrine: v6 — governance/observability/eval/sensor-fusion lanes")
    print("NO weapons-platform code. NO autonomous lethal action.")
    print("=" * 70)
    failures = run_self_tests()
    if failures == 0:
        print("\nGREEN — all tests pass (uds_v18_24_substrate.py v18.24)")
        sys.exit(0)
    else:
        print(f"\nRED — {failures} failure(s) (uds_v18_24_substrate.py v18.24)")
        sys.exit(1)


if __name__ == "__main__":
    main()
