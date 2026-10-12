"""
Главная точка входа
"""
from agents import create_ticket_crew, create_research_crew


def print_header():
    print("""
    ╔══════════════════════════════════════════╗
    ║   🎫 AI АГЕНТ ПО ПОИСКУ БИЛЕТОВ        ║
    ║   Ollama + CrewAI + DuckDuckGo         ║
    ╚══════════════════════════════════════════╝
    """)


def search_tickets():
    print("\n🎫 РЕЖИМ ПОИСКА БИЛЕТОВ")
    print("-" * 40)
    
    from_city = input("Откуда: ").strip()
    to_city = input("Куда: ").strip()
    date = input("Дата (YYYY-MM-DD): ").strip()
    
    # НОВОЕ: предпочтительное время
    print("\n⏰ Предпочтительное время:")
    print("1. 🌅 Утро (06:00-12:00)")
    print("2. ☀️ День (12:00-18:00)")
    print("3. 🌆 Вечер (18:00-00:00)")
    print("4. 🌙 Ночь (00:00-06:00)")
    print("5. ⏱️ Любое время")
    
    time_choice = input("Ваш выбор (1-5): ").strip()
    
    time_map = {
        "1": {"label": "Утро", "from": 6, "to": 12},
        "2": {"label": "День", "from": 12, "to": 18},
        "3": {"label": "Вечер", "from": 18, "to": 24},
        "4": {"label": "Ночь", "from": 0, "to": 6},
        "5": None,
    }
    
    time_preference = time_map.get(time_choice)
    
    budget_input = input("Бюджет (опционально, Enter чтобы пропустить): ").strip()
    budget = int(budget_input) if budget_input.isdigit() else None
    
    if not from_city or not to_city or not date:
        print("❌ Заполните все обязательные поля!")
        return
    
    time_text = f", предпочтительное время: {time_preference['label']}" if time_preference else ""
    print(f"\n🔍 Поиск билетов {from_city} → {to_city} на {date}{time_text}...")
    print("Это может занять 1-3 минуты.\n")
    
    try:
        crew = create_ticket_crew(
            from_city, to_city, date, budget,
            time_from=time_preference["from"] if time_preference else None,
            time_to=time_preference["to"] if time_preference else None,
        )
        result = crew.kickoff()
        
        print("\n" + "=" * 60)
        print("✅ РЕЗУЛЬТАТ:")
        print("=" * 60)
        print(result)
        
    except Exception as e:
        print(f"❌ Ошибка: {str(e)}")

def web_research():
    print("\n🔍 РЕЖИМ ВЕБ-ИССЛЕДОВАНИЯ")
    print("-" * 40)
    
    query = input("Что найти в интернете? ").strip()
    
    if not query:
        print("❌ Введите запрос!")
        return
    
    print(f"\n🔍 Поиск информации по запросу: '{query}'...")
    print("Это может занять 1-2 минуты.\n")
    
    try:
        crew = create_research_crew(query)
        result = crew.kickoff()
        
        print("\n" + "=" * 60)
        print("✅ РЕЗУЛЬТАТ:")
        print("=" * 60)
        print(result)
        
    except Exception as e:
        print(f"❌ Ошибка: {str(e)}")


def main():
    print_header()
    
    while True:
        print("\nВыберите режим:")
        print("1. 🎫 Поиск билетов")
        print("2. 🔍 Веб-исследование")
        print("3. 🚪 Выход")
        
        choice = input("\nВаш выбор (1/2/3): ").strip()
        
        if choice == '1':
            search_tickets()
        elif choice == '2':
            web_research()
        elif choice == '3':
            print("\n👋 До свидания!")
            break
        else:
            print("❌ Неверный выбор. Введите 1, 2 или 3.")
        
        input("\nНажмите Enter для продолжения...")


if __name__ == "__main__":
    main()