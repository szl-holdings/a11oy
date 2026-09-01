# SPDX-License-Identifier: Apache-2.0
# Thin Packet 8 Space adapter. Product logic is not owned here.
# GCR pin — Docker Hub python: and public.ecr.aws are factory exit 128.
FROM mirror.gcr.io/library/python:3.12-slim
WORKDIR /app
RUN python -m pip install --no-cache-dir "https://github.com/szl-holdings/szl-substrate/archive/ad2e04374717ef79dbf7dbb91aea5a8480ed10c3.tar.gz"
COPY app.py a11oy_kernel.py szl_space_brain.py policy_bundle.json vertical_manifest.json cases.json ./
EXPOSE 7860
ENV PORT=7860
CMD ["python", "app.py"]
