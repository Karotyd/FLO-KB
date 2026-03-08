"""
JSON-based storage implementation.
Stores each session as a separate JSON file.
"""

import json
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from .base import StorageInterface
from .models import Session, Message

logger = logging.getLogger(__name__)


class JSONStorage(StorageInterface):
    """
    File-based storage using JSON format.

    Each session is stored as a separate .json file in the data directory.
    This is simple, human-readable, and suitable for development/small deployments.
    """

    def __init__(self, data_dir: str = "data/sessions"):
        """
        Initialize JSON storage.

        Args:
            data_dir: Directory where session files will be stored
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"JSONStorage initialized: {self.data_dir.absolute()}")

    def _get_session_path(self, session_id: str) -> Path:
        """Get the file path for a session."""
        return self.data_dir / f"{session_id}.json"

    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Load a session from disk.

        Args:
            session_id: Session identifier

        Returns:
            Session object if file exists, None otherwise
        """
        path = self._get_session_path(session_id)

        if not path.exists():
            logger.debug(f"Session {session_id} not found on disk")
            return None

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Reconstruct Message objects
            messages = [
                Message(
                    role=m['role'],
                    content=m['content'],
                    timestamp=datetime.fromisoformat(m['timestamp']),
                    model_used=m.get('model_used')
                )
                for m in data['messages']
            ]

            # Reconstruct Session object
            session = Session(
                id=data['id'],
                messages=messages,
                created_at=datetime.fromisoformat(data['created_at']),
                updated_at=datetime.fromisoformat(data['updated_at']),
                metadata=data.get('metadata', {})
            )

            logger.debug(f"Loaded session {session_id}: {len(messages)} messages")
            return session

        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None

    def save_session(self, session: Session) -> None:
        """
        Save a session to disk.

        Args:
            session: Session object to persist
        """
        # Update timestamp
        session.updated_at = datetime.now()

        # Serialize to dict
        data = {
            'id': session.id,
            'messages': [
                {
                    'role': m.role,
                    'content': m.content,
                    'timestamp': m.timestamp.isoformat(),
                    'model_used': m.model_used
                }
                for m in session.messages
            ],
            'created_at': session.created_at.isoformat(),
            'updated_at': session.updated_at.isoformat(),
            'metadata': session.metadata
        }

        # Write to file
        path = self._get_session_path(session.id)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.debug(f"Saved session {session.id}: {len(session.messages)} messages")

        except Exception as e:
            logger.error(f"Failed to save session {session.id}: {e}")
            raise

    def add_message(self, session_id: str, message: Message) -> None:
        """
        Add a message to a session.

        If the session doesn't exist, it will be created.

        Args:
            session_id: Session identifier
            message: Message to add
        """
        session = self.get_session(session_id)

        if session is None:
            logger.info(f"Creating new session: {session_id}")
            session = Session(id=session_id)

        session.messages.append(message)
        self.save_session(session)

    def list_sessions(self) -> List[str]:
        """
        List all session IDs.

        Returns:
            List of session IDs (without .json extension)
        """
        try:
            session_ids = [p.stem for p in self.data_dir.glob("*.json")]
            logger.debug(f"Found {len(session_ids)} sessions")
            return session_ids
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []

    def delete_session(self, session_id: str) -> None:
        """
        Delete a session file.

        Args:
            session_id: Session identifier
        """
        path = self._get_session_path(session_id)

        if path.exists():
            try:
                path.unlink()
                logger.info(f"Deleted session: {session_id}")
            except Exception as e:
                logger.error(f"Failed to delete session {session_id}: {e}")
                raise
        else:
            logger.warning(f"Cannot delete session {session_id}: file not found")
