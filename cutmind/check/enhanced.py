# check/check_enhanced_segments.py

from datetime import datetime
from pathlib import Path

from pymediainfo import MediaInfo

from cutmind.categ.categorization import match_category
from cutmind.db.repository import CutMindRepository
from shared.utils.logger import get_logger

logger = get_logger("CutMind")


def check_enhanced_segments(max_videos: int = 10) -> None:
    repo = CutMindRepository()
    videos = repo.get_videos_by_status("enhanced")[:max_videos]
    modified_count = 0
    logger.info(f"▶️ videos : {len(videos)}")
    for video in videos:
        logger.info("▶️ check_enhanced : %s", video.name)
        for seg in video.segments:
            if seg.status != "enhanced":
                logger.debug("🛑 segment non enrichi  :  %s", seg.status)
                continue

            path = Path(seg.output_path or "")
            if not path.exists():
                logger.warning("🛑 Fichier manquant : %s", path)
                continue

            try:
                media_info = MediaInfo.parse(str(path))
                for track in media_info.tracks:
                    if track.track_type == "Video":
                        updated = False

                        new_res = f"{track.width}x{track.height}"
                        if seg.resolution != new_res:
                            seg.resolution = new_res
                            updated = True

                        if seg.codec != track.codec:
                            seg.codec = track.codec
                            updated = True

                        if seg.bitrate != track.bit_rate:
                            seg.bitrate = track.bit_rate
                            updated = True

                        size_mb = round(path.stat().st_size / (1024 * 1024), 2)
                        if seg.filesize_mb != size_mb:
                            seg.filesize_mb = size_mb
                            updated = True

                        dur = round(track.duration / 1000, 3) if track.duration else None
                        if seg.duration != dur:
                            seg.duration = dur
                            updated = True

                        fps = float(track.frame_rate) if track.frame_rate else None
                        if seg.fps != fps:
                            seg.fps = fps
                            updated = True

                        if updated:
                            seg.last_updated = datetime.now()
                            seg.status = "enhanced"
                            seg.category = match_category(seg.keywords)
                            repo.update_segment_postprocess(seg)
                            logger.info("✅ Segment mis à jour : %s", seg.uid)
                            modified_count += 1

            except Exception as exc:
                logger.error("❌ Erreur sur %s : %s", seg.enhanced_path, exc)

    logger.info("✔️ Vérification terminée. %d segments mis à jour.", modified_count)
