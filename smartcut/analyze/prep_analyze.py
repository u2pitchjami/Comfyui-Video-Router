from __future__ import annotations

import os
from pathlib import Path

import cv2

from shared.utils.config import BATCH_FRAMES_DIR_SC, MULTIPLE_FRAMES_DIR_SC, TMP_FRAMES_DIR_SC
from shared.utils.logger import get_logger
from smartcut.analyze.analyze_utils import (
    delete_frames,
)
from smartcut.models_sc.ai_result import AIResult

logger = get_logger("SmartCut")


KeywordsBatches = list[AIResult]


def cleanup_temp() -> None:
    """
    Nettoyage répertoires temporaires
    """
    for path in [TMP_FRAMES_DIR_SC, MULTIPLE_FRAMES_DIR_SC, BATCH_FRAMES_DIR_SC]:
        delete_frames(Path(path))
    os.makedirs(TMP_FRAMES_DIR_SC, exist_ok=True)


def open_vid(video_path: str) -> tuple[cv2.VideoCapture, str]:
    # --- Ouverture vidéo
    video_name = Path(video_path).stem
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error(f"Impossible d'ouvrir la vidéo {video_path}")
        raise
    return cap, video_name


def release_cap(cap: cv2.VideoCapture) -> None:
    cap.release()
