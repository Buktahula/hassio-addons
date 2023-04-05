# Home Assistant Add-on:  LG ESS Solar
Python library for LG ESS Solar power converters with EnerVU app compatibility


Fetch the device password
-------------------------
1. You have to installat the Phyton App on yout Android device.

https://play.google.com/store/apps/details?id=ru.iiec.pydroid3&hl=de&gl=US
2. To fetch the device password you need to be connected to the devices wifi.** Once you are on the wifi you can
run the following to get the password.
3. Open The Python App on Smatphone and got to Terminal

   Type the flolowing comand
   -------------------------
   pip install pyess
   
   esscli --action get_password

Write the password down, it seems it is a static password per device:
