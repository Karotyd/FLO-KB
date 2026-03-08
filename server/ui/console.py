# app/ui/console.py

import requests

BASE_URL = "http://127.0.0.1:8000"
CHAT_URL = f"{BASE_URL}/chat"
MODELS_URL = f"{BASE_URL}/models"


def fetch_models():
    r = requests.get(MODELS_URL, timeout=10)
    r.raise_for_status()
    return r.json()


def run():
    print("[ Console UI | API client | prêt ]")
    print("Commandes : /models | /use <model_id> | /exit\n")

    current_model = None

    while True:
        try:
            msg = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n/exit")
            break

        if not msg:
            continue

        if msg == "/exit":
            break

        if msg == "/models":
            try:
                models = fetch_models()
                print("\nModèles disponibles :")
                for m in models:
                    print(f" - {m['id']} ({m['label']})")
                print()
            except Exception as e:
                print(f"[ERREUR API] {e}\n")
            continue

        if msg.startswith("/use "):
            current_model = msg.split(" ", 1)[1].strip()
            print(f"[modèle actif : {current_model}]\n")
            continue

        try:
            params = {"message": msg}
            if current_model:
                params["model_id"] = current_model

            r = requests.post(CHAT_URL, params=params, timeout=300)
            r.raise_for_status()
        except Exception as e:
            print(f"[ERREUR API] {e}\n")
            continue

        data = r.json()
        print(f"Assistant ▸ {data.get('reply','')}\n")


if __name__ == "__main__":
    run()
