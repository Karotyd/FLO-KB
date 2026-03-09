"""
Service d'export vers Obsidian — FLO-KB.
Orchestre la génération du vault depuis la base de connaissances.
"""

import logging

from server.knowledge.db import KnowledgeDB
from server.knowledge.exporters.obsidian_exporter import ObsidianExporter

logger = logging.getLogger(__name__)


class ExportService:
    """Orchestre l'export des connaissances vers un vault Obsidian."""

    def __init__(self, db: KnowledgeDB, vault_path: str = "data/obsidian_vault"):
        self.db = db
        self.vault_path = vault_path

    async def export_to_obsidian(self) -> dict:
        """
        Lance l'export complet vers le vault Obsidian.

        Returns:
            dict avec items_exported, themes_exported, sources_exported, vault_path.
        """
        logger.info(f"Démarrage export Obsidian → {self.vault_path}")
        exporter = ObsidianExporter(self.db, self.vault_path)
        result = await exporter.export()
        logger.info(f"Export Obsidian terminé : {result}")
        return result
