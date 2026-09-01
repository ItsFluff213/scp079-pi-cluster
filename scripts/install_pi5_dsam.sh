#!/usr/bin/env bash
set -euo pipefail

apt-get update
apt-get install -y curl

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
