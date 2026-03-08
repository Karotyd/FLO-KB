from llama_cpp.llama import Llama


class LocalLLM:
    def __init__(self, model_path: str, params: dict):
        self.llm = Llama(
            model_path=model_path,
            n_ctx=params.get("n_ctx", 2048),
            n_gpu_layers=params.get("n_gpu_layers", 0),
        )

        self.generation_params = {
            "temperature": params.get("temperature", 0.2),
            "top_p": params.get("top_p", 0.5),
            "repeat_penalty": params.get("repeat_penalty", 1.2),
            "max_tokens": params.get("max_tokens", 80),
            "stop": ["\nUtilisateur:", "\n###"],
        }

        self.history: list[str] = []

        self.system_prompt = (
            "Tu es un assistant strictement obéissant.\n"
            "Tu réponds uniquement à la demande de l'utilisateur.\n"
            "Tu réponds en français.\n"
            "Tu fais des réponses courtes et directes.\n"
            "Tu ne reformules pas la question.\n"
            "Tu ne poses pas de questions.\n"
            "Tu ne prends pas d'initiative.\n"
            "Si on te demande de dire un mot ou une phrase précise, "
            "tu la dis exactement.\n"
        )

    def chat(self, message: str) -> str:
        self.history.append(f"Utilisateur: {message}")

        prompt = (
            self.system_prompt
            + "\n"
            + "\n".join(self.history)
            + "\nAssistant:"
        )

        output = self.llm(prompt, **self.generation_params)

        response = output["choices"][0]["text"].strip()
        self.history.append(f"Assistant: {response}")

        return response
