import json

import pytest

from ella_bot.services.profile_store import (
    ProfileLimitError,
    ProfileNotFoundError,
    ProfileStore,
    ProfileValidationError,
)


def test_missing_registry_starts_empty(tmp_path):
    store = ProfileStore(tmp_path / "profiles.json")
    assert store.list_profiles() == ()
    assert store.active_profile() is None


def test_create_persists_profile_as_active(tmp_path):
    path = tmp_path / "profiles.json"
    created = ProfileStore(path).create("  Maria  ")
    restored = ProfileStore(path)

    assert created.name == "Maria"
    assert restored.list_profiles() == (created,)
    assert restored.active_profile() == created
    assert restored.checkpoint_path(created.id) == (
        tmp_path / "profiles" / created.id / "active_session.json"
    )
    assert restored.history_path(created.id) == (
        tmp_path / "profiles" / created.id / "sessions.jsonl"
    )


@pytest.mark.parametrize("name", ["", "   ", "x" * 21, "A\nB", "A\x00B"])
def test_invalid_names_are_rejected(tmp_path, name):
    store = ProfileStore(tmp_path / "profiles.json")
    with pytest.raises(ProfileValidationError):
        store.create(name)


def test_names_are_unique_by_casefold(tmp_path):
    store = ProfileStore(tmp_path / "profiles.json")
    store.create("Maria")
    with pytest.raises(ProfileValidationError):
        store.create("mARIA")


def test_sixth_profile_is_rejected(tmp_path):
    store = ProfileStore(tmp_path / "profiles.json")
    for index in range(5):
        store.create(f"Reader {index}")
    with pytest.raises(ProfileLimitError):
        store.create("Reader 6")


def test_rename_preserves_id_and_paths(tmp_path):
    store = ProfileStore(tmp_path / "profiles.json")
    profile = store.create("Old")
    before = store.checkpoint_path(profile.id)

    renamed = store.rename(profile.id, "New")

    assert renamed.id == profile.id
    assert renamed.name == "New"
    assert store.checkpoint_path(profile.id) == before


def test_select_unknown_profile_is_rejected(tmp_path):
    store = ProfileStore(tmp_path / "profiles.json")
    with pytest.raises(ProfileNotFoundError):
        store.select("missing")


def test_corrupt_registry_is_archived(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text("{broken", encoding="utf-8")

    store = ProfileStore(path)

    assert store.list_profiles() == ()
    assert not path.exists()
    assert len(list(tmp_path.glob("profiles.json.invalid-*"))) == 1


def test_failed_replace_preserves_registry_and_memory(tmp_path, monkeypatch):
    path = tmp_path / "profiles.json"
    store = ProfileStore(path)
    first = store.create("First")
    original = path.read_bytes()
    monkeypatch.setattr(
        "ella_bot.services.profile_store.os.replace",
        lambda *_: (_ for _ in ()).throw(OSError("disk full")),
    )

    with pytest.raises(OSError):
        store.create("Second")

    assert path.read_bytes() == original
    assert store.list_profiles() == (first,)
    assert store.active_profile() == first


def test_registry_with_casefold_duplicate_names_is_archived(tmp_path):
    path = tmp_path / 'profiles.json'
    path.write_text(
        json.dumps(
            {
                'schema_version': 1,
                'active_profile_id': None,
                'profiles': [
                    {
                        'id': 'a' * 32,
                        'name': 'Maria',
                        'created_at': '2026-07-28T10:00:00+08:00',
                    },
                    {
                        'id': 'b' * 32,
                        'name': 'mARIA',
                        'created_at': '2026-07-28T10:00:00+08:00',
                    },
                ],
            }
        ),
        encoding='utf-8',
    )

    store = ProfileStore(path)

    assert store.list_profiles() == ()
    assert not path.exists()
