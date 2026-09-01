#!/usr/bin/env bash
set -euo pipefail

apt-get update
apt-get install -y cpufrequtils

if command -v cpufreq-set >/dev/null 2>&1; then
  cpufreq-set -g performance || true
fi

cat >/etc/sysctl.d/99-scp079-low-latency.conf <<'EOF'
net.core.rmem_max=4194304
net.core.wmem_max=4194304
net.ipv4.tcp_low_latency=1
vm.swappiness=10
EOF

sysctl --system

echo "Check cooling and throttling with: vcgencmd get_throttled"
