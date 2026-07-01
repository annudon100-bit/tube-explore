import os

DEFAULT_CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")


def get_config_dir() -> str:
    return os.environ.get("CONFIG_DIRECTORY", DEFAULT_CONFIG_DIR)


def get_db_path() -> str:
    return os.path.join(get_config_dir(), "tube_explore.db")
