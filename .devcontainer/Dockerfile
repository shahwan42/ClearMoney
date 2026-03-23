FROM python:3.12-slim

# Install system-level tools needed for development.
RUN apt-get update && apt-get install -y git make curl && rm -rf /var/lib/apt/lists/*

# Install uv from the official distroless image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /workspace

# Keep the container alive so VS Code can attach and run commands.
CMD ["sleep", "infinity"]
