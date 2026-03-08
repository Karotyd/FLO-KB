"""
Data models for storage layer.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional


@dataclass
class Message:
    """Represents a single message in a conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    model_used: Optional[str] = None

    def __repr__(self):
        return f"Message(role={self.role}, content={self.content[:50]}..., model={self.model_used})"


@dataclass
class Session:
    """Represents a conversation session with message history."""
    id: str
    messages: List[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)

    def __repr__(self):
        return f"Session(id={self.id}, messages={len(self.messages)}, created={self.created_at})"

    @property
    def message_count(self) -> int:
        """Returns the number of messages in this session."""
        return len(self.messages)

    @property
    def last_activity(self) -> datetime:
        """Returns the timestamp of the last activity."""
        return self.updated_at
