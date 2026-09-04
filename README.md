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

- Sie bringt einen eigenen kleinen MQTT-über-TLS-Server mit (kein externer Broker nötig).
- Nach einer **einmaligen manuellen DNS-Umleitung** (siehe Installation) verbindet sich die Box zu Home Assistant statt zur echten Cloud, hält den Handshake für gültig und meldet ihre Properties ganz normal weiter.
- Alle bekannten Properties landen als Sensoren in HA — komplett lokal, kein Internetzugriff des Geräts mehr nötig.

Das Eigenschaften-Mapping (welche `siid.piid`-Kombination was bedeutet) ist aktuell ein erster Entwurf aus einem einzigen Mitschnitt — Rückmeldungen/PRs mit bestätigten Bedeutungen sind willkommen.

### Installation

1. In HACS als Custom Repository hinzufügen (Kategorie: Integration) oder über den Install-Link oben.
2. Home Assistant neu starten, Integration "MOVA Litter Box (local)" hinzufügen.
3. **Einmalig manuell:** in deinem Router/AdGuard/Pi-hole einen DNS-Rewrite für `eu.iot.mova-tech.com` und die Broker-Subdomain, die die Box in ihrem `/pair/`-Handshake meldet (z.B. `20000.mt.eu.iot.mova-tech.com`), auf die IP deiner Home-Assistant-Instanz eintragen.
4. Box stromlos machen / neu verbinden lassen.

**Achtung:** Diese Umleitung greift netzwerkweit — Geräte/die MOVAhome-App, die dieselbe Domain für andere Zwecke (Login etc.) nutzen, funktionieren währenddessen nicht mehr normal. Client-spezifische DNS-Regeln (nur für die Box) vermeiden das, falls dein DNS-Server das unterstützt.

## Why this project exists

MOVA smart litter boxes (e.g. the Q2504 model) connect over WiFi and MQTT-over-TLS exclusively to MOVA's own cloud (`*.iot.mova-tech.com`) — there's no documented local API. Reverse-engineering the real device traffic showed it doesn't properly validate the broker's TLS certificate, so it accepts a self-signed one too. This integration exploits exactly that:

- It ships its own small MQTT-over-TLS server (no external broker needed).
- After a **one-time manual DNS rewrite** (see Installation), the device connects to Home Assistant instead of the real cloud, accepts the handshake as valid, and reports its properties as normal.
- All known properties show up as sensors in HA — fully local, no internet access needed by the device anymore.

The property mapping (which `siid.piid` means what) is a first-pass guess from a single capture — feedback/PRs with confirmed meanings are welcome.

### Installation

1. Add as a Custom Repository in HACS (category: Integration), or use the install link above.
2. Restart Home Assistant, add the "MOVA Litter Box (local)" integration.
3. **One-time manual step:** in your router/AdGuard/Pi-hole, add a DNS rewrite for `eu.iot.mova-tech.com` and the broker subdomain the box reports in its `/pair/` handshake (e.g. `20000.mt.eu.iot.mova-tech.com`) pointing at your Home Assistant instance's IP.
4. Power-cycle the litter box / let it reconnect.

**Note:** this rewrite applies network-wide — other devices/the MOVAhome app using the same domain for other purposes (login etc.) won't work normally while it's active. Client-specific DNS rules (scoped to just the litter box) avoid that, if your DNS server supports them.
