#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Thin export of the Yuyay-13 System One vector.

Implementation lives in yuyay_jev so measurement and vector stay one lexicon.
"""
from __future__ import annotations

from yuyay_jev import (  # noqa: F401
    VECTOR_DIM,
    VECTOR_KIND,
    as_vector,
    compose_vector,
    floor_misses,
)

compose = compose_vector
