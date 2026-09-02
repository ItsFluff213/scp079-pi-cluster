#!/usr/bin/env bash
set -euo pipefail

dpkg --configure -a
apt-get update
apt-get install -y python3-venv libsndfile1 ffmpeg git curl tar ca-certificates

TARGET_USER="${SUDO_USER:-pi}"
mkdir -p /opt/scp079 /opt/piper
mkdir -p /var/lib/scp079
cp -r app assets env prompts requirements-voice-core.txt /opt/scp079/
bash scripts/install_piper_voice.sh
python3 -m venv /opt/scp079/.venv
/opt/scp079/.venv/bin/pip install -U pip
/opt/scp079/.venv/bin/pip install -r /opt/scp079/requirements-voice-core.txt
chown -R "${TARGET_USER}:${TARGET_USER}" /var/lib/scp079 /opt/scp079 /opt/piper

cp systemd/scp079-voice-core.service /etc/systemd/system/
sed -i "s/^User=.*/User=${TARGET_USER}/" /etc/systemd/system/scp079-voice-core.service
systemctl daemon-reload
echo "Now copy env/pi4-logic.env.example to /opt/scp079/.env and set token/model paths."
