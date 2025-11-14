""" """

from __future__ import annotations

from pathlib import Path
from typing import Any

from cutmind.db.db_utils import safe_execute_dict
from cutmind.manual.manual_utils import compare_segment, keywords_to_list_from_str
from cutmind.models_cm.cursor_protocol import DictCursorProtocol
from shared.utils.logger import get_logger

logger = get_logger(__name__)


def get_current_segment_data(cur: DictCursorProtocol, seg_id: int) -> dict[str, Any]:
    safe_execute_dict(
        cur,
        """
        SELECT s.id,
               s.video_id,
               s.start,
               s.end,
               s.duration,
               s.filename_predicted,
               s.output_path,
               s.resolution,
               s.fps,
               s.codec,
               s.bitrate,
               s.description,
               s.confidence,
               s.status,
               GROUP_CONCAT(k.keyword ORDER BY k.keyword SEPARATOR ', ') AS keywords
        FROM segments s
        LEFT JOIN segment_keywords sk ON sk.segment_id = s.id
        LEFT JOIN keywords k ON k.id = sk.keyword_id
        WHERE s.id=%s
        GROUP BY s.id
        """,
        (seg_id,),
    )
    row = cur.fetchone()
    return row or {}


def delete_segment(cur: DictCursorProtocol, seg_id: int) -> None:
    """Supprime un segment et ses mots-clés."""
    safe_execute_dict(cur, "DELETE FROM segments WHERE id=%s", (seg_id,))
    safe_execute_dict(cur, "DELETE FROM segment_keywords WHERE segment_id=%s", (seg_id,))
    logger.info("🗑️ Segment supprimé : %s", seg_id)


def insert_segment(
    cur: DictCursorProtocol, old_data: dict[str, Any], out_file: Path, s_start: float, s_end: float, s_dur: float
) -> None:
    """Insère un nouveau segment recuté en base."""
    safe_execute_dict(
        cur,
        """
        INSERT INTO segments (
            uid, video_id, start, end, duration, filename_predicted,
            output_path, status, resolution, fps, codec, bitrate,
            merged_from, source_flow
        )
        VALUES (
            UUID(), %s, %s, %s, %s, %s, %s, 'pending_check',
            %s, %s, %s, %s, JSON_ARRAY(%s), 'manual_csv'
        )
        """,
        (
            old_data["video_id"],
            s_start,
            s_end,
            s_dur,
            out_file.name,
            str(out_file),
            old_data.get("resolution"),
            old_data.get("fps"),
            old_data.get("codec"),
            old_data.get("bitrate"),
            old_data["id"],
        ),
    )

    logger.info("🟢 Nouveau segment (recut) → %s [%.2fs - %.2fs]", out_file.name, s_start, s_end)
    if not cur.lastrowid:
        raise Exception("🚨 Erreur lors de la création du nouveau segment")
    # copy_keywords(cur, cur.lastrowid, old_data.get("keywords"))


def copy_keywords(cur: DictCursorProtocol, new_seg_id: int, keywords_str: str | None) -> None:
    """Copie les mots-clés existants vers le nouveau segment."""
    old_keywords = keywords_to_list_from_str(keywords_str)
    for kw in old_keywords:
        safe_execute_dict(cur, "SELECT id FROM keywords WHERE keyword=%s", (kw,))
        row_kw = cur.fetchone()
        if not row_kw:
            safe_execute_dict(cur, "INSERT INTO keywords (keyword) VALUES (%s)", (kw,))
            kw_id = cur.lastrowid
        else:
            kw_id = row_kw["id"]
        safe_execute_dict(
            cur, "INSERT INTO segment_keywords (segment_id, keyword_id) VALUES (%s, %s)", (new_seg_id, kw_id)
        )
    logger.debug("🧩 %d mots-clés copiés vers le segment %s", len(old_keywords), new_seg_id)


def update_segment_from_csv(cur: DictCursorProtocol, seg_id: int, new_data: dict[str, Any]) -> None:
    """Compare et met à jour les champs d’un segment depuis CSV."""
    old_data = get_current_segment_data(cur, seg_id)
    if not old_data:
        logger.warning("⚠️ Segment %s non trouvé", seg_id)
        return

    diffs = compare_segment(old_data, new_data)
    if not diffs:
        logger.debug("Segment %s inchangé", seg_id)
        return

    safe_execute_dict(
        cur,
        """
        UPDATE segments
        SET description=%s, confidence=%s, status=%s,
            source_flow='manual_csv', last_updated=NOW()
        WHERE id=%s
        """,
        (
            new_data["description"],
            new_data["confidence"],
            new_data["status"],
            seg_id,
        ),
    )

    if "keywords" in diffs:
        safe_execute_dict(cur, "DELETE FROM segment_keywords WHERE segment_id=%s", (seg_id,))
        for kw in new_data["keywords"]:
            safe_execute_dict(cur, "SELECT id FROM keywords WHERE keyword=%s", (kw,))
            row_kw = cur.fetchone()
            if not row_kw:
                safe_execute_dict(cur, "INSERT INTO keywords (keyword) VALUES (%s)", (kw,))
                kw_id = cur.lastrowid
            else:
                kw_id = row_kw["id"]
            safe_execute_dict(
                cur, "INSERT INTO segment_keywords (segment_id, keyword_id) VALUES (%s, %s)", (seg_id, kw_id)
            )

    logger.info("🟦 Segment %s mis à jour (%s)", seg_id, ", ".join(diffs))
