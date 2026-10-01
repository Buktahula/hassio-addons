#!/usr/bin/with-contenv bashio
set -e

bashio::log.info "Starting LG ESS Home Assistant Add-on..."

# 1. Validate ESS Password
if ! bashio::config.has_value 'ess_password'; then
    bashio::log.fatal "Kein ESS-Passwort konfiguriert!"
    bashio::log.fatal "Bitte trage das Passwort (in der Regel die MAC-Adresse deines LG ESS ohne Doppelpunkte in Kleinbuchstaben) in den Add-on-Einstellungen ein."
    exit 1
fi

ESS_PASSWORD=$(bashio::config 'ess_password')

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

# 3. Interval & Autoconfig Sensors
INTERVAL=$(bashio::config 'interval_seconds' '5')
SENSORS=$(bashio::config 'hass_autoconfig_sensors')

# 4. Prepare CLI Arguments
ARGS=()
ARGS+=("--ess_password" "${ESS_PASSWORD}")
ARGS+=("--mqtt_server" "${MQTT_HOST}")
ARGS+=("--mqtt_port" "${MQTT_PORT}")
ARGS+=("--interval_seconds" "${INTERVAL}")

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

if [ -n "$SENSORS" ]; then
    ARGS+=("--hass_autoconfig_sensors" "${SENSORS}")
fi

bashio::log.info "Starte essmqtt (Verbinde mit MQTT-Server ${MQTT_HOST}:${MQTT_PORT})..."

# 5. Continuous run loop with auto-reconnect on temporary network drop
while true; do
    if /usr/local/bin/essmqtt "${ARGS[@]}"; then
        bashio::log.warning "essmqtt wurde beendet. Starte in 5 Sekunden neu..."
    else
        bashio::log.warning "Verbindung zu LG ESS oder MQTT unterbrochen. Neuer Versuch in 5 Sekunden..."
    fi
    sleep 5
done
