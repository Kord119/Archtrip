"""
Инструменты для чтения веб-страниц
"""
import requests
from bs4 import BeautifulSoup
from crewai.tools import tool
from urllib.parse import urlparse
from config import is_safe_url


@tool("Read webpage content")
def read_webpage(url: str, max_length: int = 5000) -> str:
    """
    Читает содержимое веб-страницы и возвращает текст.
    
    Параметры:
    - url: адрес страницы
    - max_length: максимальная длина текста
    """
    try:
        # Проверка безопасности
        if not is_safe_url(url):
            return f"⚠️ Доступ к {url} ограничен политикой безопасности"
        
        # Добавляем протокол если нет
        if not urlparse(url).scheme:
            url = "https://" + url
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Парсинг HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Удаляем ненужные элементы
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()
        
        # Извлекаем текст
        text = soup.get_text(separator='\n', strip=True)
        
        # Очищаем
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = '\n'.join(lines)
        
        # Ограничиваем длину
        if len(text) > max_length:
            text = text[:max_length] + "\n... [текст обрезан]"
        
        return f"📄 Содержимое {url}:\n\n{text}"
        
    except requests.exceptions.Timeout:
        return f"❌ Страница {url} не отвечает (timeout)"
    except requests.exceptions.HTTPError as e:
        return f"❌ Ошибка HTTP {e.response.status_code} для {url}"
    except Exception as e:
        return f"❌ Ошибка чтения {url}: {str(e)}"