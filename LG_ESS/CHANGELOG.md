# Changelog

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
