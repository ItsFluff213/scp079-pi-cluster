# pi3-relay

Dieser Branch ist fuer `relay`, den Raspberry Pi 3B oder den Discord-Rechner.

Aufgabe:

- Mikrofon oder Discord-Monitor aufnehmen
- kurze WAV-Chunks an `logic` senden
- Antwort auf lokalem Ausgang oder virtuellem Discord-Mikrofon abspielen
- keine LLM-, STT- oder TTS-Last

Start:

```bash
sudo bash scripts/install_pi3_relay.sh
sudo bash scripts/latency_tune.sh
cp env/pi3-relay.env.example /opt/scp079-relay/.env
nano /opt/scp079-relay/.env
python /opt/scp079-relay/app/relay_bridge.py --list-devices
```
