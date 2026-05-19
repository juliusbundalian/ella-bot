from ella_bot.core import constants


def test_level_order_is_canonical():
    assert constants.LEVEL_ORDER[0] == "1a"
    assert constants.LEVEL_ORDER[-1] == "4"
    assert len(constants.LEVEL_ORDER) == 13


def test_every_level_has_a_threshold():
    for level in constants.LEVEL_ORDER:
        assert level in constants.LEVEL_THRESHOLDS


def test_top_levels_are_unreachable_by_threshold():
    assert constants.LEVEL_THRESHOLDS["3"] == 1.01
    assert constants.LEVEL_THRESHOLDS["4"] == 1.01
