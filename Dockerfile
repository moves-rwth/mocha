# syntax=docker/dockerfile:1
FROM python:3.15-slim-bookworm AS builder

WORKDIR /build
COPY pyproject.toml README.md LICENCE ./
COPY src ./src
RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels \
    '.[visualization]' 'jupyterlab>=4,<5' 'ipykernel>=6,<8'

FROM python:3.15-slim-bookworm

LABEL org.opencontainers.image.source="https://github.com/moves-rwth/mocha" \
      org.opencontainers.image.description="MoChA model checking library with Graphviz and JupyterLab" \
      org.opencontainers.image.licenses="MPL-2.0"

RUN apt-get update \
    && apt-get install --yes --no-install-recommends graphviz fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=bind,from=builder,source=/wheels,target=/wheels \
    python -m pip install --no-cache-dir --no-index /wheels/*.whl

RUN useradd --create-home --uid 1000 mocha \
    && mkdir /work \
    && chown mocha:mocha /work
USER mocha
WORKDIR /work

ENV PYTHONUNBUFFERED=1
EXPOSE 8888
CMD ["sh", "-c", "\
    if [ -z \"$JUPYTER_TOKEN\" ]; then \
        JUPYTER_TOKEN=$(python -c 'import secrets; print(secrets.token_urlsafe(32))') || exit 1; \
    fi; \
    export JUPYTER_TOKEN; \
    printf '\\n============================================================\\n  Starting MoChA with JupyterLab\\n============================================================\\n\\nOpen this link in your web browser (startup takes a few seconds):\\n\\n   http://127.0.0.1:8888/lab?token=%s\\n\\nKeep this terminal open while you work.\\nTo stop: save your notebook, return here, and press Ctrl+C.\\n============================================================\\n\\n' \"$JUPYTER_TOKEN\"; \
    exec jupyter lab --ip=0.0.0.0 --port=8888 --no-browser \
        --log-level=WARN --LabApp.log_level=WARN \
        --ServerApp.root_dir=/work --ServerApp.port_retries=0 \
        --ServerApp.answer_yes=True"]
