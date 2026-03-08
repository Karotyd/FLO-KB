"""
Abstract base interface for storage implementations.
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from .models import Session, Message


class StorageInterface(ABC):
    """
    Abstract base class defining the storage interface.

    Implementations can use different backends (JSON, SQLite, Redis, etc.)
    while maintaining the same interface.
    """

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Retrieve a session by ID.

        Args:
            session_id: Unique identifier for the session

        Returns:
            Session object if found, None otherwise
        """
        pass

    @abstractmethod
    def save_session(self, session: Session) -> None:
        """
        Save or update a session.

        Args:
            session: Session object to persist
        """
        pass

    @abstractmethod
    def add_message(self, session_id: str, message: Message) -> None:
        """
        Add a message to a session's history.

        Args:
            session_id: ID of the session to update
            message: Message to add
        """
        pass

    @abstractmethod
    def list_sessions(self) -> List[str]:
        """
        List all session IDs.

        Returns:
            List of session IDs
        """
        pass

    @abstractmethod
    def delete_session(self, session_id: str) -> None:
        """
        Delete a session and all its messages.

        Args:
            session_id: ID of the session to delete
        """
        pass
