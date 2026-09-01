# pi5-dsam

Dieser Branch ist fuer `dsam`, den Raspberry Pi 5.

Aufgabe:

- Ollama im LAN bereitstellen
- Default-Modell `qwen3:4b-instruct` laden
- optional spaeter llama.cpp-Server fuer GGUF testen
- keine STT/TTS-Last, damit Token-Ausgabe moeglichst stabil bleibt

Start:

```bash
sudo bash scripts/install_pi5_dsam.sh
sudo bash scripts/latency_tune.sh
```
