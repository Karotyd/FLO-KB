# Changelog — FLO-KB

Toutes les modifications notables de ce projet sont documentées ici.

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/)
Versionnage : [Semantic Versioning](https://semver.org/lang/fr/)

---

## [Non publié]

### À faire
- Créer les symlinks vers les modèles GGUF
- Copier la spec KB dans `docs/spec_knowledgebase.md`
- Démarrer la Phase 0 du module KnowledgeBase

---

## [0.5.0] — 2026-03-08 — Isolation initiale

### Ajouté
- Backend FLO extrait du projet parent `FLO_v0.5_STABLE`
- `main.py` déplacé à la racine (était dans `server/`)
- `requirements.txt` allégé : suppression de torch, transformers, accelerate, bitsandbytes, huggingface-hub, tokenizers, safetensors
- Venv Python 3.11.9 créé avec llama-cpp-python 0.3.16 (CUDA, copié depuis le venv source)
- Dépendances supplémentaires installées : numpy, jinja2, diskcache (requis par llama-cpp-python), aiosqlite, python-multipart (pour le module KB à venir)
- Git initialisé avec `.gitignore` mis à jour (venv/, logs/, data/, models/*.gguf)
- `CLAUDE.md` — fichier de contexte session pour Claude Code
- `CHANGELOG.md` — ce fichier
- `docs/` — dossier de documentation (spec KB à y placer)

### Supprimé
- Fichiers `.txt` parasites dans `server/services/` (copiés par erreur depuis l'explorateur)
- Tous les `__pycache__/` du projet

### Vérifié
- `GET http://127.0.0.1:8000/` retourne `{"status":"ok"}`
- `import llama_cpp` fonctionne (version 0.3.16, CUDA)
- Modèles GGUF non encore liés (symlinks à créer — erreur au démarrage attendue)
