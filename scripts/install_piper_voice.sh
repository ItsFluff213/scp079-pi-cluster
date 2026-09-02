#!/usr/bin/env bash
set -euo pipefail

PIPER_VERSION="${PIPER_VERSION:-2023.11.14-2}"
PIPER_DIR="${PIPER_DIR:-/opt/piper}"
PIPER_BIN_LINK="${PIPER_BIN_LINK:-/usr/local/bin/piper}"

VOICE_NAME="${VOICE_NAME:-en_US-ryan-medium}"
VOICE_DIR_URL="${VOICE_DIR_URL:-https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/medium}"
VOICE_MODEL="${VOICE_MODEL:-${PIPER_DIR}/${VOICE_NAME}.onnx}"
VOICE_CONFIG="${VOICE_CONFIG:-${PIPER_DIR}/${VOICE_NAME}.onnx.json}"

ARCH="$(uname -m)"
case "$ARCH" in
  aarch64|arm64)
    PIPER_ASSET="piper_linux_aarch64.tar.gz"
    ;;
  armv7l|armhf)
    PIPER_ASSET="piper_linux_armv7l.tar.gz"
    ;;
  x86_64|amd64)
    PIPER_ASSET="piper_linux_x86_64.tar.gz"
    ;;
  *)
    echo "Unsupported architecture for prebuilt Piper: $ARCH" >&2
    exit 1
    ;;
esac

apt-get update
apt-get install -y ca-certificates curl tar

mkdir -p "$PIPER_DIR"

if [[ ! -x "${PIPER_DIR}/piper/piper" ]]; then
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "$tmp_dir"' EXIT
  curl -fL \
    "https://github.com/rhasspy/piper/releases/download/${PIPER_VERSION}/${PIPER_ASSET}" \
    -o "${tmp_dir}/piper.tar.gz"
  tar -xzf "${tmp_dir}/piper.tar.gz" -C "$PIPER_DIR"
fi

ln -sf "${PIPER_DIR}/piper/piper" "$PIPER_BIN_LINK"

if [[ ! -f "$VOICE_MODEL" ]]; then
  curl -fL "${VOICE_DIR_URL}/${VOICE_NAME}.onnx" -o "$VOICE_MODEL"
fi

if [[ ! -f "$VOICE_CONFIG" ]]; then
  curl -fL "${VOICE_DIR_URL}/${VOICE_NAME}.onnx.json" -o "$VOICE_CONFIG"
fi

"$PIPER_BIN_LINK" --help >/dev/null

echo "Piper installed:"
echo "  binary: $PIPER_BIN_LINK"
echo "  voice:  $VOICE_MODEL"
