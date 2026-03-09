"""
Pipeline d'extraction des connaissances via LLM local — FLO-KB.
Orchestre : filtrage → extraction → résumé → classification.

Appel au LLM :
  On utilise le Llama sous-jacent (llm.llm) directement pour avoir le contrôle
  complet sur les stop tokens et max_tokens, sans modifier le moteur FLO.
  Le format utilisé est le Mistral Instruct [INST]...[/INST].
"""

import asyncio
import logging
from typing import Optional

from server.knowledge.db import KnowledgeDB
from server.knowledge.processing.prompts import (
    FILTER_PROMPT, EXTRACT_PROMPT, SUMMARIZE_PROMPT, CLASSIFY_PROMPT
)
from server.knowledge.processing.json_parser import parse_llm_json
from server.knowledge.processing.gpu_check import select_best_model

logger = logging.getLogger(__name__)

# Taille max du texte de conversation envoyé au LLM.
# kb-light a n_ctx=4096. Les prompts EXTRACT font ~300 tokens, soit :
# 4096 - 300 (prompt) - 1200 (output buffer) ≈ 2596 tokens disponibles pour la conv.
# 2596 tokens × 2.85 chars/token ≈ 7400 chars → on prend 6000 par sécurité.
MAX_CHARS = 6_000

# Nombre de tentatives en cas de JSON invalide
MAX_RETRIES = 3

# Paramètres de génération spécifiques aux tâches KB
# (override des params du modèle pour JSON fiable)
_KB_GEN_PARAMS = {
    "temperature": 0.1,
    "top_p": 0.3,
    "repeat_penalty": 1.1,
    "max_tokens": 2000,
    # Stop tokens propres : pas de "\n###" qui tronquerait le JSON
    "stop": ["</s>", "[INST]", "Note:", "ATTENTION:"],
}


def _format_mistral_prompt(prompt: str) -> str:
    """Formate un prompt pour Mistral Instruct v0.2 ([INST]...[/INST])."""
    return f"[INST] {prompt} [/INST]"


class KnowledgeExtractor:
    """Pipeline complet de traitement des conversations par LLM local."""

    def __init__(self, db: KnowledgeDB, model_manager):
        """
        Args:
            db: Instance KnowledgeDB.
            model_manager: Instance du ModelManager de FLO.
        """
        self.db = db
        self.model_manager = model_manager
        self._llm = None       # Instance GGUFLLM
        self._llama = None     # Instance llama_cpp.Llama sous-jacente

    async def _ensure_model_loaded(self):
        """Charge le modèle KB si pas encore chargé."""
        if self._llama is not None:
            return

        selection = select_best_model()
        model_id = selection["model_id"]
        if "warning" in selection:
            logger.warning(selection["warning"])

        logger.info(f"Chargement du modèle KB : {model_id}")

        # load_model est synchrone → on le lance dans un thread pour ne pas bloquer l'event loop
        self._llm = await asyncio.to_thread(self.model_manager.load_model, model_id)

        # Accès au Llama sous-jacent pour contrôle total (stop tokens, max_tokens)
        # Cela évite les stop tokens "\n###" du GGUFLLM qui truncent le JSON
        self._llama = self._llm.llm
        logger.info(f"Modèle KB prêt : {model_id}")

    def _truncate(self, text: str) -> str:
        """Tronque le texte à MAX_CHARS en gardant début et fin."""
        if len(text) <= MAX_CHARS:
            return text
        half = MAX_CHARS // 2
        return text[:half] + "\n\n[... conversation tronquée ...]\n\n" + text[-half:]

    def _generate_sync(self, prompt: str, temperature: float = 0.1) -> str:
        """
        Génération synchrone via llama_cpp directement.
        Appelée depuis asyncio.to_thread pour ne pas bloquer.
        """
        formatted = _format_mistral_prompt(prompt)
        params = {**_KB_GEN_PARAMS, "temperature": temperature}
        output = self._llama(formatted, **params)
        return output["choices"][0]["text"].strip()

    async def _call_llm(self, prompt: str, temperature: float = 0.1) -> str:
        """Appelle le LLM de façon async (délégué dans un thread)."""
        await self._ensure_model_loaded()
        return await asyncio.to_thread(self._generate_sync, prompt, temperature)

    async def _call_llm_json(self, prompt: str) -> dict | list:
        """
        Appelle le LLM et parse la réponse JSON avec retry.

        En cas de context overflow (prompt trop long), on relance sans rien
        car c'est le prompt formaté qui déborde — le tronquage a déjà été fait.
        En cas de JSON invalide, on relance jusqu'à MAX_RETRIES fois.

        Raises:
            ValueError après MAX_RETRIES tentatives infructueuses.
        """
        last_error = None
        # Températures croissantes à chaque retry pour diversifier la sortie
        temperatures = [0.1, 0.3, 0.5]

        for attempt in range(MAX_RETRIES):
            try:
                raw = await self._call_llm(prompt, temperature=temperatures[attempt])
                return parse_llm_json(raw)
            except Exception as e:
                last_error = e
                err_str = str(e)
                # Détecter le dépassement de contexte (llama_cpp RuntimeError)
                if "exceed context window" in err_str:
                    # Pas de retry utile : le prompt est trop long même après tronquage
                    raise ValueError(f"Prompt trop long pour le contexte : {err_str}")
                logger.warning(f"Tentative {attempt + 1}/{MAX_RETRIES} — {e}")

        raise ValueError(f"JSON irrécupérable après {MAX_RETRIES} tentatives : {last_error}")

    # ------------------------------------------------------------------
    # Étape 1 : FILTRAGE
    # ------------------------------------------------------------------
    async def filter_conversation(self, conv_text: str) -> tuple[int, str]:
        """
        Évalue la valeur informationnelle d'une conversation (score 1-5).

        Returns:
            (score, reason) — score clampé entre 1 et 5.
        """
        prompt = FILTER_PROMPT.format(conversation=self._truncate(conv_text))
        try:
            result = await self._call_llm_json(prompt)
            score = int(result.get("score", 1))
            score = max(1, min(5, score))
            reason = str(result.get("reason", "")).strip()
            return score, reason
        except (ValueError, KeyError, TypeError) as e:
            logger.error(f"Erreur filtrage : {e}")
            return 0, f"Erreur : {e}"

    # ------------------------------------------------------------------
    # Étape 2 : EXTRACTION
    # ------------------------------------------------------------------
    async def extract_knowledge(self, conv_text: str) -> list[dict]:
        """
        Extrait les items de connaissance d'une conversation.

        Returns:
            Liste de dicts validés : type, title, content, source_quote, confidence.
        """
        prompt = EXTRACT_PROMPT.format(conversation=self._truncate(conv_text))
        valid_types = {"fact", "concept", "recommendation", "insight", "reference", "decision"}

        try:
            result = await self._call_llm_json(prompt)
            items = result.get("items", [])
            valid = []

            for item in items:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title", "")).strip()
                content = str(item.get("content", "")).strip()
                if not title or not content:
                    continue

                item_type = str(item.get("type", "insight")).strip()
                if item_type not in valid_types:
                    item_type = "insight"

                try:
                    confidence = float(item.get("confidence", 0.8))
                    confidence = max(0.0, min(1.0, confidence))
                except (TypeError, ValueError):
                    confidence = 0.8

                valid.append({
                    "type": item_type,
                    "title": title,
                    "content": content,
                    "source_quote": str(item.get("source_quote", "")).strip(),
                    "confidence": confidence,
                })

            return valid

        except (ValueError, KeyError) as e:
            logger.error(f"Erreur extraction : {e}")
            return []

    # ------------------------------------------------------------------
    # Étape 3 : RÉSUMÉ
    # ------------------------------------------------------------------
    async def summarize_conversation(self, conv_text: str) -> str:
        """Produit un résumé de la conversation en 3-5 lignes."""
        prompt = SUMMARIZE_PROMPT.format(conversation=self._truncate(conv_text))
        try:
            result = await self._call_llm_json(prompt)
            return str(result.get("summary", "")).strip()
        except (ValueError, KeyError) as e:
            logger.error(f"Erreur résumé : {e}")
            return ""

    # ------------------------------------------------------------------
    # Étape 4 : CLASSIFICATION
    # ------------------------------------------------------------------
    async def classify_item(self, title: str, content: str, item_type: str) -> dict:
        """
        Classifie un item de connaissance (thèmes + tags).

        Returns:
            dict avec themes (list), tags (list), new_theme_suggestion (str|None).
        """
        existing = await self.db.get_all_themes()
        themes_str = ", ".join(existing) if existing else "Aucun thème existant"

        prompt = CLASSIFY_PROMPT.format(
            existing_themes=themes_str,
            title=title,
            content=content[:500],   # Tronquer pour la classification
            item_type=item_type
        )

        try:
            result = await self._call_llm_json(prompt)
            themes = [str(t).strip() for t in result.get("themes", []) if t]
            tags = [str(t).strip() for t in result.get("tags", []) if t]
            new_theme = result.get("new_theme_suggestion")
            if new_theme and str(new_theme).lower() in ("null", "none", ""):
                new_theme = None
            return {"themes": themes, "tags": tags, "new_theme_suggestion": new_theme}
        except (ValueError, KeyError) as e:
            logger.error(f"Erreur classification : {e}")
            return {"themes": [], "tags": [], "new_theme_suggestion": None}

    # ------------------------------------------------------------------
    # PIPELINE COMPLET pour une conversation
    # ------------------------------------------------------------------
    async def process_conversation(self, conv_id: int, conv_text: str, conv_title: str) -> dict:
        """
        Traite une conversation complète : filtre → extrait → résume → classifie.

        Returns:
            dict résumé du traitement.
        """
        result = {
            "conversation_id": conv_id,
            "title": conv_title,
            "score": 0,
            "filtered_out": False,
            "items_count": 0,
            "summary": "",
            "error": None,
        }

        try:
            # --- Étape 1 : Filtrage ---
            score, reason = await self.filter_conversation(conv_text)
            result["score"] = score
            await self.db.update_conversation_score(conv_id, score)

            if score < 3:
                result["filtered_out"] = True
                await self.db.update_conversation_status(conv_id, "filtered")
                logger.info(f"  Filtrée (score={score}) : {conv_title[:60]}")
                return result

            logger.info(f"  Score={score} — extraction : {conv_title[:60]}")

            # --- Étape 2 : Extraction ---
            items = await self.extract_knowledge(conv_text)
            result["items_count"] = len(items)

            # --- Étape 3 : Résumé ---
            summary = await self.summarize_conversation(conv_text)
            result["summary"] = summary

            # --- Sauvegarde + classification de chaque item ---
            for item in items:
                item_id = await self.db.insert_knowledge_item(
                    conversation_id=conv_id,
                    item_type=item["type"],
                    title=item["title"],
                    content=item["content"],
                    summary=summary,
                    source_quote=item["source_quote"],
                    confidence=item["confidence"],
                )

                # --- Étape 4 : Classification ---
                classification = await self.classify_item(
                    title=item["title"],
                    content=item["content"],
                    item_type=item["type"],
                )

                for theme_name in classification["themes"]:
                    if theme_name:
                        theme_id = await self.db.get_or_create_theme(theme_name)
                        await self.db.link_item_theme(item_id, theme_id)

                for tag_name in classification["tags"]:
                    if tag_name:
                        tag_id = await self.db.get_or_create_tag(tag_name)
                        await self.db.link_item_tag(item_id, tag_id)

                suggestion = classification.get("new_theme_suggestion")
                if suggestion:
                    await self.db.get_or_create_theme(suggestion)

            await self.db.update_conversation_status(conv_id, "processed")
            await self.db.update_theme_counts()
            logger.info(f"  OK : {len(items)} item(s) — {conv_title[:60]}")

        except Exception as e:
            result["error"] = str(e)
            await self.db.update_conversation_status(conv_id, "error")
            logger.error(f"  ERREUR sur '{conv_title[:60]}' : {e}", exc_info=True)

        return result

    # ------------------------------------------------------------------
    # TRAITEMENT PAR LOT
    # ------------------------------------------------------------------
    async def process_all_new(self, limit: Optional[int] = None) -> dict:
        """
        Traite toutes les conversations en statut 'new'.

        Args:
            limit: Nombre max à traiter (None = toutes).

        Returns:
            dict résumé : total, processed, filtered, items_extracted, errors.
        """
        await self._ensure_model_loaded()

        conversations = await self.db.get_conversations_by_status("new")
        if limit:
            conversations = conversations[:limit]

        total = len(conversations)
        logger.info(f"Début du traitement : {total} conversation(s)")

        stats = {
            "total": total,
            "processed": 0,
            "filtered": 0,
            "items_extracted": 0,
            "errors": 0,
        }

        for i, conv in enumerate(conversations):
            logger.info(f"[{i+1}/{total}] {conv['title'][:70]}")
            r = await self.process_conversation(
                conv_id=conv["id"],
                conv_text=conv["full_text"] or "",
                conv_title=conv["title"] or "Sans titre",
            )

            if r["error"]:
                stats["errors"] += 1
            elif r["filtered_out"]:
                stats["filtered"] += 1
            else:
                stats["processed"] += 1
                stats["items_extracted"] += r["items_count"]

        logger.info(f"Traitement terminé : {stats}")
        return stats
