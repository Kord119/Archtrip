"""
Инструменты для поиска билетов с поддержкой Яндекс.Расписания
"""
import requests
from datetime import datetime, timedelta
from crewai.tools import tool
from config import AVIASALES_API_KEY
from tools.yandex_helper import get_station_code, search_routes


# Маппинг городов для Aviasales (коды IATA)
CITY_CODES = {
    "москва": "MOW",
    "санкт-петербург": "LED",
    "спб": "LED",
    "сочи": "AER",
    "казань": "KZN",
    "екатеринбург": "SVX",
    "новосибирск": "OVB",
    "краснодар": "KRR",
    "ростов-на-дону": "ROV",
    "самара": "KUF",
    "уфа": "UFA",
}


@tool("Search flights via Aviasales")
def search_flights(from_city: str, to_city: str, date: str,
                  time_from: int = None, time_to: int = None) -> str:
    """
    Ищет авиабилеты через Aviasales API.
    
    Параметры:
    - from_city, to_city: города
    - date: YYYY-MM-DD
    - time_from: час начала (опционально)
    - time_to: час конца (опционально)
    """
    try:
        from_code = CITY_CODES.get(from_city.lower(), from_city.upper())
        to_code = CITY_CODES.get(to_city.lower(), to_city.upper())
        
        if not AVIASALES_API_KEY:
            return _simulate_flights(from_city, to_city, date, from_code, to_code)
        
        url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
        params = {
            "origin": from_code,
            "destination": to_code,
            "departure_at": date,
            "sorting": "price",
            "currency": "rub",
            "limit": 30,  # больше для фильтрации
            "token": AVIASALES_API_KEY
        }
        
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        
        if data.get("success") and data.get("data"):
            flights = data["data"]
            
            # Фильтрация по времени
            if time_from is not None and time_to is not None:
                flights = _filter_flights_by_time(flights, time_from, time_to)
            
            result = f"""✈️ Авиабилеты {from_city} → {to_city} ({date})"""
            if time_from is not None:
                result += f"\n⏰ Время: {time_from:02d}:00-{time_to:02d}:00"
            result += f"\nНайдено {len(flights)} вариантов:\n"
            
            for i, flight in enumerate(flights[:5], 1):
                price = flight.get("price", "N/A")
                departure = flight.get("departure_at", "")[:16]
                transfers = flight.get("transfers", 0)
                transfer_text = "Прямой" if transfers == 0 else f"{transfers} перес."
                
                result += f"\n{i}. {price}₽ | {departure} | {transfer_text}"
            
            result += f"\n\n🔗 https://www.aviasales.ru/search/{from_code}{date.replace('-', '')}{to_code}1"
            return result
        
        return f"Билеты {from_city} → {to_city} не найдены."
        
    except Exception as e:
        return f"❌ Ошибка Aviasales: {str(e)}"

@tool("Search trains via Yandex Rasp")
def search_trains_yandex(from_city: str, to_city: str, date: str) -> str:
    """
    Ищет поезда через Яндекс.Расписания API.
    Параметры: from_city, to_city (русские названия), date (YYYY-MM-DD)
    """
    try:
        result = search_routes(from_city, to_city, date, transport="train", limit=5)
        
        if "error" in result:
            return f"❌ Ошибка: {result['error']}"
        
        segments = result.get("segments", [])
        if not segments:
            return f"🚂 Поездов {from_city} → {to_city} на {date} не найдено"
        
        output = f"""🚂 Поезда {from_city} ({result['from_code']}) → {to_city} ({result['to_code']})
📅 Дата: {date}

Найдено {len(segments)} поездов:
"""
        
        for i, seg in enumerate(segments, 1):
            thread = seg.get("thread", {})
            title = thread.get("title", "N/A")
            number = thread.get("number", "")
            carrier = thread.get("carrier", {}).get("title", "")
            
            departure = seg.get("departure", "")[:16]
            arrival = seg.get("arrival", "")[:16]
            duration = seg.get("duration", "N/A")
            
            stops = seg.get("stops", "")
            stops_text = f" ({stops})" if stops else ""
            
            output += f"""
{i}. {title} №{number}{stops_text}
   Перевозчик: {carrier}
   Отправление: {departure}
   Прибытие: {arrival}
   В пути: {duration}
"""
        
        output += "\n🔗 https://rasp.yandex.ru/"
        return output
        
    except Exception as e:
        return f"❌ Ошибка поиска поездов: {str(e)}"

def _filter_flights_by_time(flights: list, time_from: int = None, time_to: int = None) -> list:
    """Фильтрует рейсы по времени отправления"""
    if time_from is None or time_to is None:
        return flights
    
    filtered = []
    for f in flights:
        dep = f.get("departure_at", "")
        if not dep or "T" not in dep:
            continue
        
        try:
            hour = int(dep.split("T")[1].split(":")[0])
            if time_from > time_to:
                if hour >= time_from or hour < time_to:
                    filtered.append(f)
            else:
                if time_from <= hour < time_to:
                    filtered.append(f)
        except (ValueError, IndexError):
            continue
    
    return filtered if filtered else flights
@tool("Search all transport via Yandex")
def search_all_transport(from_city: str, to_city: str, date: str) -> str:
    """
    Ищет все виды транспорта через Яндекс.Расписания (поезда, самолёты, автобусы).
    Параметры: from_city, to_city (русские названия), date (YYYY-MM-DD)
    """
    try:
        result = search_routes(from_city, to_city, date, transport="all", limit=10)
        
        if "error" in result:
            return f"❌ Ошибка: {result['error']}"
        
        segments = result.get("segments", [])
        if not segments:
            return f"Транспорт {from_city} → {to_city} на {date} не найден"
        
        output = f"""🚆 Все виды транспорта {from_city} → {to_city}
📅 Дата: {date}

Найдено {len(segments)} вариантов:
"""
        
        for i, seg in enumerate(segments, 1):
            thread = seg.get("thread", {})
            transport_type = thread.get("transport_type", "")
            title = thread.get("title", "N/A")
            number = thread.get("number", "")
            
            departure = seg.get("departure", "")[:16]
            arrival = seg.get("arrival", "")[:16]
            
            icon = {"train": "🚂", "plane": "✈️", "bus": "🚌"}.get(transport_type, "🚗")
            
            output += f"\n{i}. {icon} {title} №{number} | {departure} → {arrival}"
        
        return output
        
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"


@tool("Parse travel dates")
def parse_dates(request: str) -> str:
    """Извлекает даты из запроса пользователя."""
    today = datetime.now()
    
    if "завтра" in request.lower():
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    elif "послезавтра" in request.lower():
        return (today + timedelta(days=2)).strftime("%Y-%m-%d")
    elif "сегодня" in request.lower():
        return today.strftime("%Y-%m-%d")
    else:
        import re
        match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', request)
        if match:
            day, month, year = match.groups()
            return f"{year}-{month}-{day}"
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")


def _simulate_flights(from_city, to_city, date, from_code, to_code):
    """Симуляция авиабилетов если нет API ключа"""
    flights = [
        {"flight": "SU1234", "airline": "Аэрофлот", "price": 8500},
        {"flight": "S71001", "airline": "S7 Airlines", "price": 7200},
        {"flight": "UT555", "airline": "Utair", "price": 6800}
    ]
    
    result = f"""⚠️ Режим симуляции (нет API Aviasales)
✈️ {from_city} ({from_code}) → {to_city} ({to_code}) на {date}:\n"""
    
    for i, f in enumerate(flights, 1):
        result += f"\n{i}. {f['flight']} {f['airline']} — {f['price']}₽"
    
    result += f"\n\n🔗 https://www.aviasales.ru/"
    return result