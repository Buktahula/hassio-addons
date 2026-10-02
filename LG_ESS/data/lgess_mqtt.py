#!/usr/bin/env python3
"""
LG ESS MQTT Bridge & Auto-Discovery for Home Assistant
Communicates with LG ESS solar power converters & battery storage via local API (pyess),
publishes raw and calculated telemetry to MQTT, and registers clean Home Assistant sensors
via MQTT Auto-Discovery with full multi-language localization (DE / EN).
"""

import argparse
import asyncio
import json
import logging
import sys
import aiohttp
import aiohttp.client_exceptions
from aiomqtt import Client, MqttError

from pyess.aio_ess import ESS
from pyess.ess import autodetect_ess

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger("lgess_mqtt")


def str_to_bool(val):
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("true", "1", "yes", "on", "t")


def safe_float(val, default=0.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def calc_autarky(h, c):
    load_sum = safe_float(c.get("LOAD", {}).get("today_load_consumption_sum", 0))
    grid_purchase = safe_float(c.get("GRID", {}).get("today_grid_power_purchase_energy", 0))
    if load_sum > 0:
        val = 100.0 - (grid_purchase * 100.0 / load_sum)
        return round(max(0.0, min(100.0, val)), 1)
    return 100.0


DEVICE_INFO = {
    "identifiers": ["lg_ess_inverter"],
    "name": "LG ESS",
    "manufacturer": "LG Electronics",
    "model": "ESS Home",
    "sw_version": "0.1.3",
}

# Sensor definitions with localized names, units, device classes, and extractors
SENSOR_DEFINITIONS = [
    # -------------------------------------------------------------------------
    # ⚡ Real-time Power Values
    # -------------------------------------------------------------------------
    {
        "id": "actual_grid_sell",
        "unique_id": "lgess_actual_grid_sell",
        "name": {"de": "Aktuelle Netzeinspeisung", "en": "Current Grid Feed-in"},
        "device_class": "power",
        "state_class": "measurement",
        "icon": "mdi:transmission-tower-export",
        "type": "power",
        "calc": lambda h, c: (
            safe_float(c.get("GRID", {}).get("active_power", 0))
            if str(h.get("direction", {}).get("is_grid_selling_", "0")) == "1"
            else 0.0
        ),
    },
    {
        "id": "actual_grid_buy",
        "unique_id": "lgess_actual_grid_buy",
        "name": {"de": "Aktueller Netzbezug", "en": "Current Grid Consumption"},
        "device_class": "power",
        "state_class": "measurement",
        "icon": "mdi:transmission-tower-import",
        "type": "power",
        "calc": lambda h, c: (
            safe_float(c.get("GRID", {}).get("active_power", 0))
            if str(h.get("direction", {}).get("is_grid_buying_", "0")) == "1"
            else 0.0
        ),
    },
    {
        "id": "actual_battery_charge",
        "unique_id": "lgess_actual_battery_charge",
        "name": {"de": "Aktuelle Batterieladung", "en": "Current Battery Charging"},
        "device_class": "power",
        "state_class": "measurement",
        "icon": "mdi:battery-charging-high",
        "type": "power",
        "calc": lambda h, c: (
            safe_float(c.get("BATT", {}).get("dc_power", 0))
            if str(h.get("direction", {}).get("is_battery_charging_", "0")) == "1"
            else 0.0
        ),
    },
    {
        "id": "actual_battery_discharge",
        "unique_id": "lgess_actual_battery_discharge",
        "name": {"de": "Aktuelle Batterientladung", "en": "Current Battery Discharging"},
        "device_class": "power",
        "state_class": "measurement",
        "icon": "mdi:battery-arrow-down",
        "type": "power",
        "calc": lambda h, c: (
            safe_float(c.get("BATT", {}).get("dc_power", 0))
            if str(h.get("direction", {}).get("is_battery_discharging_", "0")) == "1"
            else 0.0
        ),
    },
    {
        "id": "actual_generation_pv_full",
        "unique_id": "lgess_actual_generation_pv_full",
        "name": {"de": "Aktuelle PV-Erzeugung Gesamt", "en": "Current Solar Generation Total"},
        "device_class": "power",
        "state_class": "measurement",
        "icon": "mdi:solar-power",
        "type": "power",
        "calc": lambda h, c: safe_float(h.get("statistics", {}).get("pcs_pv_total_power", 0)),
    },
    {
        "id": "actual_generation_pv_1",
        "unique_id": "lgess_actual_generation_pv_1",
        "name": {"de": "Aktuelle PV-Erzeugung String 1", "en": "Current Solar Generation String 1"},
        "device_class": "power",
        "state_class": "measurement",
        "icon": "mdi:solar-panel",
        "type": "power",
        "calc": lambda h, c: safe_float(c.get("PV", {}).get("pv1_power", 0)),
    },
    {
        "id": "actual_generation_pv_2",
        "unique_id": "lgess_actual_generation_pv_2",
        "name": {"de": "Aktuelle PV-Erzeugung String 2", "en": "Current Solar Generation String 2"},
        "device_class": "power",
        "state_class": "measurement",
        "icon": "mdi:solar-panel",
        "type": "power",
        "calc": lambda h, c: safe_float(c.get("PV", {}).get("pv2_power", 0)),
    },
    {
        "id": "actual_consuming_house",
        "unique_id": "lgess_actual_consuming_house",
        "name": {"de": "Aktueller Hausverbrauch", "en": "Current House Consumption"},
        "device_class": "power",
        "state_class": "measurement",
        "icon": "mdi:home-lightning-bolt",
        "type": "power",
        "calc": lambda h, c: safe_float(
            c.get("LOAD", {}).get("load_power", h.get("statistics", {}).get("load_power", 0))
        ),
    },

    # -------------------------------------------------------------------------
    # 📊 Daily Energy Values (kWh) for HA Energy Dashboard
    # -------------------------------------------------------------------------
    {
        "id": "daily_grid_buy",
        "unique_id": "lgess_daily_grid_buy",
        "name": {"de": "Tagesnetzbezug", "en": "Daily Grid Consumption"},
        "device_class": "energy",
        "state_class": "total_increasing",
        "unit": "kWh",
        "icon": "mdi:transmission-tower-import",
        "calc": lambda h, c: round(safe_float(c.get("GRID", {}).get("today_grid_power_purchase_energy", 0)) * 0.001, 2),
    },
    {
        "id": "energy_sell_today",
        "unique_id": "lgess_energy_sell_today",
        "name": {"de": "Tagesnetzeinspeisung", "en": "Daily Grid Feed-in"},
        "device_class": "energy",
        "state_class": "total_increasing",
        "unit": "kWh",
        "icon": "mdi:transmission-tower-export",
        "calc": lambda h, c: round(
            safe_float(
                h.get("statistics", {}).get(
                    "current_grid_feed_in_energy",
                    c.get("GRID", {}).get("today_grid_feed_in_energy", 0),
                )
            )
            * 0.001,
            2,
        ),
    },
    {
        "id": "energy_generation_today",
        "unique_id": "lgess_energy_generation_today",
        "name": {"de": "Tages-Solarerzeugung", "en": "Daily Solar Generation"},
        "device_class": "energy",
        "state_class": "total_increasing",
        "unit": "kWh",
        "icon": "mdi:solar-power",
        "calc": lambda h, c: round(
            safe_float(
                h.get("statistics", {}).get(
                    "current_pv_generation_sum",
                    c.get("PV", {}).get("today_pv_generation_sum", 0),
                )
            )
            * 0.001,
            2,
        ),
    },
    {
        "id": "energy_batt_charge_today",
        "unique_id": "lgess_energy_batt_charge_today",
        "name": {"de": "Tages-Batterieladung", "en": "Daily Battery Charge"},
        "device_class": "energy",
        "state_class": "total_increasing",
        "unit": "kWh",
        "icon": "mdi:battery-arrow-up",
        "calc": lambda h, c: round(safe_float(c.get("BATT", {}).get("today_batt_charge_energy", 0)) * 0.001, 2),
    },
    {
        "id": "energy_batt_discharge_today",
        "unique_id": "lgess_energy_batt_discharge_today",
        "name": {"de": "Tages-Batterieentladung", "en": "Daily Battery Discharge"},
        "device_class": "energy",
        "state_class": "total_increasing",
        "unit": "kWh",
        "icon": "mdi:battery-arrow-down",
        "calc": lambda h, c: round(safe_float(c.get("BATT", {}).get("today_batt_discharge_enery", 0)) * 0.001, 2),
    },
    {
        "id": "daily_verbrauch_gesamt",
        "unique_id": "lgess_daily_verbrauch_gesamt",
        "name": {"de": "Tages-Hausverbrauch Gesamt", "en": "Daily House Consumption Total"},
        "device_class": "energy",
        "state_class": "total_increasing",
        "unit": "kWh",
        "icon": "mdi:home-lightning-bolt",
        "calc": lambda h, c: round(safe_float(c.get("LOAD", {}).get("today_load_consumption_sum", 0)) * 0.001, 2),
    },

    # -------------------------------------------------------------------------
    # 🔋 Battery & Status Metrics
    # -------------------------------------------------------------------------
    {
        "id": "battery_load_percent",
        "unique_id": "lgess_battery_load_percent",
        "name": {"de": "Batterieladestand", "en": "Battery State of Charge"},
        "device_class": "battery",
        "state_class": "measurement",
        "unit": "%",
        "calc": lambda h, c: round(safe_float(c.get("BATT", {}).get("soc", h.get("statistics", {}).get("bat_user_soc", 0))), 1),
    },
    {
        "id": "energy_day_self_consumption_rate",
        "unique_id": "lgess_energy_day_self_consumption_rate",
        "name": {"de": "Eigenverbrauchsrate (heute)", "en": "Self-Consumption Rate (today)"},
        "state_class": "measurement",
        "unit": "%",
        "icon": "mdi:chart-arc",
        "calc": lambda h, c: round(safe_float(h.get("statistics", {}).get("current_day_self_consumption", 0)), 1),
    },
    {
        "id": "calculated_self_sufficiency",
        "unique_id": "lgess_calculated_self_sufficiency",
        "name": {"de": "Autarkiegrad (heute)", "en": "Autarky Rate (today)"},
        "state_class": "measurement",
        "unit": "%",
        "icon": "mdi:home-battery",
        "calc": calc_autarky,
    },
    {
        "id": "pv1_voltage",
        "unique_id": "lgess_pv1_voltage",
        "name": {"de": "PV String 1 Spannung", "en": "PV String 1 Voltage"},
        "device_class": "voltage",
        "state_class": "measurement",
        "unit": "V",
        "icon": "mdi:sine-wave",
        "calc": lambda h, c: round(safe_float(c.get("PV", {}).get("pv1_voltage", 0)), 1),
    },
    {
        "id": "pv2_voltage",
        "unique_id": "lgess_pv2_voltage",
        "name": {"de": "PV String 2 Spannung", "en": "PV String 2 Voltage"},
        "device_class": "voltage",
        "state_class": "measurement",
        "unit": "V",
        "icon": "mdi:sine-wave",
        "calc": lambda h, c: round(safe_float(c.get("PV", {}).get("pv2_voltage", 0)), 1),
    },
    {
        "id": "grid_freq",
        "unique_id": "lgess_grid_freq",
        "name": {"de": "Netzfrequenz", "en": "Grid Frequency"},
        "device_class": "frequency",
        "state_class": "measurement",
        "unit": "Hz",
        "icon": "mdi:sine-wave",
        "calc": lambda h, c: round(safe_float(c.get("GRID", {}).get("freq", 0)), 2),
    },
    {
        "id": "battery_status",
        "unique_id": "lgess_battery_status",
        "name": {"de": "Batteriestatus", "en": "Battery Status"},
        "icon": "mdi:battery-heart",
        "calc": lambda h, c: str(c.get("BATT", {}).get("status", h.get("statistics", {}).get("bat_status", "unknown"))),
    },
    {
        "id": "operation_mode",
        "unique_id": "lgess_operation_mode",
        "name": {"de": "Betriebsmodus", "en": "Operation Mode"},
        "icon": "mdi:cog-sync",
        "calc": lambda h, c: str(c.get("PCS", {}).get("operation_mode", "unknown")),
    },
]

SWITCH_DEFINITIONS = [
    {
        "id": "winter_mode",
        "unique_id": "lgess_switch_winter_mode",
        "name": {"de": "Wintermodus", "en": "Winter Mode"},
        "icon": "mdi:snowflake",
        "command_topic": "ess/control/winter_mode",
        "state_topic": "ess/sensors/winter_mode",
    },
    {
        "id": "fastcharge",
        "unique_id": "lgess_switch_fastcharge",
        "name": {"de": "Schnellladung", "en": "Fast Charge"},
        "icon": "mdi:battery-charging-wireless-alert",
        "command_topic": "ess/control/fastcharge",
        "state_topic": "ess/sensors/fastcharge",
    },
    {
        "id": "active",
        "unique_id": "lgess_switch_active",
        "name": {"de": "ESS Aktiv", "en": "ESS Active"},
        "icon": "mdi:power",
        "command_topic": "ess/control/active",
        "state_topic": "ess/sensors/active",
    },
]


async def recursive_publish_dict(mqtt_client, prefix, data):
    """Publishes dictionary recursively to raw MQTT topics."""
    for key, value in data.items():
        topic = f"{prefix}/{key}"
        if isinstance(value, dict):
            await recursive_publish_dict(mqtt_client, topic, value)
        else:
            await mqtt_client.publish(topic, str(value))


async def publish_discovery(mqtt_client, lang="de", power_unit="kW"):
    """Publishes Home Assistant MQTT discovery payloads for all sensors and switches."""
    logger.info(f"Publishing Home Assistant MQTT discovery (language: {lang}, power_unit: {power_unit})...")

    # 1. Sensors
    for s in SENSOR_DEFINITIONS:
        name = s["name"].get(lang, s["name"]["de"])
        unit = power_unit if s.get("type") == "power" else s.get("unit")
        
        payload = {
            "name": name,
            "unique_id": s["unique_id"],
            "object_id": s["unique_id"],
            "state_topic": f"ess/sensors/{s['id']}",
            "device": DEVICE_INFO,
        }
        if "device_class" in s:
            payload["device_class"] = s["device_class"]
        if "state_class" in s:
            payload["state_class"] = s["state_class"]
        if unit:
            payload["unit_of_measurement"] = unit
        if "icon" in s:
            payload["icon"] = s["icon"]

        discovery_topic = f"homeassistant/sensor/lg_ess/{s['id']}/config"
        await mqtt_client.publish(discovery_topic, json.dumps(payload), retain=True, qos=1)

    # 2. Switches
    for sw in SWITCH_DEFINITIONS:
        name = sw["name"].get(lang, sw["name"]["de"])
        payload = {
            "name": name,
            "unique_id": sw["unique_id"],
            "object_id": sw["unique_id"],
            "command_topic": sw["command_topic"],
            "state_topic": sw["state_topic"],
            "payload_on": "ON",
            "payload_off": "OFF",
            "device": DEVICE_INFO,
            "icon": sw["icon"],
        }
        discovery_topic = f"homeassistant/switch/lg_ess/{sw['id']}/config"
        await mqtt_client.publish(discovery_topic, json.dumps(payload), retain=True, qos=1)

    logger.info(f"Successfully published {len(SENSOR_DEFINITIONS)} sensors and {len(SWITCH_DEFINITIONS)} switches to MQTT Discovery.")


async def handle_control(client, ess):
    """Listens for switch commands on ess/control/# and interacts with LG ESS."""
    try:
        await client.subscribe("ess/control/#")
        await client.subscribe("/ess/control/#")

        async with client.messages() as messages:
            async for msg in messages:
                topic = str(msg.topic)
                try:
                    payload_raw = msg.payload.decode().strip()
                    state = str_to_bool(payload_raw)
                    logger.info(f"Control command received on {topic}: {payload_raw} (parsed={state})")

                    if "winter_mode" in topic:
                        if state:
                            await ess.winter_off()
                        else:
                            await ess.winter_on()
                        await client.publish("ess/sensors/winter_mode", "ON" if state else "OFF", retain=True)

                    elif "fastcharge" in topic:
                        if state:
                            await ess.fastcharge_on()
                        else:
                            await ess.fastcharge_off()
                        await client.publish("ess/sensors/fastcharge", "ON" if state else "OFF", retain=True)

                    elif "active" in topic:
                        if state:
                            await ess.switch_on()
                        else:
                            await ess.switch_off()
                        await client.publish("ess/sensors/active", "ON" if state else "OFF", retain=True)

                except Exception as ex:
                    logger.warning(f"Error handling control message on {topic}: {ex}")
    except (asyncio.CancelledError, MqttError):
        pass
    except Exception as ex:
        logger.warning(f"Control handler exited unexpectedly: {ex}")


async def poll_loop(ess, client, interval_seconds=5, auto_create=True, lang="de", power_unit="kW"):
    """Main polling loop: queries LG ESS, calculates metrics, and publishes to MQTT."""
    logger.info("Starting LG ESS polling loop...")
    loop_count = 0

    while True:
        try:
            # 1. Fetch live states from LG ESS
            home = await ess.get_state("home")
            common = await ess.get_state("common")

            # 2. Publish raw topics (for backwards compatibility)
            await recursive_publish_dict(client, "ess/home", home)
            await recursive_publish_dict(client, "ess/common", common)

            # 3. Publish computed sensors
            if auto_create:
                for s in SENSOR_DEFINITIONS:
                    try:
                        val = s["calc"](home, common)
                        if s.get("type") == "power":
                            if power_unit == "kW":
                                val = round(val * 0.001, 3)
                            else:
                                val = round(val, 1)
                        await client.publish(f"ess/sensors/{s['id']}", str(val))
                    except Exception as calc_err:
                        logger.debug(f"Calculation error for {s['id']}: {calc_err}")

            loop_count += 1
            if loop_count % 60 == 1:
                logger.info(f"Poll cycle {loop_count} successful. ESS is healthy.")

        except (aiohttp.client_exceptions.ClientError, TimeoutError, ConnectionError) as err:
            logger.warning(f"Temporary communication error with LG ESS: {err}. Retrying in {interval_seconds}s...")
        except MqttError as err:
            logger.warning(f"MQTT connection lost: {err}. Reconnecting...")
            raise

        await asyncio.sleep(interval_seconds)


async def main():
    parser = argparse.ArgumentParser(description="LG ESS MQTT Bridge with HA Auto-Discovery")
    parser.add_argument("--ess_password", required=True, help="LG ESS password")
    parser.add_argument("--ess_host", default=None, help="LG ESS IP or hostname")
    parser.add_argument("--mqtt_server", required=True, help="MQTT Broker host")
    parser.add_argument("--mqtt_port", default=1883, type=int, help="MQTT Broker port")
    parser.add_argument("--mqtt_user", default=None, help="MQTT Username")
    parser.add_argument("--mqtt_password", default=None, help="MQTT Password")
    parser.add_argument("--interval_seconds", default=5, type=int, help="Polling interval in seconds")
    parser.add_argument("--auto_create_sensors", default="true", help="Auto-create HA sensors via MQTT Discovery")
    parser.add_argument("--sensor_language", default="de", help="Language for sensor names (de / en)")
    parser.add_argument("--power_unit", default="kW", choices=["kW", "W"], help="Power unit for real-time sensors")
    parser.add_argument("--hass_autoconfig_sensors", default=None, help="Legacy pyess autoconfig list (optional)")

    args = parser.parse_args()

    auto_create = str_to_bool(args.auto_create_sensors)
    lang = "de" if str(args.sensor_language).lower().startswith("de") else "en"
    power_unit = args.power_unit

    loop = asyncio.get_running_loop()

    # Determine LG ESS IP
    if args.ess_host:
        ip, name = args.ess_host, args.ess_host
    else:
        logger.info("Auto-detecting LG ESS in local network...")
        ip, name = await loop.run_in_executor(None, autodetect_ess)
        logger.info(f"Discovered LG ESS at {ip} ({name})")

    logger.info(f"Connecting to LG ESS at {ip}...")
    ess = await ESS.create(name, args.ess_password, ip)

    while True:
        try:
            logger.info(f"Connecting to MQTT Broker at {args.mqtt_server}:{args.mqtt_port}...")
            async with Client(
                hostname=args.mqtt_server,
                port=args.mqtt_port,
                username=args.mqtt_user,
                password=args.mqtt_password,
            ) as client:
                logger.info("Connected to MQTT Broker!")

                # Publish Home Assistant MQTT Discovery configs once on connect
                if auto_create:
                    await publish_discovery(client, lang=lang, power_unit=power_unit)

                # Start control listener task
                control_task = asyncio.create_task(handle_control(client, ess))

                try:
                    await poll_loop(
                        ess,
                        client,
                        interval_seconds=args.interval_seconds,
                        auto_create=auto_create,
                        lang=lang,
                        power_unit=power_unit,
                    )
                finally:
                    control_task.cancel()
                    await asyncio.gather(control_task, return_exceptions=True)

        except (MqttError, TimeoutError, ConnectionError) as mqtt_err:
            logger.warning(f"Connection lost to MQTT Broker: {mqtt_err}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as ex:
            logger.error(f"Unexpected error: {ex}. Retrying in 5 seconds...", exc_info=True)
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("LG ESS MQTT bridge stopped by user.")
        sys.exit(0)
