"""
Déduplication des conversations — FLO-KB.
Deux niveaux de détection :
  1. Hash exact SHA-256 → doublon parfait
  2. Même external_id, hash différent → mise à jour
"""

import logging
from ..db import KnowledgeDB
from ..parsers.base_parser import ParsedConversation

logger = logging.getLogger(__name__)


class Deduplicator:
    """Détection des doublons et mises à jour de conversations."""

    def __init__(self, db: KnowledgeDB):
        self.db = db

    async def check(self, conversation: ParsedConversation) -> str:
        """
        Vérifie le statut de déduplication d'une conversation.

        Niveau 1 : hash SHA-256 identique → 'duplicate'
        Niveau 2 : même external_id mais hash différent → 'updated'
        Sinon → 'new'

        Args:
            conversation: La conversation à vérifier.

        Returns:
            'new', 'updated', ou 'duplicate'.
        """
        # Niveau 1 : hash exact
        existing_by_hash = await self.db.find_conversation_by_hash(conversation.content_hash)
        if existing_by_hash:
            logger.debug(f"Doublon exact détecté : '{conversation.title}' (hash={conversation.content_hash[:12]}...)")
            return 'duplicate'

        # Niveau 2 : même external_id mais contenu différent (mise à jour)
        if conversation.external_id:
            existing_by_id = await self.db.find_conversation_by_external_id(conversation.external_id)
            if existing_by_id:
                logger.info(f"Mise à jour détectée : '{conversation.title}' (external_id={conversation.external_id})")
                return 'updated'

        return 'new'
