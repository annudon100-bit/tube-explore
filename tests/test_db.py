from tube_explore import db
from tube_explore.models import ProfileCreate, ProfileUpdate, QualityMode


def test_init_db_creates_tables():
    """Settings should have default values after init."""
    s = db.get_all_settings()
    assert "rate_limit" in s
    assert "temp_directory" in s
    assert "retry_count" in s
    assert "socket_timeout" in s


SEED_PROFILE_NAMES = {"best-video", "1080p", "720p", "4k", "audio-best", "audio-mp3", "smallest"}


def test_list_profiles_seeded():
    profiles = db.list_profiles()
    names = {p.name for p in profiles}
    assert names == SEED_PROFILE_NAMES


def test_create_and_get_profile():
    data = ProfileCreate(name="default", download_quality_mode=QualityMode.best)
    p = db.create_profile(data)
    assert p.id > 0
    assert p.name == "default"
    assert p.download_quality_mode == QualityMode.best

    fetched = db.get_profile(p.id)
    assert fetched is not None
    assert fetched.name == "default"


def test_create_profile_with_all_fields():
    data = ProfileCreate(
        name="hd720",
        label="HD 720p",
        download_directory="/videos",
        download_format="mp4",
        download_quality_mode=QualityMode.at_most,
        download_quality_value=720,
        embed_metadata=True,
        embed_thumbnail=True,
        subtitles=True,
        subtitle_langs="en,es",
    )
    p = db.create_profile(data)
    assert p.label == "HD 720p"
    assert p.download_quality_value == 720
    assert p.subtitle_langs == "en,es"


def test_get_profile_by_name():
    data = ProfileCreate(name="by_name_test")
    db.create_profile(data)
    p = db.get_profile_by_name("by_name_test")
    assert p is not None
    assert p.name == "by_name_test"

    assert db.get_profile_by_name("nonexistent") is None


def test_get_nonexistent_profile():
    assert db.get_profile(9999) is None


def test_update_profile():
    data = ProfileCreate(name="updatable")
    p = db.create_profile(data)

    update = ProfileUpdate(label="Updated Label", download_quality_mode=QualityMode.at_least)
    updated = db.update_profile(p.id, update)
    assert updated.label == "Updated Label"
    assert updated.download_quality_mode == QualityMode.at_least


def test_update_profile_no_changes():
    data = ProfileCreate(name="nochg")
    p = db.create_profile(data)
    updated = db.update_profile(p.id, ProfileUpdate())
    assert updated.name == "nochg"


def test_delete_profile():
    data = ProfileCreate(name="deletable")
    p = db.create_profile(data)
    db.delete_profile(p.id)
    assert db.get_profile(p.id) is None


def test_list_profiles():
    for name in ["a", "b", "c"]:
        db.create_profile(ProfileCreate(name=name))
    profiles = db.list_profiles()
    names = {p.name for p in profiles}
    assert names >= {"a", "b", "c"}
    assert "best-video" in names


def test_create_duplicate_name_raises():
    db.create_profile(ProfileCreate(name="dup"))
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        db.create_profile(ProfileCreate(name="dup"))


def test_settings_crud():
    db.set_setting("rate_limit", "5M")
    assert db.get_setting("rate_limit") == "5M"

    db.set_setting("rate_limit", "10M")
    assert db.get_setting("rate_limit") == "10M"


def test_set_settings_bulk():
    db.set_settings({"rate_limit": "1M", "temp_directory": "/tmp/dl"})
    s = db.get_all_settings()
    assert s["rate_limit"] == "1M"
    assert s["temp_directory"] == "/tmp/dl"


def test_get_nonexistent_setting():
    assert db.get_setting("nonexistent_key") is None


import pytest  # noqa: E402
