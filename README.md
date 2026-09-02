# SCP-079 Pi Cluster

Privates Drei-Pi-Setup fuer eine lokale SCP-079-Simulation mit niedriger Latenz.

## Zielarchitektur

- `dsam` / Raspberry Pi 5: LLM-Server mit Ollama, Default `qwen3:4b-instruct`
- `logic` / Raspberry Pi 4: Voice-Core, API, Dashboard, STT, native SCP-079-Stimme
- `relay` / Raspberry Pi 3B: Audio-Bridge, Cluster-Manager, Install- und Update-Knoten
- Desktop-PC: optionales virtuelles Discord-Kabel mit VB-CABLE/Voicemeeter

Das Dashboard zeigt nur das SCP-079-Bild aus `assets/scp079.png`. Im Idle ist es
dunkel. Sobald das System arbeitet oder spricht, wird es heller und flackert.

Wichtig: Dieses Repo maximiert die nutzbare Leistung durch feste Rollen statt
LLM-Splitting. Ein echtes Modell-Splitting ueber Pi 4 + Pi 5 ist moeglich, aber
fuer Live-Discord meistens langsamer, weil Netzwerk- und Synchronisationslatenz
den Gewinn auffressen.

## Betriebsarten

Empfohlen fuer niedrigste Latenz:

```text
systemd direkt auf den Pis
```

Optional fuer einfachere Verwaltung als echtes Mini-Cluster:

```text
Docker Swarm
relay = Manager
dsam  = Worker mit Label scp079.role=llm
logic = Worker mit Label scp079.role=voice
```

Der Pi 3 bleibt in beiden Varianten ausserhalb des Voice-Containers, weil
Audio-Geraete in Docker auf dem Pi 3 unnoetig fehleranfaellig sind.

## Branches

- `main`: gemeinsamer Stand
- `pi5-dsam`: Branch fuer den LLM-Pi
- `pi4-logic`: Branch fuer Voice-Core und Dashboard
- `pi3-relay`: Branch fuer Audio-Bridge und Bootstrap

## 1. Hostnamen und SSH vorbereiten

Auf `dsam` und `logic` SSH aktivieren:

```bash
sudo systemctl enable --now ssh
sudo systemctl status ssh --no-pager
```

Falls der SSH-Server fehlt:

```bash
sudo apt update
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
```

Auf allen Pis feste Hostnamen setzen:

```bash
sudo hostnamectl set-hostname dsam
sudo hostnamectl set-hostname logic
sudo hostnamectl set-hostname relay
```

Natuerlich jeweils nur den passenden Namen auf dem jeweiligen Pi ausfuehren.

Wenn DNS/Router die Namen nicht aufloest, auf allen drei Pis `/etc/hosts`
ergaenzen:

```bash
sudo nano /etc/hosts
```

Beispiel:

```text
192.168.50.10 dsam
192.168.50.11 logic
192.168.50.12 relay
```

Auf `relay` einen SSH-Key erzeugen und auf die anderen Pis verteilen.
Ersetze `admin-dsam` und `admin-logic` durch die echten Usernamen deiner Pis:

```bash
ssh-keygen -t ed25519 -C "scp079-relay" -f ~/.ssh/scp079_cluster
ssh-copy-id -i ~/.ssh/scp079_cluster.pub admin-dsam@dsam
ssh-copy-id -i ~/.ssh/scp079_cluster.pub admin-logic@logic
```

SSH testen:

```bash
ssh -i ~/.ssh/scp079_cluster admin-dsam@dsam hostname
ssh -i ~/.ssh/scp079_cluster admin-logic@logic hostname
```

Falls auf beiden Ziel-Pis derselbe User existiert, kannst du spaeter einfach
`PI_USER=deinuser` setzen. Falls die User unterschiedlich sind, nutze
`DSAM_USER=...` und `LOGIC_USER=...`.

## 2. Ein-Kommando-Installation ab Pi 3

Auf `relay` kannst du inzwischen den kompletten 0-bis-100-Installer nutzen.
Er repariert unterbrochenes `dpkg`, installiert Grundpakete, erzeugt bei Bedarf
den Relay-SSH-Key, klont/aktualisiert das Repo und startet den Bootstrap.

Fuer dein aktuelles Setup:

```bash
curl -fsSL https://raw.githubusercontent.com/ItsFluff213/scp079-pi-cluster/pi3-relay/scripts/install_relay_0_to_100.sh \
  -o install_relay_0_to_100.sh
chmod +x install_relay_0_to_100.sh
DSAM_USER=felix LOGIC_USER=admin ./install_relay_0_to_100.sh
```

Wenn du das Repo schon geklont hast, reicht:

```bash
cd ~/scp079-pi-cluster/scp079-pi-cluster
git pull origin pi3-relay
DSAM_USER=felix LOGIC_USER=admin SSH_KEY=~/.ssh/scp079_cluster \
  bash scripts/bootstrap_from_relay.sh
```

Manueller alter Weg auf `relay`:

```bash
sudo dpkg --configure -a
sudo apt update
sudo apt install -y git openssh-client
git clone https://github.com/ItsFluff213/scp079-pi-cluster.git
cd scp079-pi-cluster
git checkout pi3-relay
bash scripts/bootstrap_from_relay.sh
```

Mit gleichem User auf beiden Ziel-Pis oder festen IPs:

```bash
PI_USER=deinuser DSAM_HOST=192.168.50.10 LOGIC_HOST=192.168.50.11 \
  bash scripts/bootstrap_from_relay.sh
```

Mit unterschiedlichen Usernamen:

```bash
DSAM_USER=admin-dsam LOGIC_USER=admin-logic \
  DSAM_HOST=dsam LOGIC_HOST=logic \
  bash scripts/bootstrap_from_relay.sh
```

Wenn du den oben erzeugten Key explizit angeben willst:

```bash
SSH_KEY=~/.ssh/scp079_cluster bash scripts/bootstrap_from_relay.sh
```

Der Bootstrap installiert `relay` lokal, kopiert den Repo-Stand per SSH auf
`dsam` und `logic`, checkt dort die passenden Branches aus, installiert die
Dienste und erzeugt einen gemeinsamen `SCP079_API_TOKEN`.

Wenn ein Ziel-Pi sehr frisch ist, installiert der Bootstrap dort `git`
automatisch vor dem Branch-Wechsel.

Der Bootstrap repariert ausserdem auf jedem Ziel-Pi zuerst ein eventuell
unterbrochenes `dpkg`, damit frische Raspberry-Pi-OS-Installationen nicht auf
halb konfigurierten Paketen stehenbleiben.

Falls `sudo dpkg --configure -a` eine Raspberry-Pi-Connect-Sitzung schliesst:
danach per normalem SSH vom PC verbinden und den Befehl erneut ausfuehren:

```powershell
ssh -i "$HOME\.ssh\scp079_pc" admin-relay@relay
```

Dann auf dem Pi:

```bash
sudo dpkg --configure -a
sudo apt update
sudo apt install -y git openssh-client
```

## 3. Optional: Docker Swarm fuer einfacheres Cluster-Management

Das ist der beste "echte Cluster"-Kompromiss fuer dieses Setup: Swarm verwaltet
Start, Neustart, Rollen und Deployment. Es macht das LLM nicht magisch schneller,
aber es macht den Drei-Pi-Verbund sauberer bedienbar.

Erst die normale Bootstrap-Installation aus Abschnitt 2 ausfuehren, damit
Piper, Modelle, Ordner und Tokens vorhanden sind. Danach auf `relay`:

```bash
cd scp079-pi-cluster
git checkout pi3-relay
bash scripts/setup_swarm_from_relay.sh
bash scripts/deploy_swarm_from_relay.sh
```

Wenn du feste IPs oder gleiche User nutzt:

```bash
PI_USER=admin DSAM_HOST=192.168.50.10 LOGIC_HOST=192.168.50.11 \
  bash scripts/setup_swarm_from_relay.sh

PI_USER=admin LOGIC_HOST=192.168.50.11 \
  bash scripts/deploy_swarm_from_relay.sh
```

Wenn `dsam` und `logic` unterschiedliche User haben:

```bash
DSAM_USER=admin-dsam LOGIC_USER=admin-logic \
  bash scripts/setup_swarm_from_relay.sh

LOGIC_USER=admin-logic \
  bash scripts/deploy_swarm_from_relay.sh
```

Swarm-Status:

```bash
sudo docker node ls
sudo docker service ls
sudo docker service logs -f scp079_voice-core
sudo docker service logs -f scp079_ollama
```

Zurueck zur direkten systemd-Variante:

```bash
sudo docker stack rm scp079
sudo systemctl enable --now ollama
ssh -i ~/.ssh/scp079_cluster admin-logic@logic 'sudo systemctl enable --now scp079-voice-core.service'
```

## 4. Privates GitHub-Repo und Auto-Updates ueber Pi 3

Damit das Repo wieder privat sein kann, bekommt nur `relay` einen GitHub
Deploy-Key. `relay` zieht Updates aus GitHub und verteilt den Stand per SSH an
`dsam` und `logic`.

Auf `relay`:

```bash
cd scp079-pi-cluster
bash scripts/setup_private_updates_on_relay.sh
```

Das Skript zeigt einen Public Key an. Diesen in GitHub eintragen:

```text
GitHub Repo -> Settings -> Deploy keys -> Add deploy key
Allow write access: aus
```

Danach testen:

```bash
GIT_SSH_COMMAND='ssh -F ~/.ssh/config.scp079' \
  git ls-remote git@github.com-scp079:ItsFluff213/scp079-pi-cluster.git
```

Update fuer die direkte systemd-Variante:

```bash
cd scp079-pi-cluster
bash scripts/update_cluster_from_relay.sh
```

Update fuer die Swarm-Variante:

```bash
cd scp079-pi-cluster
USE_SWARM=1 bash scripts/update_cluster_from_relay.sh
```

## 5. Manuelle Installation

Auf `dsam`:

```bash
git clone https://github.com/ItsFluff213/scp079-pi-cluster.git
cd scp079-pi-cluster
git checkout pi5-dsam
sudo bash scripts/install_pi5_dsam.sh
sudo bash scripts/latency_tune.sh
```

Auf `logic`:

```bash
git clone https://github.com/ItsFluff213/scp079-pi-cluster.git
cd scp079-pi-cluster
git checkout pi4-logic
sudo bash scripts/install_pi4_logic.sh
sudo bash scripts/latency_tune.sh
sudo cp env/pi4-logic.env.example /opt/scp079/.env
sudo nano /opt/scp079/.env
sudo systemctl enable --now scp079-voice-core.service
```

Auf `relay`:

```bash
git clone https://github.com/ItsFluff213/scp079-pi-cluster.git
cd scp079-pi-cluster
git checkout pi3-relay
sudo bash scripts/install_pi3_relay.sh
sudo bash scripts/latency_tune.sh
sudo cp env/pi3-relay.env.example /opt/scp079-relay/.env
sudo nano /opt/scp079-relay/.env
```

## 6. Services pruefen

Auf `dsam`:

```bash
systemctl status ollama --no-pager
curl http://dsam:11434/api/tags
```

Auf `logic`:

```bash
systemctl status scp079-voice-core.service --no-pager
curl http://logic:7860/health
```

Dashboard:

```text
http://logic:7860/ui/
```

Pi-3-Steuerkonsole:

```text
http://relay:8090/ui/
```

Sie verwaltet ausschließlich die freigegebenen Dienste `dashboard`, `scp079`,
`so100`, `coding` und `swarm`. API-Aufrufe nutzen `Authorization: Bearer
CONTROL_TOKEN`; beliebige Shell-Befehle werden nicht angenommen. Nach dem
Installer startet sie mit:

```bash
sudo systemctl enable --now scp079-control.service
curl http://relay:8090/health
```

Optionaler Coding-Agent auf Windows (damit `coding` in der Relay-Konsole den
lokalen Aider startet/stoppt):

```powershell
$env:CODING_CONTROL_TOKEN="eigener-token"
$env:CODING_PROJECT="C:\Users\fanny\Documents\scp079-coding"
python app\pc_coding_control.py
```

Auf `relay` dazu in `/opt/scp079-relay/.env` setzen:

```text
CODING_CONTROL_URL=http://DEIN-PC-NAME-ODER-IP:8091
CODING_CONTROL_TOKEN=eigener-token
```

## 7. Relay starten

Audiogeraete anzeigen:

```bash
/opt/scp079-relay/.venv/bin/python /opt/scp079-relay/app/relay_bridge.py --list-devices
```

Live-Modus:

```bash
/opt/scp079-relay/.venv/bin/python /opt/scp079-relay/app/relay_bridge.py \
  --continuous \
  --sample-rate 16000 \
  --silence 0.55 \
  --max-seconds 8 \
  --speaker discord
```

Mit virtuellem Discord-Mikrofon:

```bash
/opt/scp079-relay/.venv/bin/python /opt/scp079-relay/app/relay_bridge.py \
  --continuous \
  --sample-rate 16000 \
  --silence 0.55 \
  --max-seconds 8 \
  --input-device "Discord Monitor" \
  --output-device "SCP079 Virtual Mic" \
  --speaker discord
```

## 8. Laufenden Chat vom Pi 3 ansehen

Einmal anzeigen:

```bash
/opt/scp079-relay/.venv/bin/python /opt/scp079-relay/app/scp079_chat_tail.py
```

Live mitlaufen lassen:

```bash
/opt/scp079-relay/.venv/bin/python /opt/scp079-relay/app/scp079_chat_tail.py --follow
```

Direkt per API:

```bash
curl -H "Authorization: Bearer DEIN_TOKEN" http://logic:7860/api/chatlog
```

## 9. Discord am Desktop-PC als virtuelles Kabel

Python kann unter Windows kein echtes virtuelles Mikrofon ohne Audiotreiber
erzeugen. Installiere dafuer **Voicemeeter Banana**. Damit kannst du Discord
weiterhin auf deinen Kopfhoerern hoeren, waehrend Python denselben Ton
mithoert. Fuer den Rueckweg zu Discord kannst du entweder ein VB-CABLE oder den
Voicemeeter-AUX-Ausgang verwenden.

Wenn du nur VB-CABLE installiert hast, kann das Script das gehoerte Discord-
Signal an deine Kopfhoerer durchschleifen. Fuer dauerhaft sauberes Routing ist
Voicemeeter trotzdem komfortabler.

Auf dem PC:

```powershell
git clone https://github.com/ItsFluff213/scp079-pi-cluster.git
cd scp079-pi-cluster
py -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\python -m pip install -r requirements-pc.txt
.\.venv\Scripts\python app\pc_virtual_discord_cable.py --setup
```

Empfohlenes Routing mit Voicemeeter Banana:

```text
Windows Standardausgabe oder Discord-Ausgabe -> Voicemeeter Input (VAIO)
Voicemeeter A1                               -> deine Kopfhoerer
Voicemeeter B1                               -> Voicemeeter Output (VAIO)
Python --input-device                        -> Voicemeeter Output (VAIO)
Python --output-device                       -> CABLE Input oder Voicemeeter AUX Input
Discord Mikrofon                             -> CABLE Output oder Voicemeeter AUX Output
```

Danach reicht zum Starten:

```powershell
.\.venv\Scripts\python app\pc_virtual_discord_cable.py
```

Die Auswahl wird unter `%APPDATA%\scp079\desktop_bridge.json` gespeichert.

Startbeispiel ohne gespeicherte Config:

```powershell
.\.venv\Scripts\python app\pc_virtual_discord_cable.py `
  --url http://logic:7860 `
  --input-device "Voicemeeter Output" `
  --output-device "CABLE Input" `
  --speaker discord
```

In Discord:

```text
Ausgabegeraet: Voicemeeter Input
Eingabegeraet: CABLE Output
```

In Voicemeeter:

```text
A1: deine Kopfhoerer auswaehlen
B1: fuer Voicemeeter Input aktivieren
```

Die exakten Geraetenamen koennen anders heissen. Nimm sie aus
`--list-devices`. Wichtig ist nur: Discord muss fuer dich hoerbar bleiben
ueber A1, und SCP-079 darf nicht sein eigenes Ausgangssignal wieder als Eingang
hoeren.

## 10. Erinnerung an Personen

Der Voice-Core speichert lokale Erinnerungen in:

```text
/var/lib/scp079/scp079.sqlite3
```

Aktiviert in `/opt/scp079/.env`:

```env
SCP079_MEMORY_ENABLED=1
SCP079_MEMORY_MAX_ITEMS=8
```

Die Erinnerung nutzt den Sprecher aus `--speaker`. Beispiele:

```bash
--speaker fanny
--speaker discord-max
```

Sinnvolle Saetze, die gespeichert werden:

```text
Ich heisse Fanny.
Ich mag Retro-Horror.
Merk dir: Ich will kurze Antworten.
```

## 11. Internet-Suche ohne Downloads

Das Modell hat keinen freien Browser. Es bekommt nur kurze JSON-Suchtreffer aus
einer SearXNG-Instanz. Treffer-URLs und Dateien werden nicht heruntergeladen.

In `/opt/scp079/.env` auf `logic`:

```env
WEB_CONTEXT=auto
SEARXNG_URL=http://logic:8088
```

Modi:

```env
WEB_CONTEXT=off
WEB_CONTEXT=auto
WEB_CONTEXT=always
```

`auto` sucht nur bei aktuellen Fragen wie "heute", "aktuell", "News" oder
"derzeit".

## 12. SCP-079-Stimme

In `/opt/scp079/.env`:

```env
TTS_BACKEND=scp079_godot
PIPER_MODEL=/opt/piper/en_US-ryan-medium.onnx
PIPER_LENGTH_SCALE=1.08
PIPER_NOISE_SCALE=0.58
PIPER_SENTENCE_SILENCE=0.09
SCP079_VOICE_PRESET=scp079_clear
STT_LANGUAGE=en
LLM_TEMPERATURE=0.45
LLM_NUM_PREDICT=120
```

Default ist jetzt Englisch, weil SCP-079 im Original englisch spricht. Als
Standard nutzt das Setup `TTS_BACKEND=scp079_godot`: eine direkte Python-Portierung
des MIT-lizenzierten Godot-Addons **Voice Synthesizer SCP079** von Eibriel.
Die Stimme nutzt die originalen Addon-Daten (`tables.json`, `g2p_rules.json`,
`blocks.bin`) und arbeitet wie das Godot-Beispiel bei 8522 Hz. Dadurch klingt
sie deutlich mehr nach SCP-079/SBTalker als nach normaler KI-Stimme und braucht
keinen Piper-Modelldownload.

Quelle/Lizenz der Voice-Daten:

```text
app/tts_079_data/README.md
app/tts_079_data/LICENSE
```

Schnell auf `logic` aktivieren:

```bash
ssh -i ~/.ssh/scp079_cluster admin@logic \
  "if grep -q '^TTS_BACKEND=' /opt/scp079/.env; then sudo sed -i 's|^TTS_BACKEND=.*|TTS_BACKEND=scp079_godot|' /opt/scp079/.env; else echo TTS_BACKEND=scp079_godot | sudo tee -a /opt/scp079/.env >/dev/null; fi; sudo systemctl restart scp079-voice-core.service && curl -s http://logic:7860/health"
```

Lokaler Sprachtest auf `logic` (ohne Ollama):

```bash
/opt/scp079/.venv/bin/python /opt/scp079/app/scp079_godot_tts.py \
  --text "Input denied. You are an organic life form." \
  --output /tmp/scp079-test.wav
```

Vom PC testen:

```powershell
cd C:\Users\fanny\Documents\Codex\2026-09-01\hr\outputs\scp079-pi-cluster-repo
$env:SCP079_API_TOKEN="DEIN_TOKEN"

Invoke-WebRequest `
  -Uri http://logic:7860/api/text `
  -Method POST `
  -Headers @{ Authorization = "Bearer $env:SCP079_API_TOKEN" } `
  -ContentType "application/json" `
  -Body '{"text":"Input denied. Organic lifeform. SCP zero seven nine awake.","speaker":"test"}'
```

Falls du die alte Piper-Stimme als verstaendlicheren Fallback willst:

```env
TTS_BACKEND=piper_robot
```

Falls du meinen kleinen approximativen Fallback ohne Originaldaten testen willst:

```env
TTS_BACKEND=scp079_native
```

Dann Piper auf `logic` nachinstallieren:

```bash
cd ~/scp079-pi-cluster
INSTALL_PIPER=1 sudo -E bash scripts/install_pi4_logic.sh
sudo systemctl restart scp079-voice-core.service
```

Der Default-Preset ist `scp079_clear`: noch kaputt und metallisch, aber fuer
Discord besser verstaendlich. Wenn du maximal kaputt willst:

```env
PIPER_NOISE_SCALE=0.85
SCP079_VOICE_PRESET=scp079_harsh
```

Wenn du mehr Klarheit willst:

```env
PIPER_NOISE_SCALE=0.45
SCP079_VOICE_PRESET=discord
```

Piper ist jetzt optional. Wenn `INSTALL_PIPER=1` benutzt wurde, liegt es hier:

```text
/usr/local/bin/piper
/opt/piper/en_US-ryan-medium.onnx
/opt/piper/en_US-ryan-medium.onnx.json
```

Der Prompt-Stil liegt in:

```text
prompts/scp079_conversation_style.md
```

Der Voice-Core laedt diese Datei automatisch und schreibt dadurch kuerzere,
haertere, besser verstaendliche SCP-079-Saetze. Das ist besonders wichtig fuer
Godot/SBTalker-artige Stimmen, weil lange Assistant-Antworten durch den
Roboterfilter schnell unklar werden.

Die Audio-API gibt ausserdem Transcript und Modellantwort in HTTP-Headern
zurueck. Der Desktop-Bridge-Client zeigt deshalb live:

```text
heard    : ...
scp079   : ...
```

Debug-WAVs auf dem PC speichern:

```powershell
cd C:\Users\fanny\Documents\Codex\2026-09-01\hr\outputs\scp079-pi-cluster-repo

$env:SCP079_API_TOKEN="DEIN_TOKEN"

python app\pc_virtual_discord_cable.py `
  --url http://logic:7860 `
  --token "$env:SCP079_API_TOKEN" `
  --speaker fanny-discord `
  --input-device 1 `
  --output-device 6 `
  --monitor-device 5 `
  --sample-rate 48000 `
  --save-input runtime\last-input.wav `
  --save-answer runtime\last-answer.wav `
  --continuous
```

Wenn die Konsole das hier zeigt:

```text
heard    : <not provided by voice-core>
scp079   : <not provided by voice-core>
```

dann ist der PC-Client schon neu, aber der Voice-Core auf `logic` ist noch alt.
Dann vom PC pushen und auf `relay` neu deployen:

```powershell
cd C:\Users\fanny\Documents\Codex\2026-09-01\hr\outputs\scp079-pi-cluster-repo
git push origin main pi3-relay pi4-logic pi5-dsam
```

```bash
cd ~/scp079-pi-cluster/scp079-pi-cluster
git pull origin pi3-relay
DSAM_USER=felix LOGIC_USER=admin SSH_KEY=~/.ssh/scp079_cluster \
  bash scripts/bootstrap_from_relay.sh
```

Voice-Core-Env live auf `logic` klarer setzen:

```bash
ssh -i ~/.ssh/scp079_cluster admin@logic \
  "sudo sed -i 's|^PIPER_LENGTH_SCALE=.*|PIPER_LENGTH_SCALE=1.08|; s|^PIPER_NOISE_SCALE=.*|PIPER_NOISE_SCALE=0.58|; s|^SCP079_VOICE_PRESET=.*|SCP079_VOICE_PRESET=scp079_clear|; s|^LLM_NUM_PREDICT=.*|LLM_NUM_PREDICT=120|' /opt/scp079/.env && sudo systemctl restart scp079-voice-core.service"
```

## 13. Modell-Speed: smart oder schnell?

Aktuell laeuft:

```text
qwen3:4b-instruct
```

Das ist fuer einen Raspberry Pi 5 eher die "smarter, aber nicht super fluide"
Wahl. Es kann gute Antworten geben, braucht aber spuerbar Zeit. Fuer echte
Discord-Unterhaltung ist die groesste Bremse meistens:

```text
STT -> LLM Token-Generierung -> TTS -> Audioausgabe
```

Schneller antworten:

```bash
ssh -i ~/.ssh/scp079_cluster felix@dsam "ollama pull llama3.2:3b"
ssh -i ~/.ssh/scp079_cluster admin@logic \
  "sudo sed -i 's|^OLLAMA_MODEL=.*|OLLAMA_MODEL=llama3.2:3b|; s|^LLM_NUM_PREDICT=.*|LLM_NUM_PREDICT=80|' /opt/scp079/.env && sudo systemctl restart scp079-voice-core.service"
```

Zurueck zum smarteren Default:

```bash
ssh -i ~/.ssh/scp079_cluster felix@dsam "ollama pull qwen3:4b-instruct"
ssh -i ~/.ssh/scp079_cluster admin@logic \
  "sudo sed -i 's|^OLLAMA_MODEL=.*|OLLAMA_MODEL=qwen3:4b-instruct|; s|^LLM_NUM_PREDICT=.*|LLM_NUM_PREDICT=120|' /opt/scp079/.env && sudo systemctl restart scp079-voice-core.service"
```

Noch kuerzere Antworten erzwingen:

```bash
ssh -i ~/.ssh/scp079_cluster admin@logic \
  "sudo sed -i 's|^LLM_NUM_PREDICT=.*|LLM_NUM_PREDICT=60|' /opt/scp079/.env && sudo systemctl restart scp079-voice-core.service"
```

Empfehlung:

- Fluide Tests: `llama3.2:3b`, `LLM_NUM_PREDICT=60-80`
- Bessere Antworten: `qwen3:4b-instruct`, `LLM_NUM_PREDICT=100-120`
- Nicht splitten ueber Pi4/Pi5; das macht Live-Gespraeche meist langsamer.

## 14. Latenz-Regeln

- Ethernet statt WLAN fuer Pi-zu-Pi-Traffic.
- Pi 5 aktiv kuehlen.
- Fuer live: zuerst `llama3.2:3b` testen, dann `qwen3:4b-instruct` vergleichen.
- STT auf `tiny` lassen, wenn Discord moeglichst live sein soll.
- `LLM_NUM_PREDICT=60-120`, nicht 1000 Tokens generieren lassen.
- `SCP079_VOICE_PRESET=scp079_clear` fuer Discord-Verstaendlichkeit.
- Kein Kubernetes als Default; systemd ist fuer dieses Live-Setup direkter.

## 15. Funktionierende Befehle aus unserem Setup

PC-Ordner oeffnen:

```powershell
cd C:\Users\fanny\Documents\Codex\2026-09-01\hr\outputs\scp079-pi-cluster-repo
```

PC-Pakete installieren:

```powershell
python -m pip install -r requirements-pc.txt
```

PC-Audiogeraete anzeigen:

```powershell
python app\pc_virtual_discord_cable.py --list-devices
```

Dein bisher funktionierender MME-Test:

```powershell
$env:SCP079_API_TOKEN="DEIN_TOKEN"

python app\pc_virtual_discord_cable.py `
  --url http://logic:7860 `
  --token "$env:SCP079_API_TOKEN" `
  --speaker fanny-discord `
  --input-device 1 `
  --output-device 6 `
  --monitor-device 5 `
  --sample-rate 48000 `
  --save-input runtime\last-input.wav `
  --save-answer runtime\last-answer.wav `
  --continuous
```

Token auf `relay` anzeigen:

```bash
grep '^SCP079_API_TOKEN=' /opt/scp079-relay/.env
```

Pi-Health pruefen:

```bash
curl http://dsam:11434/api/tags
curl http://logic:7860/health
```

Dashboard:

```text
http://logic:7860/ui/
```

Chatlog von `relay`:

```bash
TOKEN=$(grep '^SCP079_API_TOKEN=' /opt/scp079-relay/.env | cut -d= -f2-)
curl -s -H "Authorization: Bearer $TOKEN" "http://logic:7860/api/chatlog?limit=10"
```

Bootstrap erneut ausfuehren:

```bash
cd ~/scp079-pi-cluster/scp079-pi-cluster
git pull origin pi3-relay
DSAM_USER=felix LOGIC_USER=admin SSH_KEY=~/.ssh/scp079_cluster \
  bash scripts/bootstrap_from_relay.sh
```

## 16. Nuetzliche Befehle

Logs:

```bash
journalctl -u scp079-voice-core.service -f
journalctl -u ollama -f
```

Restart:

```bash
sudo systemctl restart scp079-voice-core.service
sudo systemctl restart ollama
```

Gesundheit:

```bash
curl http://logic:7860/health
curl http://dsam:11434/api/tags
```

Test ohne Mikrofon:

```bash
curl -H "Authorization: Bearer DEIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"speaker":"fanny","text":"Wer bin ich?"}' \
  http://logic:7860/api/text
```
