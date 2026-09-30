# SPDX-License-Identifier: Apache-2.0
"""Single version/image contract for existing generated flagship runtimes.

Importing this module has no network, credential, or provider side effects.
The baseline is the previously admitted PURIQ source and production-image
qualification, not a claim that future vulnerability databases are clean.
This Linux server lock is not a Windows development requirements file.
"""
from __future__ import annotations

RUNTIME_BASELINE = "szl-holdings/puriq-live@91717976275b685bef5f6ba9caa40b43fc1efff5"
EXPECTED_PYTHON = "3.12.13"
REQUIREMENTS = """# Generated flagship Linux runtime. Source: admitted PURIQ 91717976275b685bef5f6ba9caa40b43fc1efff5.
# Version constraints are not artifact signatures or a fresh vulnerability clearance.
annotated-doc==0.0.5
annotated-types==0.8.0
anyio==4.15.1
certifi==2026.7.22
click==8.5.0
fastapi==0.141.1
h11==0.16.0
httpcore==1.0.9
httptools==0.8.0
httpx==0.28.1
idna==3.19
pip==26.2.1
pydantic==2.11.7
pydantic_core==2.33.2
python-dotenv==1.2.3
PyYAML==6.0.3
starlette==1.6.0
typing-inspection==0.4.4
typing_extensions==4.16.0
uvicorn==0.35.0
uvloop==0.22.1
watchfiles==1.2.0
websockets==17.1
"""
DOCKERFILE = r"""FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN python -m pip install --disable-pip-version-check --no-cache-dir --only-binary=:all: 'pip==26.2.1' \
    && python -m pip install --disable-pip-version-check --no-cache-dir --only-binary=:all: -r requirements.txt \
    && python -m pip check
COPY app.py config.json index.html panels.html ./
RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin szl
USER szl
EXPOSE 7860
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","7860","--no-server-header"]
"""


def apply_runtime_contract(renderer) -> None:
    """Bind the existing publisher inputs before its artifact digest is computed."""
    if not all(isinstance(getattr(renderer, key, None), str) for key in ("REQ", "DOCKER", "APP")):
        raise TypeError("unsupported flagship renderer contract")
    renderer.REQ = REQUIREMENTS
    renderer.DOCKER = DOCKERFILE


if __name__ == "__main__":
    # Used before dependency installation; only the standard library is needed.
    print(REQUIREMENTS, end="")
