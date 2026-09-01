# Cluster-Netz fuer niedrige Latenz

Der Raspberry-Pi-Cluster-Ansatz mit Head Node, Switch, festen Adressen und
optionalem DHCP passt gut. Fuer dieses Projekt ist aber ein schlankes Service-
Cluster besser als Kubernetes oder Network-Boot.

Empfohlen:

- Alle drei Pis per Ethernet an denselben Switch.
- `dsam` als LLM-Head mit fester IP, z.B. `192.168.50.10`.
- `logic` als Voice-Core mit fester IP, z.B. `192.168.50.11`.
- `relay` als Audio-Bridge mit fester IP, z.B. `192.168.50.12`.
- Hostnamen in DNS, Router oder `/etc/hosts`: `dsam`, `logic`, `relay`.
- WLAN nur fuer Administration, Audio/LLM-Traffic ueber Kabel.

Minimaler `/etc/hosts`-Block auf allen drei Pis:

```text
192.168.50.10 dsam
192.168.50.11 logic
192.168.50.12 relay
```

Warum kein Kubernetes als Default:

- Ein einzelner Voice-Turn besteht aus Audioaufnahme, STT, LLM, TTS und Playback.
- Diese Schritte haengen seriell voneinander ab.
- Kubernetes verteilt Services gut, macht aber ein einzelnes LLM-Token nicht
  schneller und fuegt Control-Plane-Overhead hinzu.
- Systemd plus feste Services ist fuer Live-Audio auf drei Pis direkter.

Wenn du spaeter lernen willst, wie ein klassischer Pi-Cluster funktioniert,
kannst du DHCP/Network-Boot aus dem Raspberry-Pi-Tutorial ergaenzen. Fuer SCP-079
ist das aber Infrastrukturkomfort, nicht mehr Rechenleistung.
