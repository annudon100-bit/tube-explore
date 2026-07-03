import os

DEFAULT_CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "downloads")
DEFAULT_METADATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "metadata")


def get_config_dir() -> str:
    return os.environ.get("CONFIG_DIRECTORY", DEFAULT_CONFIG_DIR)


def get_db_path() -> str:
    return os.path.join(get_config_dir(), "tube_explore.db")


def get_download_dir() -> str:
    return os.environ.get("DOWNLOAD_DIRECTORY", DEFAULT_DOWNLOAD_DIR)


def get_metadata_dir() -> str:
    return os.environ.get("METADATA_DIRECTORY", DEFAULT_METADATA_DIR)
