# Home Assistant Add-on:  LG ESS Solar
Python library for LG ESS Solar power converters with EnerVU app compatibility

![Supports aarch64 Architecture][aarch64-shield] ![Supports amd64 Architecture][amd64-shield] ![Supports armhf Architecture][armhf-shield] ![Supports armv7 Architecture][armv7-shield] ![Supports i386 Architecture][i386-shield]


Command Line
------------
This module comes with a rudimentary command line interface that allows for the following actions.

Fetch the device password
.........................

Caveat: **To fetch the device password you need to be connected to the devices wifi.** Once you are on the wifi you can
run the following to get the password. Write it down, it seems it is a static password per device::

    esscli --action get_password

The command assumes that the ess device is listening on ``192.168.23.1`` on its own wifi, in my setup it reproducibly
chooses that IP.

Find the esses on your network
..............................
Get a list of ESS devices on the local network (your home wifi, not the one of ess)::

    esscli --action list_ess


Fetch the state from ess as json
................................
fetch a bunch of json states as json and display the result on the command line::

    esscli --action get_data --password <your ess_password>

Examples for the data available:
- current power from and to the grid and the battery
- current voltage and power from both strings of the photovoltaic system independently
- current ip address
- details on grid power, battery state, daily and monthly statistics

Graphite wrapper
................
