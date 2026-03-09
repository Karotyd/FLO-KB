"""
Test de l'export Obsidian.
Usage : python -m tests.test_export

Prérequis : avoir lancé test_import.py puis test_processing.py avant.
La base doit contenir des items de connaissance (status='processed').
"""

import sys
import os
import asyncio
import logging

# Forcer UTF-8 pour la console Windows (emojis dans les fichiers Markdown)
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.knowledge.db import KnowledgeDB
from server.knowledge.services.export_service import ExportService

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

VAULT_PATH = "data/obsidian_vault"
DB_PATH = "data/knowledge/kb.sqlite"


async def main():
    db = KnowledgeDB(DB_PATH)
    await db.initialize()

    stats = await db.get_stats()
    print("Stats base :")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    if stats.get("knowledge_items", 0) == 0:
        print("\nAucun item en base.")
        print("Lance d'abord : python -m tests.test_processing")
        return

    # --- Export 1 ---
    print(f"\n{'=' * 60}")
    print("EXPORT 1 : Generation du vault")
    print("=" * 60)
    service = ExportService(db, VAULT_PATH)
    result = await service.export_to_obsidian()

    for key, value in result.items():
        print(f"  {key}: {value}")

    # Compter les fichiers
    file_count_1 = sum(len(files) for _, _, files in os.walk(VAULT_PATH))
    print(f"\nFichiers dans le vault : {file_count_1}")

    # Structure du vault
    print(f"\nStructure du vault :")
    for root, dirs, files in os.walk(VAULT_PATH):
        dirs.sort()
        level = root.replace(VAULT_PATH, '').count(os.sep)
        indent = '  ' * level
        folder = os.path.basename(root)
        if level <= 2:
            print(f"  {indent}{folder}/")
        sub_indent = '  ' * (level + 1)
        for f in sorted(files):
            if level <= 2:
                print(f"  {sub_indent}{f}")

    # Apercu du MOC
    moc_path = os.path.join(VAULT_PATH, "_Index", "MOC - Base de connaissances.md")
    if os.path.exists(moc_path):
        print(f"\n{'=' * 60}")
        print("APERCU MOC")
        print("=" * 60)
        with open(moc_path, 'r', encoding='utf-8') as f:
            print(f.read()[:1500])

    # Verifier un item (premier fichier dans un dossier theme)
    for entry in os.scandir(VAULT_PATH):
        if entry.is_dir() and not entry.name.startswith('_'):
            for f in os.scandir(entry.path):
                if f.name.endswith('.md'):
                    print(f"\n{'=' * 60}")
                    print(f"APERCU ITEM : {entry.name}/{f.name}")
                    print("=" * 60)
                    with open(f.path, 'r', encoding='utf-8') as fh:
                        print(fh.read()[:800])
                    break
            break

    # --- Export 2 : Test idempotence ---
    print(f"\n{'=' * 60}")
    print("EXPORT 2 : Test idempotence")
    print("=" * 60)
    result2 = await service.export_to_obsidian()

    file_count_2 = sum(len(files) for _, _, files in os.walk(VAULT_PATH))
    print(f"  Fichiers export 1 : {file_count_1}")
    print(f"  Fichiers export 2 : {file_count_2}")

    if file_count_1 == file_count_2:
        print("  -> OK : meme nombre de fichiers (idempotent)")
    else:
        print(f"  -> ATTENTION : {file_count_2 - file_count_1} fichier(s) de difference")

    assert result["items_exported"] == result2["items_exported"], "Nombre d'items different !"
    print("  -> OK : stats identiques")

    print(f"\n{'=' * 60}")
    print("Export Obsidian termine")
    print(f"Ouvre dans Obsidian : {os.path.abspath(VAULT_PATH)}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
