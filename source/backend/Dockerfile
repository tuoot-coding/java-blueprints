# syntax=docker/dockerfile:1
# HTTP API. Пользовательский Java не исполняется здесь: только docker CLI для
# эфемерных JDK-контейнеров (через DOCKER_HOST / socket-proxy в compose).

ARG PYTHON_IMAGE=python:3.13-slim-bookworm
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.13.5
ARG DOCKER_CLI_IMAGE=docker:27-cli

FROM ${UV_IMAGE} AS uv
FROM ${DOCKER_CLI_IMAGE} AS dockercli

FROM ${PYTHON_IMAGE} AS builder
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /srv
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project
COPY app ./app
RUN uv sync --locked --no-dev

FROM ${PYTHON_IMAGE} AS runtime
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    API_HOST=0.0.0.0 \
    API_PORT=8000 \
    DATABASE_URL=sqlite:////data/java_blueprints.sqlite3 \
    STORAGE_DIR=/data/storage
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /data/storage /data/logs /java-work \
    && chown -R app:app /data /java-work
WORKDIR /srv
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /srv/app ./app
COPY --from=builder /srv/pyproject.toml ./pyproject.toml
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
USER app
EXPOSE 8000
VOLUME ["/data", "/java-work"]
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-m", "app.healthcheck"]
CMD ["python", "-m", "app"]
