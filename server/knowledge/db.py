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

# Thèmes initiaux insérés au premier démarrage
_DEFAULT_THEMES = [
    "Psychologie",
    "Tech & IA",
    "Cinéma",
    "Jeux Vidéo",
    "Musique",
    "Développement Personnel",
    "Sciences",
    "Programmation",
]

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
        """Crée le dossier, la base, les tables et les thèmes initiaux si nécessaire."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(_SCHEMA)
            # Thèmes initiaux (INSERT OR IGNORE = idempotent)
            for theme in _DEFAULT_THEMES:
                await db.execute(
                    "INSERT OR IGNORE INTO themes (name) VALUES (?)", (theme,)
                )
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

    async def update_conversation_score(self, conv_id: int, score: float):
        """Met à jour le score de valeur d'une conversation."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE conversations SET value_score = ? WHERE id = ?",
                (score, conv_id)
            )
            await db.commit()
        logger.debug(f"Conversation {conv_id} → score={score}")

    # -------------------------------------------------------------------------
    # Knowledge Items
    # -------------------------------------------------------------------------

    async def insert_knowledge_item(
        self,
        conversation_id: int,
        item_type: str,
        title: str,
        content: str,
        summary: Optional[str],
        source_quote: Optional[str],
        confidence: float,
    ) -> int:
        """
        Insère un item de connaissance extrait par le LLM.

        Returns:
            L'ID de l'item créé.
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """INSERT INTO knowledge_items
                   (conversation_id, item_type, title, content, summary, source_quote, confidence)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (conversation_id, item_type, title, content, summary, source_quote, confidence)
            )
            await db.commit()
            item_id = cursor.lastrowid
        logger.debug(f"Item inséré (id={item_id}) : [{item_type}] {title[:50]}")
        return item_id

    # -------------------------------------------------------------------------
    # Thèmes et Tags
    # -------------------------------------------------------------------------

    async def get_all_themes(self) -> list[str]:
        """Retourne la liste des noms de tous les thèmes."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT name FROM themes ORDER BY name")
            rows = await cursor.fetchall()
        return [r[0] for r in rows]

    async def get_or_create_theme(self, name: str) -> int:
        """
        Retourne l'ID du thème. Le crée s'il n'existe pas.

        Returns:
            L'ID du thème (existant ou créé).
        """
        name = name.strip()
        async with aiosqlite.connect(self.db_path) as db:
            # Chercher d'abord
            cursor = await db.execute(
                "SELECT id FROM themes WHERE name = ?", (name,)
            )
            row = await cursor.fetchone()
            if row:
                return row[0]
            # Créer
            cursor = await db.execute(
                "INSERT INTO themes (name) VALUES (?)", (name,)
            )
            await db.commit()
            theme_id = cursor.lastrowid
        logger.info(f"Nouveau thème créé : '{name}' (id={theme_id})")
        return theme_id

    async def get_or_create_tag(self, name: str) -> int:
        """
        Retourne l'ID du tag. Le crée s'il n'existe pas.

        Returns:
            L'ID du tag (existant ou créé).
        """
        name = name.strip().lower()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id FROM tags WHERE name = ?", (name,)
            )
            row = await cursor.fetchone()
            if row:
                return row[0]
            cursor = await db.execute(
                "INSERT INTO tags (name) VALUES (?)", (name,)
            )
            await db.commit()
            tag_id = cursor.lastrowid
        logger.debug(f"Nouveau tag créé : '{name}' (id={tag_id})")
        return tag_id

    async def link_item_theme(self, item_id: int, theme_id: int):
        """Lie un item à un thème. Ignore si la liaison existe déjà."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO item_themes (item_id, theme_id) VALUES (?, ?)",
                (item_id, theme_id)
            )
            await db.commit()

    async def link_item_tag(self, item_id: int, tag_id: int):
        """Lie un item à un tag. Ignore si la liaison existe déjà."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO item_tags (item_id, tag_id) VALUES (?, ?)",
                (item_id, tag_id)
            )
            await db.commit()

    async def update_theme_counts(self):
        """Met à jour les compteurs item_count de tous les thèmes."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE themes SET item_count = (
                    SELECT COUNT(*) FROM item_themes WHERE theme_id = themes.id
                )
            """)
            await db.commit()
        logger.debug("Compteurs de thèmes mis à jour")

    # -------------------------------------------------------------------------
    # Requêtes enrichies pour l'export
    # -------------------------------------------------------------------------

    async def get_all_items_with_details(self) -> list[dict]:
        """
        Retourne tous les items avec leurs thèmes, tags et infos de conversation.

        Chaque dict contient :
        id, item_type, title, content, summary, source_quote, confidence, created_at,
        conv_title, conv_source_type, conv_created_at, themes (list), tags (list).
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # Items + infos conversation
            cursor = await db.execute("""
                SELECT ki.id, ki.item_type, ki.title, ki.content, ki.summary,
                       ki.source_quote, ki.confidence, ki.created_at,
                       c.title as conv_title, c.source_type as conv_source_type,
                       c.created_at as conv_created_at, c.value_score
                FROM knowledge_items ki
                JOIN conversations c ON ki.conversation_id = c.id
                ORDER BY ki.id
            """)
            rows = await cursor.fetchall()
            items = [dict(r) for r in rows]

            # Thèmes par item
            theme_cursor = await db.execute("""
                SELECT it.item_id, t.name
                FROM item_themes it
                JOIN themes t ON it.theme_id = t.id
                ORDER BY it.item_id, t.name
            """)
            theme_rows = await theme_cursor.fetchall()

            # Tags par item
            tag_cursor = await db.execute("""
                SELECT it.item_id, tg.name
                FROM item_tags it
                JOIN tags tg ON it.tag_id = tg.id
                ORDER BY it.item_id, tg.name
            """)
            tag_rows = await tag_cursor.fetchall()

        # Indexer thèmes et tags par item_id
        themes_by_item: dict[int, list[str]] = {}
        for row in theme_rows:
            themes_by_item.setdefault(row[0], []).append(row[1])

        tags_by_item: dict[int, list[str]] = {}
        for row in tag_rows:
            tags_by_item.setdefault(row[0], []).append(row[1])

        for item in items:
            item["themes"] = themes_by_item.get(item["id"], [])
            item["tags"] = tags_by_item.get(item["id"], [])

        return items

    async def get_items_by_theme(self, theme_name: str) -> list[dict]:
        """Retourne les items liés à un thème donné (avec id, title, item_type)."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT ki.id, ki.title, ki.item_type, ki.confidence
                FROM knowledge_items ki
                JOIN item_themes it ON ki.id = it.item_id
                JOIN themes t ON it.theme_id = t.id
                WHERE t.name = ?
                ORDER BY ki.title
            """, (theme_name,))
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_themes_with_counts(self) -> list[dict]:
        """Retourne les thèmes avec leur nombre réel d'items (count live)."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT t.id, t.name,
                       COUNT(it.item_id) as item_count
                FROM themes t
                LEFT JOIN item_themes it ON t.id = it.theme_id
                GROUP BY t.id, t.name
                ORDER BY item_count DESC, t.name
            """)
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_processed_conversations(self) -> list[dict]:
        """Retourne les conversations traitées (status='processed') avec résumé."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT c.id, c.title, c.source_type, c.created_at,
                       c.value_score,
                       ki.summary
                FROM conversations c
                LEFT JOIN (
                    SELECT conversation_id, summary
                    FROM knowledge_items
                    WHERE summary IS NOT NULL AND summary != ''
                    GROUP BY conversation_id
                ) ki ON c.id = ki.conversation_id
                WHERE c.status = 'processed'
                ORDER BY c.id
            """)
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_items_for_conversation(self, conv_id: int) -> list[dict]:
        """Retourne les items d'une conversation donnée."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, title, item_type FROM knowledge_items WHERE conversation_id = ? ORDER BY id",
                (conv_id,)
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_source_stats(self) -> dict:
        """Retourne le nombre de conversations par source_type."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT source_type, COUNT(*) as count
                FROM conversations
                WHERE status = 'processed'
                GROUP BY source_type
            """)
            rows = await cursor.fetchall()
        return {row[0]: row[1] for row in rows}

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
