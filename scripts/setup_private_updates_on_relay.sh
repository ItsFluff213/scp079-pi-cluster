#!/usr/bin/env bash
set -euo pipefail

KEY_PATH="${KEY_PATH:-$HOME/.ssh/scp079_github_deploy}"
REPO_URL="${REPO_URL:-git@github.com:ItsFluff213/scp079-pi-cluster.git}"

mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"

if [[ ! -f "$KEY_PATH" ]]; then
  ssh-keygen -t ed25519 -C "relay-scp079-private-repo" -f "$KEY_PATH" -N ""
fi

cat > "$HOME/.ssh/config.scp079" <<EOF
Host github.com-scp079
  HostName github.com
  User git
  IdentityFile $KEY_PATH
  IdentitiesOnly yes
EOF
chmod 600 "$HOME/.ssh/config.scp079"

echo
echo "Add this public key to GitHub:"
echo "  Repo -> Settings -> Deploy keys -> Add deploy key"
echo "  Allow write access: off"
echo
cat "${KEY_PATH}.pub"
echo
echo "After adding it, test with:"
echo "  GIT_SSH_COMMAND='ssh -F ~/.ssh/config.scp079' git ls-remote git@github.com-scp079:ItsFluff213/scp079-pi-cluster.git"
echo
echo "Then update with:"
echo "  bash scripts/update_cluster_from_relay.sh"
