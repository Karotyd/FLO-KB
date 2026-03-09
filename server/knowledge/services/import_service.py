"""
Service d'import — orchestrateur principal de l'ingestion FLO-KB.
Enchaîne : extraction ZIP → parsing → déduplication → insertion en base.
"""

import hashlib
import logging
import os
from pathlib import Path

from ..db import KnowledgeDB
from ..parsers import detect_and_parse
from ..parsers.zip_handler import extract_zip
from ..processing.deduplicator import Deduplicator

logger = logging.getLogger(__name__)


def _file_hash(filepath: str) -> str:
    """Calcule le SHA-256 d'un fichier brut (pour détecter les réimports)."""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


class ImportService:
    """Orchestre l'import complet d'un fichier d'export."""

    def __init__(self, db: KnowledgeDB):
        self.db = db
        self.deduplicator = Deduplicator(db)

    async def import_file(self, filepath: str) -> dict:
        """
        Importe un fichier (ZIP, JSON ou Markdown).

        Flux :
          1. Si .zip → extrait les fichiers utiles
          2. Calcule le hash du fichier source (dédup au niveau fichier)
          3. Pour chaque fichier : parse + dédup conversation par conversation + insert
          4. Retourne un résumé des opérations

        Args:
            filepath: Chemin absolu ou relatif vers le fichier à importer.

        Returns:
            dict avec les compteurs : source_files, total_conversations,
            new, updated, duplicates, errors.
        """
        result = {
            "filename": os.path.basename(filepath),
            "source_files": 0,
            "total_conversations": 0,
            "new": 0,
            "updated": 0,
            "duplicates": 0,
            "errors": 0,
        }

        # Étape 1 : résoudre la liste de fichiers à traiter
        if filepath.endswith('.zip'):
            try:
                source_files = extract_zip(filepath)
                logger.info(f"{len(source_files)} fichier(s) extrait(s) du ZIP")
            except Exception as e:
                logger.error(f"Échec de l'extraction ZIP {filepath} : {e}")
                result["errors"] += 1
                return result
        else:
            source_files = [filepath]

        result["source_files"] = len(source_files)

        # Étape 2 : traiter chaque fichier
        for src_file in source_files:
            await self._process_file(src_file, result)

        logger.info(
            f"Import terminé : {result['new']} nouvelles, "
            f"{result['updated']} màj, {result['duplicates']} doublons, "
            f"{result['errors']} erreur(s)"
        )
        return result

    async def _process_file(self, filepath: str, result: dict):
        """Traite un fichier individuel (JSON ou Markdown)."""
        filename = os.path.basename(filepath)

        # Calcul du hash du fichier source
        try:
            fhash = _file_hash(filepath)
        except Exception as e:
            logger.error(f"Impossible de lire {filepath} : {e}")
            result["errors"] += 1
            return

        # Vérifier si ce fichier a déjà été importé avec succès
        if await self.db.file_already_imported(fhash):
            logger.info(f"Fichier déjà importé (hash={fhash[:12]}...) : {filename} — skip")
            # Les conversations de ce fichier sont toutes des doublons
            # On les parse quand même pour mettre à jour le compteur affiché
            try:
                conversations = detect_and_parse(filepath)
                result["total_conversations"] += len(conversations)
                result["duplicates"] += len(conversations)
            except ValueError:
                pass  # Fichier non reconnu (métadonnées) — ignoré
            except Exception as e:
                logger.warning(f"Erreur parsing pour le comptage doublons {filename} : {e}")
            return

        # Parser le fichier
        try:
            conversations = detect_and_parse(filepath)
        except ValueError:
            # Fichier non reconnu (métadonnées d'export : user.json, etc.)
            logger.debug(f"Format non reconnu, ignoré : {filename}")
            return
        except Exception as e:
            logger.error(f"Erreur de parsing {filename} : {e}")
            result["errors"] += 1
            return

        if not conversations:
            logger.debug(f"Aucune conversation dans {filename}")
            return

        result["total_conversations"] += len(conversations)

        # Détecter le source_type depuis la première conversation
        source_type = conversations[0].source_type if conversations else 'unknown'

        # Créer l'entrée import en base
        import_id = await self.db.create_import(
            filename=filename,
            source_type=source_type,
            file_hash=fhash
        )

        # Traiter chaque conversation
        new_count = 0
        updated_count = 0
        dup_count = 0

        for conv in conversations:
            try:
                status = await self.deduplicator.check(conv)

                if status == 'duplicate':
                    dup_count += 1
                    result["duplicates"] += 1
                    continue

                # Insérer la conversation (new ou updated)
                await self.db.insert_conversation(
                    import_id=import_id,
                    external_id=conv.external_id,
                    title=conv.title,
                    source_type=conv.source_type,
                    created_at=conv.created_at,
                    content_hash=conv.content_hash,
                    full_text=conv.full_text,
                    status=status
                )

                if status == 'new':
                    new_count += 1
                    result["new"] += 1
                else:
                    updated_count += 1
                    result["updated"] += 1

            except Exception as e:
                logger.error(f"Erreur traitement conversation '{conv.title}' : {e}")
                result["errors"] += 1

        # Finaliser l'import
        inserted = new_count + updated_count
        await self.db.update_import_status(
            import_id=import_id,
            status='done',
            conversation_count=inserted
        )

        logger.info(
            f"{filename} : {new_count} nouvelles, {updated_count} màj, "
            f"{dup_count} doublons"
        )
