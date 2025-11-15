from __future__ import annotations

from pathlib import Path
import subprocess

from shared.ffmpeg.ffmpeg_utils import get_duration


def ffmpeg_recut_video(input_path: Path, recut_points: list[float], output_dir: Path) -> list[Path]:
    """
    Découpe physiquement une vidéo à plusieurs points avec ffmpeg.

    Args:
        input_path (Path): fichier vidéo d'entrée
        recut_points (List[float]): secondes de coupure
        output_dir (Path): dossier de sortie

    Returns:
        List[Path]: liste des fichiers vidéo créés
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {input_path}") from None

    output_dir.mkdir(parents=True, exist_ok=True)

    # On récupère la durée totale
    try:
        duration = get_duration(video_path=(input_path))
    except Exception:
        raise RuntimeError("Impossible de lire la durée de la vidéo") from None

    recut_points = sorted([p for p in recut_points if 0 < p < duration])
    cuts = [0.0, *recut_points, duration]

    output_files = []

    for i in range(len(cuts) - 1):
        start = cuts[i]
        end = cuts[i + 1]
        out_path = output_dir / f"{input_path.stem}_part{i + 1}.mp4"

        cmd = ["ffmpeg", "-y", "-ss", str(start), "-to", str(end), "-i", str(input_path), "-c", "copy", str(out_path)]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        output_files.append(out_path)

    return output_files
