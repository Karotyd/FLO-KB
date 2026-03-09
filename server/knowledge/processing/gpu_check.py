"""
Détection VRAM et sélection du modèle KB — FLO-KB.
Pour l'instant, on utilise toujours kb-light (Mistral 7B).
Prêt pour ajouter un modèle plus lourd si nécessaire.
"""

import subprocess
import logging

logger = logging.getLogger(__name__)


def get_available_vram_gb() -> float:
    """Détecte la VRAM disponible via nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10
        )
        free_mb = float(result.stdout.strip().split('\n')[0])
        free_gb = free_mb / 1024
        logger.info(f"VRAM disponible : {free_gb:.1f} Go")
        return free_gb
    except Exception as e:
        logger.warning(f"Impossible de détecter la VRAM : {e}")
        return 0.0


def select_best_model(task: str = "all") -> dict:
    """
    Sélectionne le meilleur modèle KB selon la VRAM disponible.
    Pour l'instant, toujours kb-light (Mistral 7B, ~5 Go VRAM).

    Returns:
        dict avec 'model_id' et optionnellement 'warning'.
    """
    vram = get_available_vram_gb()

    if vram < 6:
        return {
            "model_id": "kb-light",
            "warning": (
                f"VRAM limitée ({vram:.1f} Go). "
                "Le traitement pourrait être lent ou partiellement sur CPU."
            )
        }

    return {"model_id": "kb-light"}
