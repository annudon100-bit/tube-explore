import os
import posixpath
from pathlib import Path


class PathMappingError(ValueError):
    pass


def map_tube_path_to_arr_path(local_path: str, tube_write_path: str, arr_import_path: str) -> str:
    local = Path(local_path).resolve(strict=False)
    tube_root = Path(tube_write_path).resolve(strict=False)

    try:
        relative = local.relative_to(tube_root)
    except ValueError:
        raise PathMappingError(
            f"Path {local_path} is outside configured Tube Explore write path {tube_write_path}"
        )

    return posixpath.join(arr_import_path.rstrip("/"), *relative.parts)


def to_arr_path(
    tube_write_path: str,
    arr_import_path: str,
    arr_item_path: str,
    local_file_path: str,
) -> tuple[str, str]:
    """Map a local file to the Arr-visible path.

    Returns (local_staging_dir, arr_staging_dir) where both point to the
    same content but from different roots (Tube vs Arr container).
    """
    radarr_base = arr_import_path.rstrip("/")
    subdir = arr_item_path
    if radarr_base and arr_item_path.startswith(radarr_base):
        subdir = arr_item_path[len(radarr_base):].lstrip("/")
    tube_dest_dir = os.path.join(tube_write_path, subdir)
    dest = os.path.join(tube_dest_dir, os.path.basename(local_file_path))
    return tube_dest_dir, dest


def stage_path_for_playlist_item(
    tube_write_path: str,
    arr_import_path: str,
    job_id: str,
    item_id: str,
    filename: str,
) -> tuple[str, str]:
    """Build staging paths for a single playlist download item.

    Returns (local_stage_dir, local_stage_file) — both are tube-side paths.
    The arr-side path is derived by mapping local_stage_file through
    map_tube_path_to_arr_path.

    Staging layout:
        <tube_write_path>/_tube-explore/sonarr-playlists/<job_id>/<item_id>/<filename>
    """
    rel = os.path.join("_tube-explore", "sonarr-playlists", job_id, item_id)
    tube_stage_dir = os.path.join(tube_write_path, rel)
    tube_stage_file = os.path.join(tube_stage_dir, filename)
    return tube_stage_dir, tube_stage_file
