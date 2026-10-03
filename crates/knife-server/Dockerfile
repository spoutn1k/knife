# Build from the repository root:
#   docker build -f crates/knife-server/Dockerfile .

FROM rust:1-slim AS build
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY .cargo .cargo
COPY crates crates
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/src/target \
    cargo build --release --locked -p knife-server \
    && cp target/release/knife-server /usr/local/bin/

# Same Debian release as the rust image, for glibc. ca-certificates is needed
# to reach Google's APIs over TLS.
FROM debian:trixie-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /usr/local/bin/knife-server /usr/local/bin/knife-server
USER nobody
# Cloud Run sets $PORT.
CMD ["knife-server"]
