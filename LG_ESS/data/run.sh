#!/usr/bin/with-contenv bashio
set -e

CONFIG="/etc/essmqtt.conf"

bashio::log.info "Initialize the essmqtt configuration..."

echo "ess_password=$(bashio::config "ess_password")" > $CONFIG
echo "mqtt_server=$(bashio::config "mqtt_server")" >> $CONFIG
echo "mqtt_user=$(bashio::config "mqtt_user")" >> $CONFIG
echo "mqtt_password=$(bashio::config "mqtt_password")" >> $CONFIG
echo "interval_seconds=$(bashio::config "interval_seconds")" >> $CONFIG
echo "hass_autoconfig_sensors=$(bashio::config "hass_autoconfig_sensors")" >> $CONFIG

/usr/local/bin/essmqtt --config_file /etc/essmqtt.conf
