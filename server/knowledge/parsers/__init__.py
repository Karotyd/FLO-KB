"""Parseurs de conversations IA — FLO-KB"""

from .base_parser import BaseParser, ParsedConversation, ParsedMessage
from .chatgpt_parser import ChatGPTParser
from .claude_parser import ClaudeParser
from .markdown_parser import MarkdownParser

# Ordre de priorité pour la détection automatique
# MarkdownParser en dernier car il accepte .md/.txt (fallback)
ALL_PARSERS = [
    ChatGPTParser(),
    ClaudeParser(),
    MarkdownParser(),  # fallback en dernier
]


def detect_and_parse(filepath: str) -> list[ParsedConversation]:
    """
    Détecte automatiquement le format et parse le fichier.

    Teste chaque parseur dans l'ordre de priorité et utilise le premier
    qui déclare pouvoir traiter le fichier.

    Args:
        filepath: Chemin absolu vers le fichier à parser.

    Returns:
        Liste de conversations normalisées.

    Raises:
        ValueError: Si aucun parseur ne peut traiter le fichier.
    """
    for parser in ALL_PARSERS:
        if parser.can_parse(filepath):
            return parser.parse(filepath)
    raise ValueError(f"Aucun parseur compatible pour : {filepath}")
