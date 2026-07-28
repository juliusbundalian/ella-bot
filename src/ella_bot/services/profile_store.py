from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from uuid import uuid4

SCHEMA_VERSION = 1
MAX_PROFILES = 5

_PROFILE_FIELDS = {"id", "name", "created_at"}
_REGISTRY_FIELDS = {"schema_version", "active_profile_id", "profiles"}
_LOGGER = logging.getLogger(__name__)


class ProfileStoreError(Exception):
    pass


class ProfileValidationError(ProfileStoreError):
    pass


class ProfileLimitError(ProfileStoreError):
    pass


class ProfileNotFoundError(ProfileStoreError):
    pass


@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    created_at: str


class ProfileStore:
    """Persist a small set of learner profiles in a single JSON registry."""

    def __init__(self, registry_path: Path) -> None:
        self.registry_path = Path(registry_path)
        self.profiles_root = self.registry_path.parent / "profiles"
        self._profiles: tuple[Profile, ...] = ()
        self._active_profile_id: str | None = None
        self._load()

    def list_profiles(self) -> tuple[Profile, ...]:
        return self._profiles

    def active_profile(self) -> Profile | None:
        return next(
            (profile for profile in self._profiles if profile.id == self._active_profile_id),
            None,
        )

    def create(self, name: str) -> Profile:
        normalized_name = self._validate_name(name)
        if len(self._profiles) >= MAX_PROFILES:
            raise ProfileLimitError(f"A maximum of {MAX_PROFILES} profiles is allowed")

        profile = Profile(
            id=uuid4().hex,
            name=normalized_name,
            created_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        )
        profiles = self._profiles + (profile,)
        self._write(profiles, profile.id)
        self._profiles = profiles
        self._active_profile_id = profile.id
        return profile

    def rename(self, profile_id: str, name: str) -> Profile:
        profile = self._require_profile(profile_id)
        normalized_name = self._validate_name(name, excluding_profile_id=profile_id)
        renamed = replace(profile, name=normalized_name)
        profiles = tuple(
            renamed if candidate.id == profile_id else candidate
            for candidate in self._profiles
        )
        self._write(profiles, self._active_profile_id)
        self._profiles = profiles
        return renamed

    def select(self, profile_id: str) -> Profile:
        profile = self._require_profile(profile_id)
        self._write(self._profiles, profile_id)
        self._active_profile_id = profile_id
        return profile

    def checkpoint_path(self, profile_id: str) -> Path:
        self._require_profile(profile_id)
        return self.profiles_root / profile_id / "active_session.json"

    def history_path(self, profile_id: str) -> Path:
        self._require_profile(profile_id)
        return self.profiles_root / profile_id / "sessions.jsonl"

    def _require_profile(self, profile_id: str) -> Profile:
        profile = next(
            (candidate for candidate in self._profiles if candidate.id == profile_id),
            None,
        )
        if profile is None:
            raise ProfileNotFoundError(f"Unknown profile: {profile_id}")
        return profile

    def _validate_name(self, name: str, excluding_profile_id: str | None = None) -> str:
        if not isinstance(name, str):
            raise ProfileValidationError("Profile name must be a string")

        trimmed = name.strip()
        if not 1 <= len(trimmed) <= 20:
            raise ProfileValidationError("Profile name must contain 1 to 20 characters")
        if any(not character.isprintable() for character in trimmed):
            raise ProfileValidationError("Profile name contains non-printable characters")

        name_key = trimmed.casefold()
        for profile in self._profiles:
            if profile.id != excluding_profile_id and profile.name.casefold() == name_key:
                raise ProfileValidationError("Profile name must be unique")
        return trimmed

    def _load(self) -> None:
        if not self.registry_path.exists():
            return

        try:
            payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
            profiles, active_profile_id = self._parse_registry(payload)
        except (OSError, json.JSONDecodeError, ProfileValidationError, ValueError, TypeError):
            self._archive_invalid_registry()
            return

        self._profiles = profiles
        self._active_profile_id = active_profile_id

    def _parse_registry(self, payload: object) -> tuple[tuple[Profile, ...], str | None]:
        if not isinstance(payload, dict) or set(payload) != _REGISTRY_FIELDS:
            raise ProfileValidationError("Registry has an invalid schema")
        if payload["schema_version"] != SCHEMA_VERSION or isinstance(
            payload["schema_version"], bool
        ):
            raise ProfileValidationError("Registry schema version is unsupported")

        raw_profiles = payload["profiles"]
        if not isinstance(raw_profiles, list) or len(raw_profiles) > MAX_PROFILES:
            raise ProfileValidationError("Registry has an invalid profile list")

        profiles = tuple(self._parse_profile(raw_profile) for raw_profile in raw_profiles)
        ids = [profile.id for profile in profiles]
        if len(ids) != len(set(ids)):
            raise ProfileValidationError("Registry contains duplicate profile IDs")

        active_profile_id = payload["active_profile_id"]
        if active_profile_id is not None and (
            not isinstance(active_profile_id, str) or active_profile_id not in ids
        ):
            raise ProfileValidationError("Registry has an invalid active profile")
        name_keys = [profile.name.casefold() for profile in profiles]
        if len(name_keys) != len(set(name_keys)):
            raise ProfileValidationError('Registry contains duplicate profile names')
        return profiles, active_profile_id

    def _parse_profile(self, raw_profile: object) -> Profile:
        if not isinstance(raw_profile, dict) or set(raw_profile) != _PROFILE_FIELDS:
            raise ProfileValidationError("Registry has an invalid profile")
        profile_id = raw_profile["id"]
        name = raw_profile["name"]
        created_at = raw_profile["created_at"]
        if not isinstance(profile_id, str) or not self._is_profile_id(profile_id):
            raise ProfileValidationError("Registry has an invalid profile ID")
        normalized_name = self._validate_name(name)
        if not isinstance(created_at, str) or not self._is_timezone_aware_timestamp(created_at):
            raise ProfileValidationError("Registry has an invalid creation timestamp")
        return Profile(id=profile_id, name=normalized_name, created_at=created_at)

    @staticmethod
    def _is_profile_id(profile_id: str) -> bool:
        return len(profile_id) == 32 and all(character in "0123456789abcdef" for character in profile_id)

    @staticmethod
    def _is_timezone_aware_timestamp(timestamp: str) -> bool:
        try:
            parsed = datetime.fromisoformat(timestamp)
        except ValueError:
            return False
        return parsed.tzinfo is not None and parsed.utcoffset() is not None

    def _write(self, profiles: tuple[Profile, ...], active_profile_id: str | None) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: str | None = None
        payload = {
            "schema_version": SCHEMA_VERSION,
            "active_profile_id": active_profile_id,
            "profiles": [
                {"id": profile.id, "name": profile.name, "created_at": profile.created_at}
                for profile in profiles
            ],
        }
        try:
            with tempfile.NamedTemporaryFile(
                delete=False,
                dir=self.registry_path.parent,
                encoding="utf-8",
                mode="w",
            ) as temporary_file:
                temporary_path = temporary_file.name
                json.dump(payload, temporary_file)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, self.registry_path)
            temporary_path = None
        finally:
            if temporary_path is not None:
                try:
                    Path(temporary_path).unlink()
                except FileNotFoundError:
                    pass

    def _archive_invalid_registry(self) -> None:
        archive_path = self.registry_path.with_name(
            f"{self.registry_path.name}.invalid-"
            f"{datetime.now().astimezone().strftime('%Y%m%dT%H%M%S%f')}"
        )
        try:
            os.replace(self.registry_path, archive_path)
        except OSError:
            _LOGGER.exception("Unable to archive invalid profile registry: %s", self.registry_path)
