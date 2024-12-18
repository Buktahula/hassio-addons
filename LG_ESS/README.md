# Home Assistant Add-on:  LG ESS Solar

Python library for LG ESS Solar power converters with EnerVU app compatibility
from https://github.com/gluap/pyess in a Docker Container for Home Assistant.

Copyright (c) 2019-2020 Paul Görgen

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

![Supports aarch64 Architecture][aarch64-shield] ![Supports amd64 Architecture][amd64-shield] ![Supports armhf Architecture][armhf-shield] ![Supports armv7 Architecture][armv7-shield] ![Supports i386 Architecture][i386-shield]

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armhf-shield]: https://img.shields.io/badge/armhf-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-red.svg
[i386-shield]: https://img.shields.io/badge/i386-yes-red.svg

## Requirements

### Install and configure MQTT broker for Home Assistant like:
https://github.com/home-assistant/addons/tree/master/mosquitto

### Fetch the device password

First method:

1.You can simply use your router to look up the MAC address of your LG ESS Solar power converter. The password is exactly that but without the colons.
For the MAC address a3:4d:c2:03:0c:ef your password will be a34dc2030cef. That’s it. (Not my MAC address, only an example)


If the first method not work:

1. You have to install the phyton App on your Android device.
https://play.google.com/store/apps/details?id=ru.iiec.pydroid3&hl=de&gl=US

2. To fetch the device password you need to be connected to the devices Wi-Fi. ** Once you are on the Wi-Fi you can
open The Python App on Mobile phone go to the Terminal run the following command to get the password.

   pip install pyess
   
   esscli --action get_password

3. Write the password down

### Configure the Addon

ess_password: "the written down password of your LG ESS Converter."

mqtt_server: "your configured mqtt server."

mqtt_usser: "your configured mqtt broker user."

mqtt_password: "your configured mqtt broker password."

interval_seconds: "set the interval."

hass_autoconfig_sensors: "preconfigured all possible Converter sensors."

### Sensor example
4. Here you can find a German example for the sensor.yaml to use the whole thing in the Home Assistant Energy Dashboard:
https://github.com/Buktahula/hassio-addons/blob/main/LG_ESS/sensor.yaml

