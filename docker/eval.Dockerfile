# PRIMER eval image template (AD-2)
# Built once per (repo, commit); deps pre-baked so pip install costs no eval-timeout budget.
# Source is NOT baked — a fresh copy is mounted at /work per run.
# Base image is always resolved to a sha256 digest before build (M5).
#
# This file is a template reference. The actual build in images.py generates
# a Dockerfile dynamically from the repo's manifest files.

ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE}

WORKDIR /work

# Copy manifest files only (source is mounted at runtime)
# These are copied in by images.build_eval_image() from the repo
COPY pyproject.toml* ./
COPY requirements*.txt* ./

# Install dependencies (this is the pre-baked layer; runs once per repo/commit)
RUN pip install --no-cache-dir -e . 2>/dev/null || pip install --no-cache-dir pytest
RUN pip install --no-cache-dir pytest pytest-timeout 2>/dev/null || true

# Note: claude CLI (Claude Code) is expected to be installed in the container
# by the user's eval image configuration or injected at build time.
# The default assumption is that claude is available at /usr/local/bin/claude.
