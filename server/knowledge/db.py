"""
Gestionnaire de la base SQLite des connaissances — FLO-KB.
Toutes les opérations sont async (aiosqlite).
Le fichier de base est créé automatiquement si absent.
"""

import aiosqlite
import json
import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Schéma SQL complet
_SCHEMA = """
CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    source_type TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    conversation_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    metadata TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id INTEGER REFERENCES imports(id),
    external_id TEXT,
    title TEXT,
    source_type TEXT NOT NULL,
    created_at TIMESTAMP,
    content_hash TEXT NOT NULL,
    status TEXT DEFAULT 'new',
    value_score REAL DEFAULT 0,
    full_text TEXT
);

CREATE TABLE IF NOT EXISTS knowledge_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER REFERENCES conversations(id),
    item_type TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    summary TEXT,
    source_quote TEXT,
    confidence REAL DEFAULT 0.8,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS themes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    parent_id INTEGER REFERENCES themes(id),
    description TEXT,
    color TEXT,
    item_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS item_themes (
    item_id INTEGER REFERENCES knowledge_items(id),
    theme_id INTEGER REFERENCES themes(id),
    PRIMARY KEY (item_id, theme_id)
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS item_tags (
    item_id INTEGER REFERENCES knowledge_items(id),
    tag_id INTEGER REFERENCES tags(id),
    PRIMARY KEY (item_id, tag_id)
);

-- Index pour les recherches fréquentes
CREATE INDEX IF NOT EXISTS idx_conversations_content_hash ON conversations(content_hash);
CREATE INDEX IF NOT EXISTS idx_conversations_external_id ON conversations(external_id);
CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations(status);
CREATE INDEX IF NOT EXISTS idx_imports_file_hash ON imports(file_hash);
"""


class KnowledgeDB:
    """Gestionnaire de la base SQLite des connaissances."""

    def __init__(self, db_path: str = "data/knowledge/kb.sqlite"):
        self.db_path = db_path

    async def initialize(self):
        """Crée le dossier, la base et les tables si nécessaire."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(_SCHEMA)
            await db.commit()
        logger.info(f"Base de données initialisée : {self.db_path}")

    # -------------------------------------------------------------------------
    # Imports
    # -------------------------------------------------------------------------

    async def create_import(
        self,
        filename: str,
        source_type: str,
        file_hash: str,
        metadata: Optional[dict] = None
    ) -> int:
        """
        Enregistre un nouvel import en base.

        Returns:
            L'ID de l'import créé.
        """
        metadata_json = json.dumps(metadata) if metadata else None
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO imports (filename, source_type, file_hash, metadata) VALUES (?, ?, ?, ?)",
                (filename, source_type, file_hash, metadata_json)
            )
            await db.commit()
            import_id = cursor.lastrowid
        logger.info(f"Import créé (id={import_id}) : {filename}")
        return import_id

    async def update_import_status(
        self,
        import_id: int,
        status: str,
        conversation_count: Optional[int] = None
    ):
        """Met à jour le statut d'un import (et optionnellement le nombre de conversations)."""
        async with aiosqlite.connect(self.db_path) as db:
            if conversation_count is not None:
                await db.execute(
                    "UPDATE imports SET status = ?, conversation_count = ? WHERE id = ?",
                    (status, conversation_count, import_id)
                )
            else:
                await db.execute(
                    "UPDATE imports SET status = ? WHERE id = ?",
                    (status, import_id)
                )
            await db.commit()
        logger.debug(f"Import {import_id} → statut '{status}'")

    async def file_already_imported(self, file_hash: str) -> bool:
        """Vérifie si un fichier a déjà été importé avec succès (par hash SHA-256)."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id FROM imports WHERE file_hash = ? AND status = 'done' LIMIT 1",
                (file_hash,)
            )
            row = await cursor.fetchone()
        return row is not None

    # -------------------------------------------------------------------------
    # Conversations
    # -------------------------------------------------------------------------

    async def find_conversation_by_hash(self, content_hash: str) -> Optional[dict]:
        """
        Cherche une conversation par son hash de contenu.

        Returns:
            dict avec les colonnes de la conversation, ou None si absente.
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM conversations WHERE content_hash = ? LIMIT 1",
                (content_hash,)
            )
            row = await cursor.fetchone()
        return dict(row) if row else None

    async def find_conversation_by_external_id(self, external_id: str) -> Optional[dict]:
        """Cherche une conversation par son ID externe (ex: ID ChatGPT)."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM conversations WHERE external_id = ? LIMIT 1",
                (external_id,)
            )
            row = await cursor.fetchone()
        return dict(row) if row else None

    async def insert_conversation(
        self,
        import_id: int,
        external_id: str,
        title: str,
        source_type: str,
        created_at: Optional[datetime],
        content_hash: str,
        full_text: str,
        status: str = 'new'
    ) -> int:
        """
        Insère une nouvelle conversation en base.

        Returns:
            L'ID de la conversation créée.
        """
        created_at_str = created_at.isoformat() if created_at else None
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """INSERT INTO conversations
                   (import_id, external_id, title, source_type, created_at, content_hash, full_text, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (import_id, external_id, title, source_type, created_at_str, content_hash, full_text, status)
            )
            await db.commit()
            conv_id = cursor.lastrowid
        logger.debug(f"Conversation insérée (id={conv_id}) : '{title}' [{status}]")
        return conv_id

    async def update_conversation_status(self, conv_id: int, status: str):
        """Met à jour le statut d'une conversation."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE conversations SET status = ? WHERE id = ?",
                (status, conv_id)
            )
            await db.commit()
        logger.debug(f"Conversation {conv_id} → statut '{status}'")

    async def get_conversations_by_status(self, status: str) -> list[dict]:
        """Retourne toutes les conversations avec un statut donné."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM conversations WHERE status = ?",
                (status,)
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # -------------------------------------------------------------------------
    # Statistiques
    # -------------------------------------------------------------------------

    async def get_stats(self) -> dict:
        """Retourne les stats globales de la base."""
        async with aiosqlite.connect(self.db_path) as db:
            async def count(query: str, params=()) -> int:
                cursor = await db.execute(query, params)
                row = await cursor.fetchone()
                return row[0] if row else 0

            imports_total = await count("SELECT COUNT(*) FROM imports")
            imports_done = await count("SELECT COUNT(*) FROM imports WHERE status = 'done'")
            conv_total = await count("SELECT COUNT(*) FROM conversations")
            conv_new = await count("SELECT COUNT(*) FROM conversations WHERE status = 'new'")
            conv_updated = await count("SELECT COUNT(*) FROM conversations WHERE status = 'updated'")
            conv_duplicate = await count("SELECT COUNT(*) FROM conversations WHERE status = 'duplicate'")
            conv_processed = await count("SELECT COUNT(*) FROM conversations WHERE status = 'processed'")
            items_total = await count("SELECT COUNT(*) FROM knowledge_items")
            themes_total = await count("SELECT COUNT(*) FROM themes")
            tags_total = await count("SELECT COUNT(*) FROM tags")

        return {
            "imports_total": imports_total,
            "imports_done": imports_done,
            "conversations_total": conv_total,
            "conversations_new": conv_new,
            "conversations_updated": conv_updated,
            "conversations_duplicate": conv_duplicate,
            "conversations_processed": conv_processed,
            "knowledge_items": items_total,
            "themes": themes_total,
            "tags": tags_total,
        }
