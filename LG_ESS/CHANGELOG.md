# Changelog

## 0.1.18
- **Einspeisebegrenzung / Einspeisemenge im Installateur-Modus steuerbar (`number.feed_in_limitation`)**:
  - Neue Steuerentität `number.feed_in_limitation` (Bereich: 0 % bis 100 %, Schrittweite 1 %): Erlaubt die stufenlose Vorgabe der Wirkleistungseinspeisung / Einspeisebegrenzung direkt aus Home Assistant heraus.
  - Neuer Sensor `sensor.feed_in_limitation` (Legacy: `sensor.feed_in_limitation`, Modern: `sensor.einspeisebegrenzung`): Zeigt die aktuelle Begrenzung der Netzeinspeisung in Prozent an.
  - Das Add-on überträgt Änderungen über den offiziellen Installateur-Endpunkt (`/v1/installer/setting/pcs`, Parameter `pv_feedin_limit`) unter Verwendung des (automatisch erkannten oder konfigurierten) Installateur-Kennworts.
  - Live-Rückmeldung und bidirektionale Synchronisation mit den echten Telemetriedaten des Wechselrichters auf jedem Polling-Zyklus (`common/PCS/feed_in_limitation`).

## 0.1.17
- **Vollautomatische Erkennung des Installateur-Kennworts (Registrierungsnummer)**:
  - Das Installateur-Kennwort (die Registrierungsnummer des Wechselrichters, z. B. `DE2208BKRE...`) wird nun beim Benutzer-Login am Wechselrichter vollautomatisch ausgelesen und als Installateur-Zugang verifiziert.
  - Das manuelle Eintragen von `installer_password` in der Add-on-Konfiguration ist nicht mehr erforderlich – das Add-on erkennt es selbstständig und übernimmt es automatisch in die Konfiguration.
- **Korrektur der Ladezustands-Untergrenze (`safety_soc` vs. `safty_soc`)**:
  - Unterstützung beider Schreibweisen (`safety_soc` und `safty_soc`), da die neuere LG ESS Firmware intern `safety_soc` (mit 'e') verwendet.
  - Beim Einstellen von `number.battery_safety_soc` wird der Wert nun im Installateur-Modus zuverlässig an den Wechselrichter übertragen und dort persistiert.
- **Sensor-Stabilität (`sensor.battery_safety_soc` & `number.battery_safety_soc`)**:
  - Unterdrückung der Publikation von `None`-Werten im Polling-Zyklus, wodurch verhindert wird, dass die Entitäten in Home Assistant auf `unknown` zurückfallen.
  - Live-Rückmeldung und bidirektionale Synchronisation mit den echten Hardware-Werten des LG ESS.

## 0.1.16
- **Wintermodus-Datum ohne abschließenden Punkt (`TT.MM`)**:
  - Die Anzeige der Wintermodus-Daten (`text.winter_mode_start` und `text.winter_mode_end`) erfolgt nun sauber im Format `01.11` und `28.02` ohne störenden Punkt am Ende.
  - Akzeptiert bei der Eingabe weiterhin alle Varianten (`01.11`, `01.11.`, `1101` etc.).
- **Installateur-Modus & Registrierungsnummer (`installer_password`)**:
  - Neue Add-on-Option `installer_password`: Ermöglicht die Eingabe des Installateur-Kennworts (welches beim LG ESS werkseitig der **Registrierungsnummer** des Wechselrichters entspricht, z. B. `DE200...`).
  - Beim Einstellen der Ladezustands-Untergrenze (`number.battery_safety_soc`) meldet sich das Add-on über den offiziellen Installateur-Endpunkt (`/v1/installer/setting/login`) am Wechselrichter an und überträgt den gewünschten Safety-SoC direkt an `/v1/installer/setting/batt`.
- **Stabilität & Validierung**:
  - `number.battery_safety_soc` unterstützt nun den vollen Bereich ab 0 % bis 50 %, wodurch HA-Validierungsfehler bei Systemen mit 0 % Minimal-SoC vermieden werden.
  - Behebung von Textlängen-Meldungen bei älteren gespeicherten MQTT-Nachrichten.

## 0.1.15
- **Wintermodus-Datumseinstellung ohne Jahreszahl (`text.winter_mode_start` & `text.winter_mode_end`)**:
  - Wie in der offiziellen LG EnerVu App ist die Wintermodus-Einstellung eine jährlich wiederkehrende Kalenderspanne (nur Tag und Monat).
  - Umstellung von `date`-Entitäten (die zwingend ein Jahr `YYYY-MM-DD` erzwingen) auf saubere `text`-Entitäten im intuitiven Format `TT.MM.` (z. B. `01.11.` und `28.02.`).
  - Automatische Bereinigung alter `date`-Discovery-Topics in MQTT, sodass die früheren Jahres-Datumsentitäten in Home Assistant sauber und rückstandslos entfernt werden.
  - Das Add-on akzeptiert bei Eingaben weiterhin flexible Formate (`01.11.`, `01.11`, `1101` oder ISO) und synchronisiert diese im korrekten 4-stelligen `MMDD`-Format mit dem LG ESS.
- **Batterie-Ladezustandsuntergrenze (`battery_safety_soc` / Safety SoC)**:
  - **Neuer Sensor `sensor.battery_safety_soc`**: Zeigt die im Wechselrichter hinterlegte Tiefentladeschutz-Untergrenze (`safty_soc`, üblicherweise 5%, 10% oder 15%) an.
  - **Neue Steuerentität `number.battery_safety_soc`**: Ermöglicht das Anpassen der Sicherheitsuntergrenze über das Add-on (5% bis 50% in 5%-Schritten).
  - *Hintergrundinfo*: In der offiziellen Kunden-App ist dieser Wert bewusst gesperrt („Wenden Sie sich an den Installateur“), um die Batteriezellen und Herstellergarantie vor Tiefentladung bei langen winterlichen Standzeiten zu schützen. Sollte der Wechselrichter Änderungen via Nutzer-Rechten abweisen, synchronisiert das Add-on automatisch den echten Hardware-Wert zurück. Für die normale Nutzung zur Reservehaltung im Backup-Betrieb steht weiterhin `number.backup_soc` zur Verfügung.

## 0.1.14
- **Wintermodus-Datumseinstellung & Aktivitäts-Status**:
  - **Neue Datums-Entitäten (`date.winter_mode_start` & `date.winter_mode_end`)**:
    - Ermöglicht das direkte Einstellen des Start- und Enddatums für den Wintermodus (z. B. Start: 01.11., Ende: 28.02.) über native Home Assistant Datums-Picker.
    - Die Entitäten synchronisieren sich automatisch mit den im LG ESS Wechselrichter gespeicherten Parametern (`startdate` und `stopdate` im Format MMDD).
    - Berücksichtigt den Jahreswechsel über die Wintersaison (z. B. November 2026 bis Februar 2027) vollautomatisch.
    - Flexibles MQTT-Kommando-Handling: Akzeptiert sowohl ISO-Datumsstrings (`YYYY-MM-DD`), deutsches Datumsformat (`DD.MM.`), als auch rohe 4-stellige `MMDD`-Werte auf den Themen `ess/control/winter_mode_start` und `ess/control/winter_mode_end`.
  - **Neuer Binärsensor `binary_sensor.winter_mode_active`**:
    - Zeigt an, ob der Wintermodus zum heutigen Datum **aktiv** ist (`winter_status` des Wechselrichters).
    - Schafft klare Trennung zwischen dem Konfigurationsschalter (`switch.winter_mode`, ob der Modus prinzipiell aktiviert ist) und dem tatsächlichen saisonalen Schutzstatus (`binary_sensor.winter_mode_active`).

## 0.1.13
- **Entfernung des redundanten Schnelllade-Schalters (`switch.fastcharge`)**:
  - Da mit Version 0.1.12 die offizielle 3-Wege-Auswahl `select.charging_mode` (*Batteriepflege*, *Schnellladung*, *Wettervorhersage*) eingeführt wurde, war der binäre Schalter `switch.fastcharge` redundant und konnte den 3-Zustands-Modus nicht vollständig abbilden (z. B. versehentliches Überschreiben von *Wettervorhersage* beim Ausschalten).
  - Der Schalter `switch.fastcharge` wird nicht mehr über MQTT Discovery registriert und veraltete Discovery-Nachrichten werden beim Start automatisch bereinigt.
  - Das MQTT-Steuerthema `ess/control/fastcharge` und das Statusthema `ess/sensors/fastcharge` bleiben für bestehende Hintergrundskripte oder Automationen weiterhin abwärtskompatibel erhalten.

## 0.1.12
- **Lademodus-Auswahl (Select-Entität) & Fix für Schnellladung (#16)**:
  - **Neues Dropdown/Select `select.charging_mode` (Lademodus)**:
    - Unterstützt alle 3 offiziellen Lademodi der LG EnerVu Plus App:
      1. **Batteriepflege** (`battery_care`, Wert `0`)
      2. **Schnellladung** (`fast_charge`, Wert `1`)
      3. **Wettervorhersage** (`weather_forecast`, Wert `2`)
    - Automatische Lokalisierung (Deutsch: *Batteriepflege / Schnellladung / Wettervorhersage*, Englisch: *Battery Care / Fast Charge / Weather Forecast*).
    - Flexibles MQTT-Kommando-Handling: Akzeptiert sowohl deutsche Namen, englische Bezeichnungen, numerische IDs (0, 1, 2) als auch Raw-Keys.
  - **Reparatur des Schnelllade-Schalters (`switch.fastcharge`)**:
    - Das bisherige Problem, bei dem das Einschalten von `switch.fastcharge` sofort wieder auf `OFF` zurücksprang, ist behoben. `pyess` hatte fälschlicherweise `alg_setting: "on"` gesendet, was der Wechselrichter ablehnte. Nun wird sauber `alg_setting: 1` gesetzt.
    - Volle Abwärtskompatibilität: Beim Einschalten von `switch.fastcharge` wird in den Schnelllade-Modus gewechselt, beim Ausschalten in die Batteriepflege. Bestehende Dashboards und die *LG ESS Solar Card* funktionieren nahtlos weiter.
- **Neuer Backup-Modus (`switch.backup_mode` & `number.backup_soc`)**:
  - **Schalter `switch.backup_mode`**: Aktiviert oder deaktiviert den Notstrom-/Backup-Modus (`backupmode: "on"` / `"off"`).
  - **Zahlenfeld `number.backup_soc`**: Ermöglicht das Einstellen des Notstrom-Mindestladestands (Reserve-SoC von 5% bis 100% in 5%-Schritten).
- **Neuer Schalter „Aufladen vom Netz“ (`switch.charge_from_grid`)**:
  - Ermöglicht das aktive Laden des Batteriespeichers aus dem Stromnetz (`autocharge: "1"` / `"0"`), besonders nützlich für dynamische Stromtarife (z. B. Tibber) im Winter.
- **Erweiterte Live-Zustandssynchronisation**:
  - Alle neuen Modi (Lademodus, Schnellladung, Backup-Modus, Netzladung, Backup-SoC) werden zyklisch direkt aus den Batterieeinstellungen des Wechselrichters synchronisiert, sodass Änderungen in der Hersteller-App sofort in Home Assistant sichtbar sind.

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
