"""
Export des connaissances vers un vault Obsidian structuré — FLO-KB.

Structure générée :
  data/obsidian_vault/
  ├── _Index/        MOC principal + un Index par thème
  ├── <Thème>/       Un dossier par thème, un fichier par item
  ├── _Non classé/   Items sans thème
  ├── _Sources/      Résumés des conversations traitées
  └── _Templates/    Templates vides pour usage manuel dans Obsidian
"""

import logging
import os
import re
from datetime import date, datetime
from typing import Optional

from server.knowledge.db import KnowledgeDB

logger = logging.getLogger(__name__)

# Emojis par défaut par thème
THEME_EMOJIS: dict[str, str] = {
    "Psychologie": "🧠",
    "Tech & IA": "💻",
    "Cinéma": "🎬",
    "Jeux Vidéo": "🎮",
    "Musique": "🎵",
    "Développement Personnel": "🌱",
    "Sciences": "🔬",
    "Programmation": "⌨️",
    "Sports": "🏃",
    "Tennis": "🎾",
    "Navigation maritime": "⛵",
    "Arts et Création": "🎨",
}
DEFAULT_EMOJI = "📌"

# Dossier pour les items sans thème
UNCLASSIFIED_FOLDER = "_Non classé"


class ObsidianExporter:
    """Génère un vault Obsidian depuis la base de connaissances."""

    def __init__(self, db: KnowledgeDB, vault_path: str = "data/obsidian_vault"):
        self.db = db
        self.vault_path = vault_path
        self.today = date.today().isoformat()

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------

    def _sanitize_filename(self, name: str) -> str:
        """
        Convertit un nom en nom de fichier valide (Windows + Obsidian).
        Retire les caractères interdits, limite à 100 chars.
        """
        # Caractères interdits sur Windows et/ou Obsidian
        clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name)
        clean = clean.strip('. ')
        if len(clean) > 100:
            # Couper sur un espace pour ne pas tronquer un mot
            clean = clean[:100].rsplit(' ', 1)[0].strip()
        return clean or "Sans titre"

    def _wikilink(self, title: str) -> str:
        """Crée un wikilink Obsidian : [[nom_fichier]]"""
        return f"[[{self._sanitize_filename(title)}]]"

    def _theme_emoji(self, theme_name: str) -> str:
        """Retourne l'emoji associé à un thème, ou le défaut."""
        return THEME_EMOJIS.get(theme_name, DEFAULT_EMOJI)

    def _write_file(self, path: str, content: str):
        """Écrit un fichier UTF-8 (crée les dossiers si nécessaire, écrase si existant)."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def _format_date(self, raw: Optional[str]) -> str:
        """Convertit un timestamp ISO ou None en date YYYY-MM-DD."""
        if not raw:
            return "Inconnue"
        try:
            return raw[:10]  # Les 10 premiers chars d'un ISO = YYYY-MM-DD
        except Exception:
            return "Inconnue"

    def _source_label(self, source_type: str) -> str:
        """Retourne un label lisible pour le source_type."""
        labels = {
            "chatgpt": "ChatGPT",
            "claude": "Claude",
            "gemini": "Gemini",
            "markdown": "Markdown",
        }
        return labels.get(source_type.lower(), source_type.capitalize())

    # ------------------------------------------------------------------
    # Génération des items de connaissance
    # ------------------------------------------------------------------

    def _generate_item_content(
        self,
        item: dict,
        same_theme_items: list[dict],
    ) -> str:
        """Génère le contenu Markdown d'un item de connaissance."""
        themes = item.get("themes", [])
        tags = item.get("tags", [])
        primary_theme = themes[0] if themes else UNCLASSIFIED_FOLDER
        conv_title = item.get("conv_title") or "Source inconnue"
        conv_source = self._source_label(item.get("conv_source_type") or "")
        conv_date = self._format_date(item.get("conv_created_at"))

        # Frontmatter YAML
        themes_yaml = "\n".join(f"  - {t}" for t in themes) if themes else "  - Non classé"
        tags_yaml = "\n".join(f"  - {t}" for t in tags) if tags else ""

        frontmatter = f"""---
type: {item['item_type']}
source: {conv_source}
source_conversation: "{conv_title.replace('"', "'")}"
date_extraction: {self.today}
themes:
{themes_yaml}
"""
        if tags_yaml:
            frontmatter += f"tags:\n{tags_yaml}\n"
        frontmatter += f"confidence: {item['confidence']:.2f}\n---\n"

        # Corps
        body = f"\n# {item['title']}\n\n{item['content']}\n"

        # Citation source (si disponible)
        if item.get("source_quote"):
            body += f"\n> *\"{item['source_quote']}\"*\n"

        # Wikilinks "Voir aussi" : autres items du même thème (max 5)
        see_also_items = [
            i for i in same_theme_items
            if i["id"] != item["id"]
        ][:5]

        body += "\n## Voir aussi\n\n"
        for other in see_also_items:
            body += f"- {self._wikilink(other['title'])} — {other['item_type']}\n"
        if themes:
            body += f"- {self._wikilink('Index ' + primary_theme)}\n"
        if not see_also_items and not themes:
            body += "- Aucun item lié pour l'instant\n"

        # Pied de page
        source_filename = self._make_source_filename(
            conv_source, conv_date, conv_title
        )
        body += f"\n---\n*Extrait de : {self._wikilink(source_filename[:-3])}*\n"

        return frontmatter + body

    # ------------------------------------------------------------------
    # Génération des index de thèmes
    # ------------------------------------------------------------------

    def _generate_theme_index(self, theme_name: str, items: list[dict]) -> str:
        """Génère le fichier Index d'un thème."""
        emoji = self._theme_emoji(theme_name)
        count = len(items)

        frontmatter = f"""---
type: index
theme: {theme_name}
item_count: {count}
updated: {self.today}
---

"""
        header = f"# {emoji} {theme_name}\n\n> {count} item(s) de connaissance\n\n"

        items_section = "## Items\n\n"
        for item in sorted(items, key=lambda x: x["title"]):
            items_section += f"- {self._wikilink(item['title'])} — {item['item_type']}\n"

        footer = f"\n---\n*Retour : {self._wikilink('MOC - Base de connaissances')}*\n"

        return frontmatter + header + items_section + footer

    # ------------------------------------------------------------------
    # Génération du MOC
    # ------------------------------------------------------------------

    def _generate_moc(
        self,
        themes_with_counts: list[dict],
        total_items: int,
        recent_items: list[dict],
        source_stats: dict,
    ) -> str:
        """Génère le MOC (Map of Content) principal."""
        nb_themes = sum(1 for t in themes_with_counts if t["item_count"] > 0)

        frontmatter = f"""---
type: moc
updated: {self.today}
total_items: {total_items}
---

"""
        header = (
            f"# 🧠 Base de connaissances\n\n"
            f"> Dernière mise à jour : {self.today} | "
            f"{total_items} items | {nb_themes} thèmes\n\n"
        )

        # Section thèmes (uniquement ceux avec des items)
        themes_section = "## Thèmes\n\n"
        for theme in themes_with_counts:
            if theme["item_count"] == 0:
                continue
            emoji = self._theme_emoji(theme["name"])
            themes_section += (
                f"### {emoji} {theme['name']} ({theme['item_count']} items)\n"
                f"→ {self._wikilink('Index ' + theme['name'])}\n\n"
            )

        # Derniers ajouts (10 max)
        recent_section = "## Derniers ajouts\n\n"
        for item in recent_items[:10]:
            recent_section += f"- {self._wikilink(item['title'])} — {self._format_date(item.get('created_at'))}\n"

        # Sources
        sources_section = "\n## Sources\n\n"
        for source_type, count in source_stats.items():
            label = self._source_label(source_type)
            sources_section += f"- {count} conversation(s) {label}\n"
        if not source_stats:
            sources_section += "- Aucune source traitée\n"

        return frontmatter + header + themes_section + recent_section + sources_section

    # ------------------------------------------------------------------
    # Génération des fichiers sources
    # ------------------------------------------------------------------

    def _make_source_filename(self, source_label: str, conv_date: str, conv_title: str) -> str:
        """Construit le nom de fichier pour une source."""
        title_part = self._sanitize_filename(conv_title)[:60]
        return f"{source_label} - {conv_date} - {title_part}.md"

    def _generate_source_content(self, conv: dict, items: list[dict]) -> str:
        """Génère le fichier Markdown d'une source (conversation traitée)."""
        source_label = self._source_label(conv.get("source_type") or "")
        conv_date = self._format_date(conv.get("created_at"))
        title = conv.get("title") or "Sans titre"
        score = conv.get("value_score") or 0
        summary = conv.get("summary") or "Pas de résumé disponible."

        frontmatter = f"""---
type: source
source_type: {conv.get('source_type', 'unknown')}
original_title: "{title.replace('"', "'")}"
date_conversation: {conv_date}
date_import: {self.today}
value_score: {score}
---

"""
        header = f"# {source_label} — {title}\n\n> Score de valeur : {score}/5\n\n"

        summary_section = f"## Résumé\n\n{summary}\n\n"

        items_section = "## Items extraits\n\n"
        if items:
            for item in items:
                items_section += f"- {self._wikilink(item['title'])}\n"
        else:
            items_section += "- Aucun item extrait\n"

        footer = f"\n---\n*Retour : {self._wikilink('MOC - Base de connaissances')}*\n"

        return frontmatter + header + summary_section + items_section + footer

    # ------------------------------------------------------------------
    # Génération des templates
    # ------------------------------------------------------------------

    def _generate_templates(self):
        """Génère les templates vides dans _Templates/."""
        templates_dir = os.path.join(self.vault_path, "_Templates")

        item_template = """---
type:
source:
source_conversation: ""
date_extraction:
themes:
  -
tags:
  -
confidence: 0.8
---

# Titre de l'item

Contenu de l'item de connaissance.

## Voir aussi

-

---
*Extrait de : *
"""
        self._write_file(
            os.path.join(templates_dir, "Template Knowledge Item.md"),
            item_template
        )

        source_template = """---
type: source
source_type:
original_title: ""
date_conversation:
date_import:
value_score:
---

# Source — Titre

> Score de valeur : /5

## Résumé

Résumé de la conversation.

## Items extraits

-

---
*Retour : [[MOC - Base de connaissances]]*
"""
        self._write_file(
            os.path.join(templates_dir, "Template Source.md"),
            source_template
        )

    # ------------------------------------------------------------------
    # Point d'entrée principal
    # ------------------------------------------------------------------

    async def export(self) -> dict:
        """
        Exporte la base complète vers le vault Obsidian.
        Idempotent : écrase les fichiers existants sans créer de doublons.

        Returns:
            dict avec items_exported, themes_exported, sources_exported, vault_path.
        """
        logger.info(f"Début de l'export Obsidian → {self.vault_path}")

        # --- Récupérer les données ---
        all_items = await self.db.get_all_items_with_details()
        themes_with_counts = await self.db.get_themes_with_counts()
        processed_convs = await self.db.get_processed_conversations()
        source_stats = await self.db.get_source_stats()

        if not all_items:
            logger.warning("Aucun item en base — vault vide généré")

        # --- Préparer la structure ---
        # Indexer les items par thème principal
        items_by_theme: dict[str, list[dict]] = {}
        for item in all_items:
            themes = item.get("themes", [])
            primary = themes[0] if themes else UNCLASSIFIED_FOLDER
            items_by_theme.setdefault(primary, []).append(item)

        # Créer les dossiers de base
        for folder in ["_Index", "_Sources", "_Templates"]:
            os.makedirs(os.path.join(self.vault_path, folder), exist_ok=True)
        for theme_name in items_by_theme:
            os.makedirs(
                os.path.join(self.vault_path, self._sanitize_filename(theme_name)),
                exist_ok=True
            )

        items_exported = 0
        themes_exported = 0

        # --- Générer les fichiers items ---
        for primary_theme, theme_items in items_by_theme.items():
            theme_folder = self._sanitize_filename(primary_theme)

            for item in theme_items:
                filename = self._sanitize_filename(item["title"]) + ".md"
                filepath = os.path.join(self.vault_path, theme_folder, filename)
                content = self._generate_item_content(item, theme_items)
                self._write_file(filepath, content)
                items_exported += 1

            logger.info(f"  {primary_theme} : {len(theme_items)} item(s)")

        # --- Générer les index de thèmes ---
        for theme in themes_with_counts:
            if theme["item_count"] == 0:
                continue
            theme_name = theme["name"]
            theme_items_list = await self.db.get_items_by_theme(theme_name)
            index_content = self._generate_theme_index(theme_name, theme_items_list)
            index_filename = f"Index {self._sanitize_filename(theme_name)}.md"
            self._write_file(
                os.path.join(self.vault_path, "_Index", index_filename),
                index_content
            )
            themes_exported += 1

        # --- Générer le MOC ---
        recent_items = sorted(all_items, key=lambda x: x.get("created_at") or "", reverse=True)
        moc_content = self._generate_moc(
            themes_with_counts, len(all_items), recent_items, source_stats
        )
        self._write_file(
            os.path.join(self.vault_path, "_Index", "MOC - Base de connaissances.md"),
            moc_content
        )

        # --- Générer les sources ---
        sources_exported = 0
        for conv in processed_convs:
            source_label = self._source_label(conv.get("source_type") or "")
            conv_date = self._format_date(conv.get("created_at"))
            conv_title = conv.get("title") or "Sans titre"

            conv_items = await self.db.get_items_for_conversation(conv["id"])
            source_content = self._generate_source_content(conv, conv_items)
            source_filename = self._make_source_filename(source_label, conv_date, conv_title)
            self._write_file(
                os.path.join(self.vault_path, "_Sources", source_filename),
                source_content
            )
            sources_exported += 1

        # --- Générer les templates ---
        self._generate_templates()

        result = {
            "items_exported": items_exported,
            "themes_exported": themes_exported,
            "sources_exported": sources_exported,
            "vault_path": os.path.abspath(self.vault_path),
        }
        logger.info(f"Export terminé : {result}")
        return result
