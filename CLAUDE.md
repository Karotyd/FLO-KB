# CLAUDE.md — Contexte projet FLO-KB

> Lis ce fichier en début de chaque session.
> Mets-le à jour après chaque modification significative.

---

## Description du projet

**FLO-KB** est le backend LLM local de FLO, isolé en projet autonome réutilisable.

Il est composé de deux couches :

1. **FLO core** (existant, stable) — serveur FastAPI + llama-cpp-python qui charge des modèles GGUF, gère les sessions de chat, et expose une API SSE pour les réponses en streaming.

2. **Module KnowledgeBase** (à construire) — pipeline d'extraction/filtrage/résumé/classification de conversations IA (ChatGPT, Claude, Gemini, Copilot, Mistral), stocké en SQLite, exporté vers un vault Obsidian structuré.

---

## Environnement

| Paramètre | Valeur |
|-----------|--------|
| OS | Windows 11 Pro |
| Python | 3.11.9 |
| GPU | RTX 3090 (24 Go VRAM) |
| CUDA | Activé (via llama-cpp-python 0.3.16) |
| Shell | bash (Git Bash / Unix syntax) |
| Venv | `venv/` à la racine du projet |

---

## État actuel du projet

- [x] FLO isolé du projet parent et fonctionnel (`{"status":"ok"}` sur GET /)
- [x] `requirements.txt` allégé (sans torch/transformers/accelerate)
- [x] Venv Python 3.11 + llama-cpp-python 0.3.16 CUDA
- [x] Git initialisé (commit initial)
- [ ] **Symlinks modèles GGUF à créer** (voir section Modèles)
- [x] Spec KB dans `docs/spec_knowledgebase.md`
- [ ] Module KnowledgeBase — non commencé (Phase 0 à démarrer)

---

## Structure du projet

```
FLO-KB/
├── main.py                          <- Point d'entrée FastAPI (racine)
├── models.json                      <- Registre des modèles GGUF
├── requirements.txt                 <- Dépendances allégées
├── run_api.bat / run_api.ps1        <- Scripts de lancement Windows
├── .gitignore
├── CLAUDE.md                        <- CE FICHIER
├── CHANGELOG.md                     <- Historique des versions
│
├── docs/                            <- Documentation
│   └── spec_knowledgebase.md        <- Spec complète du module KB
│
├── data/
│   ├── sessions/                    <- Sessions de chat (gitignored)
│   ├── knowledge/                   <- Base KB SQLite + imports (gitignored, à créer)
│   │   ├── kb.sqlite
│   │   └── imports/
│   └── obsidian_vault/              <- Vault généré (gitignored, à créer)
│
├── logs/                            <- Logs applicatifs (gitignored)
├── models/                          <- Fichiers GGUF (gitignored, symlinks à créer)
│   ├── Mistral-7B/
│   └── Guanaco-7B/
│
├── venv/                            <- Environnement virtuel (gitignored)
│
└── server/
    ├── __init__.py
    ├── config.py                    <- Configuration centralisée (ports, logs, etc.)
    │
    ├── api/
    │   ├── chat.py                  <- NE PAS MODIFIER — API chat existante
    │   ├── test_services.py         <- Tests des services
    │   └── knowledge.py             <- A CRÉER (Phase 5) — endpoints KB
    │
    ├── engine/                      <- NE PAS MODIFIER — moteur LLM
    │   ├── llm.py                   <- Interface abstraite LLM
    │   ├── gguf_llm.py              <- Implémentation llama-cpp-python
    │   ├── model_manager.py         <- Chargement/déchargement des modèles
    │   └── factory.py               <- Création d'instances LLM
    │
    ├── knowledge/                   <- A CRÉER — module KnowledgeBase
    │   ├── __init__.py
    │   ├── db.py                    <- Schéma SQLite + migrations
    │   ├── parsers/                 <- Parseurs par source IA
    │   │   ├── base_parser.py
    │   │   ├── chatgpt_parser.py
    │   │   ├── claude_parser.py
    │   │   ├── gemini_parser.py
    │   │   └── markdown_parser.py
    │   ├── processing/              <- Pipeline de traitement IA
    │   │   ├── prompts.py
    │   │   ├── extractor.py
    │   │   ├── classifier.py
    │   │   ├── deduplicator.py
    │   │   └── gpu_check.py
    │   ├── exporters/
    │   │   └── obsidian_exporter.py
    │   └── services/
    │       ├── import_service.py
    │       ├── knowledge_service.py
    │       └── export_service.py
    │
    ├── models/
    │   └── registry.py              <- Modèles Pydantic partagés
    │
    ├── router/
    │   └── model_router.py          <- Routage automatique vers le bon modèle
    │
    ├── services/                    <- NE PAS MODIFIER — services chat existants
    │   ├── chat_service.py
    │   ├── session_service.py
    │   ├── stats_service.py
    │   └── buggy_export.py          <- A investiguer (fichier hérité du projet parent)
    │
    ├── storage/                     <- Stockage JSON des sessions
    │   ├── base.py
    │   ├── json_storage.py
    │   └── models.py
    │
    └── ui/
        ├── index.html               <- NE PAS MODIFIER — UI chat existante
        ├── console.py
        └── knowledge.html           <- A CRÉER (Phase 5) — UI import KB
```

---

## Fichiers à NE PAS MODIFIER

Ces fichiers constituent le cœur fonctionnel de FLO. On ajoute à côté, on ne touche pas à l'existant :

| Fichier | Raison |
|---------|--------|
| `server/engine/` (tout) | Moteur LLM — stable, testé |
| `server/api/chat.py` | API chat — stable |
| `server/services/` (tout) | Services chat — stables |
| `server/ui/index.html` | UI chat existante |

**Seul changement autorisé dans `main.py`** : ajouter la ligne d'enregistrement du router KB :
```python
from server.api.knowledge import router as knowledge_router
app.include_router(knowledge_router, prefix="/kb")
```

---

## Conventions de code

| Élément | Convention |
|---------|------------|
| Code (variables, fonctions, classes) | Anglais |
| Commentaires inline | Français |
| Docstrings (fonctions publiques) | Français |
| Prompts LLM | Français |
| Messages de log | Français |
| Commits Git | Français, format `[Phase X] Description` |

---

## Modèles GGUF

### Modèles existants (symlinks à créer)

Source : `C:\Users\jouin\FLO GLOBAL\llm-manager\FLO_v0.5_WORK\models\`

| ID | Fichier | VRAM | Usage |
|----|---------|------|-------|
| `mistral-7b` | `Mistral-7B/mistral-7b-instruct-v0.2.Q4_K_M.gguf` | ~5 Go | Chat général, modèle par défaut |
| `guanaco-7b` | `Guanaco-7B/guanaco-7b-uncensored.Q4_K_M.gguf` | ~5 Go | Chat créatif |

**Commande pour créer les symlinks (PowerShell en tant qu'administrateur) :**
```powershell
cd "C:\Users\jouin\Projets\FLO-KB\models"
New-Item -ItemType Directory -Force -Path "Mistral-7B"
New-Item -ItemType Directory -Force -Path "Guanaco-7B"
New-Item -ItemType SymbolicLink `
  -Path "Mistral-7B\mistral-7b-instruct-v0.2.Q4_K_M.gguf" `
  -Target "C:\Users\jouin\FLO GLOBAL\llm-manager\FLO_v0.5_WORK\models\Mistral-7B\mistral-7b-instruct-v0.2.Q4_K_M.gguf"
New-Item -ItemType SymbolicLink `
  -Path "Guanaco-7B\guanaco-7b-uncensored.Q4_K_M.gguf" `
  -Target "C:\Users\jouin\FLO GLOBAL\llm-manager\FLO_v0.5_WORK\models\Guanaco-7B\guanaco-7b-uncensored.Q4_K_M.gguf"
```

### Modèles KB à ajouter (Phase 0)

| ID | Modèle | VRAM | Usage KB |
|----|--------|------|----------|
| `kb-extractor` | Qwen2.5-14B-Instruct Q5_K_M | ~12 Go | Extraction, résumé |
| `kb-light` | Mistral 7B Q4_K_M (déjà présent) | ~5 Go | Classification, tagging, fallback |

Qwen2.5-14B à télécharger depuis HuggingFace et à placer dans `models/Qwen2.5-14B/`.
Config à ajouter dans `models.json` (voir spec KB).

---

## Phases du projet KnowledgeBase

Spec complète : `docs/spec_knowledgebase.md` (à copier depuis la conversation de démarrage).

| Phase | Description | Statut |
|-------|-------------|--------|
| **Phase 0** | Préparation : symlinks GGUF, dossiers KB, models.json KB, test démarrage | Non commencé |
| **Phase 1** | Parseurs : base_parser, chatgpt_parser, markdown_parser | Non commencé |
| **Phase 2** | Base de données SQLite + déduplication par hash SHA-256 | Non commencé |
| **Phase 3** | Traitement IA : filtrage, extraction, résumé, classification | Non commencé |
| **Phase 4** | Export Obsidian : vault Markdown + wikilinks + MOC | Non commencé |
| **Phase 5** | API FastAPI `/kb/*` + UI knowledge.html | Non commencé |
| **Phase 6** | Parseurs additionnels (Claude, Gemini) + polish | Non commencé |

---

## Points de vigilance

1. **Parsing JSON des LLM locaux** — Les modèles Q4/Q5 ne retournent pas toujours du JSON valide. Toujours prévoir : strip des backticks markdown, retry 2-3 fois, fallback avec marquage "à retraiter".

2. **Contexte LLM** — Les conversations longues peuvent dépasser la fenêtre de contexte. Découper en chunks de ~3000 tokens avec chevauchement.

3. **Ne pas casser le chat existant** — Tester `GET /` après chaque ajout de code au projet.

4. **Temps de traitement** — 1-3s/conversation pour le filtrage, 5-15s pour l'extraction complète. Sur 300 conversations : environ 30-60 minutes.

5. **Formats d'export** — Les formats JSON de ChatGPT/Claude évoluent. Les parseurs sont modulaires pour faciliter les mises à jour futures.

---

## Commandes utiles

```bash
# Activer le venv (Git Bash)
source venv/Scripts/activate

# Démarrer FLO
venv/Scripts/python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

# Tester que FLO répond
curl http://127.0.0.1:8000/

# Lister les dépendances installées
venv/Scripts/pip.exe list

# Installer les dépendances depuis requirements.txt
venv/Scripts/pip.exe install -r requirements.txt
```

---

## Convention Git

- Format : `[Phase X] Description courte en français`
- Exemples :
  - `[Phase 0] Ajout symlinks modèles GGUF et dossiers KB`
  - `[Phase 1] Parseurs ChatGPT et Markdown`
  - `[Phase 3] Extracteur avec retry JSON robuste`
- Ne jamais committer : `venv/`, `data/`, `logs/`, `models/*.gguf`

---

## Dernière mise à jour

**Date** : 2026-03-08
**Description** : Isolation initiale du backend FLO depuis FLO_v0.5_STABLE. Création de CLAUDE.md et CHANGELOG.md. Venv Python 3.11 + llama-cpp-python 0.3.16 CUDA opérationnel. Spec KB ajoutée dans docs/. Module KB non commencé.
