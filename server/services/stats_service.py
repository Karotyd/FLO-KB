import logging
from typing import Dict, List
from datetime import datetime
from collections import defaultdict
from server.storage.base import StorageInterface

logger = logging.getLogger(__name__)

class StatsService:
    """Service pour collecter et afficher des statistiques d'utilisation"""
    
    def __init__(self, storage: StorageInterface):
        self.storage = storage
        self.model_usage = defaultdict(int)  # Nombre d'utilisation par modèle
        self.response_times = defaultdict(list)  # Temps de réponse par modèle
        self.total_messages = 0
    
    def record_model_usage(self, model_id: str, response_time: float = None):
        """Enregistre l'utilisation d'un modèle"""
        self.model_usage[model_id] += 1
        self.total_messages += 1
        
        if response_time:
            self.response_times[model_id].append(response_time)
        
        logger.debug(f"Stats: {model_id} utilisé {self.model_usage[model_id]} fois")
    
    def get_stats(self) -> Dict:
        """Retourne les statistiques complètes"""
        
        # Statistiques par modèle
        model_stats = {}
        for model_id, count in self.model_usage.items():
            avg_time = None
            if model_id in self.response_times and self.response_times[model_id]:
                avg_time = sum(self.response_times[model_id]) / len(self.response_times[model_id])
            
            model_stats[model_id] = {
                "usage_count": count,
                "percentage": round((count / self.total_messages * 100), 2) if self.total_messages > 0 else 0,
                "avg_response_time": round(avg_time, 2) if avg_time else None
            }
        
        # Nombre de sessions actives
        active_sessions = len(self.storage.list_sessions())
        
        # Statistiques globales
        return {
            "total_messages": self.total_messages,
            "active_sessions": active_sessions,
            "models": model_stats,
            "timestamp": datetime.now().isoformat()
        }
    
    def reset_stats(self):
        """Réinitialise toutes les statistiques"""
        self.model_usage.clear()
        self.response_times.clear()
        self.total_messages = 0
        logger.info("Statistiques réinitialisées")