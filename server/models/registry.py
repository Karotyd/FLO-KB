from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

MODELS = {
    "mistral_7b": {
        "label": "Mistral 7B Instruct v0.2",
        "path": BASE_DIR / "models" / "Mistral-7B" / "mistral-7b-instruct-v0.2.Q4_K_M.gguf",
        "backend": "gguf",
        "params": {
            "n_ctx": 2048,
            "n_threads": 8,
            "temperature": 0.2,
            "top_p": 0.5,
            "repeat_penalty": 1.2,
            "max_tokens": 80,
        }
    },
    "guanaco_7b": {
        "label": "Guanaco 7B Uncensored",
        "path": BASE_DIR / "models" / "Guanaco-7B" / "guanaco-7b-uncensored.Q4_K_M.gguf",
        "backend": "gguf",
        "params": {
            "n_ctx": 2048,
            "n_gpu_layers": 20,
            "temperature": 0.2,
            "top_p": 0.5,
            "repeat_penalty": 1.15,
            "max_tokens": 80,
        }
    }
}

DEFAULT_MODEL = "mistral_7b"
