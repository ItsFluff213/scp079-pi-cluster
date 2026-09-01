#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-$PWD}"
REPO_URL="${REPO_URL:-git@github.com-scp079:ItsFluff213/scp079-pi-cluster.git}"
GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh -F $HOME/.ssh/config.scp079}"
USE_SWARM="${USE_SWARM:-0}"
export GIT_SSH_COMMAND

cd "$REPO_DIR"

if [[ ! -d .git ]]; then
  echo "This command must run inside the scp079-pi-cluster git repo." >&2
  exit 1
fi

git remote set-url origin "$REPO_URL"
git fetch origin --prune
git checkout pi3-relay
git pull --ff-only origin pi3-relay

if [[ "$USE_SWARM" == "1" ]]; then
  bash scripts/deploy_swarm_from_relay.sh
else
  bash scripts/bootstrap_from_relay.sh
fi
