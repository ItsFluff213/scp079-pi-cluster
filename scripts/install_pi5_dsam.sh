#!/usr/bin/env bash
set -euo pipefail

dpkg --configure -a
apt-get update
apt-get install -y curl

TARGET_USER="${SUDO_USER:-pi}"
# Permit the Pi-3 controller to manage the optional SO-100 service without a TTY.
printf '%s ALL=(root) NOPASSWD: /usr/bin/systemctl start so100-webctl.service, /usr/bin/systemctl stop so100-webctl.service, /usr/bin/systemctl restart so100-webctl.service, /usr/bin/systemctl status so100-webctl.service\n' "${TARGET_USER}" > /etc/sudoers.d/scp079-control
chmod 0440 /etc/sudoers.d/scp079-control

if ! command -v ollama >/dev/null 2>&1; then
  curl -fsSL https://ollama.com/install.sh | sh
fi

mkdir -p /etc/systemd/system/ollama.service.d
cat >/etc/systemd/system/ollama.service.d/scp079-listen.conf <<'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF

systemctl daemon-reload
systemctl enable --now ollama
ollama pull qwen3:4b-instruct
systemctl restart ollama
