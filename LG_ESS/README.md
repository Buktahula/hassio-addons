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
auto_create_sensors: true # Automatisch Home Assistant Sensoren via MQTT erstellen
sensor_language: "auto" # "auto" (Systemsprache von HA), "de" (Deutsch) oder "en" (Englisch)
power_unit: "kW" # "kW" (Standard) oder "W" für aktuelle Leistungswerte
mqtt_server: "" # Optional: Nur nötig bei externem MQTT-Broker
mqtt_port: 1883
mqtt_user: ""
mqtt_password: ""
```

* **`ess_password`** *(Pflicht)*: Das ermittelte Passwort des LG ESS.
* **`ess_host`** *(Optional)*: Die IP-Adresse oder der Hostname des LG ESS. Wenn leer, wird der Wechselrichter automatisch per mDNS/Broadcast im lokalen Netzwerk gesucht.
* **`interval_seconds`** *(Standard: 5)*: Aktualisierungsintervall in Sekunden.
* **`auto_create_sensors`** *(Standard: true)*: Legt alle Sensoren und Schalter vollautomatisch als Home Assistant Entitäten unter einem "LG ESS" Gerät an.
* **`sensor_language`** *(Standard: auto)*: Erkennt automatisch die Systemsprache von Home Assistant und benennt die Sensoren auf Deutsch oder Englisch. Kann auch fest auf `de` oder `en` gestellt werden.
* **`power_unit`** *(Standard: kW)*: Einheit für Live-Leistungswerte (`kW` oder `W`).
* **`mqtt_*`** *(Optional)*: Nur angeben, wenn ein externer MQTT-Server außerhalb von Home Assistant genutzt wird.

---

## ⚡ Automatische Sensor-Erstellung & Energie-Dashboard

Wenn `auto_create_sensors: true` aktiv ist, musst du **keine einzige Zeile YAML** schreiben!

Alle Sensoren und Schalter werden automatisch erstellt und unter **Einstellungen ➔ Geräte & Dienste ➔ MQTT ➔ Geräte ➔ LG ESS** gruppiert.

### Zuordnung im Energie-Dashboard (**Einstellungen ➔ Dashboards ➔ Energie**):

| Bereich im Energie-Dashboard | Zu wählender Sensor (DE) | Zu wählender Sensor (EN) |
| :--- | :--- | :--- |
| **Netzverbrauch ➔ Netzbezug** | `sensor.lgess_daily_grid_buy` *(Tagesnetzbezug)* | `sensor.lgess_daily_grid_buy` *(Daily Grid Consumption)* |
| **Netzverbrauch ➔ Rückeinspeisung** | `sensor.lgess_energy_sell_today` *(Tagesnetzeinspeisung)* | `sensor.lgess_energy_sell_today` *(Daily Grid Feed-in)* |
| **Sonnenkollektoren ➔ Solarproduktion** | `sensor.lgess_energy_generation_today` *(Tages-Solarerzeugung)* | `sensor.lgess_energy_generation_today` *(Daily Solar Generation)* |
| **Batteriesysteme ➔ In Batterie geladen** | `sensor.lgess_energy_batt_charge_today` *(Tages-Batterieladung)* | `sensor.lgess_energy_batt_charge_today` *(Daily Battery Charge)* |
| **Batteriesysteme ➔ Aus Batterie entnommen** | `sensor.lgess_energy_batt_discharge_today` *(Tages-Batterieentladung)* | `sensor.lgess_energy_batt_discharge_today` *(Daily Battery Discharge)* |

> ℹ️ **Manuelle Template-Sensoren (`sensor.yaml`):** Für fortgeschrittene Anwender, die `auto_create_sensors: false` bevorzugen oder eigene Template-Sensoren definieren möchten, steht die Datei [`sensor.yaml`](sensor.yaml) weiterhin als Vorlage zur Verfügung.
