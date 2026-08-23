# Development/agent container for ReasonScript.
#
# Mirrors the setup steps in .github/workflows/ci.yml and test.yml so that
# `./reason ci --json` (and pytest) work out of the box, without depending on
# whatever Python interpreter (system Python, an unrelated venv, etc.) an
# agent runner happens to invoke `reason` with.
FROM rust:1-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        libayatana-appindicator3-dev \
        libgtk-3-dev \
        libglib2.0-dev \
        librsvg2-dev \
        libwebkit2gtk-4.1-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Isolate dev dependencies (pydantic, pytest, fastapi, ...) in a dedicated
# venv so `reason ci` never depends on the container's system Python having
# the right packages, and put it first on PATH so `python3` / `pip` resolve
# here by default.
ENV VIRTUAL_ENV=/opt/reasonscript-venv
RUN python3 -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /workspace
COPY requirements-dev.txt .
RUN pip install --upgrade pip && pip install -r requirements-dev.txt

COPY . .
RUN for manifest in */Cargo.toml; do cargo fetch --manifest-path "$manifest"; done

CMD ["./reason", "ci", "--json"]
