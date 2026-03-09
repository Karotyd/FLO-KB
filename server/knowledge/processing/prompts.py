"""
Prompts système pour le traitement des connaissances — FLO-KB.
Chaque prompt retourne du JSON parsable.
IMPORTANT : itérer sur ces prompts pour améliorer les résultats.
"""

# ============================================================================
# PROMPT 1 : FILTRAGE — Évalue la valeur d'une conversation
# ============================================================================
FILTER_PROMPT = """Tu es un analyste de contenu. Tu évalues la VALEUR INFORMATIONNELLE
d'une conversation entre un utilisateur et un assistant IA.

RÈGLES :
- Score de 1 à 5 (1 = aucune valeur, 5 = très haute valeur)
- Score 1-2 : bavardage, debug technique pas à pas, formules de politesse,
  tests, messages d'erreur répétitifs, mise en place de projet sans contenu
- Score 3 : information utile mais basique ou facilement trouvable
- Score 4-5 : connaissances substantielles, insights, recommandations
  concrètes, analyses, explications de concepts

CONVERSATION À ÉVALUER :
{conversation}

Réponds UNIQUEMENT avec ce JSON (rien d'autre) :
{{"score": <1-5>, "reason": "<explication courte>"}}"""


# ============================================================================
# PROMPT 2 : EXTRACTION — Extrait les points clés
# ============================================================================
EXTRACT_PROMPT = """Tu es un extracteur de connaissances. Tu analyses une conversation
et tu en extrais UNIQUEMENT les informations qui ont une valeur durable.

EXTRAIRE :
- Faits vérifiables et informations concrètes
- Concepts expliqués et définitions
- Recommandations et conseils actionnables
- Analyses et raisonnements intéressants
- Références (livres, articles, outils, personnes mentionnées)
- Décisions prises et leurs justifications

NE PAS EXTRAIRE :
- Formules de politesse et bavardage
- Étapes de debug/dépannage technique
- Reformulations et répétitions
- Questions de clarification
- Messages d'erreur et stack traces
- Mise en place de projet (installation, configuration basique)

CONVERSATION :
{conversation}

Réponds UNIQUEMENT avec ce JSON (rien d'autre) :
{{
  "items": [
    {{
      "type": "fact|concept|recommendation|insight|reference|decision",
      "title": "<titre court et descriptif>",
      "content": "<contenu extrait, reformulé clairement>",
      "source_quote": "<citation courte originale pour vérification>",
      "confidence": <0.0 à 1.0>
    }}
  ]
}}

Si rien de valuable, retourne : {{"items": []}}"""


# ============================================================================
# PROMPT 3 : RÉSUMÉ — Produit un résumé concis
# ============================================================================
SUMMARIZE_PROMPT = """Tu es un rédacteur concis. Résume cette conversation en extrayant
l'ESSENTIEL en 3 à 5 lignes maximum.

Le résumé doit permettre à quelqu'un de comprendre en 10 secondes :
- De quoi parlait la conversation
- Quelles conclusions ou informations clés en ressortent
- Ce qui est actionnable ou mémorable

CONVERSATION :
{conversation}

Réponds UNIQUEMENT avec ce JSON :
{{"summary": "<résumé en 3-5 lignes>"}}"""


# ============================================================================
# PROMPT 4 : CLASSIFICATION — Attribue thèmes et tags
# ============================================================================
CLASSIFY_PROMPT = """Tu es un bibliothécaire expert en classification.
Tu attribues des thèmes et des tags aux items de connaissance.

THÈMES EXISTANTS (utilise-les en priorité) :
{existing_themes}

Si aucun thème existant ne convient, tu peux en suggérer un nouveau.

ITEM À CLASSIFIER :
Titre : {title}
Contenu : {content}
Type : {item_type}

Réponds UNIQUEMENT avec ce JSON :
{{
  "themes": ["<thème principal>", "<thème secondaire optionnel>"],
  "tags": ["<tag1>", "<tag2>", "<tag3>"],
  "new_theme_suggestion": "<nom du nouveau thème ou null>"
}}"""
