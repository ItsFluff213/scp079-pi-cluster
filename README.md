# SCP-079 Pi Cluster

Latenz-optimierte Rollen:

- `dsam` / Raspberry Pi 5: LLM-Server, bevorzugt Ollama oder optional llama.cpp.
- `logic` / Raspberry Pi 4: Web/API, Speech-to-Text, Piper TTS, Stimmeffekte.
- `relay` / Raspberry Pi 3B oder Discord-PC: Mikrofon/Discord-Audio aufnehmen und Antwort abspielen.

Das ist fuer Live-Discord sinnvoller als ein geteiltes Monster-Modell: Der Pi 5
rechnet nur Tokens, der Pi 4 macht die Voice-Pipeline, der Pi 3 bleibt leicht.
Siehe auch `docs/cluster-network.md` fuer die Head-Node/Compute-Node-
Netzwerkidee aus dem Raspberry-Pi-Cluster-Tutorial.

## Branches

- `main`: gemeinsame Dateien und Doku
- `pi5-dsam`: LLM-Knoten
- `pi4-logic`: Voice-Core und Web-Dashboard
- `pi3-relay`: Audio-Bridge

Auf jedem Pi:

```bash
git clone <DEIN-REPO-URL>
cd scp079-pi-cluster
git checkout <PASSENDER-BRANCH>
```

## Pi 5: dsam

```bash
sudo bash scripts/install_pi5_dsam.sh
sudo bash scripts/latency_tune.sh
```

Default ist `qwen3:4b-instruct`, weil es auf 8 GB RAM deutlich live-tauglicher
ist als ein groesseres 7B/8B-Modell. Wenn du lieber rohe Modellgroesse willst:

```bash
ollama pull llama3.1:8b-instruct-q4_0
sudo systemctl edit ollama
```

Setze dann im Service `OLLAMA_MODEL` bzw. im Voice-Core `.env` passend um.

## Pi 4: logic

```bash
sudo bash scripts/install_pi4_logic.sh
sudo bash scripts/latency_tune.sh
sudo cp env/pi4-logic.env.example /opt/scp079/.env
sudo nano /opt/scp079/.env
sudo systemctl enable --now scp079-voice-core.service
```

UI: `http://logic:7860/ui/`

API: `http://logic:7860/api/audio`

## Pi 3 oder Discord-PC: relay

```bash
sudo bash scripts/install_pi3_relay.sh
sudo bash scripts/latency_tune.sh
cp env/pi3-relay.env.example /opt/scp079-relay/.env
nano /opt/scp079-relay/.env
python /opt/scp079-relay/app/relay_bridge.py --list-devices
```

Fuer Discord mit virtuellen Audiogeraeten:

```bash
python /opt/scp079-relay/app/relay_bridge.py \
  --continuous \
  --sample-rate 16000 \
  --silence 0.55 \
  --max-seconds 8 \
  --input-device "Discord Monitor" \
  --output-device "SCP079 Virtual Mic"
```

## Aktuelle Themen

Lokale Modelle sind nicht tagesaktuell. Fuer aktuelle Themen nutze auf `logic`
eine lokale oder LAN-SearXNG-Instanz:

```env
WEB_CONTEXT=auto
SEARXNG_URL=http://logic:8088
```

## Performance-Regeln

- Pi 5 aktiv kuehlen und `arm_freq`/Power stabil halten.
- Erst `qwen3:4b-instruct` testen, dann groessere Modelle.
- Fuer Live-Discord kurze Antworten nutzen: `num_predict`/`max_tokens` bleibt niedrig.
- STT auf `tiny` oder `base` lassen; groessere Whisper-Modelle erhoehen Latenz stark.
- Audio nicht ueber den LLM-Pi routen, damit Token-Ausgabe gleichmaessig bleibt.
