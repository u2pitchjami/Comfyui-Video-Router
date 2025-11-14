"""
Import réel des modifications manuelles de segments depuis CSV (v1.2)
====================================================================

Lit un CSV d'édition manuelle et met à jour la base CutMind :
 - description, confidence, status, keywords
 - gère les suppressions (status = delete / to_delete)
 - nettoie les 'None', 'NULL', etc.
"""

from __future__ import annotations

import csv
from pathlib import Path

from cutmind.db.db_connection import db_conn, get_dict_cursor
from cutmind.db.manual_db import (
    delete_segment,
    get_current_segment_data,
    update_segment_from_csv,
)
from cutmind.manual.manual_utils import (
    build_new_data_from_csv_row,
    compare_segment,
    summarize_import,
    write_csv_log,
)
from cutmind.recut.recut_segment import parse_recut_points, perform_recut
from cutmind.validation.revalidate_manual import revalidate_manual_videos
from shared.utils.config import CSV_LOG_PATH, MANUAL_CSV_PATH, TRASH_DIR_SC
from shared.utils.logger import get_logger
from shared.utils.trash import move_to_trash

logger = get_logger(__name__)


def update_segments_csv(manual_csv: Path = Path(MANUAL_CSV_PATH), csv_log: Path = Path(CSV_LOG_PATH)) -> None:
    """Import principal des segments CSV vers la base."""
    stats = {"checked": 0, "updated": 0, "deleted": 0, "unchanged": 0, "errors": 0}
    log_rows: list[dict[str, str]] = []

    with db_conn() as conn:
        with get_dict_cursor(conn) as cur, open(manual_csv, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                seg_id = row.get("segment_id")
                if not seg_id:
                    continue
                stats["checked"] += 1

                try:
                    old_data = get_current_segment_data(cur, int(seg_id))
                    new_data = build_new_data_from_csv_row(row)
                    status = new_data["status"]

                    if status in ("delete", "to_delete"):
                        if old_data.get("output_path"):
                            old_output = Path(str(old_data.get("output_path")))
                            move_to_trash(file_path=old_output, trash_root=TRASH_DIR_SC)
                        delete_segment(cur, int(seg_id))
                        stats["deleted"] += 1
                        log_rows.append({"segment_id": seg_id, "action": "deleted", "differences": "ALL"})
                        continue

                    recut_points = parse_recut_points(status)
                    if recut_points:
                        perform_recut(cur, int(seg_id), recut_points)
                        stats["updated"] += 1
                        log_rows.append(
                            {"segment_id": seg_id, "action": f"recut @{recut_points}", "differences": "recut"}
                        )
                        continue

                    if not old_data:
                        logger.warning("⚠️ Segment %s non trouvé", seg_id)
                        continue

                    diffs = compare_segment(old_data, new_data)
                    if not diffs:
                        stats["unchanged"] += 1
                        log_rows.append({"segment_id": seg_id, "action": "unchanged", "differences": ""})
                        continue

                    update_segment_from_csv(cur, int(seg_id), new_data)
                    stats["updated"] += 1
                    log_rows.append({"segment_id": seg_id, "action": "updated", "differences": ", ".join(diffs)})

                except Exception as exc:  # pylint: disable=broad-except
                    stats["errors"] += 1
                    logger.exception("❌ Erreur segment %s : %s", seg_id, exc)
                    log_rows.append({"segment_id": seg_id or "", "action": "error", "differences": str(exc)})

            conn.commit()

    write_csv_log(csv_log, log_rows)
    summarize_import(stats, csv_log)
    revalidate_manual_videos()
