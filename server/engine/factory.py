from server.engine.llm import LocalLLM
from server.engine.gguf_llm import GGUFLLM


def create_llm(engine: str, model_path: str, params: dict):
    if engine == "local":
        return LocalLLM(model_path=model_path, params=params)

    if engine == "gguf":
        return GGUFLLM(model_path=model_path, params=params)

    raise ValueError(f"Unknown LLM engine: {engine}")