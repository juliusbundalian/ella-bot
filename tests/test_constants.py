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


def test_tier_sublevels_cover_all_levels_once():
    seen = []
    for subs in constants.TIER_SUBLEVELS.values():
        seen.extend(subs)
    assert seen == list(constants.LEVEL_ORDER)
    assert sorted(constants.TIER_SUBLEVELS.keys()) == [1, 2, 3, 4]
    assert constants.TIER_SUBLEVELS[1] == ["1a", "1b", "1c", "1d", "1e", "1f", "1g"]


def test_tier_of_maps_each_level_to_its_tier():
    assert constants.tier_of("1a") == 1
    assert constants.tier_of("1g") == 1
    assert constants.tier_of("2c") == 2
    assert constants.tier_of("3") == 3
    assert constants.tier_of("4") == 4


def test_tier_of_returns_zero_for_unknown_level():
    assert constants.tier_of("hard") == 0
