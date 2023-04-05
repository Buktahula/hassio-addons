# Home Assistant Add-on:  LG ESS Solar

Python library for LG ESS Solar power converters with EnerVU app compatibility

![Supports aarch64 Architecture][aarch64-shield] ![Supports amd64 Architecture][amd64-shield] ![Supports armhf Architecture][armhf-shield] ![Supports armv7 Architecture][armv7-shield] ![Supports i386 Architecture][i386-shield]

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armhf-shield]: https://img.shields.io/badge/armhf-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-no-red.svg
[i386-shield]: https://img.shields.io/badge/i386-no-red.svg


## Install and configure MQTT broker for Home Assistant.
https://github.com/home-assistant/addons/tree/master/mosquitto

## Fetch the device password
1. You have to install the phyton App on your Android device.
https://play.google.com/store/apps/details?id=ru.iiec.pydroid3&hl=de&gl=US

2. To fetch the device password you need to be connected to the devices Wi-Fi. ** Once you are on the Wi-Fi you can
open The Python App on Mobile phone go to the Terminal run the following command to get the password.

   pip install pyess
   
   esscli --action get_password

3. Write the password down

## Configure the Addon

ess_password: "the written down password of your LG ESS Converter."

mqtt_server: "your configured mqtt server."

mqtt_usser: "your configured mqtt broker user."

mqtt_password: "your configured mqtt broker password."

interval_seconds: "set the interval."

hass_autoconfig_sensors: "preconfigured all possible Converter sensors."

