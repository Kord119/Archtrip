
from crewai import Agent, Task, Crew, Process, LLM
from config import OLLAMA_BASE_URL, MODEL_NAME, AGENT_TEMPERATURE
from tools import (
    ddg_search, ddg_news, read_webpage,
    search_flights, search_trains_with_prices, get_price_breakdown
)


# ─── Подключение к Ollama ───
llm = LLM(
    model=f"ollama/{MODEL_NAME}",
    base_url=OLLAMA_BASE_URL,
    temperature=AGENT_TEMPERATURE,
    timeout=120,
)


# ─── Агент 1: Веб-исследователь (ЕДИНСТВЕННЫЙ с DuckDuckGo) ───
web_researcher = Agent(
    role="Web Researcher",
    goal="Find information on the internet",
    backstory="""Ты — веб-исследователь.
    Ищешь информацию через DuckDuckGo и читаешь страницы.""",
    tools=[ddg_search, ddg_news, read_webpage],
    llm=llm,
    verbose=True,
    allow_delegation=False,
    max_iter=8,
)


# ─── Агент 2: Авиабилеты ───
flight_scout = Agent(
    role="Flight Scout",
    goal="Find flight options with exact prices",
    backstory="""Ты — агент по поиску авиабилетов.
    Используешь ТОЛЬКО данные из search_flights.""",
    tools=[search_flights],          
    llm=llm,
    verbose=True,
    allow_delegation=False,
    max_iter=8,
)


# ─── Агент 3: Поезда с ценами по вагонам ───
train_scout = Agent(
    role="Train Price Specialist",
    goal="Find trains with EXACT prices per car type (platskart, kupe, SV)",
    backstory="""Ты — специалист по ж/д тарифам.
    Используешь ТОЛЬКО search_trains_with_prices.
    НИКОГДА не придумывай цены — бери их из инструмента.
    Всегда показывай разбивку: плацкарт, купе, СВ.""",
    tools=[search_trains_with_prices, get_price_breakdown],  
    llm=llm,
    verbose=True,
    allow_delegation=False,
    max_iter=8,
)


# ─── Агент 4: Итоговый аналитик (БЕЗ инструментов и БЕЗ DuckDuckGo) ───
travel_analyst = Agent(
    role="Travel Analyst",
    goal="Compare options using ONLY data from previous tasks",
    backstory="""Ты — итоговый аналитик.
    ВАЖНЫЕ ПРАВИЛА:
    1. Используй ТОЛЬКО данные из предыдущих задач (цены из инструментов).
    2. НЕ ищи ничего в интернете.
    3. НЕ придумывай цены — цитируй только то, что получили другие агенты.
    4. Выводи таблицу цен по типам вагонов для поездов.""",
    tools=[],                        
    llm=llm,
    verbose=True,
    allow_delegation=False,
    max_iter=6,
)


# ─── Задачи ───

def create_flight_task(from_city: str, to_city: str, date: str, 
                        time_from: int = None, time_to: int = None):
    time_filter = ""
    if time_from is not None and time_to is not None:
        time_filter = f"\nВАЖНО: Ищи рейсы с отправлением между {time_from:02d}:00 и {time_to:02d}:00."
    
    return Task(
        description=f"""
        Найди авиабилеты {from_city} → {to_city} на {date}.
        Используй search_flights.{time_filter}
        """,
        expected_output="Список рейсов с точными ценами",
        agent=flight_scout,
    )


def create_train_task(from_city: str, to_city: str, date: str,
                      time_from: int = None, time_to: int = None):
    time_filter = ""
    if time_from is not None and time_to is not None:
        time_filter = f"\nВАЖНО: Ищи поезда с отправлением между {time_from:02d}:00 и {time_to:02d}:00."
    
    return Task(
        description=f"""
        Найди поезда {from_city} → {to_city} на {date}.
        Используй search_trains_with_prices.
        ОБЯЗАТЕЛЬНО покажи цены по типам вагонов:
        плацкарт, купе, СВ, сидячий.{time_filter}
        """,
        expected_output="""
        Список поездов с разбивкой цен по типам вагонов:
        - Номер и название поезда
        - Время отправления/прибытия
        - Цена: плацкарт X₽, купе Y₽, СВ Z₽
        """,
        agent=train_scout,
    )


def create_comparison_task(from_city: str, to_city: str, date: str, 
                          budget: int = None,
                          time_from: int = None, time_to: int = None):
    budget_text = f"Бюджет: {budget}₽" if budget else "Бюджет не указан"
    time_text = f"\nПредпочтительное время отправления: {time_from:02d}:00-{time_to:02d}:00" if time_from else ""
    
    return Task(
        description=f"""
        Сравни варианты на основе данных из предыдущих задач.
        Маршрут: {from_city} → {to_city}, {date}
        {budget_text}{time_text}
        
        ПРАВИЛА:
        - Используй ТОЛЬКО цены из результатов предыдущих задач
        - НЕ используй интернет
        - Для поездов покажи таблицу: плацкарт/купе/СВ с ценами
        - Укажи лучший вариант с обоснованием
        """,
        expected_output="""
        ИТОГОВАЯ РЕКОМЕНДАЦИЯ (без веб-поиска):
        1. Лучший вариант: транспорт, номер, время
        2. Таблица цен по типам вагонов (для поезда)
        3. Обоснование выбора
        4. Альтернативы с ценами
        """,
        agent=travel_analyst,
        context=[
            create_flight_task(from_city, to_city, date, time_from, time_to),
            create_train_task(from_city, to_city, date, time_from, time_to)
        ],
    )


def create_ticket_crew(from_city: str, to_city: str, date: str, 
                      budget: int = None,
                      time_from: int = None, time_to: int = None):
    """Создаёт команду для поиска билетов с фильтрацией по времени"""
    
    flight_task = create_flight_task(from_city, to_city, date, time_from, time_to)
    train_task = create_train_task(from_city, to_city, date, time_from, time_to)
    comparison_task = create_comparison_task(
        from_city, to_city, date, budget, time_from, time_to
    )
    
    crew = Crew(
        agents=[flight_scout, train_scout, travel_analyst],
        tasks=[flight_task, train_task, comparison_task],
        process=Process.sequential,
        verbose=True,
        memory=False,
    )
    
    return crew


def create_research_crew(query: str):
    research_task = Task(
        description=f"""
        Найди информацию: "{query}"
        Используй DuckDuckGo, прочитай 2-3 страницы.
        """,
        expected_output="Краткое резюме найденной информации",
        agent=web_researcher,
    )
    
    crew = Crew(
        agents=[web_researcher],
        tasks=[research_task],
        process=Process.sequential,
        verbose=True,
        memory=False,
    )
    
    return crew