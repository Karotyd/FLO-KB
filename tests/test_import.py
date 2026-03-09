"""
Test de l'import complet avec déduplication.
Usage : python -m tests.test_import

Test en 3 étapes :
1. Import du ZIP ChatGPT → doit insérer toutes les conversations
2. Réimport du même ZIP → doit détecter 100% de doublons
3. Afficher les stats de la base
"""

import sys
import os
import asyncio
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.knowledge.db import KnowledgeDB
from server.knowledge.services.import_service import ImportService

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

ZIP_PATH = r"C:\Users\jouin\Downloads\Export chat GPT\93da9c3805145d86452c9d08988d77946fa5b0ce9973cf8c99843ce2fa6ef7f0-2026-03-08-10-15-24-592450e9078b45119650c674bb77078b.zip"

# Base de test isolée pour ne pas polluer la base principale
TEST_DB_PATH = "data/knowledge/kb_test.sqlite"


async def main():
    # Supprimer la base de test si elle existe (repartir de zéro)
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
        print(f"Base de test précédente supprimée : {TEST_DB_PATH}")

    db = KnowledgeDB(db_path=TEST_DB_PATH)
    await db.initialize()

    service = ImportService(db)

    # --- Test 1 : Premier import ---
    print("=" * 60)
    print("TEST 1 : Premier import")
    print("=" * 60)
    result = await service.import_file(ZIP_PATH)
    print(f"  Fichiers source traites  : {result['source_files']}")
    print(f"  Conversations trouvees   : {result['total_conversations']}")
    print(f"  Nouvelles                : {result['new']}")
    print(f"  Mises a jour             : {result['updated']}")
    print(f"  Doublons                 : {result['duplicates']}")
    print(f"  Erreurs                  : {result['errors']}")

    assert result['new'] > 0, "ECHEC : Aucune conversation importee !"
    assert result['duplicates'] == 0, "ECHEC : Doublons au premier import !"
    print("  -> OK")

    first_import_new = result['new']

    # --- Test 2 : Réimport (tout doit être doublon) ---
    print(f"\n{'=' * 60}")
    print("TEST 2 : Reimport (detection doublons)")
    print("=" * 60)
    result2 = await service.import_file(ZIP_PATH)
    print(f"  Conversations trouvees   : {result2['total_conversations']}")
    print(f"  Nouvelles                : {result2['new']}")
    print(f"  Doublons                 : {result2['duplicates']}")

    assert result2['new'] == 0, f"ECHEC : {result2['new']} conversation(s) reimportee(s) !"
    assert result2['duplicates'] == first_import_new, (
        f"ECHEC : {result2['duplicates']} doublons detectes, attendu {first_import_new}"
    )
    print("  -> OK")

    # --- Test 3 : Stats ---
    print(f"\n{'=' * 60}")
    print("TEST 3 : Stats de la base")
    print("=" * 60)
    stats = await db.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    assert stats['conversations_total'] == first_import_new, (
        f"ECHEC : {stats['conversations_total']} conversations en base, attendu {first_import_new}"
    )
    print("  -> OK")

    print(f"\n{'=' * 60}")
    print("TOUS LES TESTS PASSENT")
    print(f"{'=' * 60}")

    # Nettoyage
    os.remove(TEST_DB_PATH)
    print(f"Base de test supprimee : {TEST_DB_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
