# Multi-stage Docker build for ClearMoney.
#
# Multi-stage builds use multiple FROM statements. Each FROM starts a new "stage".
# The first stage ("builder") compiles the Go binary. The second stage copies
# just the binary into a minimal Alpine image — resulting in a tiny final image
# (~20MB vs ~1GB if you used the full Go image).
#
# This is similar to:
#   - Laravel: building assets with Node, then copying to a PHP image
#   - Django: pip install in builder, copy site-packages to runtime image
#
# See: https://docs.docker.com/build/building/multi-stage/

# Stage 1: Build the Go binary.
# golang:1.25-alpine is the official Go image based on Alpine Linux (small footprint).
# "AS builder" names this stage so we can reference it later with COPY --from=builder.
FROM golang:1.25-alpine AS builder

# WORKDIR sets the working directory inside the container.
# All subsequent commands (COPY, RUN) are relative to this path.
# Like `cd /app` in a shell.
WORKDIR /app

# Copy dependency manifests first (go.mod + go.sum).
# Docker caches each layer — by copying these BEFORE the source code,
# `go mod download` is cached and only re-runs when dependencies change.
# This is the same cache optimization you'd use with package.json/composer.json.
COPY go.mod go.sum ./
RUN go mod download

# Copy the entire source code and build the binary.
# CGO_ENABLED=0 creates a statically-linked binary (no C library dependencies),
# which is required for running on the minimal Alpine image in stage 2.
# -o /clearmoney specifies the output binary path.
# ./cmd/server is the Go package to build (contains main()).
COPY . .
RUN CGO_ENABLED=0 go build -o /clearmoney ./cmd/server

# Stage 2: Runtime image.
# alpine:3.21 is a minimal Linux distribution (~5MB base).
# We only copy the compiled binary — no Go toolchain, no source code.
FROM alpine:3.21

# ca-certificates: needed for HTTPS calls (e.g., if the app calls external APIs).
# tzdata: timezone data so time.LoadLocation() works correctly in Go.
RUN apk add --no-cache ca-certificates tzdata

# Copy ONLY the compiled binary from the builder stage.
# This is why multi-stage builds produce small images — everything else is discarded.
COPY --from=builder /clearmoney /clearmoney

# Document which port the app listens on.
# EXPOSE doesn't actually publish the port — it's documentation.
# The actual port mapping happens in docker-compose.yml or `docker run -p`.
EXPOSE 8080

# CMD sets the default command when the container starts.
# JSON array syntax (exec form) is preferred over shell form for signal handling.
# This runs the binary directly without a shell wrapper.
# See: https://docs.docker.com/reference/dockerfile/#cmd
CMD ["/clearmoney"]
