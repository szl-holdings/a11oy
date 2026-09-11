#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Canonical vertical estate publisher.

The established Domain Experience v4 implementation remains the renderer for
Terra, Sentra, Counsel, and Finance. Lyte is no longer regenerated as a generic shell:
the same A11oy single-writer job publishes the exact tested default-branch
revision of ``szl-holdings/lyte-services`` through a dedicated source-owned
publisher. Sentra remains the sole Assurance Command. Vessels remains a
capability plane inside Killinchu and is filtered before independent publication.

The job then publishes and attests the combined six-engine Python intelligence
runtime from the exact tested vertical-services default-branch tip observed at
deployment time. Each source revision is immutable for the run and guarded
against default-branch drift before mutation.

One public product surface does not require one undifferentiated code module.
Models propose, kernels constrain, Hatun reviews, and humans retain
consequential authority.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from types import ModuleType
from typing import Any

HERE = Path(__file__).resolve().parent
FLAGSHIP_IMPL = HERE / "hf_publish_vertical_flagships_v4_impl.py"
LYTE_IMPL = HERE / "hf_publish_lyte_enterprise.py"
BASE_COMBINED_IMPL = HERE / "hf_publish_vertical_services.py"
COMBINED_IMPL = HERE / "hf_publish_vertical_services_intelligence_v4.py"
SPACE_GUARD_IMPL = HERE / "hf_existing_space_guard.py"
FLAGSHIP_RECEIPT = Path("hf-vertical-flagships-receipt.json")
LYTE_RECEIPT = Path("hf-lyte-enterprise-receipt.json")
COMBINED_RECEIPT = Path("hf-vertical-services-receipt.json")

PUBLIC_FLAGSHIP_SLUGS = ("terra", "sentra", "counsel", "finance", "lyte")
GENERATED_FLAGSHIP_SLUGS = ("terra", "sentra", "counsel", "finance")
SOURCE_OWNED_FLAGSHIP_SLUGS = ("lyte",)
FOLDED_INTO_KILLINCHU = ("vessels",)
KILLINCHU_SPACE = "SZLHOLDINGS/killinchu"
SENTRA_SPACE = "SZLHOLDINGS/sentra"
LYTE_SOURCE_REVISION = "dd17d9f524b76c8f0e260d7ec1e084cc079dfc43"
VERTICAL_SERVICES_REPOSITORY = "szl-holdings/vertical-services"
GITHUB_API = "https://api.github.com"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
