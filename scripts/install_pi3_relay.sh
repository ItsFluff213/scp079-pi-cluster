#!/usr/bin/env bash
set -euo pipefail

apt-get update
apt-get install -y python3-venv libportaudio2 portaudio19-dev git

TARGET_USER="${SUDO_USER:-pi}"
mkdir -p /opt/scp079-relay
cp -r app assets env requirements-relay.txt /opt/scp079-relay/
python3 -m venv /opt/scp079-relay/.venv
/opt/scp079-relay/.venv/bin/pip install -U pip
/opt/scp079-relay/.venv/bin/pip install -r /opt/scp079-relay/requirements-relay.txt
chown -R "${TARGET_USER}:${TARGET_USER}" /opt/scp079-relay

cp systemd/scp079-relay.service /etc/systemd/system/
sed -i "s/^User=.*/User=${TARGET_USER}/" /etc/systemd/system/scp079-relay.service
systemctl daemon-reload
echo "Now copy env/pi3-relay.env.example to /opt/scp079-relay/.env and set token/audio devices."
