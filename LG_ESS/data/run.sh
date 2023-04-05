#!/usr/bin/with-contenv bashio
set -e

CONFIG="/etc/essmqtt.conf"

bashio::log.info "Initialize the essmqtt configuration..."

echo "ess_password=$(bashio::config "options.ess_password")" > $CONFIG
echo "mqtt_server=$(bashio::config "options.mqtt_server")" >> $CONFIG
echo "mqtt_user=$(bashio::config "options.mqtt_user")" >> $CONFIG
echo "mqtt_password=$(bashio::config "options.mqtt_password")" >> $CONFIG
echo "interval_seconds=$(bashio::config "options.interval_seconds")" >> $CONFIG
echo "hass_autoconfig_sensors=$(bashio::config "options.hass_autoconfig_sensors")" >> $CONFIG

#/usr/local/bin/essmqtt --config_file /etc/essmqtt.conf
 /bin/sh
