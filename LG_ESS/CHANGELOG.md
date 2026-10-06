# Changelog

## 0.1.11
- **Vollautomatische Kennwort-Erkennung via MAC-Adresse (Zero-Configuration Authentication) (#16)**:
  - Das Add-on ermittelt nun bei leer gelassenem `ess_password` die MAC-Adresse des LG ESS vollautomatisch über den lokalen ARP-Cache und mDNS/Netzwerk-Probing.
  - Leitet das werkseitige Standard-Passwort (MAC-Adresse in Kleinbuchstaben ohne Doppelpunkte) automatisch ab und meldet sich damit am Wechselrichter an.
  - Speichert das ermittelte Passwort nach erfolgreicher Anmeldung über die Home Assistant Supervisor API (`/addons/self/options`) direkt in die Add-on-Konfiguration, sodass das Feld in der Benutzeroberfläche für den Nutzer automatisch ausgefüllt wird.
  - Nutzer, die das Standard-Passwort nicht geändert haben, müssen ab sofort **überhaupt kein Passwort mehr eingeben** – das Add-on funktioniert nach der Installation komplett "out-of-the-box" (Zero-Config).
  - Falls das Standard-Passwort am Wechselrichter geändert wurde, kann wie gewohnt weiterhin ein eigenes Kennwort in `ess_password` hinterlegt werden. Bei ungültigen Standard-Passwörtern weist das Protokoll nun mit einer klaren Meldung darauf hin.

## 0.1.10
- **Fix für Entity-ID Übernahme via MQTT Auto-Discovery (`default_entity_id`) (#15)**:
  - Behebt ein Problem bei neueren Home Assistant Versionen (ab Core 2026.4), in denen das bisherige MQTT-Discovery-Feld `object_id` entfernt wurde.
  - Das Add-on übermittelt nun standardkonform `default_entity_id: "sensor.<obj_id>"` (bzw. `default_entity_id: "switch.<obj_id>"`).
  - Dadurch generiert Home Assistant bei `entity_naming: legacy` wieder exakt die erwarteten Legacy-IDs (`sensor.actual_grid_buy`, `sensor.battery_load_percent`, `sensor.energy_generation_today`, etc.) anstatt automatisch den Gerätenamen voranzustellen (`sensor.lg_ess_aktueller_netzbezug`).
  - **Erweiterte Migrations-Diagnose**: Erkennt automatisch beim Start, wenn Home Assistant noch Entitäten mit `sensor.lg_ess_*` aus Vorversionen gespeichert hat, und gibt eine 1-Klick-Anleitung zur sauberen Neugenerierung aus (durch einmaliges Löschen des MQTT-Geräts „LG ESS“ in Home Assistant).

## 0.1.9
- **Fix für Wintermodus-Schalter (#14)**:
  - Behebt die invertierte Steuerung des Wintermodus (`winter_mode`): Das Einschalten des Schalters in Home Assistant schaltet nun wie vorgesehen den Wintermodus am LG ESS ein (`winter_on`), das Ausschalten schaltet ihn aus (`winter_off`). Bisher war die Logik vertauscht, wodurch die Schalterstellung in Home Assistant und in der LG EnerVU App gegensätzlich war.
  - **Live-Zustandssynchronisation**: Der Status des Wintermodus (`ess/sensors/winter_mode`) und der ESS-Aktivität (`ess/sensors/active`) wird nun in jedem Abfragezyklus direkt aus den Live-Telemetriedaten des Wechselrichters (`common["BATT"]["winter_setting"]` bzw. `home["operation"]["status"]`) synchronisiert. Bei Änderungen in der offiziellen LG-App oder am Wechselrichter aktualisiert sich der Schalter in Home Assistant automatisch nach wenigen Sekunden.
  - Auch der Schnellladungs-Status (`fastcharge`) wird nun zyklisch aus den Batterieeinstellungen abgeglichen.
- **Klarstellung zu den zwei MQTT-Geräten ("ESS" vs. "LG ESS")**:
  - Bei aktiver Option `legacy_raw_sensors: true` (Standard) stellt das Add-on weiterhin das historische Gerät „ESS“ für die 65 pyess-Rohsensoren (`sensor.ess_ess_*`) bereit, um volle Abwärtskompatibilität für bestehende Installationen zu gewährleisten.
  - Alle modernen, berechneten Sensoren sowie die Steuerungs-Schalter befinden sich im Gerät „LG ESS“. Wer die Rohsensoren nicht benötigt und nur ein einziges aufgeräumtes Gerät wünscht, kann `legacy_raw_sensors: false` in den Add-on-Optionen setzen.

## 0.1.8
- **Fix für Legacy-Rohdaten-Sensoren (#13)**:
  - Behebt ein Problem bei der Einheiten-Zuordnung für klassische `sensor.ess_ess_*` Sensoren: Sensoren wie `ess_ess_common_grid_today_grid_power_purchase_energy` (und die entsprechenden Monats-/Load-Sensoren), die sowohl `power` als auch `energy` im Namen tragen, werden nun prioritär als Energie-Sensoren mit der Einheit `Wh` (`device_class: energy`, `state_class: total_increasing`) registriert statt fälschlicherweise als `power` (`W`).
  - Stellt sicher, dass bestehende Einbindungen dieser Rohsensoren im Home Assistant Energie-Dashboard oder in Langzeitstatistiken ohne Fehlermeldung erhalten bleiben.

## 0.1.7
- **Volle Abwärtskompatibilität für pyess-Rohsensoren (`legacy_raw_sensors: true`)**:
  - Bringt die klassischen `sensor.ess_ess_*` Entitäten für alle Nutzer zurück, die bisher direkt diese Rohdaten in ihren Lovelace-Dashboards oder Automatisierungen verwendet haben.
  - Repariert automatisch fehlerhafte Einheiten aus früheren pyess-Versionen (z. B. saubere `%` statt des fehlerhaften `A` für `current_day_self_consumption`).
  - Kann über die neue Add-on-Option `legacy_raw_sensors: false` deaktiviert werden, falls ein aufgeräumtes System nur mit den neuen Standard-Sensoren gewünscht ist.
  - Gewährleistet das „Zero Breaking Changes“-Prinzip: Egal ob Nutzer von der alten `sensor.yaml` kommen, Rohsensoren verwendet haben oder neu einsteigen – alles funktioniert direkt nach dem Update weiter!

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
