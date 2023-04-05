#!/usr/bin/with-contenv bashio
set -e

CONFIG="/etc/essmqtt.conf"

bashio::log.info "Initialize the essmqtt configuration..."
# User access
{
    echo "user = \"root\""
    echo "group = \"plugdev\""
    echo "ignoreControllerConfirmation = \"false\"" 
} > "${CONFIG}"

# settings
for setting in $(bashio::config 'settings|setting'); do
    ess_password=$(bashio::config "settings[${setting}].ess_password")
    mqtt_server=$(bashio::config "settings[${setting}].mqtt_server")
    mqtt_user=$(bashio::config "settings[${setting}].mqtt_user")
    mqtt_password=$(bashio::config "settings[${setting}].mqtt_password")
    interval_seconds=$(bashio::config "settings[${setting}].interval_seconds")
>> "${CONFIG}"
done
