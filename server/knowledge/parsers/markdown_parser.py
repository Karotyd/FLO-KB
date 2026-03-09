"""
Parseur Markdown — fallback universel pour FLO-KB.
Gère les exports Markdown de Copilot, Mistral, ou tout copier-coller.
Détecte les rôles via des patterns (## User, **Human**:, etc.) ou traite comme bloc unique.
"""

import re
import logging
from pathlib import Path
from .base_parser import BaseParser, ParsedConversation, ParsedMessage

logger = logging.getLogger(__name__)

# Pattern pour détecter les marqueurs de rôle dans le Markdown
# Ex: "## User", "**Human**:", "You:", "Assistant:", "### Claude:"
_ROLE_PATTERN = re.compile(
    r'(?:^|\n)(?:#{1,3}\s*)?(?:\*\*)?'
    r'(User|Human|You|Utilisateur|Assistant|AI|Bot|Claude|ChatGPT|Gemini|Copilot)'
    r'(?:\*\*)?[\s:]*\n?(.*?)(?=\n(?:#{1,3}\s*)?(?:\*\*)?'
    r'(?:User|Human|You|Utilisateur|Assistant|AI|Bot|Claude|ChatGPT|Gemini|Copilot)|$)',
    re.IGNORECASE | re.DOTALL
)

# Rôles qui correspondent à 'user'
_USER_ROLES = {'user', 'human', 'you', 'utilisateur'}


class MarkdownParser(BaseParser):
    """Parse les exports Markdown (Copilot, Mistral, ou copier-coller)."""

    def can_parse(self, filepath: str) -> bool:
        """Vérifie que le fichier est un .md ou .txt."""
        return filepath.endswith(('.md', '.txt'))

    def parse(self, filepath: str) -> list[ParsedConversation]:
        """
        Parse un fichier Markdown ou texte.
        Si des marqueurs de rôle sont détectés, extrait les messages séparément.
        Sinon, traite tout le contenu comme un bloc unique (rôle: assistant).
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()

        messages = []

        for match in _ROLE_PATTERN.finditer(text):
            role_raw = match.group(1).lower()
            content = match.group(2).strip()

            if not content:
                continue

            role = 'user' if role_raw in _USER_ROLES else 'assistant'
            messages.append(ParsedMessage(role=role, content=content))

        # Si aucun pattern détecté, traiter comme un bloc unique
        if not messages and text.strip():
            logger.debug(f"Aucun marqueur de rôle détecté dans {filepath} — bloc unique")
            messages.append(ParsedMessage(role='assistant', content=text.strip()))

        if not messages:
            logger.warning(f"Fichier vide ou non parsable : {filepath}")
            return []

        filename = Path(filepath).stem
        title = filename.replace('_', ' ').replace('-', ' ').title()

        logger.info(f"1 conversation parsée depuis {filepath} ({len(messages)} message(s))")

        return [ParsedConversation(
            external_id=filename,
            title=title,
            source_type='markdown',
            messages=messages
        )]
