"""Where the downloaded files live. All of it is OUTSIDE the repository (weights and binaries never enter it)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("IMAGEM_LAUDO_MODELOS", str(Path.home() / "imagem-laudo-modelos")))
LLAMA_SERVER = ROOT / "llama" / "bin" / "llama-server.exe"
RESULTS = ROOT / "results"

SMOLVLM2 = (ROOT / "smolvlm2" / "SmolVLM2-2.2B-Instruct-Q4_K_M.gguf", ROOT / "smolvlm2" / "mmproj-SmolVLM2-2.2B-Instruct-Q8_0.gguf")
QWEN_VL_7B = (ROOT / "qwen25vl" / "Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf", ROOT / "qwen25vl" / "mmproj-Qwen2.5-VL-7B-Instruct-Q8_0.gguf")
QWEN_TEXT_1_5B = (ROOT / "qwen15b" / "qwen2.5-1.5b-instruct-q4_k_m.gguf", None)
OPENCLIP = ROOT / "clip" / "open_clip_model.safetensors"
