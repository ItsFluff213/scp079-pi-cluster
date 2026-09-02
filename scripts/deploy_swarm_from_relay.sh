#!/usr/bin/env bash
set -euo pipefail

PI_USER="${PI_USER:-pi}"
LOGIC_HOST="${LOGIC_HOST:-logic}"
LOGIC_USER="${LOGIC_USER:-$PI_USER}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/scp079_cluster}"
REMOTE_TMP="${REMOTE_TMP:-/tmp/scp079-bootstrap}"
SCP079_API_TOKEN="${SCP079_API_TOKEN:-}"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen3:4b-instruct}"
WEB_CONTEXT="${WEB_CONTEXT:-auto}"
SEARXNG_URL="${SEARXNG_URL:-}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SSH_OPTS=()
if [[ -f "$SSH_KEY" ]]; then
  SSH_OPTS=(-i "$SSH_KEY")
fi

case "$REMOTE_TMP" in
  /tmp/scp079-*) ;;
  *)
    echo "REMOTE_TMP must stay below /tmp/scp079-* for safety, got: $REMOTE_TMP" >&2
    exit 1
    ;;
esac

if [[ -z "$SCP079_API_TOKEN" ]]; then
  if [[ -f /opt/scp079-relay/.env ]]; then
    SCP079_API_TOKEN="$(grep '^SCP079_API_TOKEN=' /opt/scp079-relay/.env | tail -n1 | cut -d= -f2- || true)"
  fi
fi

if [[ -z "$SCP079_API_TOKEN" ]]; then
  if command -v openssl >/dev/null 2>&1; then
    SCP079_API_TOKEN="$(openssl rand -hex 24)"
  else
    SCP079_API_TOKEN="$(date +%s)-scp079-change-me"
  fi
fi

echo "==> Copying repo snapshot to logic for local image build"
ssh "${SSH_OPTS[@]}" "${LOGIC_USER}@${LOGIC_HOST}" "mkdir -p '${REMOTE_TMP}'"
tar \
  --exclude='.git/hooks' \
  --exclude='__pycache__' \
  --exclude='.venv' \
  --exclude='runtime' \
  --exclude='models' \
  -czf - . | ssh "${SSH_OPTS[@]}" "${LOGIC_USER}@${LOGIC_HOST}" "rm -rf '${REMOTE_TMP:?}'/* && tar -xzf - -C '${REMOTE_TMP}'"

echo "==> Building voice-core image on logic"
ssh -t "${SSH_OPTS[@]}" "${LOGIC_USER}@${LOGIC_HOST}" "
  set -e
  sudo mkdir -p /var/lib/scp079
  cd '${REMOTE_TMP}'
  sudo docker build -f docker/Dockerfile.voice-core -t scp079/voice-core:local .
"

echo "==> Deploying swarm stack"
export SCP079_API_TOKEN
export OLLAMA_MODEL
export WEB_CONTEXT
export SEARXNG_URL
sudo --preserve-env=SCP079_API_TOKEN,OLLAMA_MODEL,WEB_CONTEXT,SEARXNG_URL \
  docker stack deploy --resolve-image never -c docker/swarm-stack.yml scp079

echo
echo "Stack deployed."
echo "Useful checks:"
echo "  sudo docker service ls"
echo "  sudo docker service logs -f scp079_voice-core"
echo "  sudo docker service logs -f scp079_ollama"
echo "  curl http://logic:7860/health"
echo "  curl http://dsam:11434/api/tags"
