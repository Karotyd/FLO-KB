"""
Service for managing conversation sessions and message history.
"""

import logging
from typing import List, Optional
from server.storage.base import StorageInterface
from server.storage.models import Session, Message

logger = logging.getLogger(__name__)


class SessionService:
    """
    Handles session management and message history.

    Responsibilities:
    - Create and retrieve sessions
    - Add messages to sessions
    - Format history for the Engine layer
    - Trim history to manage context length
    """

    def __init__(self, storage: StorageInterface):
        """
        Initialize the session service.

        Args:
            storage: Storage backend to use for persistence
        """
        self.storage = storage
        self.cache = {}  # In-memory cache for active sessions

    def get_or_create(self, session_id: str) -> Session:
        """
        Get an existing session or create a new one.

        Args:
            session_id: Unique session identifier

        Returns:
            Session object
        """
        # Try cache first
        if session_id in self.cache:
            logger.debug(f"Session {session_id} retrieved from cache")
            return self.cache[session_id]

        # Try loading from storage
        session = self.storage.get_session(session_id)

        if session is None:
            logger.info(f"Creating new session: {session_id}")
            session = Session(id=session_id)
            # Save immediately to create the file
            self.storage.save_session(session)
        else:
            logger.info(f"Session {session_id} loaded from storage ({len(session.messages)} messages)")

        # Cache the session
        self.cache[session_id] = session
        return session

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        model_used: Optional[str] = None
    ) -> None:
        """
        Add a message to a session.

        Args:
            session_id: Session identifier
            role: Message role ("user" or "assistant")
            content: Message content
            model_used: Model that generated this message (for assistant messages)
        """
        message = Message(role=role, content=content, model_used=model_used)

        # Update cache
        if session_id in self.cache:
            self.cache[session_id].messages.append(message)

        # Persist to storage
        self.storage.add_message(session_id, message)
        logger.debug(f"Message added to session {session_id} (role={role})")

    def get_history_as_strings(
        self,
        session_id: str,
        max_messages: Optional[int] = None
    ) -> List[str]:
        """
        Get conversation history formatted as strings for the Engine layer.

        Format: ["Utilisateur: message", "Assistant: response", ...]

        Args:
            session_id: Session identifier
            max_messages: Maximum number of messages to return (from end)

        Returns:
            List of formatted message strings
        """
        session = self.get_or_create(session_id)
        messages = session.messages

        # Limit number of messages if specified
        if max_messages:
            messages = messages[-max_messages:]

        # Format messages for the Engine
        return [
            f"{'Utilisateur' if m.role == 'user' else 'Assistant'}: {m.content}"
            for m in messages
        ]

    def trim_history(self, session_id: str, max_tokens: int = 1500) -> None:
        """
        Remove old messages if history is too long.

        Uses a simple heuristic: ~4 characters per token.
        Keeps at least the last 2 messages to maintain context.

        Args:
            session_id: Session identifier
            max_tokens: Maximum number of tokens to keep (approximate)
        """
        session = self.get_or_create(session_id)
        approx_chars = max_tokens * 4

        # Calculate total length
        total_chars = sum(len(m.content) for m in session.messages)

        # Remove old messages while staying over limit
        while total_chars > approx_chars and len(session.messages) > 2:
            removed = session.messages.pop(0)
            total_chars -= len(removed.content)
            logger.debug(f"Trimmed message from session {session_id}")

        # Save if we modified the session
        if len(session.messages) != session.message_count:
            self.storage.save_session(session)
            # Update cache
            self.cache[session_id] = session

    def list_all_sessions(self) -> List[str]:
        """
        List all session IDs.

        Returns:
            List of session IDs
        """
        return self.storage.list_sessions()

    def delete_session(self, session_id: str) -> None:
        """
        Delete a session from storage and cache.

        Args:
            session_id: Session identifier
        """
        self.storage.delete_session(session_id)

        # Remove from cache
        if session_id in self.cache:
            del self.cache[session_id]

        logger.info(f"Session {session_id} deleted")

    def get_session_info(self, session_id: str) -> dict:
        """
        Get information about a session.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary with session metadata
        """
        session = self.get_or_create(session_id)

        return {
            "session_id": session.id,
            "message_count": session.message_count,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "metadata": session.metadata
        }
