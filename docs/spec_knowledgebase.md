# KnowledgeBase — Spécification complète du projet

## 📋 Résumé du projet

**Nom** : KnowledgeBase (module intégré à FLO)
**Objectif** : Extraire, filtrer, résumer et organiser les connaissances issues de conversations IA (ChatGPT, Claude, Gemini, Copilot, Mistral) et les exporter vers un vault Obsidian structuré et navigable.

**Matériel** : RTX 3090 (24 Go VRAM)
**Backend** : FLO v0.3 (FastAPI + llama-cpp-python)
**Sortie** : Vault Obsidian (Markdown + tags + graph view)
**Utilisateur** : Accès potentiellement distant

---

## 🏗️ Stratégie d'intégration avec FLO

### Pourquoi étendre FLO plutôt que créer un projet séparé ?

FLO possède déjà tout le socle technique nécessaire : le `ModelManager` (chargement/déchargement de modèles GGUF), la `factory` d'engines, le streaming SSE, le routage, et la gestion de sessions. Créer un projet séparé obligerait à dupliquer tout cela ou à maintenir deux services — plus complexe pour un débutant.

### Principe : ajouter sans casser

On va ajouter un **nouveau module `knowledge`** à côté du module `chat` existant. FLO reste fonctionnel tel quel. Les deux modules partagent le `ModelManager` et le `GGUFLLM`, mais ont chacun leurs propres endpoints, services et logique.

### Ce qu'on ne touche PAS dans FLO

- `server/api/chat.py` → reste intact
- `server/engine/` → aucune modification (on réutilise tel quel)
- `server/router/model_router.py` → reste intact
- `server/services/chat_service.py` → reste intact
- `server/services/session_service.py` → reste intact
- `main.py` → on ajoute juste 1 ligne pour enregistrer le nouveau router

### Ce qu'on AJOUTE à FLO

```
FLO/
├── server/
│   ├── api/
│   │   ├── chat.py                  ← EXISTANT (inchangé)
│   │   └── knowledge.py             ← NOUVEAU (endpoints KB)
│   ├── engine/                      ← EXISTANT (inchangé, réutilisé)
│   ├── knowledge/                   ← NOUVEAU MODULE
│   │   ├── __init__.py
│   │   ├── parsers/                 ← Parseurs par source IA
│   │   │   ├── __init__.py
│   │   │   ├── base_parser.py       ← Classe abstraite
│   │   │   ├── chatgpt_parser.py    ← JSON ChatGPT
│   │   │   ├── claude_parser.py     ← JSON Claude
│   │   │   ├── gemini_parser.py     ← JSON Gemini (Google Takeout)
│   │   │   └── markdown_parser.py   ← Fallback Markdown générique
│   │   ├── processing/              ← Pipeline de traitement IA
│   │   │   ├── __init__.py
│   │   │   ├── prompts.py           ← Tous les prompts système
│   │   │   ├── extractor.py         ← Extraction des connaissances
│   │   │   ├── classifier.py        ← Classification thématique
│   │   │   └── deduplicator.py      ← Détection de doublons
│   │   ├── exporters/               ← Export vers Obsidian
│   │   │   ├── __init__.py
│   │   │   └── obsidian_exporter.py ← Génération du vault Markdown
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── import_service.py    ← Orchestration de l'import
│   │       ├── knowledge_service.py ← CRUD sur la base de connaissances
│   │       └── export_service.py    ← Orchestration de l'export
│   ├── models/                      ← EXISTANT
│   ├── router/                      ← EXISTANT
│   ├── services/                    ← EXISTANT (inchangé)
│   ├── storage/                     ← EXISTANT
│   └── ui/
│       ├── index.html               ← EXISTANT (inchangé)
│       └── knowledge.html           ← NOUVEAU (UI d'import/suivi)
├── data/
│   ├── sessions/                    ← EXISTANT
│   ├── knowledge/                   ← NOUVEAU
│   │   ├── kb.sqlite                ← Base SQLite des connaissances
│   │   └── imports/                 ← Fichiers importés (originaux)
│   └── obsidian_vault/              ← NOUVEAU (vault généré)
├── models/                          ← EXISTANT (fichiers GGUF)
├── models.json                      ← EXISTANT (à compléter)
└── main.py                          ← 1 ligne ajoutée
```

### Modification de main.py (unique changement dans l'existant)

```python
# Ligne à ajouter dans main.py, après la ligne existante :
# app.include_router(chat_router)

from server.api.knowledge import router as knowledge_router
app.include_router(knowledge_router, prefix="/kb")
```

C'est la SEULE modification du code existant de FLO.

---

## 🔧 Architecture détaillée

### Vue d'ensemble du flux de données

```
[Fichier export]     [Fichier export]     [Fichier Markdown]
  ChatGPT JSON         Claude JSON           Copilot .md
       │                    │                      │
       ▼                    ▼                      ▼
┌──────────────────────────────────────────────────────┐
│                    PARSEURS                           │
│  Chaque parseur normalise vers un format interne     │
│  commun : liste de ConversationEntry                 │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│                 DÉDUPLICATION                         │
│  Hash SHA-256 (doublons exacts)                      │
│  + comparaison texte (doublons proches)              │
│  → Marque : NEW / UPDATED / DUPLICATE                │
└──────────────────────┬───────────────────────────────┘
                       │ (seulement NEW et UPDATED)
                       ▼
┌──────────────────────────────────────────────────────┐
│              TRAITEMENT IA (via FLO/GGUFLLM)         │
│                                                      │
│  Étape 1 : FILTRAGE                                  │
│  → Le LLM note chaque échange sur sa valeur (1-5)   │
│  → On écarte tout ce qui est < 3                     │
│                                                      │
│  Étape 2 : EXTRACTION                                │
│  → Le LLM extrait les points clés, faits,            │
│    recommandations, décisions                        │
│                                                      │
│  Étape 3 : RÉSUMÉ                                    │
│  → Le LLM produit un résumé concis (3-5 lignes)     │
│                                                      │
│  Étape 4 : CLASSIFICATION                            │
│  → Le LLM attribue des thèmes et des tags           │
│    parmi une taxonomie existante + peut en créer     │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│              BASE SQLite (kb.sqlite)                  │
│  Tables : imports, conversations, knowledge_items,   │
│           themes, tags, content_hashes               │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│           EXPORT OBSIDIAN                             │
│  Génère un vault Markdown structuré :                │
│  - 1 fichier par item de connaissance                │
│  - Frontmatter YAML (tags, source, date)             │
│  - Liens [[wikilinks]] entre thèmes                  │
│  - Index par thème                                   │
│  - MOC (Map of Content) principal                    │
└──────────────────────────────────────────────────────┘
                       │
                       ▼
              📂 Vault Obsidian
         (ouvrir avec l'app Obsidian)
```

---

## 📊 Schéma de base de données (SQLite)

```sql
-- Table des imports (traçabilité)
CREATE TABLE imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    source_type TEXT NOT NULL,        -- 'chatgpt', 'claude', 'gemini', 'markdown'
    file_hash TEXT NOT NULL,          -- SHA-256 du fichier importé
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    conversation_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending'     -- 'pending', 'processing', 'done', 'error'
);

-- Table des conversations normalisées
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id INTEGER REFERENCES imports(id),
    external_id TEXT,                 -- ID original dans la source
    title TEXT,
    source_type TEXT NOT NULL,
    created_at TIMESTAMP,
    content_hash TEXT NOT NULL,       -- Pour déduplication
    status TEXT DEFAULT 'new',        -- 'new', 'updated', 'duplicate', 'processed'
    value_score REAL DEFAULT 0        -- Score de valeur (1-5) attribué par le LLM
);

-- Table des items de connaissance (résultat du traitement)
CREATE TABLE knowledge_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER REFERENCES conversations(id),
    item_type TEXT NOT NULL,          -- 'fact', 'recommendation', 'concept',
                                     -- 'decision', 'insight', 'reference'
    title TEXT NOT NULL,
    content TEXT NOT NULL,            -- Le contenu extrait
    summary TEXT,                     -- Résumé court
    source_quote TEXT,                -- Citation originale (pour vérification)
    confidence REAL DEFAULT 0.8,      -- Confiance du LLM dans l'extraction
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des thèmes (taxonomie)
CREATE TABLE themes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,        -- Ex: 'Psychologie', 'LLM & IA', 'Cinéma'
    parent_id INTEGER REFERENCES themes(id),  -- Hiérarchie
    description TEXT,
    color TEXT,                       -- Pour l'affichage
    item_count INTEGER DEFAULT 0
);

-- Table de liaison items <-> thèmes (many-to-many)
CREATE TABLE item_themes (
    item_id INTEGER REFERENCES knowledge_items(id),
    theme_id INTEGER REFERENCES themes(id),
    PRIMARY KEY (item_id, theme_id)
);

-- Table des tags (étiquettes libres)
CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- Table de liaison items <-> tags (many-to-many)
CREATE TABLE item_tags (
    item_id INTEGER REFERENCES knowledge_items(id),
    tag_id INTEGER REFERENCES tags(id),
    PRIMARY KEY (item_id, tag_id)
);
```

---

## 🤖 Modèles GGUF recommandés

### Configuration dans models.json

Ajouter ces modèles à votre `models.json` existant :

```json
{
  "models": [
    // ... vos modèles existants (mistral-7b, etc.) ...
    {
      "id": "kb-extractor",
      "name": "Qwen2.5-14B Instruct (Q5_K_M)",
      "path": "models/Qwen2.5-14B/qwen2.5-14b-instruct-q5_k_m.gguf",
      "specialties": ["extraction", "summarization", "classification"],
      "context_length": 8192,
      "params": {
        "n_ctx": 8192,
        "n_gpu_layers": 49,
        "n_threads": 8,
        "temperature": 0.1,
        "top_p": 0.3,
        "repeat_penalty": 1.1,
        "max_tokens": 2000
      },
      "keywords": [],
      "vram_estimate_gb": 12
    },
    {
      "id": "kb-light",
      "name": "Mistral 7B Instruct (Q4_K_M)",
      "path": "models/Mistral-7B/mistral-7b-instruct-v0.2.Q4_K_M.gguf",
      "specialties": ["classification", "tagging"],
      "context_length": 4096,
      "params": {
        "n_ctx": 4096,
        "n_gpu_layers": 35,
        "n_threads": 8,
        "temperature": 0.1,
        "top_p": 0.3,
        "repeat_penalty": 1.1,
        "max_tokens": 1000
      },
      "keywords": [],
      "vram_estimate_gb": 5
    }
  ]
}
```

### Pourquoi deux modèles ?

- **Qwen2.5-14B** (12 Go VRAM) : pour l'extraction et le résumé, qui demandent de la compréhension fine. Son contexte de 8K tokens permet de traiter des conversations longues.
- **Mistral 7B** (5 Go VRAM) : pour la classification et le tagging, plus rapide et suffisant pour ces tâches. C'est aussi le modèle de secours si la VRAM est insuffisante.

### Détection automatique de VRAM

```python
# server/knowledge/processing/gpu_check.py

import subprocess
import logging

logger = logging.getLogger(__name__)

def get_available_vram_gb() -> float:
    """Détecte la VRAM disponible via nvidia-smi"""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10
        )
        free_mb = float(result.stdout.strip().split('\n')[0])
        free_gb = free_mb / 1024
        logger.info(f"VRAM disponible : {free_gb:.1f} Go")
        return free_gb
    except Exception as e:
        logger.warning(f"Impossible de détecter la VRAM : {e}")
        return 0.0

def select_best_model(task: str) -> dict:
    """
    Sélectionne le meilleur modèle selon la VRAM disponible.
    
    Returns:
        dict avec 'model_id', 'warning' (optionnel)
    """
    vram = get_available_vram_gb()
    
    if task in ("extraction", "summarization"):
        if vram >= 14:
            return {"model_id": "kb-extractor"}
        elif vram >= 6:
            return {
                "model_id": "kb-light",
                "warning": f"VRAM disponible : {vram:.1f} Go. "
                           f"Utilisation du modèle léger (Mistral 7B). "
                           f"Les résultats peuvent être moins précis. "
                           f"Libérez de la VRAM pour utiliser Qwen2.5-14B."
            }
        else:
            return {
                "model_id": "kb-light",
                "warning": f"VRAM très limitée ({vram:.1f} Go). "
                           f"Le traitement sera lent (CPU). "
                           f"Fermez les applications GPU pour de meilleures performances."
            }
    
    # Pour classification/tagging, Mistral 7B suffit
    return {"model_id": "kb-light"}
```

---

## 📝 Prompts système (le cœur du traitement)

### Fichier `server/knowledge/processing/prompts.py`

```python
"""
Prompts système pour le traitement des connaissances.
Chaque prompt est conçu pour retourner du JSON parsable.
IMPORTANT : itérer sur ces prompts au fil du temps pour améliorer les résultats.
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
```

---

## 📥 Parseurs : format de chaque source

### Format interne commun (cible de tous les parseurs)

```python
# server/knowledge/parsers/base_parser.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from abc import ABC, abstractmethod

@dataclass
class ParsedMessage:
    """Un message individuel dans une conversation"""
    role: str                        # 'user' ou 'assistant'
    content: str
    timestamp: Optional[datetime] = None

@dataclass 
class ParsedConversation:
    """Une conversation normalisée (format interne commun)"""
    external_id: str                 # ID original dans la source
    title: str
    source_type: str                 # 'chatgpt', 'claude', 'gemini', 'markdown'
    messages: list[ParsedMessage] = field(default_factory=list)
    created_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)
    
    @property
    def full_text(self) -> str:
        """Texte complet de la conversation (pour le LLM)"""
        lines = []
        for msg in self.messages:
            role = "Utilisateur" if msg.role == "user" else "Assistant"
            lines.append(f"{role}: {msg.content}")
        return "\n\n".join(lines)
    
    @property
    def content_hash(self) -> str:
        """Hash SHA-256 du contenu pour déduplication"""
        import hashlib
        return hashlib.sha256(self.full_text.encode()).hexdigest()

class BaseParser(ABC):
    """Classe abstraite pour tous les parseurs"""
    
    @abstractmethod
    def can_parse(self, filepath: str) -> bool:
        """Vérifie si ce parseur peut traiter ce fichier"""
        pass
    
    @abstractmethod
    def parse(self, filepath: str) -> list[ParsedConversation]:
        """Parse le fichier et retourne les conversations normalisées"""
        pass
```

### Parseur ChatGPT (JSON)

ChatGPT exporte via Settings → Data Controls → Export Data.
Le fichier `conversations.json` a cette structure :

```python
# server/knowledge/parsers/chatgpt_parser.py

import json
from datetime import datetime
from .base_parser import BaseParser, ParsedConversation, ParsedMessage

class ChatGPTParser(BaseParser):
    
    def can_parse(self, filepath: str) -> bool:
        if not filepath.endswith('.json'):
            return False
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # ChatGPT : liste de conversations avec 'mapping'
            if isinstance(data, list) and len(data) > 0:
                return 'mapping' in data[0]
            return False
        except:
            return False
    
    def parse(self, filepath: str) -> list[ParsedConversation]:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        conversations = []
        for conv in data:
            messages = []
            
            # ChatGPT utilise un arbre de messages dans 'mapping'
            for node_id, node in conv.get('mapping', {}).items():
                msg = node.get('message')
                if msg is None:
                    continue
                
                role = msg.get('author', {}).get('role', '')
                if role not in ('user', 'assistant'):
                    continue
                
                # Le contenu peut être dans différents formats
                content_parts = msg.get('content', {}).get('parts', [])
                content = ' '.join(
                    str(p) for p in content_parts if isinstance(p, str)
                )
                
                if not content.strip():
                    continue
                
                timestamp = None
                if msg.get('create_time'):
                    timestamp = datetime.fromtimestamp(msg['create_time'])
                
                messages.append(ParsedMessage(
                    role=role,
                    content=content.strip(),
                    timestamp=timestamp
                ))
            
            if messages:
                conversations.append(ParsedConversation(
                    external_id=conv.get('id', ''),
                    title=conv.get('title', 'Sans titre'),
                    source_type='chatgpt',
                    messages=messages,
                    created_at=datetime.fromtimestamp(conv['create_time'])
                        if conv.get('create_time') else None
                ))
        
        return conversations
```

### Parseur Claude (JSON)

```python
# server/knowledge/parsers/claude_parser.py
# Claude exporte aussi en JSON (structure différente de ChatGPT)

import json
from datetime import datetime
from .base_parser import BaseParser, ParsedConversation, ParsedMessage

class ClaudeParser(BaseParser):
    
    def can_parse(self, filepath: str) -> bool:
        if not filepath.endswith('.json'):
            return False
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Claude : liste avec 'chat_messages' ou 'uuid'
            if isinstance(data, list) and len(data) > 0:
                return 'chat_messages' in data[0] or 'uuid' in data[0]
            return False
        except:
            return False
    
    def parse(self, filepath: str) -> list[ParsedConversation]:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        conversations = []
        for conv in data:
            messages = []
            
            for msg in conv.get('chat_messages', []):
                role = msg.get('sender', '')
                if role == 'human':
                    role = 'user'
                elif role == 'assistant':
                    role = 'assistant'
                else:
                    continue
                
                # Claude stocke le contenu dans 'text' ou 'content'
                content = ''
                if isinstance(msg.get('text'), str):
                    content = msg['text']
                elif isinstance(msg.get('content'), list):
                    content = ' '.join(
                        p.get('text', '') for p in msg['content']
                        if isinstance(p, dict) and p.get('type') == 'text'
                    )
                elif isinstance(msg.get('content'), str):
                    content = msg['content']
                
                if not content.strip():
                    continue
                
                messages.append(ParsedMessage(
                    role=role,
                    content=content.strip(),
                    timestamp=datetime.fromisoformat(msg['created_at'])
                        if msg.get('created_at') else None
                ))
            
            if messages:
                conversations.append(ParsedConversation(
                    external_id=conv.get('uuid', conv.get('id', '')),
                    title=conv.get('name', conv.get('title', 'Sans titre')),
                    source_type='claude',
                    messages=messages,
                    created_at=datetime.fromisoformat(conv['created_at'])
                        if conv.get('created_at') else None
                ))
        
        return conversations
```

### Parseur Markdown (fallback universel)

```python
# server/knowledge/parsers/markdown_parser.py
# Pour Copilot, Mistral, ou tout export en Markdown

import re
from pathlib import Path
from .base_parser import BaseParser, ParsedConversation, ParsedMessage

class MarkdownParser(BaseParser):
    """Parse les exports Markdown (Copilot, Mistral, ou copier-coller)"""
    
    def can_parse(self, filepath: str) -> bool:
        return filepath.endswith(('.md', '.txt'))
    
    def parse(self, filepath: str) -> list[ParsedConversation]:
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
        
        messages = []
        
        # Patterns courants pour détecter les rôles
        # "## User", "### Human:", "You:", "User:", "**User**:", etc.
        pattern = re.compile(
            r'(?:^|\n)(?:#{1,3}\s*)?(?:\*\*)?'
            r'(User|Human|You|Utilisateur|Assistant|AI|Bot|Claude|ChatGPT|Gemini|Copilot)'
            r'(?:\*\*)?[\s:]*\n?(.*?)(?=\n(?:#{1,3}\s*)?(?:\*\*)?'
            r'(?:User|Human|You|Utilisateur|Assistant|AI|Bot|Claude|ChatGPT|Gemini|Copilot)|$)',
            re.IGNORECASE | re.DOTALL
        )
        
        for match in pattern.finditer(text):
            role_raw = match.group(1).lower()
            content = match.group(2).strip()
            
            if role_raw in ('user', 'human', 'you', 'utilisateur'):
                role = 'user'
            else:
                role = 'assistant'
            
            if content:
                messages.append(ParsedMessage(role=role, content=content))
        
        # Si aucun pattern détecté, traiter comme un bloc unique
        if not messages and text.strip():
            messages.append(ParsedMessage(role='assistant', content=text.strip()))
        
        filename = Path(filepath).stem
        
        return [ParsedConversation(
            external_id=filename,
            title=filename.replace('_', ' ').replace('-', ' ').title(),
            source_type='markdown',
            messages=messages
        )] if messages else []
```

---

## 📂 Structure du vault Obsidian généré

```
obsidian_vault/
├── 🗂️ _Index/
│   ├── MOC - Base de connaissances.md    ← Point d'entrée principal
│   ├── Index Psychologie.md
│   ├── Index Tech & IA.md
│   ├── Index Cinéma.md
│   └── Index Jeux Vidéo.md
├── 📁 Psychologie/
│   ├── Biais cognitif de confirmation.md
│   ├── Thérapie cognitivo-comportementale.md
│   └── ...
├── 📁 Tech & IA/
│   ├── Fonctionnement des transformers.md
│   ├── Comparaison LLM locaux vs cloud.md
│   └── ...
├── 📁 Cinéma/
│   └── ...
├── 📁 Jeux Vidéo/
│   └── ...
├── 📁 _Sources/
│   ├── ChatGPT - 2025-01-15 - Discussion psycho.md
│   └── ...     (résumés des conversations originales)
└── 📁 _Templates/
    ├── Template Knowledge Item.md
    └── Template Source.md
```

### Format d'un item de connaissance

```markdown
---
type: concept
source: chatgpt
source_conversation: "Discussion sur les biais cognitifs"
date_extraction: 2025-03-08
themes:
  - Psychologie
  - Biais cognitifs
tags:
  - cognition
  - prise-de-décision
  - biais
confidence: 0.9
---

# Biais de confirmation

Le biais de confirmation est la tendance à favoriser les informations
qui confirment nos croyances préexistantes, tout en ignorant ou
minimisant celles qui les contredisent.

## Points clés

- Affecte la recherche d'information ET son interprétation
- Particulièrement fort sur les sujets émotionnellement chargés
- Stratégie de mitigation : chercher activement les contre-arguments

## Voir aussi

- [[Biais d'ancrage]]
- [[Pensée critique]]
- [[Index Psychologie]]

---
*Extrait de : [[ChatGPT - 2025-01-15 - Discussion psycho]]*
```

### Format du MOC principal

```markdown
---
type: moc
updated: 2025-03-08
total_items: 147
---

# 🧠 Base de connaissances

> Dernière mise à jour : 2025-03-08 | 147 items | 4 thèmes

## Thèmes

### 🧠 Psychologie (43 items)
→ [[Index Psychologie]]

### 💻 Tech & IA (67 items)
→ [[Index Tech & IA]]

### 🎬 Cinéma (22 items)
→ [[Index Cinéma]]

### 🎮 Jeux Vidéo (15 items)
→ [[Index Jeux Vidéo]]

## Derniers ajouts
- [[Biais de confirmation]] — 2025-03-08
- [[Fonctionnement des transformers]] — 2025-03-07
- ...

## Sources
- 85 conversations ChatGPT
- 42 conversations Claude
- 15 conversations Gemini
- 5 fichiers Markdown divers
```

---

## 🖥️ Interface web (UI minimale d'import)

L'interface web sera simple — une page `knowledge.html` dans `server/ui/` qui permet de :

1. **Uploader** un fichier d'export (drag & drop ou bouton)
2. **Voir la progression** du traitement (barre de progression)
3. **Consulter les résultats** : combien de conversations importées, combien filtrées, combien de nouveaux items
4. **Lancer l'export** Obsidian (bouton qui génère/met à jour le vault)
5. **Voir les avertissements** VRAM si nécessaire

L'interface de CONSULTATION reste Obsidian. La web UI ne sert qu'à l'import et au suivi.

---

## 📋 Plan de développement phase par phase

### Phase 0 — Préparation (1-2 heures)

**Objectif** : Préparer l'environnement sans toucher au code de FLO.

1. Télécharger le modèle Qwen2.5-14B-Instruct GGUF (Q5_K_M) depuis HuggingFace
2. Le placer dans `models/Qwen2.5-14B/`
3. Mettre à jour `models.json` avec les configs des modèles KB
4. Tester que FLO charge toujours correctement avec `python -m uvicorn main:app`
5. Créer les dossiers : `data/knowledge/`, `data/knowledge/imports/`, `data/obsidian_vault/`
6. Installer les dépendances supplémentaires : `pip install aiosqlite`

**Validation** : FLO démarre normalement, les nouveaux dossiers existent.

---

### Phase 1 — Parseurs (2-3 heures)

**Objectif** : Pouvoir importer un fichier d'export et le normaliser.

1. Créer `server/knowledge/parsers/base_parser.py`
2. Créer `server/knowledge/parsers/chatgpt_parser.py`
3. Créer `server/knowledge/parsers/markdown_parser.py`
4. Créer un script de test : importer un vrai fichier ChatGPT et afficher les conversations parsées

**Commande Claude Code** :
```
claude "Crée le module parseur dans server/knowledge/parsers/ en suivant 
exactement la spec du fichier spec_knowledgebase.md. Commence par 
base_parser.py, puis chatgpt_parser.py. Crée un test simple dans 
tests/test_parsers.py qui parse un fichier ChatGPT d'exemple."
```

**Validation** : Le test affiche les conversations avec titre, nombre de messages, et le texte complet.

---

### Phase 2 — Base de données et déduplication (2-3 heures)

**Objectif** : Stocker les conversations en base et détecter les doublons.

1. Créer le schéma SQLite dans `server/knowledge/db.py`
2. Créer `server/knowledge/processing/deduplicator.py`
3. Créer `server/knowledge/services/import_service.py` (orchestrateur)
4. Tester : importer le même fichier deux fois → la 2e fois doit détecter les doublons

**Validation** : Import d'un fichier → conversations en base. Réimport → statut "duplicate".

---

### Phase 3 — Traitement IA (3-5 heures)

**Objectif** : Le LLM filtre, extrait, résume et classifie.

C'est la phase la plus délicate. Procédez étape par étape.

1. Créer `server/knowledge/processing/prompts.py` (copier les prompts de la spec)
2. Créer `server/knowledge/processing/gpu_check.py` (détection VRAM)
3. Créer `server/knowledge/processing/extractor.py`
   - Utilise `model_manager.load_model("kb-extractor")` pour charger le modèle
   - Envoie chaque conversation au LLM avec le prompt de filtrage
   - Si score >= 3, envoie le prompt d'extraction
   - Parse le JSON retourné par le LLM
   - Sauvegarde les items en base
4. Créer `server/knowledge/processing/classifier.py`
   - Charge les thèmes existants depuis la base
   - Envoie chaque item au LLM avec le prompt de classification
   - Crée les nouveaux thèmes si suggérés
5. Tester sur 5-10 conversations réelles

**Point d'attention** : Le LLM ne retourne pas toujours du JSON valide. Prévoir un parsing robuste avec retry et fallback.

**Commande Claude Code** :
```
claude "Crée le module extractor.py dans server/knowledge/processing/.
Il doit : 1) charger le modèle via model_manager, 2) envoyer la 
conversation avec le prompt FILTER_PROMPT, 3) parser le JSON retourné,
4) si score >= 3, envoyer EXTRACT_PROMPT, 5) sauvegarder en base SQLite.
Prévoir un parsing JSON robuste avec gestion des erreurs."
```

**Validation** : Traitement de 5 conversations → items de connaissance en base avec thèmes et tags.

---

### Phase 4 — Export Obsidian (2-3 heures)

**Objectif** : Générer le vault Markdown.

1. Créer `server/knowledge/exporters/obsidian_exporter.py`
2. Il lit la base SQLite et génère :
   - Un dossier par thème
   - Un fichier Markdown par item de connaissance (avec frontmatter YAML)
   - Les fichiers d'index par thème
   - Le MOC principal
   - Les wikilinks entre items liés
3. Tester : ouvrir le vault dans Obsidian → vérifier le graph view

**Validation** : Le vault s'ouvre dans Obsidian, les liens fonctionnent, le graph view montre les connexions.

---

### Phase 5 — API et UI (2-3 heures)

**Objectif** : Interface web pour importer et suivre le traitement.

1. Créer `server/api/knowledge.py` avec les endpoints :
   - `POST /kb/import` — Upload d'un fichier d'export
   - `GET /kb/status` — Statut du traitement en cours
   - `GET /kb/stats` — Statistiques de la base
   - `POST /kb/export` — Déclencher l'export Obsidian
   - `GET /kb/themes` — Liste des thèmes et compteurs
2. Créer `server/ui/knowledge.html` — page d'import avec drag & drop
3. Ajouter la ligne dans `main.py` pour enregistrer le router

**Validation** : Ouvrir `http://localhost:8000/ui/knowledge.html`, uploader un fichier, voir la progression, lancer l'export.

---

### Phase 6 — Parseurs additionnels + polish (2-3 heures)

**Objectif** : Support Claude, Gemini, et améliorations.

1. Créer `server/knowledge/parsers/claude_parser.py`
2. Créer `server/knowledge/parsers/gemini_parser.py`
3. Ajouter la détection automatique du format (essayer chaque parseur)
4. Améliorer la gestion d'erreurs
5. Ajouter des thèmes initiaux en base (Psychologie, Tech & IA, Cinéma, Jeux Vidéo)

---

## ⏱️ Estimation totale

| Phase | Durée estimée | Difficulté |
|-------|---------------|------------|
| Phase 0 : Préparation | 1-2h | Facile |
| Phase 1 : Parseurs | 2-3h | Facile |
| Phase 2 : BDD + dédup | 2-3h | Moyen |
| Phase 3 : Traitement IA | 3-5h | Difficile |
| Phase 4 : Export Obsidian | 2-3h | Moyen |
| Phase 5 : API + UI | 2-3h | Moyen |
| Phase 6 : Parseurs + polish | 2-3h | Facile |
| **TOTAL** | **14-22h** | |

Ces estimations sont pour un développement avec Claude Code qui guide chaque étape.

---

## ⚠️ Points de vigilance

1. **Parsing JSON du LLM** : Les modèles locaux ne retournent pas toujours du JSON parfait. Prévoir : nettoyage des backticks markdown autour du JSON, retry (2-3 tentatives), fallback en cas d'échec (marquer la conversation comme "à retraiter").

2. **Contexte du modèle** : Les conversations longues dépassent le contexte du LLM. Prévoir un découpage en chunks de ~3000 tokens avec chevauchement.

3. **Temps de traitement** : Sur quelques centaines de conversations, compter 1-3 secondes par conversation pour le filtrage, et 5-15 secondes pour l'extraction complète. Soit environ 30-60 minutes pour 300 conversations.

4. **Format des exports** : Les formats d'export des IA évoluent. Les parseurs devront être mis à jour. La structure modulaire le permet facilement.

5. **Sauvegarde** : Le vault Obsidian est un dossier de fichiers Markdown. Il peut être versionné avec Git pour garder un historique.

---

## 🚀 Pour commencer

Quand vous êtes prêt à démarrer, lancez Claude Code et dites :

```
claude "Je veux créer le module KnowledgeBase dans mon projet FLO.
Voici la spec complète : [coller le contenu de ce fichier ou le chemin].
Commence par la Phase 0 : crée les dossiers nécessaires et vérifie 
que FLO démarre toujours correctement. Puis passe à la Phase 1."
```

Claude Code vous guidera pas à pas pour chaque fichier à créer.
