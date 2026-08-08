from __future__ import annotations

import os
import glob
import time
from dataclasses import dataclass
from typing import Optional

from ella_bot.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_LOW_BATTERY_THRESHOLD = 20.0  # Percentage threshold <= 20% triggers low battery modal


@dataclass
class BatteryStatus:
    """Dataclass holding battery telemetry data."""
    percent: float
    is_charging: bool
    is_low_battery: bool
    has_battery: bool = True
    voltage: float = 0.0
    source: str = "unknown"


class BatteryService:
    """Service to monitor battery status across Waveshare UPS HAT (E), sysfs, psutil, and mock modes."""

    def __init__(self, threshold: float = DEFAULT_LOW_BATTERY_THRESHOLD, poll_interval: float = 3.0) -> None:
        self.threshold = threshold
        self.poll_interval = poll_interval
        self._last_status: Optional[BatteryStatus] = None
        self._last_check_time: float = 0.0

    def get_status(self, force_refresh: bool = False) -> BatteryStatus:
        """Fetch battery status, using cached result if within poll interval unless force_refresh is True."""
        now = time.time()
        if not force_refresh and self._last_status is not None and (now - self._last_check_time) < self.poll_interval:
            return self._last_status

        status = self._read_status()
        self._last_status = status
        self._last_check_time = now
        return status

    def _read_status(self) -> BatteryStatus:
        # 1. Environment Variable Mock Override (Highest Priority for Dev / Testing)
        mock_env_percent = os.environ.get("ELLA_MOCK_BATTERY")
        if mock_env_percent is not None:
            try:
                percent = float(mock_env_percent)
                mock_plugged = os.environ.get("ELLA_MOCK_PLUGGED", "0").lower() in ("1", "true", "yes")
                is_low = (percent <= self.threshold) and (not mock_plugged)
                return BatteryStatus(
                    percent=percent,
                    is_charging=mock_plugged,
                    is_low_battery=is_low,
                    has_battery=True,
                    voltage=3.7,
                    source="mock",
                )
            except ValueError:
                logger.warning("Invalid ELLA_MOCK_BATTERY value: %s", mock_env_percent)

        # 2. Waveshare UPS HAT (E) I2C Hardware Probing
        i2c_status = self._read_waveshare_ups_i2c()
        if i2c_status is not None:
            return i2c_status

        # 3. Linux sysfs (/sys/class/power_supply/*)
        sysfs_status = self._read_sysfs_battery()
        if sysfs_status is not None:
            return sysfs_status

        # 4. psutil sensors_battery fallback
        psutil_status = self._read_psutil_battery()
        if psutil_status is not None:
            return psutil_status

        # 5. Fallback: No battery detected (e.g. standard AC power without UPS)
        return BatteryStatus(
            percent=100.0,
            is_charging=True,
            is_low_battery=False,
            has_battery=False,
            voltage=0.0,
            source="none",
        )

    def _read_waveshare_ups_i2c(self) -> Optional[BatteryStatus]:
        """Probe I2C for Waveshare UPS HAT (E) sensor chips (INA219 or MAX17048)."""
        try:
            import smbus2
        except ImportError:
            try:
                import smbus as smbus2  # type: ignore
            except ImportError:
                return None

        # Check I2C bus 1 (standard on Raspberry Pi 5 / 4)
        bus_num = 1
        i2c_dev_path = f"/dev/i2c-{bus_num}"
        if not os.path.exists(i2c_dev_path):
            return None

        # Waveshare UPS HAT (E) typical I2C addresses (0x2d MCU fuel gauge, INA219 at 0x42, 0x41, 0x43, or MAX17048 at 0x36)
        possible_addrs = [0x2d, 0x42, 0x41, 0x43, 0x36, 0x48]
        
        try:
            with smbus2.SMBus(bus_num) as bus:
                for addr in possible_addrs:
                    try:
                        if addr == 0x2d:
                            # Official Waveshare UPS HAT (E) (4x 21700 Li-ion cells)
                            data_20 = bus.read_i2c_block_data(0x2d, 0x20, 0x0C)
                            voltage = round((data_20[0] | (data_20[1] << 8)) / 1000.0, 2)
                            
                            current_ma = data_20[2] | (data_20[3] << 8)
                            if current_ma > 0x7FFF:
                                current_ma -= 0xFFFF
                                
                            percent = float(data_20[4] | (data_20[5] << 8))
                            if not (0.0 <= percent <= 100.0):
                                percent = 100.0
                                
                            # VBUS input voltage (register 0x10)
                            data_10 = bus.read_i2c_block_data(0x2d, 0x10, 0x06)
                            vbus_v = (data_10[0] | (data_10[1] << 8)) / 1000.0
                            
                            # State register (0x02)
                            state_byte = bus.read_i2c_block_data(0x2d, 0x02, 0x01)[0]
                            is_discharging = bool(state_byte & 0x20)
                            is_charging_flag = bool(state_byte & 0xC0)
                            
                            # Charging if VBUS > 4.5V and current > -30mA (or positive charging current)
                            is_charging = (vbus_v > 4.5 and current_ma >= -30) or (current_ma > 30) or (is_charging_flag and not is_discharging)
                            is_low = (percent <= self.threshold) and (not is_charging)
                            
                            return BatteryStatus(
                                percent=percent,
                                is_charging=is_charging,
                                is_low_battery=is_low,
                                has_battery=True,
                                voltage=voltage,
                                source="waveshare_ups_e_0x2d",
                            )

                        elif addr == 0x36:
                            # MAX17048 Fuel Gauge
                            soc_raw = bus.read_word_data(addr, 0x04)
                            # Swap bytes for big endian word
                            soc_swap = ((soc_raw & 0xFF) << 8) | ((soc_raw >> 8) & 0xFF)
                            percent = round(soc_swap / 256.0, 1)
                            
                            vcell_raw = bus.read_word_data(addr, 0x02)
                            vcell_swap = ((vcell_raw & 0xFF) << 8) | ((vcell_raw >> 8) & 0xFF)
                            voltage = round((vcell_swap >> 4) * 0.00125, 2)
                            
                            crate_raw = bus.read_word_data(addr, 0x16)
                            crate_swap = ((crate_raw & 0xFF) << 8) | ((crate_raw >> 8) & 0xFF)
                            if crate_swap & 0x8000:
                                crate_swap -= 65536
                            is_charging = crate_swap > 0 or voltage >= 4.15
                            
                            is_low = (percent <= self.threshold) and (not is_charging)
                            return BatteryStatus(
                                percent=percent,
                                is_charging=is_charging,
                                is_low_battery=is_low,
                                has_battery=True,
                                voltage=voltage,
                                source="waveshare_max17048",
                            )

                        else:
                            # INA219 Sensor (Standard Waveshare UPS HAT E)
                            # Read Bus Voltage Register (0x02)
                            bus_val = bus.read_word_data(addr, 0x02)
                            bus_val = ((bus_val & 0xFF) << 8) | ((bus_val >> 8) & 0xFF)
                            voltage = round((bus_val >> 3) * 0.004, 2)
                            
                            if voltage < 1.0 or voltage > 15.0:
                                continue  # Invalid voltage reading for UPS HAT
                            
                            # Read Current Register (0x04) or Shunt Voltage Register (0x01)
                            shunt_val = bus.read_word_data(addr, 0x01)
                            shunt_val = ((shunt_val & 0xFF) << 8) | ((shunt_val >> 8) & 0xFF)
                            if shunt_val & 0x8000:
                                shunt_val -= 65536
                                
                            # Positive shunt/current indicates charging, negative indicates discharging
                            is_charging = (shunt_val > 0) or (voltage >= 4.18)

                            # Estimate percentage based on Li-ion 21700 cell discharge curve (3.2V to 4.2V)
                            min_v, max_v = 3.2, 4.20
                            percent = round(min(100.0, max(0.0, ((voltage - min_v) / (max_v - min_v)) * 100.0)), 1)
                            
                            is_low = (percent <= self.threshold) and (not is_charging)
                            return BatteryStatus(
                                percent=percent,
                                is_charging=is_charging,
                                is_low_battery=is_low,
                                has_battery=True,
                                voltage=voltage,
                                source=f"waveshare_ina219_0x{addr:02x}",
                            )

                    except Exception:
                        continue
        except Exception as exc:
            logger.debug("I2C polling failed or device not accessible: %s", exc)

        return None

    def _read_sysfs_battery(self) -> Optional[BatteryStatus]:
        """Probe Linux sysfs power supplies (/sys/class/power_supply/*)."""
        power_supplies = glob.glob("/sys/class/power_supply/*")
        for path in power_supplies:
            try:
                type_path = os.path.join(path, "type")
                if os.path.exists(type_path):
                    with open(type_path, "r") as f:
                        ps_type = f.read().strip().lower()
                    if ps_type not in ("battery", "ups"):
                        continue

                cap_path = os.path.join(path, "capacity")
                if not os.path.exists(cap_path):
                    continue

                with open(cap_path, "r") as f:
                    percent = float(f.read().strip())

                status_path = os.path.join(path, "status")
                is_charging = False
                if os.path.exists(status_path):
                    with open(status_path, "r") as f:
                        st = f.read().strip().lower()
                        is_charging = st in ("charging", "full", "not charging")

                online_path = os.path.join(path, "online")
                if os.path.exists(online_path):
                    with open(online_path, "r") as f:
                        is_charging = is_charging or (f.read().strip() == "1")

                voltage = 0.0
                volt_path = os.path.join(path, "voltage_now")
                if os.path.exists(volt_path):
                    with open(volt_path, "r") as f:
                        voltage = round(float(f.read().strip()) / 1e6, 2)

                is_low = (percent <= self.threshold) and (not is_charging)
                return BatteryStatus(
                    percent=percent,
                    is_charging=is_charging,
                    is_low_battery=is_low,
                    has_battery=True,
                    voltage=voltage,
                    source=f"sysfs_{os.path.basename(path)}",
                )
            except Exception as exc:
                logger.debug("Failed reading sysfs battery path %s: %s", path, exc)
                continue

        return None

    def _read_psutil_battery(self) -> Optional[BatteryStatus]:
        """Probe battery via psutil library if present."""
        try:
            import psutil
            bat = psutil.sensors_battery()
            if bat is not None:
                percent = float(bat.percent)
                is_charging = bool(bat.power_plugged)
                is_low = (percent <= self.threshold) and (not is_charging)
                return BatteryStatus(
                    percent=percent,
                    is_charging=is_charging,
                    is_low_battery=is_low,
                    has_battery=True,
                    voltage=0.0,
                    source="psutil",
                )
        except Exception:
            pass
        return None
