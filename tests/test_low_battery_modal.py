import unittest
from unittest.mock import MagicMock

from ella_bot.services.battery_service import BatteryStatus
from ella_bot.ui.pygame_gui.components.low_battery_modal import LowBatteryModal


class TestLowBatteryModal(unittest.TestCase):

    def setUp(self):
        self.mock_app = MagicMock()
        self.mock_app.audio_feedback = False
        self.mock_app.tts = None
        self.modal = LowBatteryModal(self.mock_app)

    def test_modal_initial_state(self):
        self.assertFalse(self.modal.visible)
        self.assertIsNone(self.modal.hit_test((100, 100)))

    def test_modal_open_on_low_battery(self):
        status = BatteryStatus(
            percent=15.0,
            is_charging=False,
            is_low_battery=True,
            has_battery=True,
            voltage=3.35,
            source="waveshare_ina219_0x42"
        )
        self.modal.open(status)

        self.assertTrue(self.modal.visible)
        self.assertEqual(self.modal.hit_test((100, 100)), "consumed")

    def test_modal_auto_dismiss_when_charging(self):
        low_status = BatteryStatus(
            percent=15.0,
            is_charging=False,
            is_low_battery=True,
            has_battery=True,
            voltage=3.35,
            source="waveshare_ina219_0x42"
        )
        self.modal.open(low_status)
        self.assertTrue(self.modal.visible)

        # Plug in charger -> charging status updated
        charging_status = BatteryStatus(
            percent=15.0,
            is_charging=True,
            is_low_battery=False,
            has_battery=True,
            voltage=4.10,
            source="waveshare_ina219_0x42"
        )
        self.modal.update_status(charging_status)

        self.assertFalse(self.modal.visible)
        self.assertIsNone(self.modal.hit_test((100, 100)))

    def test_modal_auto_dismiss_when_battery_safe(self):
        low_status = BatteryStatus(
            percent=19.0,
            is_charging=False,
            is_low_battery=True,
            has_battery=True,
            voltage=3.38,
            source="sysfs_BAT0"
        )
        self.modal.open(low_status)
        self.assertTrue(self.modal.visible)

        safe_status = BatteryStatus(
            percent=25.0,
            is_charging=False,
            is_low_battery=False,
            has_battery=True,
            voltage=3.60,
            source="sysfs_BAT0"
        )
        self.modal.update_status(safe_status)
        self.assertFalse(self.modal.visible)

    def test_audio_warning_spoken_on_open(self):
        self.mock_app.audio_feedback = True
        self.mock_app.tts = MagicMock()

        status = BatteryStatus(
            percent=18.0,
            is_charging=False,
            is_low_battery=True,
            has_battery=True,
            voltage=3.36,
            source="mock"
        )
        self.modal.open(status)
        self.mock_app.tts.speak.assert_called_once_with(
            "Battery low. To continue using ELLA, please charge or plug in ELLA."
        )


if __name__ == "__main__":
    unittest.main()
