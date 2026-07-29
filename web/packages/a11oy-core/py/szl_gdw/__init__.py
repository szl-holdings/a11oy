"""MODELED Lambda-AttnRes and Governed Delta Workspace research organ."""

from .kernel_adapter import ReferenceImmutableKernel, kernel_dispose
from .math_core import delta_update, governed_depth_attention
from .models import (
    CapabilityLabel,
    Decision,
    DepthSummary,
    Evidence,
    KernelReceipt,
    Proposal,
    WorkspaceState,
)
from .workspace import GovernedDeltaWorkspace

__all__ = [
    "CapabilityLabel",
    "Decision",
    "DepthSummary",
    "Evidence",
    "GovernedDeltaWorkspace",
    "KernelReceipt",
    "Proposal",
    "ReferenceImmutableKernel",
    "WorkspaceState",
    "delta_update",
    "governed_depth_attention",
    "kernel_dispose",
]
