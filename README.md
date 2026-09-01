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

## Ein-Kommando-Installation ab Pi 3

Am einfachsten: Repo einmal auf `relay` / Pi 3 klonen, dann installiert Pi 3
per SSH die passenden Rollen auf `dsam` und `logic`.

Voraussetzungen:

- Hostnamen `dsam`, `logic`, `relay` loesen im LAN auf.
- Von `relay` aus funktioniert `ssh pi@dsam` und `ssh pi@logic`.
- Der User `pi` darf auf allen Pis `sudo` verwenden.

Auf `relay`:

```bash
sudo apt update
sudo apt install -y git openssh-client
git clone https://github.com/ItsFluff213/scp079-pi-cluster.git
cd scp079-pi-cluster
git checkout pi3-relay
bash scripts/bootstrap_from_relay.sh
```

Falls deine SSH-User/Hostnamen anders sind:

```bash
PI_USER=deinuser DSAM_HOST=192.168.50.10 LOGIC_HOST=192.168.50.11 \
  bash scripts/bootstrap_from_relay.sh
```

Weil das Repo privat ist, ist dieser Weg absichtlich so gebaut, dass nur `relay`
GitHub-Zugriff braucht. Die anderen Pis bekommen den Repo-Stand per SSH-Kopie.

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

Das Dashboard nutzt einen SCP-079-artigen CRT-Terminal-Look: schwarzer
Hintergrund, gruene Monospace-Schrift, Scanlines, Vignette, rote Warnakzente und
kurze Maschinenlabels.

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

## SCP-079-Stimme

Der Voice-Core nutzt das Preset `SCP079_VOICE_PRESET=scp079`. Es kombiniert:

- enge Bandbegrenzung wie ein alter Monitor/Lautsprecher
- 6/7-bit Bitcrushing
- Ringmodulation und harte Amplitudenmodulation
- kurzen Flanger/Comb-Delay
- kurzes Slapback-Echo
- leichtes Netzbrummen und Rauschen

Feintuning in `/opt/scp079/.env`:

```env
PIPER_LENGTH_SCALE=1.18
PIPER_NOISE_SCALE=0.72
PIPER_SENTENCE_SILENCE=0.09
SCP079_VOICE_PRESET=scp079
```

Mehr Verstaendlichkeit: `PIPER_NOISE_SCALE=0.55` und `SCP079_VOICE_PRESET=robot`.
Mehr kaputte Computerstimme: `PIPER_NOISE_SCALE=0.85`, aber das kann Nuscheln
verstaerken.
