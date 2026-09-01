#!/usr/bin/env bash
set -euo pipefail

PI_USER="${PI_USER:-pi}"
DSAM_HOST="${DSAM_HOST:-dsam}"
LOGIC_HOST="${LOGIC_HOST:-logic}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/scp079_cluster}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SSH_OPTS=()
if [[ -f "$SSH_KEY" ]]; then
  SSH_OPTS=(-i "$SSH_KEY")
fi

install_docker_local() {
  if command -v docker >/dev/null 2>&1; then
    return
  fi
  sudo apt update
  sudo apt install -y docker.io
  sudo systemctl enable --now docker
}

install_docker_remote() {
  local host="$1"
  ssh -t "${SSH_OPTS[@]}" "${PI_USER}@${host}" "
    set -e
    if ! command -v docker >/dev/null 2>&1; then
      sudo apt update
      sudo apt install -y docker.io
    fi
    sudo systemctl enable --now docker
  "
}

swarm_state() {
  sudo docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null || true
}

relay_ip() {
  hostname -I | awk '{print $1}'
}

echo "==> Installing Docker on relay, dsam and logic"
install_docker_local
install_docker_remote "$DSAM_HOST"
install_docker_remote "$LOGIC_HOST"

if [[ "$(swarm_state)" != "active" ]]; then
  echo "==> Initializing Docker Swarm on relay"
  sudo docker swarm init --advertise-addr "$(relay_ip)"
else
  echo "==> Swarm already active on relay"
fi

WORKER_TOKEN="$(sudo docker swarm join-token -q worker)"
MANAGER_ADDR="$(relay_ip):2377"

join_worker() {
  local host="$1"
  ssh -t "${SSH_OPTS[@]}" "${PI_USER}@${host}" "
    set -e
    state=\$(sudo docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null || true)
    if [ \"\$state\" != 'active' ]; then
      sudo docker swarm join --token '${WORKER_TOKEN}' '${MANAGER_ADDR}'
    else
      echo '${host} is already in a swarm'
    fi
  "
}

echo "==> Joining workers"
join_worker "$DSAM_HOST"
join_worker "$LOGIC_HOST"

echo "==> Labeling nodes"
sudo docker node update --label-add scp079.role=control relay >/dev/null
sudo docker node update --label-add scp079.role=llm "$DSAM_HOST" >/dev/null
sudo docker node update --label-add scp079.role=voice "$LOGIC_HOST" >/dev/null

echo
echo "Swarm ready."
sudo docker node ls
echo
echo "Next:"
echo "  bash scripts/deploy_swarm_from_relay.sh"
