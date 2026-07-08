import logging
import os
import threading
import time
from datetime import datetime, UTC
from typing import Any

from tube_explore import config, ytdlp
from tube_explore.arr import db as arr_db
from tube_explore.arr.base_client import ArrError
from tube_explore.arr.crypto import decrypt_api_key
from tube_explore.arr.models import SONARR_PLAYLIST_JOB_STATUSES
from tube_explore.arr.path_mapper import stage_path_for_playlist_item
from tube_explore.arr.sonarr_client import SonarrClient
from tube_explore.arr.sonarr_importer import SonarrEpisodeImporter, ImportFailed, ImportTimeout
from tube_explore.models import Profile, TaskInfo

logger = logging.getLogger(__name__)

# In-memory running-jobs tracker for pause/cancel coordination
_running_jobs: dict[str, dict] = {}
_running_jobs_lock = threading.Lock()


class SonarrPlaylistDownloadWorker:

    def __init__(self, task_store: dict, task_lock: threading.Lock, broadcast_fn, main_loop) -> None:
        self._tasks = task_store
        self._lock = task_lock
        self._broadcast = broadcast_fn
        self._main_loop = main_loop

    # ── Job creation ───────────────────────────────────────────

    def enqueue_from_mapping(self, mapping_id: str) -> dict:
        """Snapshot a mapping into a durable job and child item rows."""
        mapping = arr_db.get_playlist_mapping(mapping_id)
        if not mapping:
            raise ValueError(f"Mapping {mapping_id} not found")

        items = mapping.get("items", [])
        instance = arr_db.get_arr_instance(mapping["arr_instance_id"])
        if not instance:
            raise ValueError("Arr instance not found")
        if instance.kind != "sonarr":
            raise ValueError("Instance is not a Sonarr instance")
        if not instance.enabled:
            raise ValueError(f"Instance '{instance.name}' is disabled")

        # Fetch Sonarr episodes to check hasFile
        config_dir = config.get_config_dir()
        decrypted = decrypt_api_key(instance.api_key_encrypted, config_dir)
        client = SonarrClient(instance.base_url, decrypted)
        try:
            sonarr_episodes = client.get_episodes(mapping["series_id"], mapping.get("season_number"))
        except Exception as e:
            raise ValueError(f"Failed to fetch episodes from Sonarr: {e}")

        has_file_by_episode = {ep["id"]: ep.get("hasFile", False) for ep in sonarr_episodes}

        downloadable = []
        skipped = []
        episode_ids_seen: set[int] = set()

        for item in items:
            if item["action"] != "download":
                skipped.append((item, "skipped_by_user"))
                continue
            if not item.get("episode_id"):
                raise ValueError(
                    f"Playlist item '{item.get('video_title', '?')}' (index {item['playlist_index']}) "
                    "has no mapped episode — all included entries must be mapped before download"
                )
            ep_id = item["episode_id"]
            if ep_id in episode_ids_seen:
                raise ValueError(f"Duplicate episode mapping: episode {ep_id} appears in multiple playlist items")
            episode_ids_seen.add(ep_id)
            if has_file_by_episode.get(ep_id):
                skipped.append((item, "skipped_existing"))
                continue
            downloadable.append(item)

        job = arr_db.create_sonarr_playlist_download_job(
            mapping_id=mapping["id"],
            arr_instance_id=instance.id,
            series_id=mapping["series_id"],
            series_title=mapping.get("series_title", ""),
            season_number=mapping.get("season_number"),
            playlist_url=mapping["playlist_url"],
            total_items=len(downloadable) + len(skipped),
            queued_items=len(downloadable),
            skipped_items=len(skipped),
        )
        job_id = job["id"]

        dl_rows = []
        for item in downloadable:
            dl_rows.append({
                "mapping_item_id": item["id"],
                "playlist_index": item["playlist_index"],
                "source_url": item["video_url"],
                "source_title": item.get("video_title", ""),
                "episode_id": item["episode_id"],
                "series_id": mapping["series_id"],
                "season_number": item.get("season_number") or mapping.get("season_number") or 0,
                "episode_number": item.get("episode_number") or 0,
                "episode_title": item.get("episode_title", ""),
                "status": "queued",
                "confidence": item.get("confidence", "none"),
                "action": "download",
            })
        arr_db.create_sonarr_playlist_download_items(job_id, dl_rows)

        for item, reason in skipped:
            skip_status = "skipped_existing" if reason == "skipped_existing" else "skipped_by_user"
            arr_db.create_sonarr_playlist_download_items(job_id, [{
                "mapping_item_id": item["id"],
                "playlist_index": item["playlist_index"],
                "source_url": item.get("video_url", ""),
                "source_title": item.get("video_title", ""),
                "episode_id": item["episode_id"] or 0,
                "series_id": mapping["series_id"],
                "season_number": item.get("season_number") or mapping.get("season_number") or 0,
                "episode_number": item.get("episode_number") or 0,
                "episode_title": item.get("episode_title", ""),
                "status": skip_status,
                "confidence": item.get("confidence", "none"),
                "action": "skip",
            }])

        # Create parent task for UI
        tid = self._create_parent_task(job, instance)
        arr_db.update_sonarr_playlist_download_job(job_id, task_id=tid)

        # Start worker thread
        t = threading.Thread(target=self._run_job_worker, args=(job_id,), daemon=True)
        t.start()

        return arr_db.get_sonarr_playlist_download_job(job_id)

    # ── Parent task creation ───────────────────────────────────

    @staticmethod
    def _fp_status(db_status: str) -> str:
        """Map DB item status to frontend fileProgress status."""
        mapping = {
            "queued": "pending",
            "downloading": "downloading",
            "downloaded": "downloaded",
            "staging": "staging",
            "import_requested": "importing",
            "importing": "importing",
            "imported": "completed",
            "skipped_existing": "completed",
            "skipped_by_user": "skipped",
            "failed_download": "failed",
            "failed_stage": "failed",
            "failed_import": "failed",
            "cancelled": "cancelled",
        }
        return mapping.get(db_status, db_status)

    def _task_data(self, task: TaskInfo, job: dict | None = None) -> dict:
        """Build full task response dict for SSE broadcasts."""
        import json
        total = job.get("total_items", 0) if job else 0
        done = (job.get("imported_items", 0) + job.get("failed_items", 0) + job.get("skipped_items", 0)) if job else 0
        current_idx = done if total > 0 else 0
        progress = int(done / max(total, 1) * 100) if total > 0 else 0

        meta = task.integration_meta or {}
        # Merge DB status with in-memory runtime data (percent, speed, thumbnailUrl)
        fp_by_idx: dict[int, dict] = {e.get("index"): e for e in (task.file_progress or [])}
        items: list[dict] = []
        if job:
            job_id = job["id"]
            db_items = arr_db.get_sonarr_playlist_download_items(job_id)
            for it in db_items:
                idx = it["playlist_index"]
                fp_st = self._fp_status(it["status"])
                entry = {
                    "index": idx,
                    "title": it.get("episode_title") or it.get("source_title", ""),
                    "status": fp_st,
                    "percent": 100.0 if fp_st == "completed" else 0.0,
                }
                mem = fp_by_idx.get(idx)
                if mem:
                    entry["percent"] = mem.get("percent", entry["percent"])
                    if mem.get("speed"):
                        entry["speed"] = mem["speed"]
                    if mem.get("downloadedBytes"):
                        entry["downloadedBytes"] = mem["downloadedBytes"]
                    if mem.get("totalBytes"):
                        entry["totalBytes"] = mem["totalBytes"]
                    if mem.get("thumbnailUrl"):
                        entry["thumbnailUrl"] = mem["thumbnailUrl"]
                items.append(entry)

        return {
            "id": task.id,
            "type": "playlist",
            "status": task.status,
            "title": meta.get("seriesTitle") or task.url,
            "url": task.url,
            "channel": meta.get("seriesTitle"),
            "progressPercent": min(progress, 100),
            "totalItems": total,
            "currentIndex": min(current_idx, total - 1) if total > 0 else None,
            "downloadedBytes": task.downloaded_bytes,
            "totalBytes": task.total_bytes,
            "speed": task.speed,
            "eta": task.eta,
            "elapsed": task.elapsed,
            "progressStep": task.progress_step,
            "thumbnailPath": task.thumbnail_path,
            "createdAt": task.created_at.isoformat() if task.created_at else None,
            "fileProgress": items,
            "integration": {
                "type": "sonarr",
                "targetType": "episode_playlist",
                "jobId": meta.get("jobId"),
                "seriesTitle": meta.get("seriesTitle"),
                "seriesId": meta.get("seriesId"),
                "seasonNumber": meta.get("seasonNumber"),
                "importedEpisodes": job.get("imported_items", 0) if job else 0,
                "failedEpisodes": job.get("failed_items", 0) if job else 0,
                "totalEpisodes": total,
            },
        }

    def _create_parent_task(self, job: dict, instance) -> str:
        import uuid
        tid = str(uuid.uuid4())
        task = TaskInfo(
            id=tid,
            type="playlist",
            url=job["playlist_url"],
            params={"jobId": job["id"], "instanceId": instance.id},
            status="running",
            progress_percent=0,
            created_at=datetime.now(UTC),
            integration="sonarr",
            integration_meta={
                "targetType": "episode_playlist",
                "jobId": job["id"],
                "instanceId": instance.id,
                "instanceName": instance.name,
                "seriesId": job["series_id"],
                "seriesTitle": job["series_title"],
                "seasonNumber": job.get("season_number"),
                "importStatus": "importing",
                "importedEpisodes": 0,
                "failedEpisodes": 0,
                "totalEpisodes": job["total_items"],
            },
        )
        # Build initial file_progress from DB items
        db_items = arr_db.get_sonarr_playlist_download_items(job["id"])
        fp_init: list[dict] = []
        for it in db_items:
            fp_init.append({
                "index": it["playlist_index"],
                "title": it.get("episode_title") or it.get("source_title", ""),
                "status": "pending",
                "percent": 0.0,
            })

        task = task.model_copy(update={
            "title": job.get("series_title") or job["playlist_url"],
            "channel": job.get("series_title"),
            "total_items": job.get("total_items", 0) or 0,
            "current_index": 0,
            "file_progress": fp_init,
        })

        # Try to cache a thumbnail from the first downloadable item
        try:
            for it in db_items:
                if it.get("source_url") and it["status"] == "queued":
                    meta = ytdlp.get_metadata(it["source_url"])
                    thumb_rel = ytdlp.cache_thumbnail(meta["id"], meta.get("thumbnail"))
                    if thumb_rel:
                        task = task.model_copy(update={"thumbnail_path": f"/api/{thumb_rel}"})
                    break
        except Exception:
            logger.warning("Could not cache thumbnail for job %s", job["id"])

        with self._lock:
            self._tasks[tid] = task
        data = self._task_data(task, job)
        self._broadcast("task_created", data)
        return tid

    def _update_parent_task(self, job: dict):
        with self._lock:
            task = self._tasks.get(job.get("task_id", ""))
            if not task:
                return
            meta = dict(task.integration_meta or {})
            meta["importedEpisodes"] = job.get("imported_items", 0)
            meta["failedEpisodes"] = job.get("failed_items", 0)
            meta["totalEpisodes"] = job.get("total_items", 0)
            progress = 0
            total = job.get("total_items", 1) or 1
            done = job.get("imported_items", 0) + job.get("failed_items", 0) + job.get("skipped_items", 0)
            progress = int(done / total * 100)
            task = task.model_copy(update={
                "progress_percent": min(progress, 100),
                "title": job.get("series_title") or task.title or task.url,
                "channel": job.get("series_title") or task.channel,
                "total_items": job.get("total_items", 0) or 0,
                "current_index": min(done, total - 1) if total > 0 else 0,
                "integration_meta": meta,
            })
            self._tasks[task.id] = task
        data = self._task_data(task, job)
        self._broadcast("task_updated", data)

    # ── Job execution ──────────────────────────────────────────

    def _run_job_worker(self, job_id: str):
        with _running_jobs_lock:
            _running_jobs[job_id] = {"cancel": False, "pause": False}

        try:
            arr_db.update_sonarr_playlist_download_job(job_id, status="running", started_at=datetime.now(UTC).isoformat())
            job = arr_db.get_sonarr_playlist_download_job(job_id)
            self._broadcast("sonarr_playlist_job_created", {"jobId": job_id, "status": "running"})

            while True:
                with _running_jobs_lock:
                    ctrl = _running_jobs.get(job_id, {})
                    if ctrl.get("cancel"):
                        self._cancel_current_child(job_id)
                        arr_db.update_sonarr_playlist_download_job(job_id, status="cancelled", completed_at=datetime.now(UTC).isoformat())
                        self._broadcast("sonarr_playlist_job_failed", {"jobId": job_id, "status": "cancelled"})
                        return
                    if ctrl.get("pause"):
                        self._pause_current_child(job_id)
                        return

                item = arr_db.get_next_queued_sonarr_playlist_item(job_id)
                if not item:
                    break

                self._run_item(job_id, item)
                job = arr_db.recompute_sonarr_playlist_job_summary(job_id)
                if job:
                    self._update_parent_task(job)

            # Finalize
            job = arr_db.get_sonarr_playlist_download_job(job_id)
            if not job:
                return
            final_status = self._determine_final_status(job)
            arr_db.update_sonarr_playlist_download_job(
                job_id,
                status=final_status,
                completed_at=datetime.now(UTC).isoformat(),
            )
            self._update_parent_task(arr_db.get_sonarr_playlist_download_job(job_id))
            event = {
                "completed": "sonarr_playlist_job_completed",
                "partially_completed": "sonarr_playlist_job_partially_completed",
                "failed": "sonarr_playlist_job_failed",
            }.get(final_status, "sonarr_playlist_job_failed")
            self._broadcast(event, {"jobId": job_id, "status": final_status})

        except Exception as e:
            logger.error("Job %s failed with error: %s", job_id, e)
            arr_db.update_sonarr_playlist_download_job(
                job_id,
                status="failed",
                error_message=str(e),
                completed_at=datetime.now(UTC).isoformat(),
            )
            self._broadcast("sonarr_playlist_job_failed", {"jobId": job_id, "status": "failed"})
        finally:
            with _running_jobs_lock:
                _running_jobs.pop(job_id, None)

    def _determine_final_status(self, job: dict) -> str:
        total = job.get("total_items", 0)
        imported = job.get("imported_items", 0)
        failed = job.get("failed_items", 0)
        skipped = job.get("skipped_items", 0)
        if total == 0:
            return "completed"
        if imported == total or (imported + skipped) == total:
            return "completed"
        if imported > 0 and failed > 0:
            return "partially_completed"
        if failed > 0 and imported == 0:
            return "failed"
        if imported == 0 and skipped == total:
            return "completed"
        return "failed"

    # ── Single item execution ──────────────────────────────────

    def _run_item(self, job_id: str, item: dict):
        item_id = item["id"]
        logger.info("Running item %s for job %s (episode %d)", item_id, job_id, item["episode_id"])
        _run_job = arr_db.get_sonarr_playlist_download_job(job_id) or {}
        _task_id = _run_job.get("task_id", "")

        # Double-check Sonarr hasn't already gotten this file
        instance = arr_db.get_arr_instance_for_job(job_id)
        if not instance:
            arr_db.update_sonarr_playlist_download_item(item_id, status="failed_download", error_message="Instance not found")
            return
        client = self._make_client(instance)
        try:
            ep = client.get_episode(item["episode_id"])
            if ep.get("hasFile"):
                arr_db.update_sonarr_playlist_download_item(item_id, status="skipped_existing")
                logger.info("Item %s: episode already has file, skipping", item_id)
                return
        except Exception as e:
            logger.warning("Item %s: could not check episode status: %s", item_id, e)
            # Proceed anyway

        # ── Download phase ──
        arr_db.update_sonarr_playlist_download_item(
            item_id, status="downloading",
            download_attempts=item.get("download_attempts", 0) + 1,
            started_at=datetime.now(UTC).isoformat(),
        )
        self._broadcast_parent_task(job_id)
        self._broadcast("sonarr_playlist_item_downloading", {"jobId": job_id, "itemId": item_id, "episodeId": item["episode_id"]})

        download_base = config.get_download_dir()
        settings = {}
        try:
            from tube_explore import db as main_db
            settings = main_db.get_all_settings()
        except Exception:
            pass
        temp_dir = settings.get("temp_directory", "").strip() or "/temp"

        work_dir = os.path.join(download_base, "_tube-explore", "work", job_id, item_id)
        os.makedirs(work_dir, exist_ok=True)
        arr_db.update_sonarr_playlist_download_item(item_id, work_dir=work_dir)

        profile = Profile(
            id=0, name="__playlist_item__",
            download_quality_mode="best",
            embed_metadata=True, embed_thumbnail=False,
            subtitles=False,
            filename_template="%(title)s [%(id)s].%(ext)s",
            created_at=datetime.now(), updated_at=datetime.now(),
        )

        # Cache individual video thumbnail
        _item_thumb_path: str | None = None
        try:
            meta = ytdlp.get_metadata(item["source_url"])
            thumb_rel = ytdlp.cache_thumbnail(meta["id"], meta.get("thumbnail"))
            if thumb_rel:
                _item_thumb_path = f"/api/{thumb_rel}"
        except Exception:
            pass

        # Stamp thumbnail into in-memory file_progress entry
        if _item_thumb_path:
            with self._lock:
                t = self._tasks.get(_task_id)
                if t:
                    fp = t.file_progress.copy()
                    for entry in fp:
                        if entry.get("index") == item["playlist_index"]:
                            entry["thumbnailUrl"] = _item_thumb_path
                            break
                    self._tasks[t.id] = t.model_copy(update={"file_progress": fp})

        try:
            source_url = item["source_url"]
            _last_broadcast_pct = -5
            _dl_speed: int | None = None
            _dl_downloaded: int = 0
            _dl_total: int | None = None

            def _progress(pct: int, file_progress_list: list[dict] | None = None, extra: dict | None = None):
                nonlocal _last_broadcast_pct, _dl_speed, _dl_downloaded, _dl_total
                if extra:
                    _dl_speed = extra.get("speed") or _dl_speed
                    _dl_downloaded = extra.get("downloaded_bytes", 0) or _dl_downloaded
                    _dl_total = extra.get("total_bytes") or _dl_total

                if not (pct >= _last_broadcast_pct + 5 or pct == 0 or pct == 100):
                    return
                _last_broadcast_pct = pct

                with self._lock:
                    task = self._tasks.get(_task_id)
                    if not task:
                        return
                    fp = task.file_progress.copy()
                    for entry in fp:
                        if entry.get("index") == item["playlist_index"]:
                            entry["percent"] = pct
                            entry["status"] = "downloading"
                            if _dl_speed:
                                entry["speed"] = _dl_speed
                            if _dl_downloaded:
                                entry["downloadedBytes"] = _dl_downloaded
                            if _dl_total:
                                entry["totalBytes"] = _dl_total
                            break
                    task = task.model_copy(update={
                        "file_progress": fp,
                        "speed": _dl_speed,
                        "downloaded_bytes": _dl_downloaded,
                        "total_bytes": _dl_total,
                    })
                    self._tasks[task.id] = task

                self._broadcast_parent_task(job_id)

            result = ytdlp.download_video(
                url=source_url,
                output_dir=work_dir,
                profile=profile,
                settings=settings,
                task_id=None,
                progress_callback=_progress,
                download_base=download_base,
                temp_dir=temp_dir,
            )
        except Exception as exc:
            logger.error("Item %s download failed: %s", item_id, exc)
            arr_db.update_sonarr_playlist_download_item(
                item_id, status="failed_download",
                error_message=str(exc),
            )
            self._broadcast("sonarr_playlist_item_failed", {"jobId": job_id, "itemId": item_id, "phase": "download"})
            return

        files = result.get("files", [])
        if not files:
            arr_db.update_sonarr_playlist_download_item(
                item_id, status="failed_download",
                error_message="No files produced by download",
            )
            return

        # Take the first media file
        dl_file = files[0]
        dl_path = dl_file["path"]
        if not os.path.isfile(dl_path):
            arr_db.update_sonarr_playlist_download_item(
                item_id, status="failed_download",
                error_message=f"File not found: {dl_path}",
            )
            return

        arr_db.update_sonarr_playlist_download_item(
            item_id, status="downloaded",
            local_download_path=dl_path,
            downloaded_at=datetime.now(UTC).isoformat(),
        )
        self._broadcast("sonarr_playlist_item_downloaded", {"jobId": job_id, "itemId": item_id, "episodeId": item["episode_id"]})

        # ── Staging phase ──
        arr_db.update_sonarr_playlist_download_item(item_id, status="staging")
        self._broadcast_parent_task(job_id)
        importer = SonarrEpisodeImporter(client, instance)
        file_ext = os.path.splitext(dl_path)[1].lstrip(".") or "mp4"
        try:
            local_stage_file, arr_stage_path = importer.stage_file_for_episode(
                job_id=job_id,
                item_id=item_id,
                downloaded_file_path=dl_path,
                series_title=instance.name or item.get("series_title", "Unknown"),
                season_number=item["season_number"],
                episode_number=item["episode_number"],
                episode_title=item.get("episode_title", "Unknown"),
                playlist_index=item["playlist_index"],
                file_ext=file_ext,
            )
        except Exception as exc:
            logger.error("Item %s staging failed: %s", item_id, exc)
            arr_db.update_sonarr_playlist_download_item(
                item_id, status="failed_stage",
                error_message=str(exc),
            )
            self._broadcast("sonarr_playlist_item_failed", {"jobId": job_id, "itemId": item_id, "phase": "stage"})
            return

        arr_db.update_sonarr_playlist_download_item(
            item_id,
            local_stage_dir=os.path.dirname(local_stage_file),
            local_stage_file=local_stage_file,
            arr_stage_path=arr_stage_path,
        )

        # Refresh item from DB so import_and_verify gets local_stage_file
        item = arr_db.get_sonarr_playlist_download_item(item_id) or item

        # ── Import phase ──
        arr_db.update_sonarr_playlist_download_item(item_id, status="importing")
        self._broadcast_parent_task(job_id)
        self._broadcast("sonarr_playlist_item_importing", {"jobId": job_id, "itemId": item_id, "episodeId": item["episode_id"]})
        try:
            episode_file = importer.import_and_verify(item, arr_stage_path)
            logger.info("Item %s imported: file_id=%s path=%s", item_id, episode_file.get("id"), episode_file.get("path"))
            self._broadcast("sonarr_playlist_item_imported", {"jobId": job_id, "itemId": item_id, "episodeId": item["episode_id"]})
        except (ImportFailed, ImportTimeout) as exc:
            logger.error("Item %s import failed: %s", item_id, exc)
            self._broadcast("sonarr_playlist_item_failed", {"jobId": job_id, "itemId": item_id, "phase": "import"})
        except Exception as exc:
            logger.error("Item %s import error: %s", item_id, exc)
            arr_db.update_sonarr_playlist_download_item(
                item_id, status="failed_import",
                error_message=str(exc),
            )
            self._broadcast("sonarr_playlist_item_failed", {"jobId": job_id, "itemId": item_id, "phase": "import"})

    # ── Client helpers ─────────────────────────────────────────

    def _make_client(self, instance) -> SonarrClient:
        config_dir = config.get_config_dir()
        decrypted = decrypt_api_key(instance.api_key_encrypted, config_dir)
        return SonarrClient(instance.base_url, decrypted)

    def _broadcast_parent_task(self, job_id: str) -> None:
        job = arr_db.get_sonarr_playlist_download_job(job_id)
        if not job:
            return
        job = arr_db.recompute_sonarr_playlist_job_summary(job_id) or job
        with self._lock:
            task = self._tasks.get(job.get("task_id", ""))
            if task:
                self._broadcast("task_updated", self._task_data(task, job))

    # ── Control operations ─────────────────────────────────────

    def pause_job(self, job_id: str) -> None:
        with _running_jobs_lock:
            ctrl = _running_jobs.get(job_id)
            if ctrl is not None:
                ctrl["pause"] = True
        arr_db.update_sonarr_playlist_download_job(job_id, status="paused")
        job = arr_db.get_sonarr_playlist_download_job(job_id) or {}
        with self._lock:
            task = self._tasks.get(job.get("task_id", ""))
            if task:
                task = task.model_copy(update={"status": "paused"})
                self._tasks[task.id] = task
                self._broadcast("task_updated", self._task_data(task, job))

    def resume_job(self, job_id: str) -> None:
        with _running_jobs_lock:
            ctrl = _running_jobs.get(job_id)
            if ctrl is not None:
                ctrl["pause"] = False
        arr_db.update_sonarr_playlist_download_job(job_id, status="running")
        job = arr_db.get_sonarr_playlist_download_job(job_id) or {}
        with self._lock:
            task = self._tasks.get(job.get("task_id", ""))
            if task:
                task = task.model_copy(update={"status": "running"})
                self._tasks[task.id] = task
                self._broadcast("task_updated", self._task_data(task, job))
        t = threading.Thread(target=self._run_job_worker, args=(job_id,), daemon=True)
        t.start()

    def cancel_job(self, job_id: str) -> None:
        with _running_jobs_lock:
            ctrl = _running_jobs.get(job_id)
            if ctrl is not None:
                ctrl["cancel"] = True
        with _running_jobs_lock:
            _running_jobs.pop(job_id, None)
        # Cancel all queued items
        items = arr_db.get_sonarr_playlist_download_items(job_id)
        for item in items:
            if item["status"] in ("queued",):
                arr_db.update_sonarr_playlist_download_item(item["id"], status="cancelled")
        job = arr_db.update_sonarr_playlist_download_job(job_id, status="cancelled", completed_at=datetime.now(UTC).isoformat())
        job = arr_db.get_sonarr_playlist_download_job(job_id) or {}
        with self._lock:
            task = self._tasks.get(job.get("task_id", ""))
            if task:
                task = task.model_copy(update={"status": "cancelled", "progress_percent": 100})
                self._tasks[task.id] = task
                data = self._task_data(task, job)
                self._broadcast("task_updated", data)
        self._broadcast("sonarr_playlist_job_failed", {"jobId": job_id, "status": "cancelled"})

    def _pause_current_child(self, job_id: str) -> None:
        job = arr_db.update_sonarr_playlist_download_job(job_id, status="paused")
        job = arr_db.get_sonarr_playlist_download_job(job_id) or {}
        with self._lock:
            task = self._tasks.get(job.get("task_id", ""))
            if task:
                task = task.model_copy(update={"status": "paused"})
                self._tasks[task.id] = task
                self._broadcast("task_updated", self._task_data(task, job))

    def _cancel_current_child(self, job_id: str) -> None:
        items = arr_db.get_sonarr_playlist_download_items(job_id)
        for item in items:
            if item["status"] in ("queued",):
                arr_db.update_sonarr_playlist_download_item(item["id"], status="cancelled")

    def retry_item(self, item_id: str) -> dict | None:
        item = arr_db.get_sonarr_playlist_download_item(item_id)
        if not item:
            raise ValueError(f"Item {item_id} not found")
        if item["status"] not in ("failed_download", "failed_stage", "failed_import"):
            raise ValueError(f"Cannot retry item in status '{item['status']}'")

        job = arr_db.get_sonarr_playlist_download_job(item["job_id"])
        if not job:
            raise ValueError("Parent job not found")

        # Reset to queued
        arr_db.update_sonarr_playlist_download_item(
            item_id,
            status="queued",
            error_code=None,
            error_message=None,
            work_dir=None,
            local_download_path=None,
            local_stage_dir=None,
            local_stage_file=None,
            arr_stage_path=None,
            sonarr_command_id=None,
            sonarr_episode_file_id=None,
            sonarr_episode_file_path=None,
        )

        # Restart worker if job is not running
        with _running_jobs_lock:
            ctrl = _running_jobs.get(item["job_id"])
            if ctrl is None or ctrl.get("cancel"):
                t = threading.Thread(target=self._run_job_worker, args=(item["job_id"],), daemon=True)
                t.start()

        return arr_db.get_sonarr_playlist_download_item(item_id)

    def retry_failed_items(self, job_id: str) -> int:
        items = arr_db.get_sonarr_playlist_download_items(job_id)
        retried = 0
        for item in items:
            if item["status"] in ("failed_download", "failed_stage", "failed_import"):
                try:
                    self.retry_item(item["id"])
                    retried += 1
                except ValueError:
                    pass
        return retried
