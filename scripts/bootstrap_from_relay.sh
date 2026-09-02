#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/ItsFluff213/scp079-pi-cluster.git}"
PI_USER="${PI_USER:-pi}"
DSAM_HOST="${DSAM_HOST:-dsam}"
LOGIC_HOST="${LOGIC_HOST:-logic}"
DSAM_USER="${DSAM_USER:-$PI_USER}"
LOGIC_USER="${LOGIC_USER:-$PI_USER}"
REMOTE_TMP="${REMOTE_TMP:-/tmp/scp079-bootstrap}"
INSTALL_RELAY="${INSTALL_RELAY:-1}"
INSTALL_REMOTE="${INSTALL_REMOTE:-1}"
SCP079_API_TOKEN="${SCP079_API_TOKEN:-}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/scp079_cluster}"

usage() {
  cat <<EOF
Usage: bash scripts/bootstrap_from_relay.sh

Environment overrides:
  PI_USER=pi
  DSAM_USER=$PI_USER
  LOGIC_USER=$PI_USER
  DSAM_HOST=dsam
  LOGIC_HOST=logic
  SSH_KEY=~/.ssh/scp079_cluster
  INSTALL_RELAY=1
  INSTALL_REMOTE=1

Run this on relay / Pi 3 after cloning the private repo once.
It installs relay locally, then copies this repo over SSH to dsam and logic.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing command: $1" >&2
    exit 1
  fi
}

require_cmd git
require_cmd ssh
require_cmd tar

case "$REMOTE_TMP" in
  /tmp/scp079-*) ;;
  *)
    echo "REMOTE_TMP must stay below /tmp/scp079-* for safety, got: $REMOTE_TMP" >&2
    exit 1
    ;;
esac

if [[ -z "$SCP079_API_TOKEN" ]]; then
  if command -v openssl >/dev/null 2>&1; then
    SCP079_API_TOKEN="$(openssl rand -hex 24)"
  else
    SCP079_API_TOKEN="$(date +%s)-scp079-change-me"
  fi
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "SCP-079 bootstrap from relay"
echo "Repo: $ROOT_DIR"
echo "Targets: ${DSAM_USER}@${DSAM_HOST}, ${LOGIC_USER}@${LOGIC_HOST}"
echo "Bridge token: generated for this install"

SSH_OPTS=()
if [[ -f "$SSH_KEY" ]]; then
  SSH_OPTS=(-i "$SSH_KEY")
  echo "SSH key: $SSH_KEY"
else
  echo "SSH key not found at $SSH_KEY, falling back to default SSH auth"
fi

if [[ -d .git ]]; then
  git fetch origin --prune || true
fi

install_remote_node() {
  local host="$1"
  local user="$2"
  local branch="$3"
  local install_script="$4"
  local service="$5"

  echo
  echo "==> Preparing ${user}@${host} (${branch})"
  ssh "${SSH_OPTS[@]}" "${user}@${host}" "mkdir -p '${REMOTE_TMP}'"

  tar \
    --exclude='.git/hooks' \
    --exclude='__pycache__' \
    --exclude='.venv' \
    --exclude='runtime' \
    --exclude='models' \
    -czf - . | ssh "${SSH_OPTS[@]}" "${user}@${host}" "rm -rf '${REMOTE_TMP:?}'/* && tar -xzf - -C '${REMOTE_TMP}'"

  ssh -t "${SSH_OPTS[@]}" "${user}@${host}" "
    set -e
    if ! command -v git >/dev/null 2>&1; then
      sudo apt-get update
      sudo apt-get install -y git
    fi
    cd '${REMOTE_TMP}'
    git checkout '${branch}'
    sudo bash '${install_script}'
    sudo bash scripts/latency_tune.sh
    if [ '${branch}' = 'pi4-logic' ] && [ ! -f /opt/scp079/.env ]; then
      sudo cp env/pi4-logic.env.example /opt/scp079/.env
    fi
    if [ '${branch}' = 'pi4-logic' ]; then
      sudo sed -i 's/^SCP079_API_TOKEN=.*/SCP079_API_TOKEN=${SCP079_API_TOKEN}/' /opt/scp079/.env
    fi
    sudo systemctl daemon-reload
    if [ -n '${service}' ]; then
      sudo systemctl enable --now '${service}'
    fi
  "
}

if [[ "$INSTALL_RELAY" == "1" ]]; then
  echo
  echo "==> Installing relay locally"
  sudo bash scripts/install_pi3_relay.sh
  sudo bash scripts/latency_tune.sh
  if [[ ! -f /opt/scp079-relay/.env ]]; then
    sudo cp env/pi3-relay.env.example /opt/scp079-relay/.env
  fi
  sudo sed -i "s/^SCP079_API_TOKEN=.*/SCP079_API_TOKEN=${SCP079_API_TOKEN}/" /opt/scp079-relay/.env
fi

if [[ "$INSTALL_REMOTE" == "1" ]]; then
  install_remote_node "$DSAM_HOST" "$DSAM_USER" "pi5-dsam" "scripts/install_pi5_dsam.sh" ""
  install_remote_node "$LOGIC_HOST" "$LOGIC_USER" "pi4-logic" "scripts/install_pi4_logic.sh" "scp079-voice-core.service"
fi

echo
echo "Bootstrap complete."
echo "Set the same SCP079_API_TOKEN in:"
echo "  /opt/scp079/.env on logic"
echo "  /opt/scp079-relay/.env on relay"
echo
echo "Then start relay:"
echo "  /opt/scp079-relay/.venv/bin/python /opt/scp079-relay/app/relay_bridge.py --continuous --silence 0.55 --max-seconds 8"
