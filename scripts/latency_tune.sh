#!/usr/bin/env bash
set -euo pipefail

apt-get update

install_if_available() {
  local package="$1"
  local candidate
  candidate="$(apt-cache policy "$package" | awk '/Candidate:/ {print $2; exit}')"
  if [[ -n "$candidate" && "$candidate" != "(none)" ]]; then
    apt-get install -y "$package"
  else
    echo "Package not available, skipping: $package"
  fi
}

install_if_available cpufrequtils
install_if_available linux-cpupower

if command -v cpufreq-set >/dev/null 2>&1; then
  cpufreq-set -g performance || true
fi

if command -v cpupower >/dev/null 2>&1; then
  cpupower frequency-set -g performance || true
fi

for governor in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
  if [[ -w "$governor" ]]; then
    echo performance > "$governor" || true
  fi
done

cat >/etc/sysctl.d/99-scp079-low-latency.conf <<'EOF'
net.core.rmem_max=4194304
net.core.wmem_max=4194304
net.ipv4.tcp_low_latency=1
vm.swappiness=10
EOF

sysctl --system

echo "Check cooling and throttling with: vcgencmd get_throttled"
