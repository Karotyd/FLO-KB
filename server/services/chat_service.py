"""
Service for handling chat operations and message generation.
"""

import logging
from typing import Tuple, Optional, Generator

from server.engine.model_manager import ModelManager
from server.router.model_router import ModelRouter
from .session_service import SessionService

logger = logging.getLogger(__name__)


class ChatService:
    """
    Orchestrates chat interactions between user, model routing, and message generation.

    Responsibilities:
    - Route messages to appropriate models
    - Generate responses (streaming and non-streaming)
    - Update conversation history
    - Handle model loading and errors
    """

    def __init__(
        self,
        model_manager: ModelManager,
        model_router: ModelRouter,
        session_service: SessionService
    ):
        """
        Initialize the chat service.

        Args:
            model_manager: Manager for loading and handling LLM models
            model_router: Router for selecting appropriate models
            session_service: Service for managing conversation sessions
        """
        self.model_manager = model_manager
        self.model_router = model_router
        self.session_service = session_service

    def send_message(
        self,
        session_id: str,
        message: str,
        model: Optional[str] = None,
        auto_route: bool = True
    ) -> Tuple[str, str, str]:
        """
        Send a message and get a response (non-streaming).

        Args:
            session_id: Session identifier
            message: User message
            model: Explicit model to use (None for auto-routing)
            auto_route: Enable automatic routing based on message content

        Returns:
            Tuple of (response, model_used, routing_reason)

        Raises:
            ValueError: If model is not found or invalid
            FileNotFoundError: If model file doesn't exist
            Exception: For other errors during generation
        """
        # 1. ROUTING: Determine which model to use
        selected_model_id, routing_reason = self.model_router.route(
            message=message,
            explicit_model=model,
            use_auto_routing=auto_route
        )

        logger.info(f"→ Model selected: '{selected_model_id}' (reason: {routing_reason})")

        # 2. LOADING: Load the model (or get from cache)
        llm = self.model_manager.load_model(selected_model_id)

        # 3. HISTORY: Retrieve and trim conversation history
        self.session_service.trim_history(session_id)
        history = self.session_service.get_history_as_strings(session_id)

        # 4. GENERATION: Generate response
        logger.debug("Generating response...")
        response = llm.generate(message, history)

        # 5. SAVE: Update conversation history
        self.session_service.add_message(session_id, "user", message)
        self.session_service.add_message(
            session_id,
            "assistant",
            response,
            model_used=selected_model_id
        )

        logger.info(f"✓ Response generated (length: {len(response)})")

        return response, selected_model_id, routing_reason

    def generate_stream(
        self,
        session_id: str,
        message: str,
        model: Optional[str] = None,
        auto_route: bool = True
    ) -> Generator[str, None, Tuple[str, str]]:
        """
        Generate a streaming response token by token.

        Args:
            session_id: Session identifier
            message: User message
            model: Explicit model to use (None for auto-routing)
            auto_route: Enable automatic routing

        Yields:
            Individual tokens as they are generated

        Returns:
            Tuple of (full_response, model_used) after streaming completes

        Raises:
            ValueError: If model is not found or invalid
            FileNotFoundError: If model file doesn't exist
            Exception: For other errors during generation
        """
        # 1. ROUTING: Determine which model to use
        selected_model_id, routing_reason = self.model_router.route(
            message=message,
            explicit_model=model,
            use_auto_routing=auto_route
        )

        logger.info(f"→ Model selected: '{selected_model_id}' (reason: {routing_reason})")

        # 2. LOADING: Load the model
        llm = self.model_manager.load_model(selected_model_id)

        # 3. HISTORY: Retrieve and trim conversation history
        self.session_service.trim_history(session_id)
        history = self.session_service.get_history_as_strings(session_id)

        # 4. STREAMING: Generate response token by token
        logger.debug("Starting streaming generation...")
        buffer = []

        for token in llm.generate_stream(message, history):
            buffer.append(token)
            yield token

        # 5. SAVE: Update conversation history after generation completes
        full_response = "".join(buffer).strip()

        self.session_service.add_message(session_id, "user", message)
        self.session_service.add_message(
            session_id,
            "assistant",
            full_response,
            model_used=selected_model_id
        )

        logger.info(f"✓ Streaming completed (length: {len(full_response)})")

        return full_response, selected_model_id
