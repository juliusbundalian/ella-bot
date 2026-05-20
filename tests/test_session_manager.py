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
