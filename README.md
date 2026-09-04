![MOVA Litter Box (local)](https://raw.githubusercontent.com/dhaucke/mova-litterbox/main/assets/mova-litterbox-banner.png)

# MOVA Litter Box (local)

**Runs your MOVA smart litter box entirely on your own network — no MOVA/Dreame cloud required after setup.**

[![Release](https://img.shields.io/github/v/release/dhaucke/mova-litterbox?style=flat-square)](https://github.com/dhaucke/mova-litterbox/releases/latest)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5?style=flat-square)](https://github.com/hacs/integration)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Custom%20Integration-18BCF2?style=flat-square)](https://www.home-assistant.io/)
[![License](https://img.shields.io/github/license/dhaucke/mova-litterbox?style=flat-square)](https://github.com/dhaucke/mova-litterbox/blob/main/LICENSE)

[Install via HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=dhaucke&repository=mova-litterbox&category=integration) · [Report an issue](https://github.com/dhaucke/mova-litterbox/issues)

**Language:** [Deutsch](#warum-dieses-projekt-existiert) · [English](#why-this-project-exists)

## Warum dieses Projekt existiert

MOVA-Katzentoiletten (z.B. das Q2504-Modell) verbinden sich per WLAN und MQTT-über-TLS ausschließlich mit MOVAs eigener Cloud (`*.iot.mova-tech.com`) — es gibt keine dokumentierte lokale API. Reverse Engineering des echten Geräte-Traffics zeigte: das Gerät prüft das TLS-Zertifikat des Brokers nicht ordentlich, akzeptiert also auch ein selbstsigniertes. Diese Integration nutzt genau das aus:

- Sie bringt einen eigenen kleinen MQTT-über-TLS-**Proxy** mit (kein externer Broker nötig).
- Nach einer **einmaligen manuellen DNS-Umleitung** (siehe Installation) verbindet sich die Box zu Home Assistant statt direkt zur echten Cloud.
- Der Proxy baut selbst eine echte Verbindung zu MOVAs Cloud auf und leitet jede Nachricht in beide Richtungen durch — die Box bleibt aus Sicht der Cloud (und der MOVAhome-App!) ganz normal online, während HA jede Nachricht mitliest.
- Alle bekannten Properties landen als Sensoren in HA, komplett lokal auswertbar, **und** die offizielle App funktioniert weiterhin.

Das Eigenschaften-Mapping (welche `siid.piid`-Kombination was bedeutet) ist aktuell ein erster Entwurf aus einem einzigen Mitschnitt — Rückmeldungen/PRs mit bestätigten Bedeutungen sind willkommen. Befehle (z.B. Reinigung starten) werden aktuell nur mitgelesen, noch nicht selbst ausgelöst.

### Installation

1. In HACS als Custom Repository hinzufügen (Kategorie: Integration) oder über den Install-Link oben.
2. Home Assistant neu starten, Integration "MOVA Litter Box (local)" hinzufügen.
3. Beim Einrichten die **Broker-Adresse deines Geräts** eintragen (Format `host:port`, z.B. `20000.mt.eu.iot.mova-tech.com:19974`) — findest du im `/pair/`-Handshake deines Geräts (siehe Reverse-Engineering-Notizen im Repo) oder über einen einmaligen Cloud-Login-Abruf.
4. **Einmalig manuell:** in deinem Router/AdGuard/Pi-hole einen DNS-Rewrite für `eu.iot.mova-tech.com` und genau diese Broker-Subdomain auf die IP deiner Home-Assistant-Instanz eintragen.
5. Box stromlos machen / neu verbinden lassen.

Da die Integration die echte Cloud-Verbindung transparent durchreicht, bleiben Box **und** MOVAhome-App gleichzeitig funktionsfähig — die Umleitung betrifft nur, wo die Verbindung technisch ankommt, nicht was am Ende passiert.

## Why this project exists

MOVA smart litter boxes (e.g. the Q2504 model) connect over WiFi and MQTT-over-TLS exclusively to MOVA's own cloud (`*.iot.mova-tech.com`) — there's no documented local API. Reverse-engineering the real device traffic showed it doesn't properly validate the broker's TLS certificate, so it accepts a self-signed one too. This integration exploits exactly that:

- It ships its own small MQTT-over-TLS **proxy** (no external broker needed).
- After a **one-time manual DNS rewrite** (see Installation), the device connects to Home Assistant instead of directly to the real cloud.
- The proxy opens its own real connection to MOVA's cloud and relays every message both ways - the device stays online from the cloud's (and the MOVAhome app's!) point of view, while HA reads every message passing through.
- Known properties show up as sensors in HA, fully local, **and** the official app keeps working.

The property mapping (which `siid.piid` means what) is a first-pass guess from a single capture — feedback/PRs with confirmed meanings are welcome. Commands (e.g. starting a cleaning cycle) are currently only observed, not yet issuable from HA.

### Installation

1. Add as a Custom Repository in HACS (category: Integration), or use the install link above.
2. Restart Home Assistant, add the "MOVA Litter Box (local)" integration.
3. During setup, enter your device's **broker address** (format `host:port`, e.g. `20000.mt.eu.iot.mova-tech.com:19974`) - found in your device's own `/pair/` handshake (see the reverse-engineering notes in this repo) or via a one-time cloud login lookup.
4. **One-time manual step:** in your router/AdGuard/Pi-hole, add a DNS rewrite for `eu.iot.mova-tech.com` and that exact broker subdomain, pointing at your Home Assistant instance's IP.
5. Power-cycle the litter box / let it reconnect.

Because the integration transparently relays the real cloud connection, both the box **and** the MOVAhome app keep working at the same time - the rewrite only changes where the connection technically lands, not what happens at the other end.
