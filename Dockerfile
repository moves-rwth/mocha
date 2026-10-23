# syntax=docker/dockerfile:1
FROM python:3.14-slim-bookworm AS builder

WORKDIR /build
COPY pyproject.toml README.md LICENCE ./
COPY src ./src
RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels '.[visualization]'

FROM python:3.14-slim-bookworm

LABEL org.opencontainers.image.source="https://github.com/moves-rwth/mocha" \
      org.opencontainers.image.description="MoChA model checking library with Graphviz" \
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
CMD ["python"]
