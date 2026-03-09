"""
Test du pipeline de traitement IA sur un petit échantillon.
Usage : python -m tests.test_processing

ATTENTION : ce test charge le modèle GGUF et fait tourner le LLM local.
Il nécessite ~5 Go de VRAM et prend 2-10 minutes pour 5 conversations.
Lance d'abord test_import.py pour peupler la base.
"""

import sys
import os
import asyncio
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.knowledge.db import KnowledgeDB
from server.knowledge.processing.extractor import KnowledgeExtractor
from server.engine.model_manager import ModelManager
import aiosqlite

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = "data/knowledge/kb.sqlite"
NB_CONVERSATIONS = 5  # Nombre de conversations à traiter pour le test


async def main():
    print("=" * 60)
    print("TEST PIPELINE TRAITEMENT IA — FLO-KB")
    print("=" * 60)

    # Vérifier que la base existe et contient des conversations
    db = KnowledgeDB(DB_PATH)
    await db.initialize()

    conversations = await db.get_conversations_by_status("new")
    if not conversations:
        print("\nAucune conversation en statut 'new'.")
        print("Lance d'abord : python -m tests.test_import")
        return

    print(f"\n{len(conversations)} conversations en attente de traitement")
    print(f"Test sur les {NB_CONVERSATIONS} premières uniquement\n")

    # Instancier le ModelManager (lit models.json)
    model_manager = ModelManager()

    # Créer l'extracteur
    extractor = KnowledgeExtractor(db, model_manager)

    # Traiter les N premières conversations
    print("Chargement du modèle LLM...")
    stats = await extractor.process_all_new(limit=NB_CONVERSATIONS)

    print(f"\n{'=' * 60}")
    print("RESULTATS DU TRAITEMENT")
    print("=" * 60)
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Afficher les items extraits
    print(f"\n{'=' * 60}")
    print("ITEMS DE CONNAISSANCE EXTRAITS")
    print("=" * 60)

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            """SELECT ki.*, c.title as conv_title
               FROM knowledge_items ki
               JOIN conversations c ON ki.conversation_id = c.id
               ORDER BY ki.id DESC LIMIT 20"""
        ) as cursor:
            items = await cursor.fetchall()

    if items:
        for item in items:
            print(f"\n  [{item['item_type']}] {item['title']}")
            print(f"     {item['content'][:120]}...")
            print(f"     Source: {item['conv_title'][:50]} | Confiance: {item['confidence']:.2f}")
    else:
        print("  Aucun item extrait (toutes les conversations filtrées ?)")

    # Afficher les thèmes utilisés
    themes = await db.get_all_themes()
    print(f"\nThemes en base : {', '.join(themes[:15])}")

    # Stats finales
    final_stats = await db.get_stats()
    print(f"\n{'=' * 60}")
    print("STATS BASE APRES TRAITEMENT")
    print("=" * 60)
    for key, value in final_stats.items():
        print(f"  {key}: {value}")

    print(f"\n{'=' * 60}")
    print("Test Phase 3 termine")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
