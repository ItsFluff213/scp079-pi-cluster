#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/ItsFluff213/scp079-pi-cluster.git}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/scp079-pi-cluster}"
BRANCH="${BRANCH:-pi3-relay}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/scp079_cluster}"
DSAM_USER="${DSAM_USER:-${PI_USER:-pi}}"
LOGIC_USER="${LOGIC_USER:-${PI_USER:-pi}}"
DSAM_HOST="${DSAM_HOST:-dsam}"
LOGIC_HOST="${LOGIC_HOST:-logic}"
RUN_BOOTSTRAP="${RUN_BOOTSTRAP:-1}"
SETUP_SWARM="${SETUP_SWARM:-0}"

banner() {
  cat <<'EOF'

   ███████╗ ██████╗██████╗        ██████╗ ███████╗ █████╗ 
   ██╔════╝██╔════╝██╔══██╗      ██╔═████╗╚════██║██╔══██╗
   ███████╗██║     ██████╔╝█████╗██║██╔██║    ██╔╝╚█████╔╝
   ╚════██║██║     ██╔═══╝ ╚════╝████╔╝██║   ██╔╝ ██╔══██╗
   ███████║╚██████╗██║           ╚██████╔╝   ██║  ╚█████╔╝
   ╚══════╝ ╚═════╝╚═╝            ╚═════╝    ╚═╝   ╚════╝ 

        LOCAL ANOMALOUS COMPUTE CLUSTER // BOOT SEQUENCE
        ORGANIC OPERATOR DETECTED ... INSTALLATION ACCEPTED

EOF
}

step() {
  echo
  echo "==> $*"
}

repo_dir() {
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    printf '%s\n' "$INSTALL_DIR"
  elif [[ -d "$INSTALL_DIR/scp079-pi-cluster/.git" ]]; then
    printf '%s\n' "$INSTALL_DIR/scp079-pi-cluster"
  else
    printf '%s\n' "$INSTALL_DIR"
  fi
}

banner

step "Repairing interrupted package state if needed"
sudo dpkg --configure -a

step "Installing relay prerequisites"
sudo apt update
sudo apt install -y git openssh-client tar

mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"

if [[ ! -f "$SSH_KEY" ]]; then
  step "Creating relay SSH key for dsam/logic automation"
  ssh-keygen -t ed25519 -C "scp079-relay" -f "$SSH_KEY" -N ""
else
  step "Using existing relay SSH key: $SSH_KEY"
fi

REPO_DIR="$(repo_dir)"
if [[ -d "$REPO_DIR/.git" ]]; then
  step "Updating existing repo at $REPO_DIR"
  cd "$REPO_DIR"
  git fetch origin --prune
else
  step "Cloning repo into $INSTALL_DIR"
  parent_dir="$(dirname "$INSTALL_DIR")"
  mkdir -p "$parent_dir"
  git clone "$REPO_URL" "$INSTALL_DIR"
  cd "$INSTALL_DIR"
fi

git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

cat <<EOF

Relay public key. If bootstrap cannot SSH into dsam/logic yet, install this key:

$(cat "${SSH_KEY}.pub")

Commands for the target Pis:
  ssh-copy-id -i ${SSH_KEY}.pub ${DSAM_USER}@${DSAM_HOST}
  ssh-copy-id -i ${SSH_KEY}.pub ${LOGIC_USER}@${LOGIC_HOST}

EOF

if [[ "$RUN_BOOTSTRAP" == "1" ]]; then
  step "Starting full Pi cluster bootstrap"
  DSAM_USER="$DSAM_USER" \
  LOGIC_USER="$LOGIC_USER" \
  DSAM_HOST="$DSAM_HOST" \
  LOGIC_HOST="$LOGIC_HOST" \
  SSH_KEY="$SSH_KEY" \
    bash scripts/bootstrap_from_relay.sh
fi

if [[ "$SETUP_SWARM" == "1" ]]; then
  step "Enabling optional Docker Swarm management layer"
  DSAM_USER="$DSAM_USER" \
  LOGIC_USER="$LOGIC_USER" \
  DSAM_HOST="$DSAM_HOST" \
  LOGIC_HOST="$LOGIC_HOST" \
  SSH_KEY="$SSH_KEY" \
    bash scripts/setup_swarm_from_relay.sh

  LOGIC_USER="$LOGIC_USER" \
  LOGIC_HOST="$LOGIC_HOST" \
  SSH_KEY="$SSH_KEY" \
    bash scripts/deploy_swarm_from_relay.sh
fi

cat <<EOF

████ BOOT COMPLETE ████

Checks:
  curl http://${DSAM_HOST}:11434/api/tags
  curl http://${LOGIC_HOST}:7860/health

Dashboard:
  http://${LOGIC_HOST}:7860/ui/

EOF
