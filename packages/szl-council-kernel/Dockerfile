ARG PYTHON_IMAGE=python:3.13-slim
FROM ${PYTHON_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN useradd --create-home --uid 10001 council
WORKDIR /app
COPY . /app
RUN python -m pip install --no-compile .[api] && mkdir -p /data/runtime && chown -R council:council /data
USER council
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/healthz',timeout=2)"
CMD ["alloy-council","serve","--db","/data/council.sqlite3","--runtime-root","/data/runtime","--host","0.0.0.0","--port","8765"]
