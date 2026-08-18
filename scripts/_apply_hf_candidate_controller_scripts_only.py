#!/usr/bin/env python3
"""Apply only the large validator/test portion of the staged HF wiring."""

from __future__ import annotations

from _apply_hf_candidate_controller_wiring import patch_tests, patch_validator


def main() -> None:
    patch_validator()
    patch_tests()


if __name__ == "__main__":
    main()
