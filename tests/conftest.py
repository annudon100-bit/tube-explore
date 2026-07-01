import tempfile

import pytest

from tube_explore import db


@pytest.fixture(autouse=True)
def temp_config_dir(monkeypatch):
    """Isolate each test with its own config directory and fresh DB."""
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("CONFIG_DIRECTORY", tmp)
    db.init_db()
    yield
    import shutil

    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def sample_profile_data():
    return {
        "name": "test_profile",
        "label": "Test Profile",
        "download_directory": "/tmp/downloads",
        "download_quality_mode": "at_most",
        "download_quality_value": 720,
        "embed_metadata": True,
        "embed_thumbnail": False,
        "subtitles": False,
    }
