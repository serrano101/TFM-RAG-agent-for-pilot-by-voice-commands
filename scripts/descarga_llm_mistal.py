from huggingface_hub import snapshot_download
from pathlib import Path

# Path relativo al root del proyecto para portabilidad
mistral_models_path = Path(__file__).resolve().parent.parent / "models_data" / "llms" / "mistral_models" / "7B-Instruct-v0.3"
mistral_models_path.mkdir(parents=True, exist_ok=True)

snapshot_download(
    repo_id="mistralai/Mistral-7B-Instruct-v0.3",
    allow_patterns=["params.json", "consolidated.safetensors", "tokenizer.model.v3"],
    local_dir=str(mistral_models_path)
)
