# app/llm_local.py
from typing import Optional
from .config import settings
import json, os

# Try import llama-cpp-python (may not be present in all envs)
try:
    from llama_cpp import Llama
    LLM_AVAILABLE = True
except Exception:
    LLM_AVAILABLE = False
    Llama = None

class LocalLLM:
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or settings.ggml_model_path
        self.client = None

        # Only attempt to instantiate if llama_cpp is installed AND model path exists on disk
        if LLM_AVAILABLE:
            if self.model_path and os.path.isfile(self.model_path):
                try:
                    # Increase context window to accommodate router/agent prompts
                    self.client = Llama(model_path=self.model_path, n_ctx=2048)
                    print("[LocalLLM] Loaded local Llama model.")
                except Exception as e:
                    # If instantiation fails, log and keep client None (avoid destructor issues)
                    print("[LocalLLM] Failed to instantiate Llama:", e)
                    self.client = None
            else:
                # don't attempt to call Llama() with a missing path — avoids partial-construction destructor errors
                print(f"[LocalLLM] Model path does not exist or not provided: {self.model_path!r}. Running in fallback mode.")
        else:
            print("[LocalLLM] llama-cpp-python not available; running in fallback mode.")

    def generate(self, prompt: str, max_tokens: int = 256, temperature: float = 0.0) -> str:
        """
        Use llama-cpp to generate text if available; otherwise return deterministic fallback JSON.
        """
        if self.client is None:
            # fallback deterministic JSON for router tests
            fallback = {"intent":"unknown","confidence":0.5,"entities":{},"reasoning":"no-local-llm"}
            return json.dumps(fallback)
        try:
            resp = self.client(prompt, max_tokens=max_tokens, temperature=temperature)
            if isinstance(resp, dict):
                # Llama returns dict with 'choices' list
                return resp.get('choices', [{}])[0].get('text', '')
            return str(resp)
        except Exception as e:
            print("[LocalLLM] generation error:", e)
            return json.dumps({"intent":"unknown","confidence":0.5,"entities":{},"reasoning":"error"})
