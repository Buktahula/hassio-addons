#!/usr/bin/with-contenv bashio
set -e

CONFIG="/etc/essmqtt.conf"

bashio::log.info "Initialize the essmqtt configuration..."

> "${CONFIG}"
# settings
    ess_password=$(bashio::config "options.ess_password")
    mqtt_server=$(bashio::config "options.mqtt_server")
    mqtt_user=$(bashio::config "options.mqtt_user")
    mqtt_password=$(bashio::config "options.mqtt_password")
    interval_seconds=$(bashio::config "options.interval_seconds")
>> "${CONFIG}"

#/usr/local/bin/essmqtt --config_file /etc/essmqtt.conf
bin/bash
