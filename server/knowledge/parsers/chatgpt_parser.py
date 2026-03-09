"""
Parseur pour les exports JSON de ChatGPT — FLO-KB.
Format : fichier conversations.json (exporté via Settings → Data Controls → Export Data).
Structure : liste de conversations avec un 'mapping' (arbre de messages non ordonné).
"""

import json
import logging
from datetime import datetime
from .base_parser import BaseParser, ParsedConversation, ParsedMessage

logger = logging.getLogger(__name__)


class ChatGPTParser(BaseParser):
    """Parse les exports JSON de ChatGPT."""

    def can_parse(self, filepath: str) -> bool:
        """
        Vérifie que le fichier est un JSON avec la structure ChatGPT.
        Critère : liste avec 'mapping' dans le premier élément.
        """
        if not filepath.endswith('.json'):
            return False
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # ChatGPT : liste de conversations avec 'mapping'
            if isinstance(data, list) and len(data) > 0:
                return 'mapping' in data[0]
            return False
        except Exception:
            return False

    def parse(self, filepath: str) -> list[ParsedConversation]:
        """
        Parse le fichier conversations.json de ChatGPT.
        Le mapping est un arbre non ordonné — les messages sont triés par timestamp.
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        conversations = []

        for conv in data:
            messages = self._extract_messages(conv)

            if messages:
                # Trier par timestamp (le mapping n'est pas ordonné)
                messages.sort(key=lambda m: m.timestamp or datetime.min)

                created_at = None
                if conv.get('create_time'):
                    try:
                        created_at = datetime.fromtimestamp(conv['create_time'])
                    except (ValueError, OSError) as e:
                        logger.warning(f"Timestamp invalide pour la conversation {conv.get('id', '?')} : {e}")

                conversations.append(ParsedConversation(
                    external_id=conv.get('id', ''),
                    title=conv.get('title', 'Sans titre'),
                    source_type='chatgpt',
                    messages=messages,
                    created_at=created_at
                ))

        logger.info(f"{len(conversations)} conversation(s) parsée(s) depuis {filepath}")
        return conversations

    def _extract_messages(self, conv: dict) -> list[ParsedMessage]:
        """Extrait et normalise les messages depuis le mapping ChatGPT."""
        messages = []

        for node_id, node in conv.get('mapping', {}).items():
            msg = node.get('message')
            if msg is None:
                continue  # Nœuds sans message (racine de l'arbre, etc.)

            role = msg.get('author', {}).get('role', '')
            if role not in ('user', 'assistant'):
                continue  # Ignorer les messages système, tool, etc.

            # Le contenu peut être dans différents formats (texte, images, fichiers)
            content_parts = msg.get('content', {}).get('parts', [])
            content = ' '.join(
                str(p) for p in content_parts if isinstance(p, str)
            )

            if not content.strip():
                continue  # Ignorer les messages vides (ex: messages d'images)

            timestamp = None
            if msg.get('create_time'):
                try:
                    timestamp = datetime.fromtimestamp(msg['create_time'])
                except (ValueError, OSError) as e:
                    logger.debug(f"Timestamp de message invalide : {e}")

            messages.append(ParsedMessage(
                role=role,
                content=content.strip(),
                timestamp=timestamp
            ))

        return messages
