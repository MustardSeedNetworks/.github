#!/bin/sh
# Writes a throwaway self-signed certificate for the session fixture, the way
# seed, stem and niac-go each mint their own on first start. The gate has to
# reach such a daemon; a fixture served over plain HTTP could not show it.
set -eu
dir=$1
mkdir -p "$dir"
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=127.0.0.1 \
  -keyout "$dir/key.pem" -out "$dir/cert.pem" 2>/dev/null
