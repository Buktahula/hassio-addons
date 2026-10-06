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
import os
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
    "sw_version": "0.1.10",
}

# Sensor definitions with localized names, units, device classes, and extractors
SENSOR_DEFINITIONS = [
    # -------------------------------------------------------------------------
    # ⚡ Real-time Power Values
    # -------------------------------------------------------------------------
    {
        "id": "actual_grid_sell",
        "unique_id": "lgess_actual_grid_sell",
        "object_ids": {"de": "aktuelle_netzeinspeisung", "en": "current_grid_feed_in"},
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
        "object_ids": {"de": "aktueller_netzbezug", "en": "current_grid_consumption"},
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
        "object_ids": {"de": "aktuelle_batterieladung", "en": "current_battery_charging"},
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
        "object_ids": {"de": "aktuelle_batterientladung", "en": "current_battery_discharging"},
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
        "object_ids": {"de": "aktuelle_pv_erzeugung_gesamt", "en": "current_solar_generation_total"},
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
        "object_ids": {"de": "aktuelle_pv_erzeugung_string_1", "en": "current_solar_generation_string_1"},
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
        "object_ids": {"de": "aktuelle_pv_erzeugung_string_2", "en": "current_solar_generation_string_2"},
        "name": {"de": "Aktuelle PV-Erzeugung String 2", "en": "Current Solar Generation String 2"},
        "device_class": "power",
        "state_class": "measurement",
        "icon": "mdi:solar-panel",
        "type": "power",
        "calc": lambda h, c: safe_float(c.get("PV", {}).get("pv2_power", 0)),
    },
    {
        "id": "actual_generation_pv_3",
        "unique_id": "lgess_actual_generation_pv_3",
        "object_ids": {"de": "aktuelle_pv_erzeugung_string_3", "en": "current_solar_generation_string_3"},
        "name": {"de": "Aktuelle PV-Erzeugung String 3", "en": "Current Solar Generation String 3"},
        "device_class": "power",
        "state_class": "measurement",
        "icon": "mdi:solar-panel",
        "type": "power",
        "calc": lambda h, c: safe_float(c.get("PV", {}).get("pv3_power", 0)),
    },
    {
        "id": "actual_consuming_house",
        "unique_id": "lgess_actual_consuming_house",
        "object_ids": {"de": "aktueller_hausverbrauch", "en": "current_house_consumption"},
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
        "object_ids": {"de": "tagesnetzbezug", "en": "daily_grid_consumption"},
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
        "object_ids": {"de": "tagesnetzeinspeisung", "en": "daily_grid_feed_in"},
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
        "object_ids": {"de": "tages_solarerzeugung", "en": "daily_solar_generation"},
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
        "object_ids": {"de": "tages_batterieladung", "en": "daily_battery_charge"},
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
        "object_ids": {"de": "tages_batterieentladung", "en": "daily_battery_discharge"},
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
        "object_ids": {"de": "tages_hausverbrauch_gesamt", "en": "daily_house_consumption_total"},
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
        "object_ids": {"de": "batterie_ladestand", "en": "battery_state_of_charge"},
        "name": {"de": "Batterieladestand", "en": "Battery State of Charge"},
        "device_class": "battery",
        "state_class": "measurement",
        "unit": "%",
        "calc": lambda h, c: round(safe_float(c.get("BATT", {}).get("soc", h.get("statistics", {}).get("bat_user_soc", 0))), 1),
    },
    {
        "id": "energy_day_self_consumption_rate",
        "unique_id": "lgess_energy_day_self_consumption_rate",
        "object_ids": {"de": "eigenverbrauchsrate_heute", "en": "self_consumption_rate_today"},
        "name": {"de": "Eigenverbrauchsrate (heute)", "en": "Self-Consumption Rate (today)"},
        "state_class": "measurement",
        "unit": "%",
        "icon": "mdi:chart-arc",
        "calc": lambda h, c: round(safe_float(h.get("statistics", {}).get("current_day_self_consumption", 0)), 1),
    },
    {
        "id": "calculated_self_sufficiency",
        "unique_id": "lgess_calculated_self_sufficiency",
        "object_ids": {"de": "autarkie_grad_heute", "en": "autarky_rate_today"},
        "name": {"de": "Autarkiegrad (heute)", "en": "Autarky Rate (today)"},
        "state_class": "measurement",
        "unit": "%",
        "icon": "mdi:home-battery",
        "calc": calc_autarky,
    },
    {
        "id": "pv1_voltage",
        "unique_id": "lgess_pv1_voltage",
        "object_ids": {"de": "pv_string_1_spannung", "en": "pv_string_1_voltage"},
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
        "object_ids": {"de": "pv_string_2_spannung", "en": "pv_string_2_voltage"},
        "name": {"de": "PV String 2 Spannung", "en": "PV String 2 Voltage"},
        "device_class": "voltage",
        "state_class": "measurement",
        "unit": "V",
        "icon": "mdi:sine-wave",
        "calc": lambda h, c: round(safe_float(c.get("PV", {}).get("pv2_voltage", 0)), 1),
    },
    {
        "id": "pv3_voltage",
        "unique_id": "lgess_pv3_voltage",
        "object_ids": {"de": "pv_string_3_spannung", "en": "pv_string_3_voltage"},
        "name": {"de": "PV String 3 Spannung", "en": "PV String 3 Voltage"},
        "device_class": "voltage",
        "state_class": "measurement",
        "unit": "V",
        "icon": "mdi:sine-wave",
        "calc": lambda h, c: round(safe_float(c.get("PV", {}).get("pv3_voltage", 0)), 1),
    },
    {
        "id": "grid_freq",
        "unique_id": "lgess_grid_freq",
        "object_ids": {"de": "netzfrequenz", "en": "grid_frequency"},
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
        "object_ids": {"de": "batteriestatus", "en": "battery_status"},
        "name": {"de": "Batteriestatus", "en": "Battery Status"},
        "icon": "mdi:battery-heart",
        "calc": lambda h, c: str(c.get("BATT", {}).get("status", h.get("statistics", {}).get("bat_status", "unknown"))),
    },
    {
        "id": "operation_mode",
        "unique_id": "lgess_operation_mode",
        "object_ids": {"de": "betriebsmodus", "en": "operation_mode"},
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


# Legacy 2023 sensor.yaml mapping (exact friendly names and object_ids)
LEGACY_NAMES = {
    "actual_grid_sell": "aktuelle Netzeinspeisung",
    "actual_grid_buy": "aktueller Netzbezug",
    "daily_grid_buy": "Tagesbezug",
    "daily_verbrauch_gesamt": "Verbrauch gesamt",
    "actual_battery_charge": "aktuelle Batterieladung",
    "actual_battery_discharge": "aktuelle Batterientladung",
    "actual_generation_pv_full": "aktuelle Stromerzeugung PV Haus Gesamt",
    "actual_generation_pv_1": "aktuelle Stromerzeugung PV 1",
    "actual_generation_pv_2": "aktuelle Stromerzeugung PV 2",
    "actual_generation_pv_3": "aktuelle Stromerzeugung PV 3",
    "actual_consuming_house": "aktueller Stromverbrauch Gesamt",
    "energy_sell_today": "eingespeister Strom (heute)",
    "energy_generation_today": "erzeugter Strom (heute)",
    "energy_batt_charge_today": "Tages-Batterieladung",
    "energy_batt_discharge_today": "Tages-Batterieentladung",
    "battery_load_percent": "Batterie Ladestand",
    "energy_day_self_consumption_rate": "Eigenverbrauchsrate (heute)",
    "calculated_self_sufficiency": "Autarkie-Grad",
    "pv1_voltage": "PV String 1 Spannung",
    "pv2_voltage": "PV String 2 Spannung",
    "pv3_voltage": "PV String 3 Spannung",
    "grid_freq": "Netzfrequenz",
    "battery_status": "Batteriestatus",
    "operation_mode": "Betriebsmodus",
}

LEGACY_OBJECT_IDS = {
    "actual_grid_sell": "actual_grid_sell",
    "actual_grid_buy": "actual_grid_buy",
    "daily_grid_buy": "daily_grid_buy",
    "daily_verbrauch_gesamt": "daily_verbrauch_gesamt",
    "actual_battery_charge": "actual_battery_charge",
    "actual_battery_discharge": "actual_battery_discharge",
    "actual_generation_pv_full": "actual_generation_pv_full",
    "actual_generation_pv_1": "actual_generation_pv_1",
    "actual_generation_pv_2": "actual_generation_pv_2",
    "actual_generation_pv_3": "actual_generation_pv_3",
    "actual_consuming_house": "actual_consuming_house",
    "energy_sell_today": "energy_sell_today",
    "energy_generation_today": "energy_generation_today",
    "energy_batt_charge_today": "energy_batt_charge_today",
    "energy_batt_discharge_today": "energy_batt_discharge_today",
    "battery_load_percent": "battery_load_percent",
    "energy_day_self_consumption_rate": "energy_day_self_consumption_rate",
    "calculated_self_sufficiency": "solaredge_calculated_self_sufficiency",
    "pv1_voltage": "pv1_voltage",
    "pv2_voltage": "pv2_voltage",
    "pv3_voltage": "pv3_voltage",
    "grid_freq": "grid_freq",
    "battery_status": "battery_status",
    "operation_mode": "operation_mode",
}


async def recursive_publish_dict(mqtt_client, prefix, data):
    """Publishes dictionary recursively to raw MQTT topics."""
    for key, value in data.items():
        topic = f"{prefix}/{key}"
        if isinstance(value, dict):
            await recursive_publish_dict(mqtt_client, topic, value)
        else:
            await mqtt_client.publish(topic, str(value))


async def publish_discovery(mqtt_client, lang="de", power_unit="kW", entity_naming="legacy"):
    """Publishes Home Assistant MQTT discovery payloads for all sensors and switches."""
    logger.info(f"Publishing Home Assistant MQTT discovery (naming: {entity_naming}, language: {lang}, power_unit: {power_unit})...")

    # 1. Sensors
    for s in SENSOR_DEFINITIONS:
        s_id = s["id"]
        if entity_naming == "legacy":
            name = LEGACY_NAMES.get(s_id, s["name"].get(lang, s["name"]["de"]))
            obj_id = LEGACY_OBJECT_IDS.get(s_id, s_id)
        else:
            name = s["name"].get(lang, s["name"]["de"])
            obj_id = s.get("object_ids", {}).get(lang, s_id)

        unit = power_unit if s.get("type") == "power" else s.get("unit")
        
        payload = {
            "name": name,
            "unique_id": f"lgess_mqtt_{s_id}",
            "default_entity_id": f"sensor.{obj_id}",
            "object_id": obj_id,
            "state_topic": f"ess/sensors/{s_id}",
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

        discovery_topic = f"homeassistant/sensor/lg_ess/{s_id}/config"
        await mqtt_client.publish(discovery_topic, json.dumps(payload), retain=True, qos=1)

    # 2. Switches
    for sw in SWITCH_DEFINITIONS:
        sw_id = sw["id"]
        name = sw["name"].get(lang, sw["name"]["de"])
        obj_id = sw_id if entity_naming == "legacy" else sw["unique_id"]
        payload = {
            "name": name,
            "unique_id": sw["unique_id"],
            "default_entity_id": f"switch.{obj_id}",
            "object_id": obj_id,
            "command_topic": sw["command_topic"],
            "state_topic": sw["state_topic"],
            "payload_on": "ON",
            "payload_off": "OFF",
            "device": DEVICE_INFO,
            "icon": sw["icon"],
        }
        discovery_topic = f"homeassistant/switch/lg_ess/{sw_id}/config"
        await mqtt_client.publish(discovery_topic, json.dumps(payload), retain=True, qos=1)

    logger.info(f"Successfully published {len(SENSOR_DEFINITIONS)} sensors and {len(SWITCH_DEFINITIONS)} switches to MQTT Discovery.")


DEFAULT_LEGACY_RAW_SENSORS = (
    "ess/common/BATT/soc,ess/home/statistics/pcs_pv_total_power,ess/common/GRID/active_power,"
    "ess/common/LOAD/load_power,ess/home/statistics/pcs_pv_total_power,ess/home/statistics/batconv_power,"
    "ess/home/statistics/bat_use,ess/home/statistics/bat_status,ess/home/statistics/bat_user_soc,"
    "ess/home/statistics/load_power,ess/home/statistics/load_today,ess/home/statistics/grid_power,"
    "ess/home/statistics/current_day_self_consumption,ess/home/statistics/current_pv_generation_sum,"
    "ess/home/statistics/current_grid_feed_in_energy,ess/home/direction/is_direct_consuming_,"
    "ess/home/direction/is_battery_charging_,ess/home/direction/is_battery_discharging_,"
    "ess/home/direction/is_grid_selling_,ess/home/direction/is_grid_buying_,"
    "ess/home/direction/is_charging_from_grid_,ess/common/PV/brand,ess/common/PV/capacity,"
    "ess/common/PV/pv1_voltage,ess/common/PV/pv2_voltage,ess/common/PV/pv3_voltage,"
    "ess/common/PV/pv1_power,ess/common/PV/pv2_power,ess/common/PV/pv3_power,"
    "ess/common/PV/pv1_current,ess/common/PV/pv2_current,ess/common/PV/pv3_current,"
    "ess/common/PV/today_pv_generation_sum,ess/common/PV/today_month_pv_generation_sum,"
    "ess/common/BATT/status,ess/common/BATT/soc,ess/common/BATT/dc_power,"
    "ess/common/BATT/winter_setting,ess/common/BATT/winter_status,ess/common/BATT/safty_soc,"
    "ess/common/BATT/today_batt_discharge_enery,ess/common/BATT/today_batt_charge_energy,"
    "ess/common/BATT/month_batt_charge_energy,ess/common/BATT/month_batt_discharge_energy,"
    "ess/common/GRID/active_power,ess/common/GRID/a_phase,ess/common/GRID/freq,"
    "ess/common/GRID/today_grid_feed_in_energy,ess/common/GRID/today_grid_power_purchase_energy,"
    "ess/common/GRID/month_grid_feed_in_energy,ess/common/GRID/month_grid_power_purchase_energy,"
    "ess/common/LOAD/load_power,ess/common/LOAD/today_load_consumption_sum,"
    "ess/common/LOAD/today_pv_direct_consumption_enegy,ess/common/LOAD/today_batt_discharge_enery,"
    "ess/common/LOAD/today_grid_power_purchase_energy,ess/common/LOAD/month_load_consumption_sum,"
    "ess/common/LOAD/month_pv_direct_consumption_energy,ess/common/LOAD/month_batt_discharge_energy,"
    "ess/common/LOAD/month_grid_power_purchase_energy,ess/common/PCS/today_self_consumption,"
    "ess/common/PCS/month_co2_reduction_accum,ess/common/PCS/today_pv_generation_sum,"
    "ess/common/PCS/month_pv_generation_sum,ess/common/PCS/today_grid_feed_in_energy,"
    "ess/common/PCS/month_grid_feed_in_energy,ess/common/PCS/pcs_stauts,"
    "ess/common/PCS/feed_in_limitation,ess/common/PCS/operation_mode"
)


async def publish_legacy_raw_discovery(mqtt_client, sensor_list):
    """Publishes MQTT discovery for legacy pyess raw sensors (sensor.ess_ess_*) for backward compatibility."""
    if not sensor_list:
        return
    sensors = [s.strip() for s in sensor_list.split(",") if s.strip()]
    logger.info(f"Publishing {len(sensors)} legacy pyess raw sensors (sensor.ess_ess_*) to MQTT Discovery under device 'ESS'...")
    for sensor in sensors:
        desc = {
            "name": sensor,
            "state_topic": sensor,
            "unique_id": sensor.replace("/", ""),
            "device": {
                "identifiers": ["lgesss"],
                "manufacturer": "LG",
                "model": "ESS",
                "name": "ESS",
                "sw_version": "pyess",
            },
        }
        sensor_lower = sensor.lower()
        # Energy / Wh takes precedence over power (e.g. today_grid_power_purchase_energy contains 'power' but is an energy Wh sensor)
        if "enegy" in sensor_lower or "energy" in sensor_lower or "enery" in sensor_lower or sensor_lower.endswith("_sum"):
            desc["device_class"] = "energy"
            desc["unit_of_measurement"] = "Wh"
            desc["state_class"] = "total_increasing"
            desc["icon"] = "mdi:gauge"
        elif "power" in sensor_lower:
            desc["device_class"] = "power"
            desc["unit_of_measurement"] = "W"
            desc["state_class"] = "measurement"
        elif "soc" in sensor_lower or "self_consumption" in sensor_lower:
            desc["unit_of_measurement"] = "%"
            desc["state_class"] = "measurement"
            if "soc" in sensor_lower:
                desc["device_class"] = "battery"
        elif sensor_lower.endswith("current"):
            desc["device_class"] = "current"
            desc["unit_of_measurement"] = "A"
            desc["state_class"] = "measurement"
        elif "voltage" in sensor_lower:
            desc["device_class"] = "voltage"
            desc["unit_of_measurement"] = "V"
            desc["state_class"] = "measurement"
        elif "freq" in sensor_lower:
            desc["device_class"] = "frequency"
            desc["unit_of_measurement"] = "Hz"
            desc["state_class"] = "measurement"

        node_type = "switch" if "control" in sensor else "sensor"
        discovery_topic = f"homeassistant/{node_type}/{sensor.replace('/', '')}/config"
        await mqtt_client.publish(discovery_topic, json.dumps(desc), retain=True, qos=1)

    logger.info(f"Successfully published {len(sensors)} legacy pyess raw sensors to MQTT Discovery.")


async def run_diagnostics(entity_naming="legacy", lang="de", delay=4):
    """
    Runs automated migration diagnostics via Home Assistant Supervisor API.
    Detects if orphaned YAML entities (e.g. from former template.yaml / sensor.yaml)
    are occupying target entity IDs and forcing HA to append '_2'.
    """
    try:
        await asyncio.sleep(delay)

        token = os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HASSIO_TOKEN")
        if not token:
            logger.debug("Supervisor API token not available; skipping migration diagnostics.")
            return

        url = "http://supervisor/core/api/states"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    logger.debug(f"Supervisor API returned status {resp.status}; diagnostics skipped.")
                    return
                states_list = await resp.json()

        if not isinstance(states_list, list):
            logger.debug("Supervisor API did not return a valid states list.")
            return

        ha_states = {
            item.get("entity_id"): item
            for item in states_list
            if isinstance(item, dict) and "entity_id" in item
        }

        conflicts = []

        # Check sensors
        for s in SENSOR_DEFINITIONS:
            s_id = s["id"]
            if entity_naming == "legacy":
                obj_id = LEGACY_OBJECT_IDS.get(s_id, s_id)
            else:
                obj_id = s.get("object_ids", {}).get(lang, s_id)

            target_eid = f"sensor.{obj_id}"
            dup_eids = [
                eid for eid in ha_states
                if eid.startswith(f"{target_eid}_") and eid[len(target_eid) + 1:].isdigit()
            ]
            if dup_eids:
                old_state = ha_states.get(target_eid, {})
                old_val = old_state.get("state", "nicht gefunden / not found")
                conflicts.append({
                    "target": target_eid,
                    "duplicates": dup_eids,
                    "old_state": old_val,
                })

        # Check switches
        for sw in SWITCH_DEFINITIONS:
            sw_id = sw["id"]
            obj_id = sw_id if entity_naming == "legacy" else sw["unique_id"]
            target_eid = f"switch.{obj_id}"
            dup_eids = [
                eid for eid in ha_states
                if eid.startswith(f"{target_eid}_") and eid[len(target_eid) + 1:].isdigit()
            ]
            if dup_eids:
                old_state = ha_states.get(target_eid, {})
                old_val = old_state.get("state", "nicht gefunden / not found")
                conflicts.append({
                    "target": target_eid,
                    "duplicates": dup_eids,
                    "old_state": old_val,
                })

        # Check if legacy naming was requested, but HA still holds prefixed entity IDs (e.g. sensor.lg_ess_*) from earlier versions
        prefixed_conflicts = []
        if entity_naming == "legacy":
            for s in SENSOR_DEFINITIONS:
                s_id = s["id"]
                obj_id = LEGACY_OBJECT_IDS.get(s_id, s_id)
                target_eid = f"sensor.{obj_id}"
                if target_eid not in ha_states:
                    for eid in ha_states:
                        if eid.startswith("sensor.lg_ess_") and (s_id in eid or obj_id in eid or s.get("object_ids", {}).get("de", "") in eid):
                            prefixed_conflicts.append((target_eid, eid))
                            break

        if prefixed_conflicts:
            sample_t, sample_p = prefixed_conflicts[0]
            if lang == "de":
                prefix_lines = [
                    "",
                    "================================================================================",
                    "⚠️  MIGRATIONS-HINWEIS: VORHERIGE ENTITÄTEN MIT 'lg_ess_' PRÄFIX GEFUNDEN! ⚠️",
                    "================================================================================",
                    f"Home Assistant hat für {len(prefixed_conflicts)} Sensoren noch alte Entitäts-IDs",
                    "mit 'sensor.lg_ess_*' aus einer früheren Add-on-Version gespeichert:",
                ]
                for t_eid, p_eid in prefixed_conflicts:
                    prefix_lines.append(f"  • {p_eid} ➔ sollte sein: {t_eid}")
                prefix_lines.extend([
                    "",
                    "SO STELLST DU ALLE ENTITÄTEN MIT EINEM KLICK AUF DIE LEGACY-IDS UM:",
                    "  1. Öffne in Home Assistant: Einstellungen ➔ Geräte & Dienste ➔ MQTT",
                    "  2. Klicke auf 'Geräte' und wähle das Gerät 'LG ESS' aus.",
                    "  3. Klicke oben rechts auf das Drei-Punkte-Menü (...) und wähle 'Löschen'.",
                    f"  4. Das Add-on legt die Entitäten sofort vollautomatisch mit den korrekten",
                    f"     Legacy-IDs (z. B. '{sample_t}') neu an!",
                    "================================================================================",
                    "",
                ])
            else:
                prefix_lines = [
                    "",
                    "================================================================================",
                    "⚠️  MIGRATION NOTE: PREVIOUS ENTITIES WITH 'lg_ess_' PREFIX FOUND! ⚠️",
                    "================================================================================",
                    f"Home Assistant is still retaining 'sensor.lg_ess_*' entity IDs for {len(prefixed_conflicts)} sensors",
                    "from an earlier add-on version:",
                ]
                for t_eid, p_eid in prefixed_conflicts:
                    prefix_lines.append(f"  • {p_eid} ➔ should be: {t_eid}")
                prefix_lines.extend([
                    "",
                    "HOW TO RESET ALL ENTITIES TO LEGACY IDS WITH A SINGLE CLICK:",
                    "  1. In Home Assistant, navigate to: Settings ➔ Devices & Services ➔ MQTT",
                    "  2. Click 'Devices' and select 'LG ESS'.",
                    "  3. Click the three dots menu (...) in the top right and select 'Delete'.",
                    f"  4. The add-on will immediately recreate all entities cleanly with the exact",
                    f"     legacy IDs (e.g. '{sample_t}')!",
                    "================================================================================",
                    "",
                ])
            for line in prefix_lines:
                logger.warning(line)

        if not conflicts and not prefixed_conflicts:
            if lang == "de":
                logger.info("✅ Migrations-Diagnose: Alle Sensoren und Schalter sind sauber zugeordnet. Keine blockierenden Alt-Entitäten gefunden!")
            else:
                logger.info("✅ Migration Diagnostics: All sensors and switches are mapped cleanly. No orphaned YAML entities found!")
            return

        if not conflicts:
            return

        sample_target = conflicts[0]["target"]
        sample_dup = conflicts[0]["duplicates"][0]

        if lang == "de":
            log_lines = [
                "",
                "================================================================================",
                "⚠️  MIGRATIONS-DIAGNOSE: ALT-ENTITÄTEN BLOCKIEREN MQTT-SENSOREN! ⚠️",
                "================================================================================",
                "Home Assistant hat für folgende Entitäten eine Endung wie '_2' vergeben,",
                "weil alte, inaktive YAML-Entitäten (z. B. aus template.yaml oder sensor.yaml)",
                "noch in der Home Assistant Entitäten-Registry gespeichert sind:",
                "",
            ]
            for c in conflicts:
                dup_str = ", ".join(c["duplicates"])
                log_lines.append(f"  • {c['target']} (Status der Alt-Entität: '{c['old_state']}') ➔ NEU: {dup_str}")

            log_lines.extend([
                "",
                "SO BEHEBST DU DAS IN 30 SEKUNDEN (damit deine Langzeitstatistiken nahtlos weiterlaufen):",
                "  1. Öffne in Home Assistant: Einstellungen ➔ Geräte & Dienste ➔ Entitäten",
                "  2. Suche nach den oben genannten alten Entitäten (Filter: 'Nicht verfügbar').",
                f"  3. Klicke die alte, inaktive Entität an (z. B. '{sample_target}') und wähle 'Löschen'.",
                f"  4. Öffne nun die neue Entität mit '_2' (z. B. '{sample_dup}'), klicke auf das Zahnrad-Symbol",
                f"     und entferne einfach das '_2' aus der Entitäts-ID (wieder zu '{sample_target}') ➔ Speichern!",
                "",
                "➔ Sobald das erledigt ist, laufen deine bisherigen Langzeitstatistiken und",
                "  das Energie-Dashboard ohne Datenverlust mit den neuen Live-Daten weiter!",
                "================================================================================",
                "",
            ])
        else:
            log_lines = [
                "",
                "================================================================================",
                "⚠️  MIGRATION DIAGNOSTICS: ORPHANED ENTITIES BLOCKING MQTT SENSORS! ⚠️",
                "================================================================================",
                "Home Assistant has appended '_2' to the following entities because older,",
                "inactive YAML entities (e.g. from template.yaml or sensor.yaml) are still",
                "retained in Home Assistant's Entity Registry:",
                "",
            ]
            for c in conflicts:
                dup_str = ", ".join(c["duplicates"])
                log_lines.append(f"  • {c['target']} (Old entity state: '{c['old_state']}') ➔ NEW: {dup_str}")

            log_lines.extend([
                "",
                "HOW TO FIX THIS IN 30 SECONDS (to seamlessly preserve your long-term energy stats):",
                "  1. In Home Assistant, go to: Settings ➔ Devices & Services ➔ Entities",
                "  2. Filter by 'Unavailable' or search for the affected entity.",
                f"  3. Click on the orphaned entity (e.g. '{sample_target}') and select 'Delete'.",
                f"  4. Click on the new entity with '_2' (e.g. '{sample_dup}'), open Settings (gear icon),",
                f"     and remove the '_2' from the Entity ID (back to '{sample_target}') ➔ Save!",
                "",
                "➔ Immediately afterwards, your existing Energy Dashboard and historical",
                "  statistics will resume without any data loss!",
                "================================================================================",
                "",
            ])

        for line in log_lines:
            logger.warning(line)

    except asyncio.CancelledError:
        pass
    except Exception as ex:
        logger.debug(f"Error during migration diagnostics: {ex}")


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
                            await ess.winter_on()
                        else:
                            await ess.winter_off()
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

            loop_count += 1

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

                # 4. Synchronize switch states with LG ESS live telemetry
                try:
                    batt_info = common.get("BATT", {})
                    winter_val = batt_info.get("winter_setting")
                    if winter_val is None:
                        winter_val = batt_info.get("winter_status") or home.get("wintermode", {}).get("winter_status")
                    if winter_val is not None:
                        is_winter = str(winter_val).strip().lower() in ("on", "1", "true")
                        await client.publish("ess/sensors/winter_mode", "ON" if is_winter else "OFF", retain=True)

                    op_status = home.get("operation", {}).get("status")
                    if op_status is not None:
                        is_active = str(op_status).strip().lower() in ("start", "on", "1", "true")
                        await client.publish("ess/sensors/active", "ON" if is_active else "OFF", retain=True)

                    if loop_count % 12 == 1:
                        batt_settings = await ess.get_batt_settings()
                        if batt_settings and "alg_setting" in batt_settings:
                            is_fc = str(batt_settings["alg_setting"]).strip().lower() in ("on", "1", "true")
                            await client.publish("ess/sensors/fastcharge", "ON" if is_fc else "OFF", retain=True)
                except Exception as sw_err:
                    logger.debug(f"Switch state sync error: {sw_err}")
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
    parser.add_argument("--entity_naming", default="legacy", choices=["legacy", "modern"], help="Naming schema: legacy (2023 sensor.yaml) or modern")
    parser.add_argument("--hass_autoconfig_sensors", default=None, help="Legacy pyess autoconfig list (optional)")
    parser.add_argument("--legacy_raw_sensors", default="true", help="Publish pyess legacy raw MQTT discovery sensors (sensor.ess_ess_*)")

    args = parser.parse_args()

    auto_create = str_to_bool(args.auto_create_sensors)
    legacy_raw = str_to_bool(args.legacy_raw_sensors)
    lang = "de" if str(args.sensor_language).lower().startswith("de") else "en"
    power_unit = args.power_unit
    entity_naming = args.entity_naming

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
                    await publish_discovery(client, lang=lang, power_unit=power_unit, entity_naming=entity_naming)
                    asyncio.create_task(run_diagnostics(entity_naming=entity_naming, lang=lang, delay=4))

                if legacy_raw:
                    raw_list = args.hass_autoconfig_sensors or DEFAULT_LEGACY_RAW_SENSORS
                    await publish_legacy_raw_discovery(client, raw_list)

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
