"""
Конфигурация проекта
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ─── Ollama ───
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen3.5:9b")

# ─── Настройки агента для 9B модели ───
AGENT_TEMPERATURE = 0.3
AGENT_MAX_ITER = 12
AGENT_CONTEXT_WINDOW = 8192

# ─── API ключи ───
AVIASALES_API_KEY = os.getenv("AVIASALES_API_KEY", "")
RZD_API_KEY = os.getenv("RZD_API_KEY", "")
YANDEX_RASP_API_KEY = os.getenv("YANDEX_RASP_API_KEY", "")

# ─── Безопасность ───
ALLOWED_DOMAINS = [
    "aviasales.ru",
    "rzd.ru",
    "tutu.ru",
    "wikipedia.org",
    "travelpayouts.com",
]


def is_safe_url(url: str) -> bool:
    """Проверяет что URL в белом списке"""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        return any(domain.endswith(d) for d in ALLOWED_DOMAINS)
    except:
        return False