#!/usr/bin/env python3
"""
LG ESS MQTT Bridge & Auto-Discovery for Home Assistant
Communicates with LG ESS solar power converters & battery storage via local API (pyess),
publishes raw and calculated telemetry to MQTT, and registers clean Home Assistant sensors
via MQTT Auto-Discovery with full multi-language localization (DE / EN).
"""

import argparse
import asyncio
import calendar
import datetime
import json
import logging
import os
import re
import socket
import subprocess
import sys
import time
import aiohttp
import aiohttp.client_exceptions
from aiomqtt import Client, MqttError

from pyess.aio_ess import ESS, ESSAuthException
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
    "sw_version": "1.0.0",
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
        "id": "battery_safety_soc",
        "unique_id": "lgess_battery_safety_soc",
        "object_ids": {"de": "batterie_mindest_ladezustand", "en": "battery_safety_soc"},
        "name": {"de": "Batterie Mindest-Ladezustand (Untergrenze)", "en": "Battery Minimum SoC (Safety Limit)"},
        "device_class": "battery",
        "state_class": "measurement",
        "unit": "%",
        "icon": "mdi:battery-alert",
        "calc": lambda h, c: int(round(safe_float(c.get("BATT", {}).get("safety_soc") if c.get("BATT", {}).get("safety_soc") is not None else c.get("BATT", {}).get("safty_soc")))) if (c.get("BATT", {}).get("safety_soc") is not None or c.get("BATT", {}).get("safty_soc") is not None) else None,
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
        "id": "feed_in_limitation",
        "unique_id": "lgess_feed_in_limitation",
        "object_ids": {"de": "einspeisebegrenzung", "en": "feed_in_limitation"},
        "name": {"de": "Einspeisebegrenzung", "en": "Feed-in Limitation"},
        "state_class": "measurement",
        "unit": "%",
        "icon": "mdi:transmission-tower-export",
        "calc": lambda h, c: int(round(safe_float(c.get("PCS", {}).get("feed_in_limitation")))) if c.get("PCS", {}).get("feed_in_limitation") is not None else None,
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
        "id": "backup_mode",
        "unique_id": "lgess_switch_backup_mode",
        "name": {"de": "Backup-Modus", "en": "Backup Mode"},
        "icon": "mdi:shield-battery",
        "command_topic": "ess/control/backup_mode",
        "state_topic": "ess/sensors/backup_mode",
    },
    {
        "id": "charge_from_grid",
        "unique_id": "lgess_switch_charge_from_grid",
        "name": {"de": "Aufladen vom Netz", "en": "Charge from Grid"},
        "icon": "mdi:transmission-tower-export",
        "command_topic": "ess/control/charge_from_grid",
        "state_topic": "ess/sensors/charge_from_grid",
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

SELECT_DEFINITIONS = [
    {
        "id": "charging_mode",
        "unique_id": "lgess_select_charging_mode",
        "name": {"de": "Lademodus", "en": "Charging Mode"},
        "icon": "mdi:battery-charging",
        "command_topic": "ess/control/charging_mode",
        "state_topic": "ess/sensors/charging_mode",
        "options": {
            "de": ["Batteriepflege", "Schnellladung", "Wettervorhersage"],
            "en": ["Battery Care", "Fast Charge", "Weather Forecast"],
        },
    },
]

NUMBER_DEFINITIONS = [
    {
        "id": "backup_soc",
        "unique_id": "lgess_number_backup_soc",
        "name": {"de": "Backup Mindest-SoC", "en": "Backup Min SoC"},
        "icon": "mdi:battery-heart-variant",
        "unit": "%",
        "min": 5,
        "max": 100,
        "step": 5,
        "command_topic": "ess/control/backup_soc",
        "state_topic": "ess/sensors/backup_soc",
    },
    {
        "id": "battery_safety_soc",
        "unique_id": "lgess_number_battery_safety_soc",
        "name": {"de": "Batterie Mindest-Ladezustand", "en": "Battery Min SoC"},
        "icon": "mdi:battery-alert",
        "unit": "%",
        "min": 0,
        "max": 50,
        "step": 5,
        "command_topic": "ess/control/battery_safety_soc",
        "state_topic": "ess/sensors/battery_safety_soc",
    },
    {
        "id": "feed_in_limitation",
        "unique_id": "lgess_number_feed_in_limitation",
        "name": {"de": "Einspeisebegrenzung", "en": "Feed-in Limitation"},
        "icon": "mdi:transmission-tower-export",
        "unit": "%",
        "min": 0,
        "max": 100,
        "step": 1,
        "command_topic": "ess/control/feed_in_limitation",
        "state_topic": "ess/sensors/feed_in_limitation",
    },
]

TEXT_DEFINITIONS = [
    {
        "id": "winter_mode_start",
        "unique_id": "lgess_text_winter_mode_start",
        "name": {"de": "Wintermodus Startdatum", "en": "Winter Mode Start Date"},
        "icon": "mdi:calendar-start",
        "command_topic": "ess/control/winter_mode_start",
        "state_topic": "ess/sensors/winter_mode_start",
        "min": 1,
        "max": 16,
        "mode": "text",
    },
    {
        "id": "winter_mode_end",
        "unique_id": "lgess_text_winter_mode_end",
        "name": {"de": "Wintermodus Enddatum", "en": "Winter Mode End Date"},
        "icon": "mdi:calendar-end",
        "command_topic": "ess/control/winter_mode_end",
        "state_topic": "ess/sensors/winter_mode_end",
        "min": 1,
        "max": 16,
        "mode": "text",
    },
]

BINARY_SENSOR_DEFINITIONS = [
    {
        "id": "winter_mode_active",
        "unique_id": "lgess_binary_sensor_winter_mode_active",
        "name": {"de": "Wintermodus aktiv", "en": "Winter Mode Active"},
        "icon": "mdi:snowflake-check",
        "state_topic": "ess/sensors/winter_mode_active",
        "payload_on": "ON",
        "payload_off": "OFF",
    },
]

CHARGING_MODE_LABELS = {
    0: {"de": "Batteriepflege", "en": "Battery Care", "key": "battery_care"},
    1: {"de": "Schnellladung", "en": "Fast Charge", "key": "fast_charge"},
    2: {"de": "Wettervorhersage", "en": "Weather Forecast", "key": "weather_forecast"},
}

STRING_TO_CHARGING_MODE = {
    # 0 -> Battery Care / Batteriepflege
    "0": 0,
    "battery_care": 0,
    "batteriepflege": 0,
    "battery care": 0,
    "care": 0,
    "eco": 0,
    # 1 -> Fast Charge / Schnellladung
    "1": 1,
    "fast_charge": 1,
    "fastcharge": 1,
    "schnellladung": 1,
    "schnellladen": 1,
    "fast charge": 1,
    "fast": 1,
    # 2 -> Weather Forecast / Wettervorhersage
    "2": 2,
    "weather_forecast": 2,
    "weatherforecast": 2,
    "wettervorhersage": 2,
    "weather forecast": 2,
    "weather": 2,
}


def parse_charging_mode(val):
    """Parses any charging mode representation (int, string key, localized name) to integer 0, 1, or 2."""
    if val is None:
        return None
    val_clean = str(val).strip().lower()
    return STRING_TO_CHARGING_MODE.get(val_clean, None)


def get_charging_mode_label(mode_int, lang="de"):
    """Returns the localized display string for a charging mode integer."""
    info = CHARGING_MODE_LABELS.get(mode_int, CHARGING_MODE_LABELS[0])
    return info.get(lang, info["de"])


def get_charging_mode_key(mode_int):
    """Returns the raw ASCII identifier for a charging mode integer."""
    info = CHARGING_MODE_LABELS.get(mode_int, CHARGING_MODE_LABELS[0])
    return info["key"]


def parse_mmdd(val):
    """Parses various date string formats into an MMDD string (4 digits, e.g. '1101')."""
    if not val:
        return None
    val_str = str(val).strip()
    # YYYY-MM-DD or YYYY/MM/DD
    m_iso = re.match(r"^\d{4}[-/](\d{1,2})[-/](\d{1,2})$", val_str)
    if m_iso:
        m, d = int(m_iso.group(1)), int(m_iso.group(2))
        return f"{m:02d}{d:02d}"
    # DD.MM.YYYY or DD.MM.
    m_de = re.match(r"^(\d{1,2})\.(\d{1,2})\.?(\d{4})?$", val_str)
    if m_de:
        d, m = int(m_de.group(1)), int(m_de.group(2))
        return f"{m:02d}{d:02d}"
    # MM-DD or MM/DD
    m_md = re.match(r"^(\d{1,2})[-/](\d{1,2})$", val_str)
    if m_md:
        m, d = int(m_md.group(1)), int(m_md.group(2))
        return f"{m:02d}{d:02d}"
    # 4 raw digits MMDD
    if len(val_str) == 4 and val_str.isdigit():
        m, d = int(val_str[:2]), int(val_str[2:])
        if 1 <= m <= 12 and 1 <= d <= 31:
            return val_str
    return None


def mmdd_to_display(mmdd):
    """Converts MMDD string (e.g. '1101') to day.month format '01.11' without year and without trailing dot."""
    try:
        val = str(mmdd).strip().zfill(4)
        m, d = int(val[:2]), int(val[2:])
        return f"{d:02d}.{m:02d}"
    except Exception:
        return str(mmdd)


def mmdd_to_iso(start_mmdd, stop_mmdd):
    """Converts start and stop MMDD strings into ISO format YYYY-MM-DD for Home Assistant date entities."""
    try:
        now = datetime.date.today()
        cur_y = now.year
        cur_m = now.month

        s_m, s_d = int(str(start_mmdd)[:2]), int(str(start_mmdd)[2:])
        e_m, e_d = int(str(stop_mmdd)[:2]), int(str(stop_mmdd)[2:])

        if s_m > e_m:  # Winter season crosses new year boundary (e.g. November -> February)
            if cur_m <= e_m:
                s_y = cur_y - 1
                e_y = cur_y
            else:
                s_y = cur_y
                e_y = cur_y + 1
        else:  # Within same calendar year
            if cur_m > e_m:
                s_y = cur_y + 1
                e_y = cur_y + 1
            else:
                s_y = cur_y
                e_y = cur_y

        s_d = min(s_d, calendar.monthrange(s_y, s_m)[1])
        e_d = min(e_d, calendar.monthrange(e_y, e_m)[1])
        return f"{s_y:04d}-{s_m:02d}-{s_d:02d}", f"{e_y:04d}-{e_m:02d}-{e_d:02d}"
    except Exception as ex:
        logger.warning(f"Error converting MMDD to ISO dates ({start_mmdd}, {stop_mmdd}): {ex}")
        today_iso = datetime.date.today().isoformat()
        return today_iso, today_iso


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
    "charging_mode": "Lademodus",
    "backup_mode": "Backup-Modus",
    "charge_from_grid": "Aufladen vom Netz",
    "backup_soc": "Backup Mindest-SoC",
    "battery_safety_soc": "Batterie Mindest-Ladezustand",
    "winter_mode_start": "Wintermodus Startdatum",
    "winter_mode_end": "Wintermodus Enddatum",
    "feed_in_limitation": "Einspeisebegrenzung",
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
    "charging_mode": "charging_mode",
    "backup_mode": "backup_mode",
    "charge_from_grid": "charge_from_grid",
    "backup_soc": "backup_soc",
    "battery_safety_soc": "battery_safety_soc",
    "winter_mode_start": "winter_mode_start",
    "winter_mode_end": "winter_mode_end",
    "feed_in_limitation": "feed_in_limitation",
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

    # 3. Selects
    for sel in SELECT_DEFINITIONS:
        sel_id = sel["id"]
        name = sel["name"].get(lang, sel["name"]["de"])
        obj_id = sel_id if entity_naming == "legacy" else sel["unique_id"]
        options = sel["options"].get(lang, sel["options"]["de"])
        payload = {
            "name": name,
            "unique_id": sel["unique_id"],
            "default_entity_id": f"select.{obj_id}",
            "object_id": obj_id,
            "command_topic": sel["command_topic"],
            "state_topic": sel["state_topic"],
            "options": options,
            "device": DEVICE_INFO,
            "icon": sel["icon"],
        }
        discovery_topic = f"homeassistant/select/lg_ess/{sel_id}/config"
        await mqtt_client.publish(discovery_topic, json.dumps(payload), retain=True, qos=1)

    # 4. Numbers
    for num in NUMBER_DEFINITIONS:
        num_id = num["id"]
        name = num["name"].get(lang, num["name"]["de"])
        obj_id = num_id if entity_naming == "legacy" else num["unique_id"]
        payload = {
            "name": name,
            "unique_id": num["unique_id"],
            "default_entity_id": f"number.{obj_id}",
            "object_id": obj_id,
            "command_topic": num["command_topic"],
            "state_topic": num["state_topic"],
            "min": num["min"],
            "max": num["max"],
            "step": num["step"],
            "unit_of_measurement": num["unit"],
            "device": DEVICE_INFO,
            "icon": num["icon"],
        }
        discovery_topic = f"homeassistant/number/lg_ess/{num_id}/config"
        await mqtt_client.publish(discovery_topic, json.dumps(payload), retain=True, qos=1)

    # 5. Texts (Winter mode start & end date without year: DD.MM.)
    for txt in TEXT_DEFINITIONS:
        txt_id = txt["id"]
        name = txt["name"].get(lang, txt["name"]["de"])
        obj_id = txt_id if entity_naming == "legacy" else txt["unique_id"]
        payload = {
            "name": name,
            "unique_id": txt["unique_id"],
            "default_entity_id": f"text.{obj_id}",
            "object_id": obj_id,
            "command_topic": txt["command_topic"],
            "state_topic": txt["state_topic"],
            "min": txt.get("min", 4),
            "max": txt.get("max", 6),
            "mode": txt.get("mode", "text"),
            "device": DEVICE_INFO,
            "icon": txt["icon"],
        }
        discovery_topic = f"homeassistant/text/lg_ess/{txt_id}/config"
        await mqtt_client.publish(discovery_topic, json.dumps(payload), retain=True, qos=1)

    # 6. Binary Sensors
    for bs in BINARY_SENSOR_DEFINITIONS:
        bs_id = bs["id"]
        name = bs["name"].get(lang, bs["name"]["de"])
        obj_id = bs_id if entity_naming == "legacy" else bs["unique_id"]
        payload = {
            "name": name,
            "unique_id": bs["unique_id"],
            "default_entity_id": f"binary_sensor.{obj_id}",
            "object_id": obj_id,
            "state_topic": bs["state_topic"],
            "payload_on": bs.get("payload_on", "ON"),
            "payload_off": bs.get("payload_off", "OFF"),
            "device": DEVICE_INFO,
            "icon": bs["icon"],
        }
        discovery_topic = f"homeassistant/binary_sensor/lg_ess/{bs_id}/config"
        await mqtt_client.publish(discovery_topic, json.dumps(payload), retain=True, qos=1)

    # 7. Clean up deprecated discovery topics (e.g. legacy switch.fastcharge, date entities replaced by text)
    deprecated_discovery_topics = [
        "homeassistant/switch/lg_ess/fastcharge/config",
        "homeassistant/date/lg_ess/winter_mode_start/config",
        "homeassistant/date/lg_ess/winter_mode_end/config",
    ]
    for dep_topic in deprecated_discovery_topics:
        await mqtt_client.publish(dep_topic, "", retain=True, qos=1)

    logger.info(
        f"Successfully published {len(SENSOR_DEFINITIONS)} sensors, {len(SWITCH_DEFINITIONS)} switches, "
        f"{len(SELECT_DEFINITIONS)} selects, {len(NUMBER_DEFINITIONS)} numbers, {len(TEXT_DEFINITIONS)} texts, "
        f"and {len(BINARY_SENSOR_DEFINITIONS)} binary sensors to MQTT Discovery."
    )


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

        # Check switches, selects, and numbers
        for item_list, domain in [
            (SWITCH_DEFINITIONS, "switch"),
            (SELECT_DEFINITIONS, "select"),
            (NUMBER_DEFINITIONS, "number"),
        ]:
            for item in item_list:
                item_id = item["id"]
                obj_id = item_id if entity_naming == "legacy" else item["unique_id"]
                target_eid = f"{domain}.{obj_id}"
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


def clean_mac(mac_str):
    """Normalizes any MAC address representation to 12 lowercase hex characters."""
    if not mac_str:
        return None
    clean = re.sub(r"[^0-9a-fA-F]", "", str(mac_str)).lower()
    return clean if len(clean) == 12 else None


def probe_ip(ip):
    """Sends TCP/UDP probes to ip to ensure kernel triggers ARP resolution."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.8)
        s.connect_ex((ip, 443))
        s.close()
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((ip, 80))
        s.send(b"\x00")
        s.close()
    except Exception:
        pass


def get_mac_from_arp_file(ip):
    """Reads /proc/net/arp and returns clean MAC address if found."""
    try:
        with open("/proc/net/arp", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 4 and parts[0] == ip:
                    flags = parts[2]
                    mac = parts[3].strip()
                    if flags != "0x0" and mac != "00:00:00:00:00:00":
                        cleaned = clean_mac(mac)
                        if cleaned:
                            return cleaned
    except Exception as e:
        logger.debug(f"Error reading /proc/net/arp: {e}")
    return None


def get_mac_from_system_command(ip):
    """Tries 'ip neigh' or 'arp -n' via subprocess as fallback."""
    try:
        out = subprocess.check_output(["ip", "neigh", "show", ip], stderr=subprocess.DEVNULL, text=True)
        m = re.search(r"lladdr\s+([0-9a-fA-F:]{17})", out)
        if m:
            cleaned = clean_mac(m.group(1))
            if cleaned:
                return cleaned
    except Exception:
        pass
    try:
        out = subprocess.check_output(["arp", "-n", ip], stderr=subprocess.DEVNULL, text=True)
        m = re.search(r"([0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2})", out)
        if m:
            cleaned = clean_mac(m.group(1))
            if cleaned:
                return cleaned
    except Exception:
        pass
    return None


def detect_ess_password(ip, name=None):
    """
    Attempts to discover the default ESS password (MAC address lowercase without colons).
    1. Checks if zeroconf name contains 12-char hex MAC.
    2. Probes the device IP on the network and reads kernel ARP cache (/proc/net/arp).
    3. Tries direct read endpoint in case device is in Wi-Fi hotspot mode.
    """
    logger.info(f"Suche MAC-Adresse für LG ESS ({ip})...")

    # 1. Check if name already contains a 12-character hex MAC
    if name:
        cleaned_name = clean_mac(name)
        if cleaned_name:
            logger.info(f"MAC-Adresse direkt aus Gerätenamen ({name}) ermittelt.")
            return cleaned_name

    # 2. Check ARP cache with probes (up to 6 attempts)
    for _ in range(6):
        probe_ip(ip)
        mac = get_mac_from_arp_file(ip)
        if mac:
            return mac
        mac_cmd = get_mac_from_system_command(ip)
        if mac_cmd:
            return mac_cmd
        time.sleep(0.4)

    # 3. Direct local endpoint read (Wi-Fi hotspot mode 192.168.23.1 or supported firmware)
    try:
        import urllib.request
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            f"https://{ip}/v1/user/setting/read/password",
            data=b'{"key":"lgepmsuser!@#"}',
            headers={"Content-Type": "application/json", "Charset": "UTF-8"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=1.5, context=ctx) as resp:
            data = json.loads(resp.read().decode())
            if data.get("status") == "success" and data.get("password"):
                pw = clean_mac(data["password"]) or data["password"].strip().lower()
                logger.info("Passwort erfolgreich über lokalen Einstellungs-Endpunkt ausgelesen.")
                return pw
    except Exception:
        pass

    return None


async def detect_installer_password(ess, user_password=None):
    """
    Attempts to read the inverter registration number (regnum) from /v1/user/setting/login
    and verifies if it works as the installer password via /v1/installer/setting/login.
    """
    if not ess or not getattr(ess, "ip", None):
        return None

    pw = user_password or getattr(ess, "pw", None)
    if not pw:
        return None

    try:
        login_url = f"https://{ess.ip}/v1/user/setting/login"
        async with ess.session.put(login_url, json={"password": str(pw)}) as r:
            data = await r.json()
        regnum = data.get("regnum")
        if regnum:
            regnum = str(regnum).strip()
            # Verify installer login with regnum
            inst_url = f"https://{ess.ip}/v1/installer/setting/login"
            async with ess.session.put(inst_url, json={"password": regnum}) as r_inst:
                inst_data = await r_inst.json()
            if inst_data.get("status") == "success" and "auth_key" in inst_data:
                logger.info(f"Installateur-Zugang erfolgreich mit Registrierungsnummer ({regnum}) verifiziert.")
                return regnum
            else:
                logger.debug(f"Installateur-Login mit Registrierungsnummer ({regnum}) nicht erfolgreich: {inst_data}")
    except Exception as ex:
        logger.debug(f"Fehler bei automatischer Installateur-Kennwort-Erkennung: {ex}")

    return None


async def save_password_to_supervisor(ess_password=None, installer_password=None):
    """
    Saves the automatically discovered passwords (ess_password and/or installer_password)
    back into Home Assistant Add-on options via the Supervisor API so the user sees them in the UI.
    """
    token = os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HASSIO_TOKEN")
    if not token:
        logger.debug("SUPERVISOR_TOKEN nicht verfügbar; Passwörter werden nur im Speicher gehalten.")
        return False

    options = {}
    if ess_password:
        options["ess_password"] = ess_password
    if installer_password:
        options["installer_password"] = installer_password
    if not options:
        return False

    url = "http://supervisor/addons/self/options"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"options": options}
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    saved_items = []
                    if ess_password:
                        saved_items.append("Standard-Passwort")
                    if installer_password:
                        saved_items.append("Installateur-Kennwort")
                    logger.info(f"🔑 {' & '.join(saved_items)} wurde(n) automatisch in die Home Assistant Add-on-Konfiguration übernommen!")
                    return True
                else:
                    text = await resp.text()
                    logger.debug(f"Supervisor options response ({resp.status}): {text}")
    except Exception as ex:
        logger.debug(f"Konnte Passwörter nicht in Supervisor-Optionen speichern: {ex}")
    return False


async def set_batt_safety_soc(ess, soc_val, installer_password=None):
    """
    Sets the battery safety SoC (safety_soc) on the LG ESS.
    If installer_password (typically registration number like DE200...) is configured or
    auto-detected, it authenticates via /v1/installer/setting/login and sends the setting to
    /v1/installer/setting/batt.
    Otherwise, it sends the command to /v1/user/setting/batt.
    """
    soc_str = str(soc_val)
    if not installer_password and getattr(ess, "ip", None):
        if not hasattr(set_batt_safety_soc, "_cached_installer_password"):
            set_batt_safety_soc._cached_installer_password = await detect_installer_password(ess, getattr(ess, "pw", None))
        installer_password = set_batt_safety_soc._cached_installer_password

    if installer_password and getattr(ess, "ip", None):
        inst_url = f"https://{ess.ip}/v1/installer/setting/login"
        logger.info(f"Authentifiziere am LG ESS ({ess.ip}) im Installateur-Modus...")
        try:
            async with ess.session.put(inst_url, json={"password": str(installer_password).strip()}) as r:
                resp = await r.json()
            if resp.get("status") == "success" and "auth_key" in resp:
                inst_auth = resp["auth_key"]
                logger.info("Installateur-Login erfolgreich! Sende Safety-SoC an Installateur-Endpunkt...")
                batt_url = f"https://{ess.ip}/v1/installer/setting/batt"
                # Send both safety_soc and safty_soc to ensure compatibility across all firmware versions
                payload = {"auth_key": inst_auth, "safety_soc": soc_str, "safty_soc": soc_str}
                async with ess.session.put(batt_url, json=payload) as r_batt:
                    res_batt = await r_batt.json()
                logger.info(f"Installateur-Endpunkt Antwort: {res_batt}")
                try:
                    await ess.set_batt_settings({"safety_soc": soc_str, "safty_soc": soc_str})
                except Exception:
                    pass
                return True
            else:
                logger.warning(f"Installateur-Login mit Registriernummer nicht erfolgreich: {resp}. Versuche Standard-User-Endpunkt...")
        except Exception as ex:
            logger.warning(f"Fehler beim Installateur-Login: {ex}. Versuche Standard-User-Endpunkt...")

    # Standard user endpoint fallback
    logger.info(f"Sende safety_soc={soc_str}% an /v1/user/setting/batt...")
    await ess.set_batt_settings({"safety_soc": soc_str, "safty_soc": soc_str})
    if not installer_password:
        logger.info(
            "Tipp: Wenn der Wechselrichter die Änderung der Ladezustands-Untergrenze abweist, "
            "hinterlege das Installateur-Passwort (meist die Registrierungsnummer wie DE200...) "
            "in der Add-on-Konfiguration unter 'installer_password'."
        )
    return True


async def set_pv_feedin_limit(ess, limit_val, installer_password=None):
    """
    Sets the active power feed-in limitation (pv_feedin_limit, in percent 0-100%) on the LG ESS.
    If installer_password is not provided, attempts auto-detection via regnum.
    Authenticates via /v1/installer/setting/login and sends the setting to /v1/installer/setting/pcs.
    """
    limit_str = str(limit_val)
    if not installer_password and getattr(ess, "ip", None):
        if not hasattr(set_batt_safety_soc, "_cached_installer_password"):
            set_batt_safety_soc._cached_installer_password = await detect_installer_password(ess, getattr(ess, "pw", None))
        installer_password = set_batt_safety_soc._cached_installer_password

    if installer_password and getattr(ess, "ip", None):
        inst_url = f"https://{ess.ip}/v1/installer/setting/login"
        logger.info(f"Authentifiziere am LG ESS ({ess.ip}) im Installateur-Modus für Einspeisebegrenzung...")
        try:
            async with ess.session.put(inst_url, json={"password": str(installer_password).strip()}) as r:
                resp = await r.json()
            if resp.get("status") == "success" and "auth_key" in resp:
                inst_auth = resp["auth_key"]
                logger.info(f"Installateur-Login erfolgreich! Sende Einspeisebegrenzung pv_feedin_limit={limit_str}% an /v1/installer/setting/pcs...")
                pcs_url = f"https://{ess.ip}/v1/installer/setting/pcs"
                payload = {"auth_key": inst_auth, "pv_feedin_limit": limit_str}
                async with ess.session.put(pcs_url, json=payload) as r_pcs:
                    res_pcs = await r_pcs.json()
                logger.info(f"Installateur-Endpunkt (PCS) Antwort: {res_pcs}")
                try:
                    await ess._login()
                except Exception:
                    pass
                return True
            else:
                logger.warning(f"Installateur-Login mit Registriernummer nicht erfolgreich: {resp}")
        except Exception as ex:
            logger.warning(f"Fehler beim Installateur-Login / PCS-Einstellung: {ex}")
    else:
        logger.warning(
            "Kein Installateur-Kennwort vorhanden. Die Einspeisebegrenzung kann nur im Installateur-Modus angepasst werden. "
            "Hinterlege das Installateur-Passwort (Registrierungsnummer) in der Add-on-Konfiguration unter 'installer_password'."
        )
    return False


async def handle_control(client, ess, lang="de", installer_password=None):
    """Listens for control commands on ess/control/# and interacts with LG ESS."""
    try:
        await client.subscribe("ess/control/#")
        await client.subscribe("/ess/control/#")

        async with client.messages() as messages:
            async for msg in messages:
                topic = str(msg.topic)
                try:
                    payload_raw = msg.payload.decode().strip()
                    logger.info(f"Control command received on {topic}: {payload_raw}")

                    if "winter_mode_start" in topic or "winter_start" in topic:
                        mmdd = parse_mmdd(payload_raw)
                        if mmdd:
                            await ess.set_batt_settings({"startdate": mmdd})
                            batt_settings = await ess.get_batt_settings()
                            stop_mmdd = batt_settings.get("stopdate", "0228") if batt_settings else "0228"
                            start_disp = mmdd_to_display(mmdd)
                            start_iso, _ = mmdd_to_iso(mmdd, stop_mmdd)
                            await client.publish("ess/sensors/winter_mode_start", start_disp, retain=True)
                            await client.publish("ess/sensors/winter_mode_start_iso", start_iso, retain=True)
                            await client.publish("ess/sensors/winter_mode_start_mmdd", mmdd, retain=True)
                            logger.info(f"Winter mode start date set to {mmdd} ({start_disp})")
                        else:
                            logger.warning(f"Invalid winter start date format received on {topic}: '{payload_raw}'")

                    elif "winter_mode_end" in topic or "winter_mode_stop" in topic or "winter_end" in topic or "winter_stop" in topic:
                        mmdd = parse_mmdd(payload_raw)
                        if mmdd:
                            await ess.set_batt_settings({"stopdate": mmdd})
                            batt_settings = await ess.get_batt_settings()
                            start_mmdd = batt_settings.get("startdate", "1101") if batt_settings else "1101"
                            end_disp = mmdd_to_display(mmdd)
                            _, stop_iso = mmdd_to_iso(start_mmdd, mmdd)
                            await client.publish("ess/sensors/winter_mode_end", end_disp, retain=True)
                            await client.publish("ess/sensors/winter_mode_end_iso", stop_iso, retain=True)
                            await client.publish("ess/sensors/winter_mode_end_mmdd", mmdd, retain=True)
                            logger.info(f"Winter mode end date set to {mmdd} ({end_disp})")
                        else:
                            logger.warning(f"Invalid winter end date format received on {topic}: '{payload_raw}'")

                    elif "winter_mode" in topic:
                        state = str_to_bool(payload_raw)
                        await ess.set_batt_settings({"wintermode": "on" if state else "off"})
                        await client.publish("ess/sensors/winter_mode", "ON" if state else "OFF", retain=True)
                        logger.info(f"Winter mode set to {'ON' if state else 'OFF'}")

                    elif "backup_mode" in topic:
                        state = str_to_bool(payload_raw)
                        await ess.set_batt_settings({"backupmode": "on" if state else "off"})
                        await client.publish("ess/sensors/backup_mode", "ON" if state else "OFF", retain=True)
                        logger.info(f"Backup mode set to {'ON' if state else 'OFF'}")

                    elif "charge_from_grid" in topic:
                        state = str_to_bool(payload_raw)
                        await ess.set_batt_settings({"autocharge": "1" if state else "0"})
                        await client.publish("ess/sensors/charge_from_grid", "ON" if state else "OFF", retain=True)
                        logger.info(f"Charge from grid (auto_charge) set to {'ON' if state else 'OFF'}")

                    elif "backup_soc" in topic:
                        try:
                            soc_val = int(round(float(payload_raw)))
                            soc_val = max(5, min(100, soc_val))
                            await ess.set_batt_settings({"backup_soc": str(soc_val)})
                            await client.publish("ess/sensors/backup_soc", str(soc_val), retain=True)
                            logger.info(f"Backup SOC set to {soc_val}%")
                        except ValueError as ex:
                            logger.warning(f"Invalid backup_soc value received: {payload_raw}: {ex}")

                    elif "battery_safety_soc" in topic or "safty_soc" in topic or "safety_soc" in topic:
                        try:
                            soc_val = int(round(float(payload_raw)))
                            soc_val = max(0, min(50, soc_val))
                            logger.info(f"Setting battery safety SoC to {soc_val}%...")
                            await set_batt_safety_soc(ess, soc_val, installer_password=installer_password)
                            await client.publish("ess/sensors/battery_safety_soc", str(soc_val), retain=True)
                            logger.info(f"Battery safety SoC commanded to {soc_val}%")
                        except Exception as ex:
                            logger.warning(f"Invalid battery_safety_soc value received: {payload_raw}: {ex}")

                    elif any(k in topic for k in ("feed_in_limitation", "feedin", "pv_feedin_limit", "einspeisebegrenzung")):
                        try:
                            limit_val = int(round(float(payload_raw)))
                            limit_val = max(0, min(100, limit_val))
                            logger.info(f"Setting feed-in limitation to {limit_val}%...")
                            success = await set_pv_feedin_limit(ess, limit_val, installer_password=installer_password)
                            if success:
                                await client.publish("ess/sensors/feed_in_limitation", str(limit_val), retain=True)
                                logger.info(f"Feed-in limitation commanded to {limit_val}%")
                        except Exception as ex:
                            logger.warning(f"Invalid feed_in_limitation value received: {payload_raw}: {ex}")

                    elif "charging_mode" in topic:
                        mode_int = parse_charging_mode(payload_raw)
                        if mode_int is not None:
                            await ess.set_batt_settings({"alg_setting": mode_int})
                            label = get_charging_mode_label(mode_int, lang)
                            raw_key = get_charging_mode_key(mode_int)
                            await client.publish("ess/sensors/charging_mode", label, retain=True)
                            await client.publish("ess/sensors/charging_mode_raw", raw_key, retain=True)
                            await client.publish("ess/sensors/fastcharge", "ON" if mode_int == 1 else "OFF", retain=True)
                            logger.info(f"Charging mode updated to '{label}' (alg_setting={mode_int})")
                        else:
                            logger.warning(f"Unknown charging mode option received on {topic}: '{payload_raw}'")

                    elif "fastcharge" in topic:
                        state = str_to_bool(payload_raw)
                        target_mode = 1 if state else 0
                        await ess.set_batt_settings({"alg_setting": target_mode})
                        label = get_charging_mode_label(target_mode, lang)
                        raw_key = get_charging_mode_key(target_mode)
                        await client.publish("ess/sensors/fastcharge", "ON" if state else "OFF", retain=True)
                        await client.publish("ess/sensors/charging_mode", label, retain=True)
                        await client.publish("ess/sensors/charging_mode_raw", raw_key, retain=True)
                        logger.info(f"Fast charge switched to {'ON' if state else 'OFF'} -> mode '{label}'")

                    elif "active" in topic:
                        state = str_to_bool(payload_raw)
                        if state:
                            await ess.switch_on()
                        else:
                            await ess.switch_off()
                        await client.publish("ess/sensors/active", "ON" if state else "OFF", retain=True)
                        logger.info(f"ESS active state switched to {'ON' if state else 'OFF'}")

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
                        if val is None:
                            continue
                        if s.get("type") == "power":
                            if power_unit == "kW":
                                val = round(val * 0.001, 3)
                            else:
                                val = round(val, 1)
                        await client.publish(f"ess/sensors/{s['id']}", str(val))
                    except Exception as calc_err:
                        logger.debug(f"Calculation error for {s['id']}: {calc_err}")

                # 4. Synchronize switch / select / number states with LG ESS live telemetry
                try:
                    batt_info = common.get("BATT", {})
                    safety_val = batt_info.get("safety_soc") if batt_info.get("safety_soc") is not None else batt_info.get("safty_soc")
                    if safety_val is not None:
                        try:
                            val_int = int(round(float(safety_val)))
                            await client.publish("ess/sensors/battery_safety_soc", str(val_int), retain=True)
                        except Exception:
                            await client.publish("ess/sensors/battery_safety_soc", str(safety_val), retain=True)

                    winter_val = batt_info.get("winter_setting")
                    if winter_val is None:
                        winter_val = home.get("wintermode", {}).get("winter_status")
                    if winter_val is not None:
                        is_winter = str(winter_val).strip().lower() in ("on", "1", "true")
                        await client.publish("ess/sensors/winter_mode", "ON" if is_winter else "OFF", retain=True)

                    winter_act = batt_info.get("winter_status")
                    if winter_act is not None:
                        is_act = str(winter_act).strip().lower() in ("on", "1", "true")
                        await client.publish("ess/sensors/winter_mode_active", "ON" if is_act else "OFF", retain=True)

                    op_status = home.get("operation", {}).get("status")
                    if op_status is not None:
                        is_active = str(op_status).strip().lower() in ("start", "on", "1", "true")
                        await client.publish("ess/sensors/active", "ON" if is_active else "OFF", retain=True)

                    pcs_info = common.get("PCS", {})
                    feedin_val = pcs_info.get("feed_in_limitation")
                    if feedin_val is not None:
                        try:
                            val_int = int(round(float(feedin_val)))
                            await client.publish("ess/sensors/feed_in_limitation", str(val_int), retain=True)
                        except Exception:
                            await client.publish("ess/sensors/feed_in_limitation", str(feedin_val), retain=True)

                    if loop_count % 6 == 1:
                        batt_settings = await ess.get_batt_settings()
                        if batt_settings:
                            # 4.1 Charging mode & fastcharge
                            if "alg_setting" in batt_settings:
                                raw_alg = batt_settings["alg_setting"]
                                mode_int = parse_charging_mode(raw_alg)
                                if mode_int is not None:
                                    label = get_charging_mode_label(mode_int, lang)
                                    raw_key = get_charging_mode_key(mode_int)
                                    await client.publish("ess/sensors/charging_mode", label, retain=True)
                                    await client.publish("ess/sensors/charging_mode_raw", raw_key, retain=True)
                                    await client.publish("ess/sensors/fastcharge", "ON" if mode_int == 1 else "OFF", retain=True)

                            # 4.2 Backup mode
                            bk_val = batt_settings.get("backup_setting") or batt_settings.get("backup_status")
                            if bk_val is not None:
                                is_backup = str(bk_val).strip().lower() in ("on", "1", "true")
                                await client.publish("ess/sensors/backup_mode", "ON" if is_backup else "OFF", retain=True)

                            # 4.3 Charge from grid / Auto charge
                            ac_val = batt_settings.get("auto_charge")
                            if ac_val is not None:
                                is_ac = str(ac_val).strip().lower() in ("on", "1", "true")
                                await client.publish("ess/sensors/charge_from_grid", "ON" if is_ac else "OFF", retain=True)

                            # 4.4 Backup SOC & Safety SOC
                            soc_val = batt_settings.get("backup_soc")
                            if soc_val is not None:
                                await client.publish("ess/sensors/backup_soc", str(soc_val), retain=True)

                            safety_val = batt_settings.get("safety_soc") if batt_settings.get("safety_soc") is not None else batt_settings.get("safty_soc")
                            if safety_val is not None:
                                try:
                                    val_int = int(round(float(safety_val)))
                                    await client.publish("ess/sensors/battery_safety_soc", str(val_int), retain=True)
                                except Exception:
                                    await client.publish("ess/sensors/battery_safety_soc", str(safety_val), retain=True)

                            # 4.5 Winter mode dates & status
                            start_mmdd = batt_settings.get("startdate")
                            stop_mmdd = batt_settings.get("stopdate")
                            if start_mmdd and stop_mmdd:
                                s_disp = mmdd_to_display(str(start_mmdd))
                                e_disp = mmdd_to_display(str(stop_mmdd))
                                s_iso, e_iso = mmdd_to_iso(str(start_mmdd), str(stop_mmdd))
                                await client.publish("ess/sensors/winter_mode_start", s_disp, retain=True)
                                await client.publish("ess/sensors/winter_mode_end", e_disp, retain=True)
                                await client.publish("ess/sensors/winter_mode_start_iso", s_iso, retain=True)
                                await client.publish("ess/sensors/winter_mode_end_iso", e_iso, retain=True)
                                await client.publish("ess/sensors/winter_mode_start_mmdd", str(start_mmdd), retain=True)
                                await client.publish("ess/sensors/winter_mode_end_mmdd", str(stop_mmdd), retain=True)

                            w_act = batt_settings.get("winter_status")
                            if w_act is not None:
                                is_act = str(w_act).strip().lower() in ("on", "1", "true")
                                await client.publish("ess/sensors/winter_mode_active", "ON" if is_act else "OFF", retain=True)

                            w_set = batt_settings.get("winter_setting")
                            if w_set is not None:
                                is_winter = str(w_set).strip().lower() in ("on", "1", "true")
                                await client.publish("ess/sensors/winter_mode", "ON" if is_winter else "OFF", retain=True)
                except Exception as sw_err:
                    logger.debug(f"Switch/select state sync error: {sw_err}")
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
    parser.add_argument("--ess_password", default=None, help="LG ESS password (optional, auto-detected from MAC if omitted)")
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
    parser.add_argument("--installer_password", default=None, help="LG ESS installer password (typically registration number DE200...)")

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

    # Determine Password (manual or automatic MAC discovery)
    password = args.ess_password
    auto_detected_pw = False

    if not password:
        logger.info("Kein ESS-Passwort konfiguriert. Starte automatische Ermittlung via MAC-Adresse (Standard-Kennwort)...")
        password = await loop.run_in_executor(None, lambda: detect_ess_password(ip, name))
        if not password:
            logger.error("❌ Die MAC-Adresse des LG ESS konnte nicht automatisch im Netzwerk ermittelt werden.")
            logger.error("👉 Bitte trage das Passwort (deine MAC-Adresse in Kleinbuchstaben ohne Doppelpunkte) manuell in den Add-on-Einstellungen unter 'ess_password' ein.")
            sys.exit(1)
        auto_detected_pw = True
        formatted_mac = ":".join(password[i:i+2] for i in range(0, 12, 2))
        logger.info(f"🔑 MAC-Adresse gefunden: {formatted_mac} ➔ Standard-Passwort: {password[:2]}****{password[-2:]}")

    logger.info(f"Connecting to LG ESS at {ip}...")
    try:
        ess = await ESS.create(name, password, ip)
    except ESSAuthException:
        if auto_detected_pw:
            logger.error("❌ Das automatische Standard-Passwort (MAC-Adresse) wurde vom LG ESS abgelehnt!")
            logger.error("👉 Falls du das Gerätepasswort deines LG ESS geändert hast, trage dein eigenes Passwort bitte in den Add-on-Einstellungen unter 'ess_password' ein.")
        else:
            logger.error("❌ Das angegebene ESS-Passwort ist ungültig!")
        sys.exit(1)

    if auto_detected_pw:
        logger.info("✅ Erfolgreich mit dem Standard-Passwort (MAC-Adresse) am LG ESS angemeldet!")

    # Determine Installer Password (manual or automatic detection via registration number)
    installer_password = args.installer_password
    auto_detected_inst_pw = False

    if not installer_password:
        logger.info("Kein Installateur-Passwort konfiguriert. Versuche automatische Ermittlung der Registrierungsnummer...")
        installer_password = await detect_installer_password(ess, password)
        if installer_password:
            auto_detected_inst_pw = True
            logger.info(f"🔑 Registrierungsnummer (Installateur-Kennwort) automatisch erkannt: {installer_password[:4]}****{installer_password[-2:]}")

    if auto_detected_pw or auto_detected_inst_pw:
        asyncio.create_task(
            save_password_to_supervisor(
                ess_password=password if auto_detected_pw else None,
                installer_password=installer_password if auto_detected_inst_pw else None,
            )
        )

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
                control_task = asyncio.create_task(handle_control(client, ess, lang=lang, installer_password=installer_password))

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
