#!/usr/bin/env bash
set -euo pipefail

apt-get update
apt-get install -y python3-venv libsndfile1 ffmpeg git

mkdir -p /opt/scp079 /opt/piper
cp -r app env requirements-voice-core.txt /opt/scp079/
python3 -m venv /opt/scp079/.venv
/opt/scp079/.venv/bin/pip install -U pip
/opt/scp079/.venv/bin/pip install -r /opt/scp079/requirements-voice-core.txt

cp systemd/scp079-voice-core.service /etc/systemd/system/
systemctl daemon-reload
echo "Now copy env/pi4-logic.env.example to /opt/scp079/.env and set token/model paths."
