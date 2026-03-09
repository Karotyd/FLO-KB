"""
Parsing JSON robuste pour les réponses LLM — FLO-KB.
Les modèles 7B locaux retournent souvent du JSON imparfait.
Ce module nettoie et parse de manière défensive.
"""

import json
import re
import logging

logger = logging.getLogger(__name__)


def fix_literal_newlines(text: str) -> str:
    """
    Remplace les retours à la ligne littéraux dans les strings JSON par \\n.

    Mistral 7B génère parfois des newlines réels à l'intérieur des valeurs JSON
    ce qui rend le JSON invalide (cause : "Expecting ',' delimiter").
    """
    result = []
    in_string = False
    i = 0
    while i < len(text):
        c = text[i]
        if c == '\\' and in_string and i + 1 < len(text):
            # Séquence d'échappement — on passe les deux caractères tels quels
            result.append(c)
            i += 1
            result.append(text[i])
        elif c == '"':
            in_string = not in_string
            result.append(c)
        elif in_string and c == '\n':
            result.append('\\n')
        elif in_string and c == '\r':
            result.append('\\r')
        elif in_string and c == '\t':
            result.append('\\t')
        else:
            result.append(c)
        i += 1
    return ''.join(result)


def clean_llm_json(raw: str) -> str:
    """
    Nettoie une réponse LLM pour en extraire du JSON valide.

    Gère :
    - Blocs markdown (```json ... ```)
    - Texte parasite avant/après le JSON
    - Trailing commas dans les objets/tableaux
    - Commentaires inline (//)
    """
    text = raw.strip()

    # Retirer les blocs markdown ```json ... ``` ou ``` ... ```
    md_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if md_match:
        text = md_match.group(1).strip()

    # Trouver le premier { ou [ et le dernier } ou ]
    start_obj = text.find('{')
    start_arr = text.find('[')

    if start_obj == -1 and start_arr == -1:
        raise ValueError("Aucun JSON trouvé dans la réponse LLM")

    if start_arr == -1 or (start_obj != -1 and start_obj < start_arr):
        # Objet JSON
        start = start_obj
        end = text.rfind('}')
        if end == -1:
            raise ValueError("Accolade fermante manquante dans la réponse LLM")
        text = text[start:end + 1]
    else:
        # Tableau JSON
        start = start_arr
        end = text.rfind(']')
        if end == -1:
            raise ValueError("Crochet fermant manquant dans la réponse LLM")
        text = text[start:end + 1]

    # Retirer les trailing commas (ex: {"a": 1,} → {"a": 1})
    text = re.sub(r',\s*([}\]])', r'\1', text)

    # Retirer les commentaires inline (// ...)
    text = re.sub(r'//[^\n]*', '', text)

    # Corriger les newlines littéraux dans les strings JSON
    text = fix_literal_newlines(text)

    return text


def _escape_quote_at(text: str, pos: int) -> str:
    """
    Cherche et échappe le guillemet non-structurel le plus proche avant pos.

    Le parseur JSON a fermé une string trop tôt et est en erreur à pos.
    Le guillemet fautif est quelque part avant pos.
    On le remplace par \".
    """
    i = pos - 1
    while i >= 0:
        if text[i] == '"':
            # Compter les backslashes précédents (guillemet déjà échappé ?)
            backslashes = 0
            j = i - 1
            while j >= 0 and text[j] == '\\':
                backslashes += 1
                j -= 1
            if backslashes % 2 == 0:  # Non échappé → c'est notre cible
                return text[:i] + '\\"' + text[i + 1:]
        i -= 1
    return text  # Aucun guillemet trouvé


def parse_llm_json(raw: str) -> dict | list:
    """
    Parse une réponse LLM en JSON avec réparation progressive.

    Stratégie :
    1. Nettoyage (markdown, trailing commas, fix_literal_newlines)
    2. Tentative de parse JSON
    3. Si "Expecting ',' delimiter" → cherche et échappe le guillemet fautif, retry
    4. Jusqu'à 5 tentatives de réparation

    Args:
        raw: Réponse brute du LLM.

    Returns:
        dict ou list parsé.

    Raises:
        ValueError si le JSON est irrécupérable.
    """
    if not raw or not raw.strip():
        raise ValueError("Réponse LLM vide")

    cleaned = clean_llm_json(raw)

    # Tentatives de réparation progressive des guillemets non échappés
    for repair_attempt in range(6):
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            err_str = str(e)
            if repair_attempt == 0:
                logger.warning(f"JSON invalide après nettoyage : {e}")
                logger.debug(f"Brut (500 chars) : {raw[:500]}")
            # Guillemet non échappé dans une string → réparation ciblée
            if "Expecting ',' delimiter" in err_str or "Expecting ':' delimiter" in err_str:
                fixed = _escape_quote_at(cleaned, e.pos)
                if fixed == cleaned:
                    break  # Aucun progrès possible
                cleaned = fixed
                logger.debug(f"Réparation guillemet à pos {e.pos} (tentative {repair_attempt + 1})")
            else:
                break  # Autre type d'erreur, on ne peut pas réparer

    # Dernière tentative après toutes les réparations
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.debug(f"Contenu nettoyé final : {cleaned[:500]}")
        raise ValueError(f"JSON irrécupérable : {e}")
