import json
from pathlib import Path

import pytest

from ella_bot.services.profile_store import (
    ProfileLimitError,
    ProfileNotFoundError,
    ProfileStore,
    ProfileValidationError,
)


def _write_progress(store, profile, checkpoint=b'checkpoint', history=b'history'):
    checkpoint_path = store.checkpoint_path(profile.id)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_bytes(checkpoint)
    store.history_path(profile.id).write_bytes(history)


def test_reset_progress_keeps_profile_and_other_profile_data(tmp_path):
    store = ProfileStore(tmp_path / 'profiles.json')
    first = store.create('First')
    second = store.create('Second')
    _write_progress(store, first)
    _write_progress(store, second, b'other-checkpoint', b'other-history')

    assert store.reset_progress(first.id) is True

    assert store.checkpoint_path(first.id).exists() is False
    assert store.history_path(first.id).exists() is False
    assert store.history_path(second.id).read_bytes() == b'other-history'
    assert store.list_profiles() == (first, second)


def test_delete_active_profile_clears_selection_only(tmp_path):
    store = ProfileStore(tmp_path / 'profiles.json')
    first = store.create('First')
    second = store.create('Second')
    _write_progress(store, second)

    assert store.delete(second.id) is True

    assert store.list_profiles() == (first,)
    assert store.active_profile() is None
    assert not (tmp_path / 'profiles' / second.id).exists()


def test_reset_restores_original_directory_when_recreation_fails(tmp_path, monkeypatch):
    store = ProfileStore(tmp_path / 'profiles.json')
    profile = store.create('Reader')
    _write_progress(store, profile)
    original_mkdir = Path.mkdir

    def fail_profile_recreation(path, *args, **kwargs):
        if path == tmp_path / 'profiles' / profile.id:
            raise OSError('mkdir failed')
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'mkdir', fail_profile_recreation)
    with pytest.raises(OSError):
        store.reset_progress(profile.id)
    assert store.checkpoint_path(profile.id).read_bytes() == b'checkpoint'


def test_delete_cleanup_failure_leaves_no_registered_profile(tmp_path, monkeypatch):
    store = ProfileStore(tmp_path / 'profiles.json')
    profile = store.create('Reader')
    _write_progress(store, profile)
    monkeypatch.setattr(
        'ella_bot.services.profile_store.shutil.rmtree',
        lambda *_: (_ for _ in ()).throw(OSError('busy')),
    )

    assert store.delete(profile.id) is False
    assert store.list_profiles() == ()
    assert store.active_profile() is None


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


def test_registry_read_oserror_is_raised_without_archiving(tmp_path, monkeypatch):
    path = tmp_path / 'profiles.json'
    path.write_text(
        json.dumps(
            {
                'schema_version': 1,
                'active_profile_id': None,
                'profiles': [],
            }
        ),
        encoding='utf-8',
    )
    original = path.read_bytes()
    original_read_text = Path.read_text

    def fail_registry_read(candidate, *args, **kwargs):
        if candidate == path:
            raise OSError('registry unavailable')
        return original_read_text(candidate, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', fail_registry_read)

    with pytest.raises(OSError, match='registry unavailable'):
        ProfileStore(path)

    assert path.read_bytes() == original
    assert list(tmp_path.glob('profiles.json.invalid-*')) == []


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
