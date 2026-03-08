"""
Model Manager - Gère le chargement/déchargement dynamique des modèles
Contrainte : 1 seul modèle en mémoire à la fois (VRAM limitée)
"""
import json
import logging
import gc
from pathlib import Path
from typing import Optional, Dict, Any
from server.engine.factory import create_llm

logger = logging.getLogger(__name__)


class ModelManager:
    """Gestionnaire de modèles avec support d'un seul modèle en mémoire"""

    def __init__(self, config_path: str = "models.json"):
        self.config_path = Path(config_path)
        self.models_config: Dict[str, Any] = {}
        self.current_model_id: Optional[str] = None
        self.current_model: Optional[Any] = None

        # Charger la configuration
        self._load_config()

    def _load_config(self):
        """Charge la configuration depuis models.json"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # Indexer les modèles par ID
            for model in config.get("models", []):
                self.models_config[model["id"]] = model

            self.default_model_id = config.get("default_model", "mistral-7b")
            self.routing_config = config.get("routing", {})

            logger.info(f"Configuration chargée : {len(self.models_config)} modèles disponibles")

        except FileNotFoundError:
            logger.error(f"Fichier de configuration introuvable : {self.config_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Erreur de parsing JSON : {e}")
            raise

    def get_model_config(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Récupère la configuration d'un modèle"""
        return self.models_config.get(model_id)

    def list_models(self) -> list:
        """Liste tous les modèles disponibles avec leurs infos"""
        models_list = []
        for model_id, config in self.models_config.items():
            model_path = Path(config["path"])
            models_list.append({
                "id": model_id,
                "name": config["name"],
                "specialties": config.get("specialties", []),
                "context_length": config.get("context_length", 2048),
                "is_loaded": model_id == self.current_model_id,
                "is_default": model_id == self.default_model_id,
                "path_exists": model_path.exists()
            })
        return models_list

    def unload_current_model(self):
        """Décharge le modèle actuellement en mémoire"""
        if self.current_model is None:
            return

        logger.info(f"Déchargement du modèle : {self.current_model_id}")

        # Libérer la référence
        self.current_model = None
        self.current_model_id = None

        # Forcer le garbage collection pour libérer la mémoire
        gc.collect()

        logger.info("Modèle déchargé, mémoire libérée")

    def load_model(self, model_id: str, force_reload: bool = False) -> Any:
        """
        Charge un modèle en mémoire.
        Si un autre modèle est déjà chargé, le décharge d'abord.

        Args:
            model_id: ID du modèle à charger
            force_reload: Force le rechargement même si déjà en mémoire

        Returns:
            Instance du modèle LLM

        Raises:
            ValueError: Si le modèle n'existe pas
            FileNotFoundError: Si le fichier du modèle est introuvable
        """
        # Si le modèle demandé est déjà chargé
        if self.current_model_id == model_id and not force_reload:
            logger.debug(f"Modèle '{model_id}' déjà chargé (cache hit)")
            return self.current_model

        # Vérifier que le modèle existe dans la config
        if model_id not in self.models_config:
            available = ", ".join(self.models_config.keys())
            raise ValueError(f"Modèle '{model_id}' introuvable. Disponibles : {available}")

        # Récupérer la configuration du modèle
        model_config = self.models_config[model_id]
        model_path = Path(model_config["path"])

        # Vérifier que le fichier existe
        if not model_path.exists():
            raise FileNotFoundError(f"Fichier du modèle introuvable : {model_path}")

        # Décharger le modèle actuel si présent
        if self.current_model is not None:
            logger.info(f"Changement de modèle : {self.current_model_id} -> {model_id}")
            self.unload_current_model()

        # Charger le nouveau modèle
        logger.info(f"Chargement du modèle : {model_id} ({model_config['name']})")
        logger.info(f"Chemin : {model_path}")

        try:
            # Utiliser la factory pour créer le modèle
            self.current_model = create_llm(
                engine="gguf",  # Tous les modèles sont en GGUF
                model_path=str(model_path),
                params=model_config.get("params", {})
            )

            self.current_model_id = model_id
            logger.info(f"✓ Modèle '{model_id}' chargé avec succès")

            return self.current_model

        except Exception as e:
            logger.error(f"Erreur lors du chargement du modèle '{model_id}' : {e}", exc_info=True)
            self.current_model = None
            self.current_model_id = None
            raise

    def get_current_model(self) -> tuple[Optional[str], Optional[Any]]:
        """
        Retourne le modèle actuellement chargé

        Returns:
            Tuple (model_id, model_instance)
        """
        return self.current_model_id, self.current_model

    def switch_model(self, model_id: str) -> Any:
        """
        Change de modèle (alias pour load_model pour plus de clarté)

        Args:
            model_id: ID du modèle à charger

        Returns:
            Instance du modèle LLM
        """
        return self.load_model(model_id)

    def get_default_model_id(self) -> str:
        """Retourne l'ID du modèle par défaut"""
        return self.default_model_id

    def is_routing_enabled(self) -> bool:
        """Vérifie si le routage automatique est activé"""
        return self.routing_config.get("enabled", True)

    def get_routing_config(self) -> Dict[str, Any]:
        """Retourne la configuration du routage"""
        return self.routing_config


# Singleton global du ModelManager
_model_manager_instance: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """
    Retourne l'instance singleton du ModelManager

    Returns:
        Instance globale du ModelManager
    """
    global _model_manager_instance

    if _model_manager_instance is None:
        _model_manager_instance = ModelManager()

    return _model_manager_instance
