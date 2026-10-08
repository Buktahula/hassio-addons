#!/usr/bin/with-contenv bashio
set -e

bashio::log.info "Starting LG ESS Home Assistant Add-on..."

# Fix deprecated distutils in Python 3.12+ for pyess if present
find /usr/local/lib -name "essmqtt.py" -exec sed -i "s/from distutils.util import strtobool/from setuptools._distutils.util import strtobool/" {} + 2>/dev/null || true

# 1. Determine ESS Password
ESS_PASSWORD=""
if bashio::config.has_value 'ess_password'; then
    ESS_PASSWORD=$(bashio::config 'ess_password')
fi

if [ -n "$ESS_PASSWORD" ]; then
    bashio::log.info "Manuell konfiguriertes ESS-Passwort wird verwendet."
else
    bashio::log.info "Kein ESS-Passwort hinterlegt ➔ Automatische Erkennung via MAC-Adresse (Standard-Kennwort) aktiv."
fi

# 2. Determine MQTT Broker settings (Auto-discovery via Home Assistant MQTT service)
MQTT_HOST=""
MQTT_PORT="1883"
MQTT_USER=""
MQTT_PASSWORD=""

if bashio::services.available "mqtt"; then
    bashio::log.info "Home Assistant MQTT-Service erkannt. Verwende automatische Broker-Verbindung."
    MQTT_HOST=$(bashio::services "mqtt" "host")
    MQTT_PORT=$(bashio::services "mqtt" "port")
    MQTT_USER=$(bashio::services "mqtt" "username")
    MQTT_PASSWORD=$(bashio::services "mqtt" "password")
fi

# Override with manual user configuration if provided
if bashio::config.has_value 'mqtt_server'; then
    MQTT_HOST=$(bashio::config 'mqtt_server')
fi
if bashio::config.has_value 'mqtt_port'; then
    MQTT_PORT=$(bashio::config 'mqtt_port')
fi
if bashio::config.has_value 'mqtt_user'; then
    MQTT_USER=$(bashio::config 'mqtt_user')
fi
if bashio::config.has_value 'mqtt_password'; then
    MQTT_PASSWORD=$(bashio::config 'mqtt_password')
fi

if [ -z "$MQTT_HOST" ]; then
    bashio::log.fatal "Kein MQTT-Server gefunden! Bitte installiere das Mosquitto-Broker Add-on oder trage den MQTT-Server manuell in der Konfiguration ein."
    exit 1
fi

# 3. Settings: Interval, Auto-Create Sensors, Language & Power Unit
INTERVAL=$(bashio::config 'interval_seconds' '5')
AUTO_CREATE=$(bashio::config 'auto_create_sensors' 'true')
CONFIG_LANG=$(bashio::config 'sensor_language' 'auto')
POWER_UNIT=$(bashio::config 'power_unit' 'kW')
ENTITY_NAMING=$(bashio::config 'entity_naming' 'legacy')
LEGACY_SENSORS=$(bashio::config 'hass_autoconfig_sensors' '')
LEGACY_RAW_SENSORS="true"
if bashio::config.has_value 'legacy_raw_sensors'; then
    LEGACY_RAW_SENSORS=$(bashio::config 'legacy_raw_sensors')
fi

# Determine language
SENSOR_LANG="de"
if [ "$CONFIG_LANG" = "auto" ]; then
    HA_LANG=""
    if bashio::var.has_value "${SUPERVISOR_TOKEN}"; then
        HA_LANG=$(curl -s -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" http://supervisor/core/info 2>/dev/null | jq -r '.data.language // empty' 2>/dev/null || true)
    fi
    if [[ "$HA_LANG" =~ ^de ]]; then
        SENSOR_LANG="de"
        bashio::log.info "Home Assistant Systemsprache als Deutsch erkannt ('${HA_LANG}'). Sensoren werden auf Deutsch angelegt."
    elif [ -n "$HA_LANG" ]; then
        SENSOR_LANG="en"
        bashio::log.info "Home Assistant Systemsprache erkannt: '${HA_LANG}'. Sensoren werden auf Englisch angelegt."
    else
        SENSOR_LANG="de"
        bashio::log.info "Home Assistant Systemsprache nicht ermittelbar, verwende Standard: Deutsch (de)."
    fi
else
    SENSOR_LANG="${CONFIG_LANG}"
    bashio::log.info "Sensorsprache manuell konfiguriert: ${SENSOR_LANG}"
fi

if [ "$AUTO_CREATE" = "true" ]; then
    bashio::log.info "Automatische Sensorerstellung (MQTT Auto-Discovery): AKTIVIERT (Schema: ${ENTITY_NAMING}, Sprache: ${SENSOR_LANG}, Einheit: ${POWER_UNIT})"
else
    bashio::log.info "Automatische Sensorerstellung (MQTT Auto-Discovery): DEAKTIVIERT"
fi

if [ "$LEGACY_RAW_SENSORS" = "true" ]; then
    bashio::log.info "Klassische pyess Rohdaten-Sensoren (sensor.ess_ess_*): AKTIVIERT (Volle Abwärtskompatibilität)"
fi

# 4. Prepare CLI Arguments
ARGS=()
if [ -n "$ESS_PASSWORD" ]; then
    ARGS+=("--ess_password" "${ESS_PASSWORD}")
fi
if bashio::config.has_value 'installer_password'; then
    INSTALLER_PASSWORD=$(bashio::config 'installer_password')
    if [ -n "$INSTALLER_PASSWORD" ]; then
        ARGS+=("--installer_password" "${INSTALLER_PASSWORD}")
        bashio::log.info "Installateur-Passwort konfiguriert (Erweiterter Zugriff auf Sicherheits- und Batterieeinstellungen aktiv)."
    fi
fi
ARGS+=("--mqtt_server" "${MQTT_HOST}")
ARGS+=("--mqtt_port" "${MQTT_PORT}")
ARGS+=("--interval_seconds" "${INTERVAL}")
ARGS+=("--auto_create_sensors" "${AUTO_CREATE}")
ARGS+=("--sensor_language" "${SENSOR_LANG}")
ARGS+=("--power_unit" "${POWER_UNIT}")
ARGS+=("--entity_naming" "${ENTITY_NAMING}")
ARGS+=("--legacy_raw_sensors" "${LEGACY_RAW_SENSORS}")

if bashio::config.has_value 'ess_host'; then
    ESS_HOST=$(bashio::config 'ess_host')
    bashio::log.info "Feste LG ESS IP/Host konfiguriert: ${ESS_HOST}"
    ARGS+=("--ess_host" "${ESS_HOST}")
else
    bashio::log.info "Suche LG ESS automatisch im lokalen Netzwerk..."
fi

if [ -n "$MQTT_USER" ]; then
    ARGS+=("--mqtt_user" "${MQTT_USER}")
fi
if [ -n "$MQTT_PASSWORD" ]; then
    ARGS+=("--mqtt_password" "${MQTT_PASSWORD}")
fi
if [ -n "$LEGACY_SENSORS" ]; then
    ARGS+=("--hass_autoconfig_sensors" "${LEGACY_SENSORS}")
fi

bashio::log.info "Starte LG ESS MQTT Bridge (Verbinde mit MQTT-Server ${MQTT_HOST}:${MQTT_PORT})..."

# 5. Continuous run loop with auto-reconnect
while true; do
    if python3 /usr/share/lgess_mqtt.py "${ARGS[@]}"; then
        bashio::log.warning "lgess_mqtt wurde beendet. Starte in 5 Sekunden neu..."
    else
        bashio::log.warning "Verbindung zu LG ESS oder MQTT unterbrochen. Neuer Versuch in 5 Sekunden..."
    fi
    sleep 5
done
