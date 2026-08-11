"""A11oy / Alloy Council Kernel public API."""

__version__ = "0.5.0rc1"

from .branches import branch_score, rank_branches
from .canary import run_canary
from .capability import BudgetAccount, authorize_action, validate_attenuation
from .deliberation import DeliberationGraph, GraphEdge, GraphNode, MinorityTruthVault
from .diversity import compile_diversity, effective_size
from .fourfold import (
    CouncilRegistry,
    CouncilSession,
    sign_assessment,
    sign_commitment,
    verify_settlement,
)
from .gate import EmpiricalReleaseGate, wilson_upper
from .models import *
from .proof import Ed25519Signer, PublicVerifier, verify_signed_object
from .state_bus import StateBus
from .workflow import CouncilKernel

__all__ = [
    "__version__",
    "CouncilKernel",
    "StateBus",
    "CouncilSession",
    "CouncilRegistry",
    "Ed25519Signer",
    "PublicVerifier",
    "EmpiricalReleaseGate",
    "run_canary",
    "authorize_action",
    "validate_attenuation",
    "BudgetAccount",
    "compile_diversity",
    "effective_size",
    "rank_branches",
    "branch_score",
    "DeliberationGraph",
    "GraphNode",
    "GraphEdge",
    "MinorityTruthVault",
    "sign_commitment",
    "sign_assessment",
    "verify_settlement",
    "verify_signed_object",
    "wilson_upper",
]
