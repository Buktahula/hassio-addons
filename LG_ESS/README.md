# Home Assistant Add-on: LG ESS Solar

Python library for LG ESS Solar power converters with EnerVU app compatibility
from [gluap/pyess](https://github.com/gluap/pyess) in a Docker Container for Home Assistant.

Copyright (c) 2019-2020 Paul Görgen (MIT License)

![Supports aarch64 Architecture][aarch64-shield] ![Supports amd64 Architecture][amd64-shield] ![Supports armv7 Architecture][armv7-shield] ![Supports i386 Architecture][i386-shield]

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-green.svg
[i386-shield]: https://img.shields.io/badge/i386-yes-green.svg

---

## 📋 Voraussetzungen

### 1. MQTT Broker
Installiere und starte das offizielle **Mosquitto broker** Add-on in Home Assistant.
> **Tipp:** Wenn der offizielle Mosquitto-Broker verwendet wird, verbindet sich dieses Add-on **vollautomatisch**! Du musst Server, Port und Zugangsdaten nicht manuell eingeben.

### 2. LG ESS Gerätepasswort ermitteln

#### Methode 1 (Empfohlen & am einfachsten):
Im Router nach der MAC-Adresse des LG ESS Wechselrichters suchen. Das Gerätepasswort entspricht exakt der MAC-Adresse in **Kleinbuchstaben ohne Doppelpunkte**.  
*Beispiel:*  
MAC-Adresse: `a3:4d:c2:03:0c:ef` ➔ Passwort: `a34dc2030cef`

#### Methode 2 (Über das Direkt-WLAN des Wechselrichters):
1. Verbinde dich mit dem internen WLAN-Hotspot des LG ESS.
2. Installiere eine Python-App auf dem Smartphone (z. B. [Pydroid 3](https://play.google.com/store/apps/details?id=ru.iiec.pydroid3) auf Android oder Terminal auf PC/Laptop).
3. Führe im Terminal folgende Befehle aus:
   ```bash
   pip install pyess
   esscli --action get_password
   ```
4. Notiere das ausgegebene Passwort.

---

## ⚙️ Konfiguration

Beispielkonfiguration im Add-on-Reiter:

```yaml
ess_password: "dein_ess_passwort"
ess_host: "" # Optional: Feste IP-Adresse (z. B. 192.168.1.150), falls Auto-Erkennung nicht greift
interval_seconds: 5 # Abfrage-Intervall in Sekunden (Standard: 5)
mqtt_server: "" # Optional: Nur nötig bei externem MQTT-Broker
mqtt_port: 1883
mqtt_user: ""
mqtt_password: ""
```

* **`ess_password`** *(Pflicht)*: Das ermittelte Passwort des LG ESS.
* **`ess_host`** *(Optional)*: Die IP-Adresse oder der Hostname des LG ESS. Wenn leer, wird der Wechselrichter automatisch per mDNS/Broadcast im lokalen Netzwerk gesucht.
* **`interval_seconds`** *(Standard: 5)*: Aktualisierungsintervall in Sekunden.
* **`mqtt_*`** *(Optional)*: Nur angeben, wenn ein externer MQTT-Server außerhalb von Home Assistant genutzt wird.

---

## ⚡ Einbindung in das Home Assistant Energie-Dashboard

In der Datei [`sensor.yaml`](sensor.yaml) findest du fertig vorkonfigurierte Sensoren für Home Assistant.

Kopiere den Inhalt der Datei in deine Home Assistant `configuration.yaml` unter `template:` (oder per `template: !include sensor.yaml`).

### Zuordnung im Energie-Dashboard (**Einstellungen ➔ Dashboards ➔ Energie**):

| Bereich im Energie-Dashboard | Zu wählender Sensor |
| :--- | :--- |
| **Netzverbrauch ➔ Netzbezug** | `sensor.tagesnetzbezug` (`kWh`) |
| **Netzverbrauch ➔ Rückeinspeisung** | `sensor.tagesnetzeinspeisung` (`kWh`) |
| **Sonnenkollektoren ➔ Solarproduktion** | `sensor.tages_solarerzeugung` (`kWh`) |
| **Batteriesysteme ➔ In Batterie geladen** | `sensor.tages_batterieladung` (`kWh`) |
| **Batteriesysteme ➔ Aus Batterie entnommen** | `sensor.tages_batterieentladung` (`kWh`) |
