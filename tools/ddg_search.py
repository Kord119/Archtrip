"""
Инструменты поиска DuckDuckGo
"""
from crewai.tools import tool
from duckduckgo_search import DDGS


@tool("DuckDuckGo Search")
def ddg_search(query: str, max_results: int = 5) -> str:
    """
    Ищет информацию в интернете через DuckDuckGo.
    Используй когда нужна актуальная информация из сети.
    
    Параметры:
    - query: поисковый запрос
    - max_results: количество результатов (по умолчанию 5)
    """
    try:
        max_results = min(max_results, 10)
        results = []
        
        with DDGS() as ddgs:
            search_results = list(ddgs.text(
                query,
                max_results=max_results,
                region="ru-ru"
            ))
            
            if not search_results:
                return f"По запросу '{query}' ничего не найдено."
            
            for i, result in enumerate(search_results, 1):
                title = result.get('title', 'Без заголовка')
                url = result.get('href', 'N/A')
                body = result.get('body', 'Нет описания')[:300]
                
                results.append(
                    f"{i}. {title}\n"
                    f"   URL: {url}\n"
                    f"   {body}"
                )
        
        output = f"🔍 Результаты поиска '{query}' ({len(results)} найдено):\n\n"
        output += "\n\n".join(results)
        
        return output
        
    except Exception as e:
        return f"❌ Ошибка поиска: {str(e)}"


@tool("DuckDuckGo News Search")
def ddg_news(query: str, max_results: int = 5) -> str:
    """
    Ищет НОВОСТИ через DuckDuckGo.
    Используй для поиска свежих новостей и событий.
    """
    try:
        max_results = min(max_results, 10)
        results = []
        
        with DDGS() as ddgs:
            news_results = list(ddgs.news(
                query,
                max_results=max_results,
                region="ru-ru"
            ))
            
            if not news_results:
                return f"Новости по запросу '{query}' не найдены."
            
            for i, item in enumerate(news_results, 1):
                title = item.get('title', 'Без заголовка')
                source = item.get('source', 'Неизвестно')
                date = item.get('date', 'Дата неизвестна')
                url = item.get('url', 'N/A')
                body = item.get('body', '')[:200]
                
                results.append(
                    f"{i}. {title}\n"
                    f"   Источник: {source}\n"
                    f"   Дата: {date}\n"
                    f"   URL: {url}\n"
                    f"   {body}"
                )
        
        output = f"📰 Новости по запросу '{query}':\n\n"
        output += "\n\n".join(results)
        
        return output
        
    except Exception as e:
        return f"❌ Ошибка поиска новостей: {str(e)}"