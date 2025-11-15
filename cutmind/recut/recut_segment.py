""" """

from __future__ import annotations

from pathlib import Path
import re

from cutmind.db.manual_db import (
    delete_segment,
    get_current_segment_data,
    insert_segment,
)
from cutmind.manual.manual_utils import cleanup_file, safe_to_float
from cutmind.models_cm.cursor_protocol import DictCursorProtocol
from cutmind.recut.ffmpeg_recut import ffmpeg_recut_video
from shared.utils.config import TRASH_DIR_SC
from shared.utils.logger import get_logger
from shared.utils.trash import move_to_trash

logger = get_logger("CutMind")


def perform_recut(cur: DictCursorProtocol, seg_id: int, recut_points: list[float]) -> None:
    """Découpe un segment existant en plusieurs nouveaux (ffmpeg)."""
    old_data = get_current_segment_data(cur, seg_id)
    if not old_data:
        logger.warning("⚠️ Segment %s introuvable pour recut", seg_id)
        return

    input_path = Path(str(old_data["output_path"]))
    output_dir = input_path.parent / "recut"

    try:
        new_files = ffmpeg_recut_video(input_path, recut_points, output_dir)
    except Exception as e:
        logger.error("❌ Erreur ffmpeg recut %s : %s", seg_id, e)
        return

    start, end = map(safe_to_float, (old_data.get("start", 0.0), old_data.get("end", 0.0)))
    cuts = [start, *[start + float(p) for p in sorted(recut_points)], end]

    for i, out_file in enumerate(new_files):
        s_start, s_end = cuts[i], cuts[i + 1]
        s_dur = s_end - s_start
        insert_segment(cur, old_data, out_file, s_start, s_end, s_dur)

    if old_data.get("output_path"):
        old_output = Path(str(old_data.get("output_path")))
        move_to_trash(file_path=old_output, trash_root=TRASH_DIR_SC)
    delete_segment(cur, seg_id)
    cleanup_file(Path(old_data.get("output_path") or ""))


def parse_recut_points(status: str) -> list[float]:
    """
    Extrait les points de découpe à partir du champ 'status'.
    Exemples :
        "recut:45,120" → [45.0, 120.0]
        "recut : 110"  → [110.0]
        "Recut: 85.5"  → [85.5]
        "85"            → [85.0]
    """
    if not status:
        return []

    # Normalisation
    s = re.sub(r"\s+", "", status.strip().lower())  # retire tous les espaces, ex: "recut : 110" → "recut:110"

    # recut:xx,yy,zz
    if s.startswith("recut:"):
        try:
            return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", s)]
        except ValueError:
            return []

    # Si c’est juste un nombre
    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        return [float(s)]

    return []
