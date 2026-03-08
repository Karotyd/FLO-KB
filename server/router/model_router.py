"""
Model Router - Routage intelligent des requêtes vers le modèle approprié
Analyse le contenu du message et choisit le meilleur modèle
"""
import logging
import re
from typing import Optional, Dict, List, Tuple
from server.engine.model_manager import get_model_manager

logger = logging.getLogger(__name__)


class ModelRouter:
    """Routeur intelligent pour sélectionner le modèle approprié"""

    def __init__(self):
        self.model_manager = get_model_manager()

    def _normalize_text(self, text: str) -> str:
        """
        Normalise le texte pour l'analyse
        - Minuscules
        - Suppression des caractères spéciaux
        """
        text = text.lower()
        # Garder seulement lettres, chiffres et espaces
        text = re.sub(r'[^a-zà-ÿ0-9\s]', ' ', text)
        return text

    def _calculate_keyword_score(self, message: str, keywords: List[str]) -> float:
        """
        Calcule un score basé sur la présence de mots-clés

        Args:
            message: Message de l'utilisateur (normalisé)
            keywords: Liste de mots-clés du modèle

        Returns:
            Score entre 0 et 1
        """
        if not keywords:
            return 0.0

        message_words = set(message.split())
        keyword_matches = 0

        for keyword in keywords:
            keyword_lower = keyword.lower()

            # Match exact
            if keyword_lower in message_words:
                keyword_matches += 1
            # Match partiel (le mot-clé est contenu dans le message)
            elif keyword_lower in message:
                keyword_matches += 0.5

        # Normaliser le score
        score = keyword_matches / len(keywords)
        return min(score, 1.0)  # Cap à 1.0

    def _analyze_message(self, message: str) -> Dict[str, float]:
        """
        Analyse le message et calcule un score pour chaque modèle

        Args:
            message: Message de l'utilisateur

        Returns:
            Dictionnaire {model_id: score}
        """
        normalized_message = self._normalize_text(message)
        scores = {}

        for model_id, config in self.model_manager.models_config.items():
            keywords = config.get("keywords", [])
            score = self._calculate_keyword_score(normalized_message, keywords)
            scores[model_id] = score

            logger.debug(f"Modèle '{model_id}' - Score : {score:.2f}")

        return scores

    def route(
        self,
        message: str,
        explicit_model: Optional[str] = None,
        use_auto_routing: bool = True
    ) -> Tuple[str, str]:
        """
        Détermine quel modèle utiliser pour une requête

        Args:
            message: Message de l'utilisateur
            explicit_model: Modèle explicitement demandé par l'utilisateur
            use_auto_routing: Activer le routage automatique

        Returns:
            Tuple (model_id, routing_reason)
                - model_id: ID du modèle sélectionné
                - routing_reason: Raison du choix (pour logging/debug)

        Raises:
            ValueError: Si le modèle explicite n'existe pas
        """
        # Cas 1 : L'utilisateur a spécifié un modèle explicitement
        if explicit_model:
            if explicit_model not in self.model_manager.models_config:
                available = ", ".join(self.model_manager.models_config.keys())
                raise ValueError(f"Modèle '{explicit_model}' introuvable. Disponibles : {available}")

            logger.info(f"Routage manuel : modèle '{explicit_model}' spécifié par l'utilisateur")
            return explicit_model, "explicit_user_choice"

        # Cas 2 : Routage automatique désactivé
        if not use_auto_routing or not self.model_manager.is_routing_enabled():
            default_model = self.model_manager.get_default_model_id()
            logger.info(f"Routage automatique désactivé, utilisation du modèle par défaut : {default_model}")
            return default_model, "auto_routing_disabled"

        # Cas 3 : Routage automatique activé
        scores = self._analyze_message(message)

        # Trouver le modèle avec le meilleur score
        best_model_id = max(scores, key=scores.get)
        best_score = scores[best_model_id]

        # Seuil de confiance (défini dans models.json)
        confidence_threshold = self.model_manager.routing_config.get("confidence_threshold", 0.3)

        # Si le score est trop faible, utiliser le modèle par défaut
        if best_score < confidence_threshold:
            fallback_model = self.model_manager.routing_config.get(
                "fallback_model",
                self.model_manager.get_default_model_id()
            )
            logger.info(
                f"Score trop faible ({best_score:.2f} < {confidence_threshold}), "
                f"utilisation du modèle de secours : {fallback_model}"
            )
            return fallback_model, f"low_confidence_fallback (score={best_score:.2f})"

        # Utiliser le modèle avec le meilleur score
        model_name = self.model_manager.models_config[best_model_id]["name"]
        logger.info(
            f"Routage automatique : '{best_model_id}' ({model_name}) "
            f"sélectionné (score={best_score:.2f})"
        )

        return best_model_id, f"auto_routed (score={best_score:.2f})"

    def get_routing_explanation(self, message: str) -> Dict:
        """
        Explique le routage qui serait effectué pour un message
        (utile pour debugging et transparence)

        Args:
            message: Message de l'utilisateur

        Returns:
            Dictionnaire avec les scores et la décision
        """
        scores = self._analyze_message(message)
        model_id, reason = self.route(message)

        return {
            "selected_model": model_id,
            "routing_reason": reason,
            "scores": scores,
            "models_info": {
                mid: {
                    "name": self.model_manager.models_config[mid]["name"],
                    "specialties": self.model_manager.models_config[mid].get("specialties", [])
                }
                for mid in scores.keys()
            }
        }


# Instance singleton du routeur
_router_instance: Optional[ModelRouter] = None


def get_router() -> ModelRouter:
    """
    Retourne l'instance singleton du routeur

    Returns:
        Instance globale du ModelRouter
    """
    global _router_instance

    if _router_instance is None:
        _router_instance = ModelRouter()

    return _router_instance
