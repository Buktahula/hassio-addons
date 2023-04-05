#!/usr/bin/with-contenv bashio
set -e

CONFIG="/etc/essmqtt.conf"

bashio::log.info "Initialize the essmqtt configuration..."

> "${CONFIG}"
# settings
for option in $(bashio::config 'options|keys'); do
    ess_password=$(bashio::config "options[${option}].ess_password")
    mqtt_server=$(bashio::config "options[${option}].mqtt_server")
    mqtt_user=$(bashio::config "options[${option}].mqtt_user")
    mqtt_password=$(bashio::config "options[${option}].mqtt_password")
    interval_seconds=$(bashio::config "options[${option}].interval_seconds")
>> "${CONFIG}"
done
