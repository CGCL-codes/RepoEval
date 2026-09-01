import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = Path(os.getenv("REPRO_RESULTS_DIR", str(ROOT / "results")))
DEFAULT_TARGETS_FILE = ROOT / "data" / "test.json"

PROMPT_CONTEXT_RADIUS = 12
MAX_DRIVER_CHARS = 6000
RUNNER_TIMEOUT_SEC = int(os.getenv("REPRO_RUNNER_TIMEOUT_SEC", "600"))


MODEL_CONFIGS = {
    "deepseek-v3": {
        "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
        "base_url": os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1"),
        "model_name": os.getenv("DEEPSEEK_V3_MODEL", "deepseek-chat"),
        "temperature": 0.7,
    },
    "deepseek-r1": {
        "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
        "base_url": os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1"),
        "model_name": os.getenv("DEEPSEEK_R1_MODEL", "deepseek-reasoner"),
        "temperature": 0.7,
    },
    "gpt-5-mini": {
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "base_url": os.getenv("OPENAI_API_BASE", ""),
        "model_name": os.getenv("OPENAI_MODEL", "gpt-5-mini"),
        "temperature": 0.7,
    },
    "qwen3-coder-flash": {
        "api_key": os.getenv("QWEN_API_KEY", ""),
        "base_url": os.getenv("QWEN_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        "model_name": os.getenv("QWEN_MODEL", "qwen3-coder-flash"),
        "temperature": 0.7,
    },
}
