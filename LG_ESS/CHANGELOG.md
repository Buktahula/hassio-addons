# Changelog

## 0.1.6
- **Automatische Migrations-Diagnose (`run_diagnostics`)**:
  - Erkennt automatisch beim Start, wenn alte, inaktive YAML-Sensoren (z. B. aus früheren `template.yaml`- oder `sensor.yaml`-Konfigurationen) die Entitäts-IDs blockieren und Home Assistant deshalb ein `_2` angehängt hat (z. B. `sensor.daily_grid_buy_2`).
  - Gibt im Add-on-Protokoll eine auffällige Warnung mit einer konkreten 30-Sekunden-Schritt-für-Schritt-Anleitung aus, wie die blockierende Alt-Entität gelöscht und die Namensendung `_2` entfernt werden kann, damit alle historischen Langzeitstatistiken im Energie-Dashboard nahtlos erhalten bleiben.
  - Prüft den Zustand über die Home Assistant Supervisor API und bestätigt nach erfolgreicher Bereinigung mit einem grünen Status (`✅ Migrations-Diagnose: Alle Sensoren und Schalter sind sauber zugeordnet`).

## 0.1.5
- **3. PV-String Unterstützung**:
  - `pv3_power`, `pv3_voltage` und `pv3_current` zur Standard-Konfiguration (`hass_autoconfig_sensors`) hinzugefügt.
  - Sensor für den 3. String in MQTT Auto-Discovery (`sensor.actual_generation_pv_3` / `sensor.aktuelle_pv_erzeugung_string_3`) und `sensor.pv3_voltage` integriert.
  - `sensor.yaml` um den 3. String ergänzt.

## 0.1.4
- **Konfigurierbares Namensschema (`entity_naming: legacy / modern`)**:
  - **`legacy` (Standard)**: Verwendet exakt die historischen Entity-IDs der ursprünglichen 2023er `sensor.yaml` (`sensor.daily_grid_buy`, `sensor.energy_sell_today`, `sensor.energy_generation_today`, `sensor.actual_grid_sell`, etc.). Dadurch bleiben alle bestehenden Dashboards und Langzeitstatistiken im Energie-Dashboard **sofort nahtlos erhalten**!
  - **`modern`**: Verwendet die neuen deutsch lokalisierten Entity-IDs (`sensor.tagesnetzbezug`, `sensor.tagesnetzeinspeisung`, etc.).

## 0.1.3
- **MQTT Auto-Discovery für alle Sensoren**: Kein manuelles Bearbeiten der `sensor.yaml` oder `configuration.yaml` mehr nötig! Alle Entitäten erscheinen vollautomatisch unter einem einheitlichen "LG ESS"-Gerät.
- **Automatische Spracherkennung (`sensor_language: auto`)**: Erkennt die eingestellte Sprache von Home Assistant (Deutsch oder Englisch) und benennt alle Sensoren passend. Manuelle Sprachwahl (`de` oder `en`) ebenfalls möglich.
- **Konfigurierbare Sensor-Erstellung (`auto_create_sensors`)**: In den Add-on-Optionen kann die automatische Erstellung ein- oder ausgeschaltet werden.
- **Wählbare Leistungseinheit (`power_unit`)**: Live-Leistungswerte wahlweise in `kW` (Standard) oder `W`.
- **Vollständige Energie-Dashboard-Kompatibilität**: Tageswerte (Netzbezug, Einspeisung, Solar, Batterie) direkt im offiziellen Energie-Dashboard auswählbar.
- **Integrierte Schalter**: Wintermodus, Schnellladung und ESS-Aktivierung als MQTT-Switches unter dem LG ESS Gerät.
- **Eigenes robustes Bridge-Skript (`lgess_mqtt.py`)**: Behebt Python 3.12 `distutils`-Inkompatibilitäten und fängt MQTT-Disconnects sauber ab.

## 0.1.2
- Fix: `distutils` Kompatibilität für Python 3.12 (`setuptools`)

## 0.1.1
- Fix: `init: false` hinzugefügt, damit s6-overlay als PID 1 startet

## 0.1.0
- Base Image aktualisiert auf Python 3.12 / Alpine 3.20
- Neues Home Assistant MQTT Service Discovery (Zero-Config für Mosquitto Broker)
- Optionale manuelle IP-Konfiguration (`ess_host`) hinzugefügt
- Start-Skript mit Passwort-Validierung und automatischer Reconnect-Schleife verbessert
- Modernisierte `sensor.yaml` mit `state_class: total_increasing` für vollständige Home Assistant Energy Dashboard Kompatibilität
- Schutz vor Division durch 0 um Mitternacht im Autarkie-Grad Sensor
- Dokumentation und Typo-Fixes

## 0.0.7
new pyess version 0.1.22

## 0.0.6
new pyess version 0.1.15

## 0.0.5
new pyess version

## 0.0.4

- add git Workflows

## 0.0.3

- add Changelog 

## 0.0.2

- password shown as *******
- add standard sensor to default config

## 0.0.1

- Initial version
