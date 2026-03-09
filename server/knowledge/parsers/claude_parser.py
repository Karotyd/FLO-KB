"""
Parseur pour les exports JSON de Claude (Anthropic) — FLO-KB.
Format : liste de conversations avec 'chat_messages' et 'uuid'.
Le contenu des messages peut être en 'text' (str) ou 'content' (list ou str).
"""

import json
import logging
from datetime import datetime
from .base_parser import BaseParser, ParsedConversation, ParsedMessage

logger = logging.getLogger(__name__)


class ClaudeParser(BaseParser):
    """Parse les exports JSON de Claude."""

    def can_parse(self, filepath: str) -> bool:
        """
        Vérifie que le fichier est un JSON avec la structure Claude.
        Critère : liste avec 'chat_messages' ou 'uuid' dans le premier élément.
        """
        if not filepath.endswith('.json'):
            return False
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Claude : liste avec 'chat_messages' ou 'uuid'
            if isinstance(data, list) and len(data) > 0:
                return 'chat_messages' in data[0] or 'uuid' in data[0]
            return False
        except Exception:
            return False

    def parse(self, filepath: str) -> list[ParsedConversation]:
        """Parse le fichier d'export JSON de Claude."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        conversations = []

        for conv in data:
            messages = []

            for msg in conv.get('chat_messages', []):
                role = msg.get('sender', '')
                if role == 'human':
                    role = 'user'
                elif role == 'assistant':
                    role = 'assistant'
                else:
                    continue  # Ignorer les rôles inconnus

                # Claude stocke le contenu dans 'text' ou 'content' (formats variables)
                content = ''
                if isinstance(msg.get('text'), str):
                    content = msg['text']
                elif isinstance(msg.get('content'), list):
                    # Liste de blocs de contenu (text, image, etc.)
                    content = ' '.join(
                        p.get('text', '') for p in msg['content']
                        if isinstance(p, dict) and p.get('type') == 'text'
                    )
                elif isinstance(msg.get('content'), str):
                    content = msg['content']

                if not content.strip():
                    continue

                timestamp = None
                if msg.get('created_at'):
                    try:
                        timestamp = datetime.fromisoformat(msg['created_at'])
                    except (ValueError, TypeError) as e:
                        logger.debug(f"Timestamp de message invalide : {e}")

                messages.append(ParsedMessage(
                    role=role,
                    content=content.strip(),
                    timestamp=timestamp
                ))

            if messages:
                created_at = None
                if conv.get('created_at'):
                    try:
                        created_at = datetime.fromisoformat(conv['created_at'])
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Timestamp invalide pour la conversation {conv.get('uuid', '?')} : {e}")

                conversations.append(ParsedConversation(
                    external_id=conv.get('uuid', conv.get('id', '')),
                    title=conv.get('name', conv.get('title', 'Sans titre')),
                    source_type='claude',
                    messages=messages,
                    created_at=created_at
                ))

        logger.info(f"{len(conversations)} conversation(s) parsée(s) depuis {filepath}")
        return conversations
