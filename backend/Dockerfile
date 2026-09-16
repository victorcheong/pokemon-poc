FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DISABLE_AUTOUPDATER=1 \
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1

# curl + certs are needed to fetch the Claude Code CLI installer.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Match the host's default WSL/Linux uid so the mounted ~/.claude credentials are readable.
ARG UID=1000
RUN useradd --create-home --uid ${UID} appuser

WORKDIR /app

# Install Python dependencies first so the layer is cached across source changes.
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

COPY app ./app
COPY data ./data
RUN chown -R appuser:appuser /app

USER appuser
ENV HOME=/home/appuser \
    PATH="/home/appuser/.local/bin:${PATH}"

# Claude Code CLI (native build, no Node needed). Used by the claude_code opponent agent,
# authenticating with the ~/.claude credentials mounted at runtime.
RUN curl -fsSL https://claude.ai/install.sh | bash

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
