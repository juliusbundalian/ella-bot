import os
import unittest
from unittest.mock import MagicMock, patch

from ella_bot.services.battery_service import BatteryService, BatteryStatus


class TestBatteryService(unittest.TestCase):

    def setUp(self):
        # Clear mock env vars before each test
        os.environ.pop("ELLA_MOCK_BATTERY", None)
        os.environ.pop("ELLA_MOCK_PLUGGED", None)

    def tearDown(self):
        os.environ.pop("ELLA_MOCK_BATTERY", None)
        os.environ.pop("ELLA_MOCK_PLUGGED", None)

    def test_mock_env_low_battery_unplugged(self):
        os.environ["ELLA_MOCK_BATTERY"] = "18"
        os.environ["ELLA_MOCK_PLUGGED"] = "0"
        service = BatteryService(threshold=20.0)
        status = service.get_status(force_refresh=True)

        self.assertEqual(status.percent, 18.0)
        self.assertFalse(status.is_charging)
        self.assertTrue(status.is_low_battery)
        self.assertEqual(status.source, "mock")

    def test_mock_env_low_battery_plugged_in(self):
        os.environ["ELLA_MOCK_BATTERY"] = "15"
        os.environ["ELLA_MOCK_PLUGGED"] = "1"
        service = BatteryService(threshold=20.0)
        status = service.get_status(force_refresh=True)

        self.assertEqual(status.percent, 15.0)
        self.assertTrue(status.is_charging)
        self.assertFalse(status.is_low_battery)  # Charging suppresses low battery modal!
        self.assertEqual(status.source, "mock")

    def test_mock_env_normal_battery(self):
        os.environ["ELLA_MOCK_BATTERY"] = "85"
        os.environ["ELLA_MOCK_PLUGGED"] = "0"
        service = BatteryService(threshold=20.0)
        status = service.get_status(force_refresh=True)

        self.assertEqual(status.percent, 85.0)
        self.assertFalse(status.is_charging)
        self.assertFalse(status.is_low_battery)

    @patch("ella_bot.services.battery_service.BatteryService._read_waveshare_ups_i2c")
    @patch("ella_bot.services.battery_service.BatteryService._read_sysfs_battery")
    @patch("ella_bot.services.battery_service.BatteryService._read_psutil_battery")
    def test_waveshare_i2c_priority(self, mock_psutil, mock_sysfs, mock_i2c):
        mock_i2c.return_value = BatteryStatus(
            percent=19.0,
            is_charging=False,
            is_low_battery=True,
            has_battery=True,
            voltage=3.38,
            source="waveshare_ina219_0x42"
        )

        service = BatteryService(threshold=20.0)
        status = service.get_status(force_refresh=True)

        self.assertEqual(status.percent, 19.0)
        self.assertTrue(status.is_low_battery)
        self.assertEqual(status.source, "waveshare_ina219_0x42")
        mock_sysfs.assert_not_called()
        mock_psutil.assert_not_called()

    @patch("ella_bot.services.battery_service.BatteryService._read_waveshare_ups_i2c", return_value=None)
    @patch("ella_bot.services.battery_service.BatteryService._read_sysfs_battery")
    @patch("ella_bot.services.battery_service.BatteryService._read_psutil_battery")
    def test_sysfs_fallback(self, mock_psutil, mock_sysfs, mock_i2c):
        mock_sysfs.return_value = BatteryStatus(
            percent=12.0,
            is_charging=False,
            is_low_battery=True,
            has_battery=True,
            voltage=3.30,
            source="sysfs_BAT0"
        )

        service = BatteryService(threshold=20.0)
        status = service.get_status(force_refresh=True)

        self.assertEqual(status.percent, 12.0)
        self.assertTrue(status.is_low_battery)
        self.assertEqual(status.source, "sysfs_BAT0")

    @patch("ella_bot.services.battery_service.BatteryService._read_waveshare_ups_i2c", return_value=None)
    @patch("ella_bot.services.battery_service.BatteryService._read_sysfs_battery", return_value=None)
    @patch("ella_bot.services.battery_service.BatteryService._read_psutil_battery", return_value=None)
    def test_no_battery_fallback(self, mock_psutil, mock_sysfs, mock_i2c):
        service = BatteryService(threshold=20.0)
        status = service.get_status(force_refresh=True)

        self.assertFalse(status.has_battery)
        self.assertFalse(status.is_low_battery)
        self.assertTrue(status.is_charging)
        self.assertEqual(status.source, "none")


if __name__ == "__main__":
    unittest.main()
