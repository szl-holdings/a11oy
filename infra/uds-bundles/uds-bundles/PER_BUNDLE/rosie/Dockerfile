# Copyright 2026 SZL Holdings — SPDX-License-Identifier: Apache-2.0
# rosie UDS runtime image. Derived from HF Space pattern at rosie-fresh/.
# ADDITIVE: k8s/Zarf build target only.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8080
WORKDIR /app
RUN pip install --no-cache-dir "fastapi==0.111.0" "uvicorn[standard]==0.30.1"
COPY serve.py ./serve.py
EXPOSE 8080
RUN useradd -u 65532 -m rosie
USER 65532
HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/rosie/healthz').status==200 else 1)"
CMD ["uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8080"]
