"""
Classes de base pour les parseurs de conversations IA — FLO-KB.
Définit le format interne commun vers lequel tous les parseurs normalisent.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from abc import ABC, abstractmethod
import hashlib


@dataclass
class ParsedMessage:
    """Un message individuel dans une conversation."""
    role: str                        # 'user' ou 'assistant'
    content: str
    timestamp: Optional[datetime] = None


@dataclass
class ParsedConversation:
    """Une conversation normalisée (format interne commun)."""
    external_id: str                 # ID original dans la source
    title: str
    source_type: str                 # 'chatgpt', 'claude', 'gemini', 'markdown'
    messages: list[ParsedMessage] = field(default_factory=list)
    created_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        """Texte complet de la conversation (pour le LLM)."""
        lines = []
        for msg in self.messages:
            role = "Utilisateur" if msg.role == "user" else "Assistant"
            lines.append(f"{role}: {msg.content}")
        return "\n\n".join(lines)

    @property
    def content_hash(self) -> str:
        """Hash SHA-256 du contenu pour déduplication."""
        return hashlib.sha256(self.full_text.encode()).hexdigest()


class BaseParser(ABC):
    """Classe abstraite pour tous les parseurs de conversations IA."""

    @abstractmethod
    def can_parse(self, filepath: str) -> bool:
        """Vérifie si ce parseur peut traiter ce fichier."""
        pass

    @abstractmethod
    def parse(self, filepath: str) -> list[ParsedConversation]:
        """Parse le fichier et retourne les conversations normalisées."""
        pass
