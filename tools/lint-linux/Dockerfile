# Linux lint environment for the cgo-tagged files macOS cannot lint.
#
# seed has 6 files and stem 17 behind `//go:build cgo` / `linux` tags. On macOS
# they never compile, so `golangci-lint run` silently skips them — stem shipped
# a PR that was clean locally and red in CI for exactly this reason. Running
# GOOS=linux on the host does NOT help: it forces CGO_ENABLED=0 and produces
# gopacket/pcap typecheck noise rather than findings.
#
# This image gives cgo a real Linux toolchain and the C headers those files need.
FROM golang:1.26.6-bookworm

ARG GOLANGCI_VERSION=v2.12.2

RUN apt-get update && apt-get install -y --no-install-recommends \
      libpcap-dev \
      libbpf-dev \
      libelf-dev \
      zlib1g-dev \
      clang \
      cppcheck \
 && rm -rf /var/lib/apt/lists/*

RUN go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@${GOLANGCI_VERSION}

WORKDIR /src
ENV CGO_ENABLED=1
ENTRYPOINT ["golangci-lint"]
CMD ["run", "--max-issues-per-linter=0", "--max-same-issues=0", "./..."]
