"""
Test des parseurs sur un vrai export ChatGPT.
Usage : python -m tests.test_parsers
"""

import sys
import os
import logging

# Ajouter la racine du projet au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.knowledge.parsers.zip_handler import extract_zip
from server.knowledge.parsers import detect_and_parse

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Chemin vers l'export ChatGPT
ZIP_PATH = r"C:\Users\jouin\Downloads\Export chat GPT\93da9c3805145d86452c9d08988d77946fa5b0ce9973cf8c99843ce2fa6ef7f0-2026-03-08-10-15-24-592450e9078b45119650c674bb77078b.zip"


def main():
    print("=" * 60)
    print("TEST PARSEURS FLO-KB")
    print("=" * 60)

    # Étape 1 : Extraction ZIP
    print(f"\nExtraction de : {os.path.basename(ZIP_PATH)}")
    try:
        extracted = extract_zip(ZIP_PATH)
        print(f"   -> {len(extracted)} fichier(s) extrait(s)")
        for f in extracted:
            print(f"     - {os.path.basename(f)}")
    except Exception as e:
        print(f"   ERREUR extraction : {e}")
        import traceback
        traceback.print_exc()
        return

    # Étape 2 : Parser chaque fichier extrait
    total_conversations = 0

    for filepath in extracted:
        print(f"\nParsing : {os.path.basename(filepath)}")
        try:
            conversations = detect_and_parse(filepath)
            print(f"   -> {len(conversations)} conversation(s) trouvee(s)")
            total_conversations += len(conversations)

            # Afficher un aperçu des 5 premières
            for i, conv in enumerate(conversations[:5]):
                msg_count = len(conv.messages)
                text_len = len(conv.full_text)
                hash_short = conv.content_hash[:12]
                print(f"   [{i+1}] \"{conv.title}\"")
                print(f"       Source: {conv.source_type} | Messages: {msg_count} | Taille: {text_len} chars | Hash: {hash_short}...")

                # Afficher le début du premier message
                if conv.messages:
                    first_msg = conv.messages[0].content[:100].replace('\n', ' ')
                    print(f"       Premier msg ({conv.messages[0].role}): {first_msg}...")

            if len(conversations) > 5:
                print(f"   ... et {len(conversations) - 5} autre(s) conversation(s)")

        except ValueError as e:
            # Fichier non reconnu (métadonnées de l'export, etc.) — ignoré silencieusement
            print(f"   Ignoré (format non reconnu) : {os.path.basename(filepath)}")
        except Exception as e:
            print(f"   ERREUR parsing : {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'=' * 60}")
    print(f"TOTAL : {total_conversations} conversations parsees")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
