import pytest

from ella_bot.services.session_manager import SessionManager

POOLS = {
    "1a": ["a", "the", "is"],
    "1b": ["cat", "dog"],
    "hard": ["the quick brown fox"],
}


def make_session(level="1a"):
    return SessionManager(level_pools=dict(POOLS), start_level=level)


def test_starts_on_first_sentence_of_level():
    s = SessionManager(level_pools={"1a": ["a", "the"]}, start_level="1a")
    assert s.current_level == "1a"
    assert s.expected_sentence == "a"
    assert s.level_goal == 2
    assert s.completed_in_level == 0


def test_invalid_start_level_falls_back_to_1a():
    s = SessionManager(level_pools={"1a": ["a"]}, start_level="zz")
    assert s.current_level == "1a"


def test_advance_to_next_sentence_walks_pool_and_clamps():
    s = SessionManager(level_pools={"1a": ["a", "the"]}, start_level="1a")
    s.advance_to_next_sentence()
    assert s.expected_sentence == "the"
    s.advance_to_next_sentence()  # clamp at last
    assert s.expected_sentence == "the"


def test_current_item_number_is_one_based():
    s = SessionManager(level_pools={"1a": ["a", "the"]}, start_level="1a")
    assert s.current_item_number() == 1
    s.advance_to_next_sentence()
    assert s.current_item_number() == 2


def test_display_level_name_titlecases():
    s = SessionManager(level_pools={"1a": ["a"]}, start_level="1a")
    assert s.display_level_name() == "1A"


def test_try_level_up_requires_goal_then_threshold():
    s = SessionManager(
        level_pools={"1a": ["a"], "1b": ["cat"]}, start_level="1a"
    )
    # goal not yet met -> no level up
    assert s.try_level_up(0.99) is False
    s.completed_in_level = s.level_goal
    # goal met but below 1a threshold (0.85) -> no level up
    assert s.try_level_up(0.50) is False
    # goal met and at/above threshold -> level up and reset
    assert s.try_level_up(0.90) is True
    assert s.current_level == "1b"
    assert s.completed_in_level == 0
    assert s.expected_sentence == "cat"


def test_hard_level_never_levels_up():
    s = SessionManager(level_pools=dict(POOLS), start_level="1a")
    s.current_level = "hard"
    assert s.try_level_up(1.0) is False


def test_build_start_announcement_mentions_level_item_and_sentence():
    s = SessionManager(level_pools={"1a": ["the cat"]}, start_level="1a")
    text = s.build_start_announcement()
    assert "1A" in text
    assert "item 1" in text.lower()
    assert "the cat" in text


def test_reset_to_start_returns_to_level_1a():
    from ella_bot.services.session_manager import SessionManager

    sm = SessionManager(
        level_pools={"1a": ["cat", "dog"], "1b": ["fish"]},
        start_level="1a",
    )
    sm.current_level = "1b"
    sm.level_indices["1b"] = 0
    sm.completed_in_level = 3

    sm.reset_to_start()

    assert sm.current_level == "1a"
    assert sm.completed_in_level == 0
    assert sm.level_indices["1a"] == 0
    assert sm.expected_sentence in ("cat", "dog")


FULL_POOLS = {
    "1a": ["a"], "1b": ["b"], "1c": ["c"], "1d": ["d"],
    "1e": ["e"], "1f": ["f"], "1g": ["g"],
    "2a": ["go"], "2b": ["up"], "2c": ["in"], "2d": ["on"],
    "3": ["the cat"], "4": ["the big dog"],
}


def test_tier_of_and_is_last_sublevel_of_tier():
    s = SessionManager(level_pools=dict(FULL_POOLS), start_level="1a")
    assert s.tier_of("1a") == 1
    assert s.tier_of("2c") == 2
    assert s.is_last_sublevel_of_tier("1g") is True
    assert s.is_last_sublevel_of_tier("1a") is False
    assert s.is_last_sublevel_of_tier("2d") is True
    assert s.is_last_sublevel_of_tier("3") is True
    assert s.is_last_sublevel_of_tier("4") is True


def test_is_last_tier():
    s = SessionManager(level_pools=dict(FULL_POOLS), start_level="1a")
    assert s.is_last_tier(4) is True
    assert s.is_last_tier(1) is False


def test_current_sublevel_complete_does_not_depend_on_threshold():
    # Level 3 has threshold 1.01 (unreachable) but completion is goal-based.
    s = SessionManager(level_pools=dict(FULL_POOLS), start_level="3")
    assert s.current_sublevel_complete() is False
    s.completed_in_level = s.level_goal
    assert s.current_sublevel_complete() is True


def test_current_sublevel_complete_false_for_hard():
    s = SessionManager(level_pools={"1a": ["a"], "hard": ["x y"]}, start_level="1a")
    s.current_level = "hard"
    s.completed_in_level = 99
    assert s.current_sublevel_complete() is False


def test_advance_to_higher_stage_crosses_tier_boundary():
    s = SessionManager(level_pools=dict(FULL_POOLS), start_level="1g")
    assert s.advance_to_higher_stage() is True
    assert s.current_level == "2a"
    assert s.completed_in_level == 0


def test_retry_sublevel_resets_progress():
    s = SessionManager(level_pools=dict(FULL_POOLS), start_level="1c")
    s.completed_in_level = 1
    s.level_indices["1c"] = 0
    s.retry_sublevel("1c")
    assert s.current_level == "1c"
    assert s.completed_in_level == 0


def test_retry_tier_returns_to_first_sublevel():
    s = SessionManager(level_pools=dict(FULL_POOLS), start_level="1g")
    s.completed_in_level = 1
    s.retry_tier(1)
    assert s.current_level == "1a"
    assert s.completed_in_level == 0
    assert s.level_indices["1g"] == 0


# ── Session item limit tests ──────────────────────────────────────────────────

def _tier2_pools(tier2_pool_size: int = 40) -> dict:
    """Full pool dict with a large tier-2 pool for limit testing."""
    return {
        "1a": ["a"], "1b": ["b"], "1c": ["c"], "1d": ["d"],
        "1e": ["e"], "1f": ["f"], "1g": ["g"],
        "2a": [str(i) for i in range(tier2_pool_size)],
        "2b": ["up"], "2c": ["in"], "2d": ["on"],
        "3": ["the cat"], "4": ["the big dog"],
    }


def test_tier1_level_goal_equals_full_pool_size():
    pool = [str(i) for i in range(15)]
    s = SessionManager(level_pools={"1a": pool}, start_level="1a")
    assert s.level_goal == 15


def test_tier2_level_goal_capped_at_session_limit():
    s = SessionManager(level_pools=_tier2_pools(40), start_level="2a")
    assert s.level_goal == 10


def test_tier2_small_pool_uses_full_pool_when_below_limit():
    pools = _tier2_pools()
    pools["2a"] = ["x", "y", "z"]
    s = SessionManager(level_pools=pools, start_level="2a")
    assert s.level_goal == 3


def test_tier2_session_items_are_drawn_from_full_pool():
    pools = _tier2_pools(40)
    s = SessionManager(level_pools=pools, start_level="2a")
    items = [s.expected_sentence]
    for _ in range(9):
        s.advance_to_next_sentence()
        items.append(s.expected_sentence)
    assert len(set(items)) == 10
    assert all(item in pools["2a"] for item in items)


def test_advance_to_higher_stage_builds_tier2_session_pool():
    s = SessionManager(level_pools=_tier2_pools(40), start_level="1g")
    s.advance_to_higher_stage()
    assert s.current_level == "2a"
    assert s.level_goal == 10


def test_reset_current_level_rebuilds_tier2_session_pool():
    s = SessionManager(level_pools=_tier2_pools(40), start_level="2a")
    s.completed_in_level = s.level_goal
    s.reset_current_level()
    assert s.level_goal == 10
    assert s.completed_in_level == 0


def test_retry_sublevel_rebuilds_tier2_session_pool():
    s = SessionManager(level_pools=_tier2_pools(40), start_level="2a")
    s.retry_sublevel("2a")
    assert s.level_goal == 10
    assert s.completed_in_level == 0


def test_checkpoint_round_trip_restores_exact_item_and_progress():
    pools = {"1a": ["a", "e", "i"], "1b": ["b"]}
    original = SessionManager(level_pools=pools, start_level="1a")
    original.advance_to_next_sentence()
    original.completed_in_level = 1
    original.last_announced_sentence = "e"

    restored = SessionManager.from_checkpoint(pools, original.to_checkpoint())

    assert restored.current_level == "1a"
    assert restored.current_item_number() == 2
    assert restored.expected_sentence == "e"
    assert restored.completed_in_level == 1
    assert restored.level_goal == 3
    assert restored.last_announced_sentence == "e"


def test_checkpoint_round_trip_preserves_randomized_pool_order():
    pools = _tier2_pools(40)
    original = SessionManager(level_pools=pools, start_level="2a")
    original.advance_to_next_sentence()
    original.advance_to_next_sentence()
    saved_order = list(original._session_pools["2a"])

    restored = SessionManager.from_checkpoint(pools, original.to_checkpoint())

    assert restored._session_pools["2a"] == saved_order
    assert restored.current_item_number() == 3
    assert restored.expected_sentence == saved_order[2]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update(current_level="missing"),
        lambda payload: payload["level_indices"].update({"1a": -1}),
        lambda payload: payload.update(completed_in_level=-1),
        lambda payload: payload.update(expected_sentence="not the current item"),
        lambda payload: payload.update(level_goal=1),
    ],
)
def test_checkpoint_restore_rejects_invalid_session_state(mutate):
    pools = {"1a": ["a", "e"]}
    payload = SessionManager(level_pools=pools, start_level="1a").to_checkpoint()
    mutate(payload)

    with pytest.raises(ValueError):
        SessionManager.from_checkpoint(pools, payload)
