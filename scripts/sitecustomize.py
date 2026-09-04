# SPDX-License-Identifier: Apache-2.0
"""Narrow Hugging Face publisher compatibility guard.

The Hub creation endpoint is quota-limited even when ``exist_ok=True``.  The
vertical publisher only needs creation when a target Space is actually absent.
For that one entrypoint, prove existence with a read before calling create_repo;
all non-404 failures still propagate and a genuine 404 still uses the canonical
create path.
"""
from __future__ import annotations

import os
import sys
from functools import wraps


def _activate() -> bool:
    return os.path.basename(sys.argv[0]) == "hf_publish_vertical_flagships_v4.py"


if _activate():
    from huggingface_hub import HfApi
    from huggingface_hub.utils import HfHubHTTPError

    _create_repo = HfApi.create_repo

    @wraps(_create_repo)
    def _create_only_if_missing(self, repo_id, *args, **kwargs):
        repo_type = kwargs.get("repo_type", "model")
        token = kwargs.get("token")
        try:
            self.repo_info(repo_id=repo_id, repo_type=repo_type, token=token)
        except HfHubHTTPError as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status == 404:
                return _create_repo(self, repo_id, *args, **kwargs)
            raise
        return repo_id

    HfApi.create_repo = _create_only_if_missing
