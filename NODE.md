# pi4-logic

Dieser Branch ist fuer `logic`, den Raspberry Pi 4.

Aufgabe:

- Web-Dashboard und API bereitstellen
- Audio von `relay` empfangen
- Speech-to-Text mit kleinem Whisper-Modell ausfuehren
- Text an `dsam` senden
- Antwort mit Piper sprechen und SCP-079-Effekte anwenden

Start:

```bash
sudo bash scripts/install_pi4_logic.sh
sudo bash scripts/latency_tune.sh
sudo cp env/pi4-logic.env.example /opt/scp079/.env
sudo nano /opt/scp079/.env
sudo systemctl enable --now scp079-voice-core.service
```
