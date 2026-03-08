from llama_cpp import Llama

MISTRAL_TEMPLATE = """### Instruction:
{system_prompt}

### Historique:
{history}

### Utilisateur:
{user_input}

### Réponse:
"""

class GGUFLLM:
    def __init__(self, model_path: str, params: dict):
        self.llm = Llama(
            model_path=model_path,
            n_ctx=params.get("n_ctx", 2048),
            n_threads=params.get("n_threads", 8),
            n_gpu_layers=params.get("n_gpu_layers", 0),
            verbose=False,
        )

        self.generation_params = {
            "temperature": params.get("temperature", 0.2),
            "top_p": params.get("top_p", 0.5),
            "repeat_penalty": params.get("repeat_penalty", 1.2),
            "max_tokens": params.get("max_tokens", 80),
            "stop": params.get("stop", ["\nUtilisateur:", "\n###"]),
        }

        self.system_prompt = params.get(
            "system_prompt",
            "Tu es un assistant strictement obéissant. Tu réponds en français.",
        )

    def generate(self, user_input: str, history: list[str]) -> str:
        history_text = "\n".join(history)

        prompt = MISTRAL_TEMPLATE.format(
            system_prompt=self.system_prompt,
            history=history_text,
            user_input=user_input,
        )

        output = self.llm(prompt, **self.generation_params)
        return output["choices"][0]["text"].strip()

    def generate_stream(self, user_input: str, history: list[str]):
        history_text = "\n".join(history)

        prompt = MISTRAL_TEMPLATE.format(
            system_prompt=self.system_prompt,
            history=history_text,
            user_input=user_input,
        )

        for chunk in self.llm(
            prompt,
            stream=True,
            **self.generation_params,
        ):
            token = chunk["choices"][0]["text"]
            if token:
                yield token
