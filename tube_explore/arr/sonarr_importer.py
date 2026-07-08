import logging
import os
import shutil
import time
from datetime import datetime, UTC

from tube_explore.arr import db as arr_db
from tube_explore.arr.base_client import ArrError
from tube_explore.arr.path_mapper import map_tube_path_to_arr_path, stage_path_for_playlist_item
from tube_explore.arr.sonarr_client import SonarrClient

logger = logging.getLogger(__name__)


class ImportFailed(Exception):
    pass


class ImportTimeout(Exception):
    pass


class SonarrEpisodeImporter:

    def __init__(self, client: SonarrClient, instance) -> None:
        self.client = client
        self.instance = instance

    def stage_file_for_episode(
        self,
        job_id: str,
        item_id: str,
        downloaded_file_path: str,
        series_title: str,
        season_number: int,
        episode_number: int,
        episode_title: str,
        playlist_index: int,
        file_ext: str,
    ) -> tuple[str, str]:
        """Copy the downloaded file into a single-item staging directory.

        Returns (local_stage_file, arr_stage_path).
        """
        filename = f"{series_title} - S{season_number:02d}E{episode_number:02d} - {episode_title} [tube-{playlist_index:03d}].{file_ext}"
        tube_stage_dir, tube_stage_file = stage_path_for_playlist_item(
            self.instance.tube_write_path,
            self.instance.arr_import_path,
            job_id,
            item_id,
            filename,
        )
        os.makedirs(tube_stage_dir, exist_ok=True)
        shutil.copy2(downloaded_file_path, tube_stage_file)
        logger.info("staged %s -> %s", downloaded_file_path, tube_stage_file)

        arr_stage_path = map_tube_path_to_arr_path(
            tube_stage_file,
            self.instance.tube_write_path,
            self.instance.arr_import_path,
        )
        logger.info("arr_stage_path=%s", arr_stage_path)
        return tube_stage_file, arr_stage_path

    def import_episode_via_scan(self, item: dict, arr_stage_path: str) -> dict:
        """Import using DownloadedEpisodesScan against a single-item path.

        Returns command response dict.
        """
        cmd = self.client.create_command("DownloadedEpisodesScan", path=arr_stage_path)
        cmd_id = cmd.get("id", "")
        logger.info("DownloadedEpisodesScan command=%s path=%s", cmd_id, arr_stage_path)
        return cmd

    def import_episode_via_manual(self, item: dict, arr_stage_path: str) -> dict:
        """Import using manual import endpoint (more deterministic).

        Returns command/import result.
        """
        episode_id = item["episode_id"]
        series_id = item["series_id"]
        candidates = self.client.manual_import([
            {
                "path": arr_stage_path,
                "seriesId": series_id,
                "episodeIds": [episode_id],
                "importMode": self.instance.import_mode or "move",
            }
        ])
        logger.info("manual import result=%s", candidates)
        return candidates[0] if candidates else {}

    def verify_episode_imported(
        self,
        episode_id: int,
        command_id: int | None = None,
        timeout_seconds: int = 120,
    ) -> dict:
        """Poll Sonarr until the episode has a file or timeout.

        Returns the episodeFile dict.
        """
        deadline = datetime.now(UTC).timestamp() + timeout_seconds
        while datetime.now(UTC).timestamp() < deadline:
            if command_id:
                try:
                    cmd = self.client.get_command(command_id)
                    if cmd.get("status") in ("failed", "aborted"):
                        raise ImportFailed(cmd.get("message") or "Command failed")
                except ArrError:
                    pass

            episode = self.client.get_episode(episode_id)
            if episode.get("hasFile"):
                ef = episode.get("episodeFile") or {}
                logger.info("episode %d imported: file=%s", episode_id, ef.get("path"))
                return ef

            time.sleep(2)

        raise ImportTimeout(
            f"Timed out waiting for Sonarr to import episode {episode_id}"
        )

    def import_and_verify(
        self,
        item: dict,
        arr_stage_path: str,
        attempt_manual_first: bool = True,
    ) -> dict:
        """Full import flow: stage -> import -> verify.

        Returns episode_file dict on success, raises on failure.
        """
        episode_id = item["episode_id"]
        attempt_number = item.get("import_attempts", 0) + 1
        job_id = item["job_id"]
        item_id = item["id"]

        arr_db.create_sonarr_playlist_import_attempt(
            item_id=item_id,
            job_id=job_id,
            attempt_number=attempt_number,
            local_stage_file=item.get("local_stage_file", ""),
            arr_stage_path=arr_stage_path,
            import_strategy="DownloadedEpisodesScan",
        )

        arr_db.update_sonarr_playlist_download_item(
            item_id,
            status="import_requested",
            import_attempts=attempt_number,
        )

        cmd = self.import_episode_via_scan(item, arr_stage_path)
        cmd_id = cmd.get("id")

        arr_db.update_sonarr_playlist_download_item(
            item_id,
            status="importing",
            sonarr_command_id=cmd_id,
        )

        try:
            episode_file = self.verify_episode_imported(
                episode_id, command_id=cmd_id
            )
            arr_db.update_sonarr_playlist_download_item(
                item_id,
                status="imported",
                sonarr_episode_file_id=episode_file.get("id"),
                sonarr_episode_file_path=episode_file.get("path"),
                imported_at=datetime.now(UTC).isoformat(),
            )
            return episode_file
        except (ImportFailed, ImportTimeout) as e:
            arr_db.update_sonarr_playlist_download_item(
                item_id,
                status="failed_import",
                error_message=str(e),
            )
            raise
