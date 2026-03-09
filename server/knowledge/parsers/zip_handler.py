"""
Extraction des archives ZIP d'export (ChatGPT, etc.) — FLO-KB.
Filtre les fichiers utiles (JSON, MD, TXT) et les extrait dans le dossier d'imports.
"""

import zipfile
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Extensions de fichiers utiles à extraire
_USEFUL_EXTENSIONS = {'.json', '.md', '.txt'}


def extract_zip(zip_path: str, dest_dir: str = None) -> list[str]:
    """
    Extrait un fichier ZIP et retourne la liste des fichiers extraits.

    Filtre automatiquement les fichiers non utiles (images, binaires, dossiers macOS).
    En cas de collision de noms, ajoute un suffixe numérique.

    Args:
        zip_path: Chemin vers le fichier ZIP à extraire.
        dest_dir: Dossier de destination (défaut: data/knowledge/imports/).

    Returns:
        Liste des chemins absolus des fichiers extraits.
    """
    if dest_dir is None:
        dest_dir = os.path.join("data", "knowledge", "imports")

    os.makedirs(dest_dir, exist_ok=True)

    extracted_files = []

    with zipfile.ZipFile(zip_path, 'r') as zf:
        for member in zf.namelist():
            # Ignorer les dossiers
            if member.endswith('/'):
                continue

            # Ignorer les fichiers macOS cachés
            if member.startswith('__MACOSX') or Path(member).name.startswith('._'):
                continue

            ext = Path(member).suffix.lower()
            if ext not in _USEFUL_EXTENSIONS:
                continue  # Ignorer les fichiers non utiles (images, etc.)

            # Extraire avec un nom plat (éviter les sous-dossiers)
            filename = Path(member).name
            target_path = os.path.join(dest_dir, filename)

            # Éviter les collisions de noms
            if os.path.exists(target_path):
                base, extension = os.path.splitext(filename)
                counter = 1
                while os.path.exists(target_path):
                    target_path = os.path.join(dest_dir, f"{base}_{counter}{extension}")
                    counter += 1

            with zf.open(member) as source, open(target_path, 'wb') as target:
                target.write(source.read())

            extracted_files.append(os.path.abspath(target_path))
            logger.info(f"Extrait : {member} → {target_path}")

    logger.info(f"{len(extracted_files)} fichier(s) extrait(s) depuis {zip_path}")
    return extracted_files
