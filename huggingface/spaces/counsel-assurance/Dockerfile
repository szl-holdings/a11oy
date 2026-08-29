# SPDX-License-Identifier: Apache-2.0
# Thin Packet 8 Space adapter. Product logic is not owned here.
# GCR pin — Docker Hub python: and public.ecr.aws are factory exit 128.
FROM mirror.gcr.io/library/python:3.12-slim
WORKDIR /app
COPY app.py a11oy_kernel.py policy_bundle.json vertical_manifest.json cases.json ./
EXPOSE 7860
ENV PORT=7860
CMD ["python", "app.py"]
