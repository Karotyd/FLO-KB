import logging
from fastapi.responses import StreamingResponse
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from server.engine.model_manager import get_model_manager
from server.router.model_router import get_router
from server.storage.json_storage import JSONStorage
from server.services.session_service import SessionService
from server.services.chat_service import ChatService
from server.services import StatsService
import time

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# DEPENDENCY INITIALIZATION
# ============================================================================

# Initialize Engine layer
model_manager = get_model_manager()
model_router = get_router()
# Initialisation du StatsService
storage = JSONStorage(data_dir="data/sessions")


# Initialize Storage layer
stats_service = StatsService(storage)

# Initialize Service layer
session_service = SessionService(storage=storage)
chat_service = ChatService(
    model_manager=model_manager,
    model_router=model_router,
    session_service=session_service
)

# Preload default model
try:
    default_model_id = model_manager.get_default_model_id()
    model_manager.load_model(default_model_id)
    logger.info(f"✓ Default model '{default_model_id}' preloaded")
except Exception as e:
    logger.error(f"Failed to preload default model: {e}", exc_info=True)

# ============================================================================
# REQUEST MODELS
# ============================================================================

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    session_id: str
    stream: bool = False
    model: Optional[str] = None  # Explicit model (None = auto-routing)
    auto_route: bool = True  # Enable automatic routing

# ============================================================================
# STREAMING HELPER
# ============================================================================

def sse_event_generator(session_id: str, message: str, model: Optional[str], auto_route: bool):
    """Generator for Server-Sent Events streaming."""
    try:
        # Use chat_service for streaming
        for token in chat_service.generate_stream(session_id, message, model, auto_route):
            yield f"data: {token}\n\n"

        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Error in streaming: {e}", exc_info=True)
        yield f"data: [ERROR] {str(e)}\n\n"

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/chat")
def chat(req: ChatRequest):
    """
    Handle chat requests with optional streaming.

    Delegates all business logic to ChatService.
    """
    try:
        logger.info(
            f"New request - session: {req.session_id}, "
            f"stream: {req.stream}, explicit_model: {req.model}, auto_route: {req.auto_route}"
        )

        # STREAMING MODE
        if req.stream:
            logger.debug("Streaming mode enabled")
            return StreamingResponse(
                sse_event_generator(req.session_id, req.message, req.model, req.auto_route),
                media_type="text/event-stream"
            )

        # NON-STREAMING MODE
        else:
            try:
                response, model_used, routing_reason = chat_service.send_message(
                    session_id=req.session_id,
                    message=req.message,
                    model=req.model,
                    auto_route=req.auto_route
                )

                return {
                    "response": response,
                    "model_used": model_used,
                    "routing_reason": routing_reason
                }

            except ValueError as e:
                # Model not found or routing error
                logger.error(f"Routing/validation error: {e}")
                raise HTTPException(status_code=404, detail=str(e))

            except FileNotFoundError as e:
                # Model file not found
                logger.error(f"Model file not found: {e}")
                raise HTTPException(status_code=404, detail=str(e))

            except Exception as e:
                # Model loading or generation error
                logger.error(f"Error during generation: {e}", exc_info=True)
                raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in /chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/models")
def list_models():
    """
    Liste tous les modèles disponibles avec leurs caractéristiques
    """
    try:
        models_list = model_manager.list_models()
        current_model_id, _ = model_manager.get_current_model()

        return {
            "models": models_list,
            "default_model": model_manager.get_default_model_id(),
            "current_loaded_model": current_model_id,
            "routing_enabled": model_manager.is_routing_enabled()
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des modèles : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/routing/explain")
def explain_routing(message: str):
    """
    Explique quel modèle serait sélectionné pour un message donné
    Utile pour debugging et transparence

    Args:
        message: Le message à analyser

    Returns:
        Dictionnaire avec les scores et la décision de routage
    """
    try:
        explanation = model_router.get_routing_explanation(message)
        return explanation
    except Exception as e:
        logger.error(f"Erreur lors de l'explication du routage : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models/switch")
def switch_model(model_id: str):
    """
    Change de modèle manuellement (décharge l'ancien, charge le nouveau)

    Args:
        model_id: ID du modèle à charger

    Returns:
        Confirmation du changement
    """
    try:
        logger.info(f"Demande de changement de modèle vers : {model_id}")

        # Charger le nouveau modèle (décharge automatiquement l'ancien)
        model_manager.load_model(model_id)

        return {
            "success": True,
            "message": f"Modèle '{model_id}' chargé avec succès",
            "current_model": model_id
        }
    except ValueError as e:
        logger.error(f"Modèle invalide : {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur lors du changement de modèle : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Impossible de changer de modèle: {str(e)}")
@router.get("/stats")
def get_stats():
    """
    Retourne les statistiques d'utilisation du système
    
    Returns:
        - total_messages: Nombre total de messages traités
        - active_sessions: Nombre de sessions actives
        - models: Statistiques par modèle (usage, temps moyen)
    """
    try:
        stats = stats_service.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stats : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stats/reset")
def reset_stats():
    """
    Réinitialise toutes les statistiques
    
    Returns:
        Message de confirmation
    """
    try:
        stats_service.reset_stats()
        return {
            "success": True,
            "message": "Statistiques réinitialisées avec succès"
        }
    except Exception as e:
        logger.error(f"Erreur lors de la réinitialisation des stats : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
def list_sessions():
    """
    Liste toutes les sessions sauvegardées
    
    Returns:
        Liste des IDs de session
    """
    try:
        sessions = storage.list_sessions()
        return {
            "sessions": sessions,
            "total": len(sessions)
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des sessions : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}")
def get_session_details(session_id: str):
    """
    Récupère les détails d'une session spécifique
    
    Args:
        session_id: ID de la session
        
    Returns:
        Détails de la session avec tous les messages
    """
    try:
        session = storage.get_session(session_id)
        
        if session is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} non trouvée")
        
        return {
            "id": session.id,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "message_count": len(session.messages),
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "model_used": msg.model_used
                }
                for msg in session.messages
            ],
            "metadata": session.metadata
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la session : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """
    Supprime une session
    
    Args:
        session_id: ID de la session à supprimer
        
    Returns:
        Message de confirmation
    """
    try:
        storage.delete_session(session_id)
        return {
            "success": True,
            "message": f"Session {session_id} supprimée avec succès"
        }
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la session : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
