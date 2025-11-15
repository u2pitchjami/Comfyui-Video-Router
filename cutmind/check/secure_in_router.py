# check/check_enhanced_segments.py

from datetime import datetime

from cutmind.db.repository import CutMindRepository
from shared.utils.logger import get_logger

logger = get_logger("CutMind")


def check_secure_in_router() -> None:
    repo = CutMindRepository()
    videos = repo.get_videos_by_status("processing_router")
    modified_count = 0
    logger.info(f"▶️ videos : {len(videos)}")
    for video in videos:
        logger.info("▶️ processing_router : %s", video.name)
        for seg in video.segments:
            if seg.status != "in_router":
                logger.debug("🛑 segment non modifié  :  %s", seg.status)
                continue
            try:
                seg.last_updated = datetime.now()
                seg.status = "validated"
                repo.update_segment_validation(seg)
                logger.info("✅ Segment mis à jour : %s", seg.uid)
                modified_count += 1
            except Exception as exc:
                logger.error("❌ Erreur sur %s : %s", seg.enhanced_path, exc)
        video.status = "validated"
        repo.update_segment_validation(seg)

    logger.info("✔️ Vérification Secure in Router terminée. %d segments mis à jour.", modified_count)
