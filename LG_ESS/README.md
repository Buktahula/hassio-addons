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
legacy_raw_sensors: true # Klassische sensor.ess_ess_* Rohdaten-Sensoren für volle Abwärtskompatibilität aktiv lassen
entity_naming: "legacy" # "legacy" (alte 2023er sensor.yaml IDs: sensor.daily_grid_buy etc.) oder "modern" (sensor.tagesnetzbezug etc.)
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
* **`auto_create_sensors`** *(Standard: true)*: Legt alle Sensoren und Schalter vollautomatisch als Home Assistant Entitäten unter einem einheitlichen „LG ESS“ Gerät an.
* **`legacy_raw_sensors`** *(Standard: true)*: Stellt für bestehende Dashboards alle bisherigen `sensor.ess_ess_*` Rohdaten-Sensoren mit reparierten Einheiten bereit (Zero Breaking Changes). Kann auf `false` gesetzt werden, wenn nur die neuen Standard-Sensoren gewünscht sind.
* **`entity_naming`** *(Standard: legacy)*:
  * **`legacy` (Empfohlen für bestehende Installationen)**: Verwendet exakt die historischen Entity-IDs der ursprünglichen 2023er `sensor.yaml` (`sensor.daily_grid_buy`, `sensor.energy_sell_today`, `sensor.energy_generation_today`, `sensor.actual_grid_sell` etc.). Deine bestehenden Dashboards und alle Verläufe im Energie-Dashboard bleiben **ohne jede Änderung erhalten**!
  * **`modern`**: Verwendet die neuen, voll deutsch lokalisierten Entity-IDs (`sensor.tagesnetzbezug`, `sensor.tagesnetzeinspeisung`, etc.).
* **`sensor_language`** *(Standard: auto)*: Erkennt automatisch die Systemsprache von Home Assistant und benennt die Sensoren passend (Deutsch oder Englisch). Kann auch fest auf `de` oder `en` gestellt werden.
* **`power_unit`** *(Standard: kW)*: Einheit für Live-Leistungswerte (`kW` oder `W`).
* **`mqtt_*`** *(Optional)*: Nur angeben, wenn ein externer MQTT-Server außerhalb von Home Assistant genutzt wird.

---

## ⚡ Automatische Sensor-Erstellung & Energie-Dashboard

Wenn `auto_create_sensors: true` aktiv ist, musst du **keine einzige Zeile YAML** schreiben!

Alle Sensoren und Schalter werden automatisch über MQTT Discovery angelegt und unter **Einstellungen ➔ Geräte & Dienste ➔ MQTT ➔ Geräte ➔ LG ESS** gruppiert.

### Zuordnung im Energie-Dashboard (**Einstellungen ➔ Dashboards ➔ Energie**):

| Bereich im Energie-Dashboard | Bei `entity_naming: legacy` (Standard) | Bei `entity_naming: modern` |
| :--- | :--- | :--- |
| **Netzverbrauch ➔ Netzbezug** | `sensor.daily_grid_buy` | `sensor.tagesnetzbezug` |
| **Netzverbrauch ➔ Rückeinspeisung** | `sensor.energy_sell_today` | `sensor.tagesnetzeinspeisung` |
| **Sonnenkollektoren ➔ Solarproduktion** | `sensor.energy_generation_today` | `sensor.tages_solarerzeugung` |
| **Batteriesysteme ➔ In Batterie geladen** | `sensor.energy_batt_charge_today` | `sensor.tages_batterieladung` |
| **Batteriesysteme ➔ Aus Batterie entnommen** | `sensor.energy_batt_discharge_today` | `sensor.tages_batterieentladung` |

---

## 🔄 Migration von bestehenden `sensor.yaml` Template-Sensoren

Wenn du bisher die manuelle `sensor.yaml` verwendet hast, kannst du **ohne Verlust historischer Messdaten oder Energie-Dashboard-Verläufe** auf die automatischen Sensoren umsteigen!

### 💡 Warum bleiben deine Daten erhalten?
In Home Assistant hängen alle Langzeitstatistiken (LTS) und Verläufe im Energie-Dashboard ausschließlich an der **`entity_id`** (z. B. `sensor.daily_grid_buy`). Das Add-on ist mit `entity_naming: legacy` so vorkonfiguriert, dass es **exakt dieselben Entity-IDs** erzeugt wie deine bisherige `sensor.yaml`.

### Schritt-für-Schritt Anleitung:

1. **Add-on aktualisieren & starten:**
   - Installiere Version **0.1.7** (oder neuer) und starte das Add-on. Unter MQTT erscheint das Gerät *„LG ESS“*.
2. **Alte Template-Sensoren auskommentieren:**
   - Öffne deine `configuration.yaml` (oder `template.yaml`) und kommentiere die alten LG ESS Template-Sensoren aus.
   - Starte Home Assistant neu (oder gehe auf *Entwicklerwerkzeuge ➔ YAML ➔ „Template-Entitäten neu laden“*).
3. **Alte Einträge freigeben:**
   - Gehe zu **Einstellungen ➔ Geräte & Dienste ➔ Entitäten**.
   - Die alten Sensoren erscheinen jetzt als *„Nicht verfügbar“* (ausgegraut). Klicke sie an und wähle **„Löschen“**.  
     *(Keine Sorge: Die historischen Datenbank-Statistiken werden hierbei nicht gelöscht, nur der alte Template-Eintrag wird freigegeben!)*
4. **Nahtlose Weiterführung:**
   - Die neuen MQTT-Sensoren übernehmen automatisch die gewohnten IDs (z. B. `sensor.daily_grid_buy`).
   - Falls ein Sensor vorübergehend als `_2` angelegt wurde: Einfach auf den Sensor klicken ➔ **Zahnrad (Einstellungen)** ➔ Entitäts-ID auf den Originalnamen ändern.
   - Dein Energie-Dashboard und alle Lovelace-Karten laufen **sofort ohne Anpassung weiter**!

> [!TIP]
> **Automatische Migrations-Diagnose (ab v0.1.6):**
> Das Add-on prüft beim Start vollautomatisch über die Home Assistant API, ob noch alte inaktive YAML-Sensoren die IDs blockieren und HA ein `_2` angehängt hat. Falls ja, listet das Add-on-Protokoll alle betroffenen Sensoren auf und bestätigt nach der Bereinigung mit einem grünen Häkchen (`✅ Migrations-Diagnose: Alle Sensoren und Schalter sind sauber zugeordnet`).

### 1:1 Entity-ID Übersicht:

| Messwert | Historische Entity-ID (`entity_naming: legacy`) | Neue deutsche Entity-ID (`entity_naming: modern`) |
| :--- | :--- | :--- |
| **Tagesnetzbezug** | `sensor.daily_grid_buy` ✅ | `sensor.tagesnetzbezug` |
| **Tagesnetzeinspeisung** | `sensor.energy_sell_today` ✅ | `sensor.tagesnetzeinspeisung` |
| **Tages-Solarerzeugung** | `sensor.energy_generation_today` ✅ | `sensor.tages_solarerzeugung` |
| **Tages-Batterieladung** | `sensor.energy_batt_charge_today` ✅ | `sensor.tages_batterieladung` |
| **Tages-Batterieentladung** | `sensor.energy_batt_discharge_today` ✅ | `sensor.tages_batterieentladung` |
| **Tages-Hausverbrauch** | `sensor.daily_verbrauch_gesamt` ✅ | `sensor.tages_hausverbrauch_gesamt` |
| **Live Netzeinspeisung** | `sensor.actual_grid_sell` ✅ | `sensor.aktuelle_netzeinspeisung` |
| **Live Netzbezug** | `sensor.actual_grid_buy` ✅ | `sensor.aktueller_netzbezug` |
| **Live Batterieladung** | `sensor.actual_battery_charge` ✅ | `sensor.aktuelle_batterieladung` |
| **Live Batterieentladung** | `sensor.actual_battery_discharge` ✅ | `sensor.aktuelle_batterientladung` |
| **Live Solar Gesamt** | `sensor.actual_generation_pv_full` ✅ | `sensor.aktuelle_pv_erzeugung_gesamt` |
| **Live Solar String 1** | `sensor.actual_generation_pv_1` ✅ | `sensor.aktuelle_pv_erzeugung_string_1` |
| **Live Solar String 2** | `sensor.actual_generation_pv_2` ✅ | `sensor.aktuelle_pv_erzeugung_string_2` |
| **Live Solar String 3** | `sensor.actual_generation_pv_3` ✅ | `sensor.aktuelle_pv_erzeugung_string_3` |
| **Batterieladestand (%)** | `sensor.battery_load_percent` ✅ | `sensor.batterie_ladestand` |
| **Autarkiegrad (%)** | `sensor.solaredge_calculated_self_sufficiency` ✅ | `sensor.autarkie_grad_heute` |
| **Eigenverbrauchsrate (%)** | `sensor.energy_day_self_consumption_rate` ✅ | `sensor.eigenverbrauchsrate_heute` |

---

## ❓ Häufige Fragen & Fehlerbehebung (FAQ)

### 1. „Die Maßeinheit von current_day_self_consumption wurde geändert und kann nicht in die zuvor gespeicherte Maßeinheit 'A' konvertiert werden.“
* **Ursache:** Ältere `pyess`-Versionen hatten einen Bug, bei dem Sensoren mit dem Wort `current` im Namen fälschlicherweise die Einheit **A (Ampere)** erhielten, obwohl es sich um eine prozentuale Quote handelt.
* **Lösung:** Klicke in Home Assistant unter *Entwicklerwerkzeuge ➔ Statistik* (oder direkt in der Reparatur-Meldung) einfach auf **„Statistiken löschen“** bzw. **„Bereinigen“**. Das Add-on liefert ab sofort saubere `%`-Werte.

### 2. Was passiert mit meinen alten `sensor.ess_ess_*` Rohdaten-Sensoren?
* Dank der Option **`legacy_raw_sensors: true`** (Standard) werden alle 65 klassischen Rohsensoren weiterhin via MQTT bereitgestellt. Deine bestehenden Lovelace-Karten oder Automatisierungen laufen ohne Unterbrechung weiter!
* Wenn du ein sauberes System ohne Rohsensoren bevorzugst, kannst du `legacy_raw_sensors: false` setzen und komplett auf die neuen Standard-Sensoren umsteigen.
