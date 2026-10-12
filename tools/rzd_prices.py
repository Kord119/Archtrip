"""
Цены на ж/д билеты с разбивкой по типам вагонов.
РЕАЛЬНЫЕ цены через rzd-api get_minimal_prices + расписание из search_tickets.
"""
from datetime import datetime, timedelta
from crewai.tools import tool


# ═══ СПРАВОЧНИК РАССТОЯНИЙ И ТАРИФЫ ═══
ROUTE_DISTANCES = {
    frozenset(["москва", "ярославль"]): 270,
    frozenset(["москва", "санкт-петербург"]): 650,
    frozenset(["москва", "нижний новгород"]): 400,
    frozenset(["москва", "владимир"]): 190,
    frozenset(["москва", "тверь"]): 167,
    frozenset(["москва", "казань"]): 720,
    frozenset(["москва", "воронеж"]): 460,
    frozenset(["москва", "ростов-на-дону"]): 1070,
    frozenset(["москва", "краснодар"]): 1230,
    frozenset(["москва", "сочи"]): 1360,
    frozenset(["москва", "екатеринбург"]): 1780,
    frozenset(["москва", "самара"]): 860,
    frozenset(["москва", "уфа"]): 1160,
    frozenset(["москва", "новосибирск"]): 3300,
    frozenset(["москва", "красноярск"]): 4100,
}

CAR_TYPE_RATES = {"Сидячий": 1.6, "Плацкарт": 2.3, "Купе": 3.4, "СВ": 6.2}
BASE_FARE = {"Сидячий": 200, "Плацкарт": 350, "Купе": 500, "СВ": 900}

EN_CAR_TYPE_MAP = {
    "compartment": "Купе",
    "couchette": "Купе",
    "reservedseat": "Плацкарт",
    "reserved_seat": "Плацкарт",
    "sedenary": "Сидячий",
    "sedentary": "Сидячий",
    "seating": "Сидячий",
    "luxury": "СВ",
    "sleeper": "СВ",
    "first_class": "СВ",
    "second_class": "Купе",
    "third_class": "Плацкарт",
}
# ═══ РУССКИЕ НАЗВАНИЯ ТИПОВ ВАГОНОВ (из raw CarTypeName) ═══
RU_CAR_TYPE_MAP = {
    "куп": "Купе",
    "плац": "Плацкарт",
    "св": "СВ",
    "сид": "Сидячий",
    "люкс": "Люкс",
    "мягк": "Люкс",
    "общ": "Сидячий",
}


def _is_disabled_car(car, raw: dict) -> bool:
    """Проверяет, предназначено ли место/вагон для инвалидов"""
    # Прямые атрибуты объекта
    for attr in ("is_for_disabled_persons", "is_disabled", "for_disabled"):
        if getattr(car, attr, False):
            return True
    
    # Поля в raw (IsForDisabledPersons и похожие)
    for key, val in raw.items():
        if "disabled" in key.lower():
            if val is True or str(val).lower() == "true":
                return True
    
    # Упоминание в описании
    desc = str(raw.get("CarDescription", "") or "").lower()
    if "инвалид" in desc or "disabled" in desc:
        return True
    
    return False


def _parse_carriage_result(carriage_result) -> dict:
    """
    Парсит CarriageResult в {тип_вагона: мин_цена}.
    ВАГОНЫ ДЛЯ ИНВАЛИДОВ ИСКЛЮЧАЮТСЯ.
    """
    cars = {}
    car_list = getattr(carriage_result, "cars", []) or []
    
    for car in car_list:
        raw = getattr(car, "raw", {}) or {}
        
        # === ПРОПУСКАЕМ МЕСТА ДЛЯ ИНВАЛИДОВ ===
        if _is_disabled_car(car, raw):
            continue
        
        # Русское название из raw (КУПЕ, ПЛАЦКАРТ...)
        ru_name_raw = str(raw.get("CarTypeName", "") or "").lower()
        # Английское из car_type (Compartment...)
        en_name = str(getattr(car, "car_type", "") or "").lower()
        
        # Цена
        price = getattr(car, "min_price", None)
        if price is None:
            price = raw.get("MinPrice")
        
        # Определяем тип: сначала по русскому, потом по английскому
        car_type = None
        for key, val in RU_CAR_TYPE_MAP.items():
            if key in ru_name_raw:
                car_type = val
                break
        if not car_type:
            car_type = EN_CAR_TYPE_MAP.get(en_name)
        if not car_type and en_name:
            car_type = en_name.title()
        
        if car_type and price is not None:
            try:
                p = int(float(price))
                if car_type not in cars or p < cars[car_type]:
                    cars[car_type] = p
            except (ValueError, TypeError):
                pass
    
    return cars

def _get_distance(from_city: str, to_city: str) -> int:
    key = frozenset([from_city.lower(), to_city.lower()])
    return ROUTE_DISTANCES.get(key, 800)


def _calc_price(car_type: str, distance: int, factor: float) -> int:
    raw = (BASE_FARE[car_type] + CAR_TYPE_RATES[car_type] * distance) * factor
    return int(round(raw, -1))


def _get_attr(obj, names: list, default=None):
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
        if isinstance(obj, dict) and name in obj:
            return obj[name]
    return default


def _to_hhmm(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%H:%M")
    s = str(value)
    return s[11:16] if len(s) >= 16 and "T" in s else s[:5]


def _pick_best_station(stations):
    if not stations:
        return None
    for st in stations:
        if _get_attr(st, ["node_type", "nodeType"], "") == "city":
            return st
    return stations[0]


def _extract_station_code(station):
    if isinstance(station, (str, int)):
        return str(station)
    return str(_get_attr(station, ["code", "station_code", "expressCode"], ""))


def _parse_minimal_pricing(result) -> dict:
    """Извлекает из MinimalPricingResult словарь {номер: {тип: цена}}"""
    trains = {}
    
    prices = getattr(result, "prices", []) or []
    
    for price_entry in prices:
        carriers = getattr(price_entry, "carriers", []) or []
        
        for carrier in carriers:
            train_list = _get_attr(carrier, ["Trains", "trains"], []) or []
            
            for train in train_list:
                number = str(_get_attr(train, ["TrainName", "train_name"], "") or "")
                if not number or number == "None":
                    continue
                
                car_types = _get_attr(train, ["CarTypes", "car_types"], []) or []
                
                if number not in trains:
                    trains[number] = {}
                
                for ct in car_types:
                    ct_name = str(_get_attr(ct, ["CarTypeName", "car_type_name"], "") or "").lower()
                    ct_price = _get_attr(ct, ["MinPrice", "min_price"], None)
                    is_disabled = _get_attr(ct, ["IsForDisabledPersons", "is_for_disabled"], False)
                    
                    if is_disabled:
                        continue
                    
                    ru_name = EN_CAR_TYPE_MAP.get(ct_name)
                    if ru_name and ct_price:
                        try:
                            p = int(round(float(ct_price)))
                            if ru_name not in trains[number] or p < trains[number][ru_name]:
                                trains[number][ru_name] = p
                        except (ValueError, TypeError):
                            pass
    
    return trains


def _try_real_rzd_prices(from_city: str, to_city: str, date: str):
    """
    Получает ТОЧНЫЕ цены через get_carriages для каждого поезда.
    """
    try:
        from rzd_api import RzdClient
    except ImportError:
        print("⚠️ rzd-api не установлен")
        return None
    
    client = None
    try:
        client = RzdClient()
        
        # 1. Станции
        from_st = _extract_station_code(_pick_best_station(client.find_stations(from_city)))
        to_st = _extract_station_code(_pick_best_station(client.find_stations(to_city)))
        
        if not from_st or not to_st:
            return None
        print(f"✅ Станции РЖД: {from_st} → {to_st}")
        
        # 2. Расписание поездов
        routes = client.search_tickets(from_st, to_st, date)
        if not isinstance(routes, list):
            routes = _get_attr(routes, ["outbound", "trains", "routes"], []) or []
        
        if not routes:
            print("⚠️ Поезда не найдены")
            return None
        print(f"✅ Найдено поездов: {len(routes)}")
        
        # 3. ТОЧНЫЕ цены через get_carriages для каждого поезда
        parsed = []
        for route in routes[:5]:  # первые 5 поездов
            number = str(_get_attr(route, ["number", "train_number"], "") or "")
            if not number:
                continue
            
            # Время отправления — строка, вырезаем HH:MM
            dep = str(_get_attr(route, ["departure_time", "departure"], "") or "")
            dep_hm = dep[11:16] if len(dep) >= 16 else dep
            
            cars = {}
            try:
                cr = client.get_carriages(from_st, to_st, date, dep_hm, number)
                cars = _parse_carriage_result(cr)
                if cars:
                    print(f"   🚃 {number}: {len(cars)} типов вагонов с ценами")
            except Exception as e:
                print(f"⚠️ get_carriages {number}: {e}")
            
            if cars:
                parsed.append({
                    "number": number,
                    "name": str(_get_attr(route, ["name", "title", "brand"], "") or ""),
                    "departure": dep_hm,
                    "arrival": _to_hhmm(_get_attr(route, ["arrival_time", "arrival"], None)),
                    "duration": str(_get_attr(route, ["duration", "travel_time"], "N/A")),
                    "days": 0,
                    "cars": cars,
                })
        
        return parsed if parsed else None
        
    except Exception as e:
        print(f"⚠️ rzd-api ошибка: {e}")
        return None
    finally:
        if client:
            try:
                client.close()
            except Exception:
                pass


def _generate_trains(from_city: str, to_city: str, distance: int):
    templates = [
        {"number": "001А", "name": "Фирменный экспресс", "dep": "06:40",
         "factor": 1.3, "speed": 85, "types": ["Сидячий", "Купе", "СВ"]},
        {"number": "023А", "name": "Дневной экспресс", "dep": "12:15",
         "factor": 1.15, "speed": 75, "types": ["Сидячий", "Плацкарт", "Купе"]},
        {"number": "045А", "name": "Ночной поезд", "dep": "22:30",
         "factor": 1.0, "speed": 65, "types": ["Плацкарт", "Купе", "СВ"]},
    ]
    
    trains = []
    for t in templates:
        hours = distance / t["speed"]
        h, m = int(hours), int((hours % 1) * 60)
        dep_h, dep_m = map(int, t["dep"].split(":"))
        total = dep_h * 60 + dep_m + h * 60 + m
        
        trains.append({
            "number": t["number"], "name": t["name"],
            "departure": t["dep"],
            "arrival": f"{(total // 60) % 24:02d}:{total % 60:02d}",
            "days": total // 1440,
            "duration": f"{h}ч {m:02d}м",
            "cars": {ct: _calc_price(ct, distance, t["factor"]) for ct in t["types"]},
        })
    return trains

def _filter_by_time(trains: list, time_from: int = None, time_to: int = None) -> list:
    """Фильтрует поезда по времени отправления"""
    if time_from is None or time_to is None:
        return trains
    
    filtered = []
    for t in trains:
        dep_str = t.get("departure", "")
        if not dep_str or ":" not in dep_str:
            continue
        
        try:
            hour = int(dep_str.split(":")[0])
            
            # Обработка ночного времени (18:00-24:00)
            if time_from > time_to:  # например 18 > 6 (вечер+ночь)
                if hour >= time_from or hour < time_to:
                    filtered.append(t)
            else:  # обычный диапазон
                if time_from <= hour < time_to:
                    filtered.append(t)
        except (ValueError, IndexError):
            continue
    
    return filtered if filtered else trains  # если ничего не нашли — возвращаем все
@tool("Search trains with prices")
def search_trains_with_prices(from_city: str, to_city: str, date: str, 
                             time_from: int = None, time_to: int = None) -> str:
    """
    Ищет поезда с ТОЧНЫМИ ценами по типам вагонов.
    
    Параметры:
    - from_city: город отправления
    - to_city: город прибытия
    - date: дата YYYY-MM-DD
    - time_from: час начала (0-23, опционально)
    - time_to: час конца (0-23, опционально)
    """
    try:
        distance = _get_distance(from_city, to_city)
        
        real_trains = _try_real_rzd_prices(from_city, to_city, date)
        
        if real_trains:
            trains, source = real_trains, "🟢 РЕАЛЬНЫЕ данные РЖД (ticket.rzd.ru)"
        else:
            trains = _generate_trains(from_city, to_city, distance)
            source = "🟡 Оценка по тарифам РЖД"
        
        # Фильтрация по времени
        if time_from is not None and time_to is not None:
            original_count = len(trains)
            trains = _filter_by_time(trains, time_from, time_to)
            if len(trains) < original_count:
                source += f" (фильтр: {time_from:02d}:00-{time_to:02d}:00, найдено {len(trains)} из {original_count})"
        
        if not trains:
            return f"🚂 Поезда {from_city} → {to_city} на {date} в указанное время не найдены"
        
        result = f"""🚂 ПОЕЗДА {from_city.upper()} → {to_city.upper()}
📅 Дата: {date}
📊 Источник цен: {source}
"""
        for i, t in enumerate(trains, 1):
            result += f"""
{'─' * 50}
{i}. ПОЕЗД №{t['number']} «{t['name']}»"""
            if t["departure"]:
                result += f"\n   Отправление: {t['departure']} → Прибытие: {t['arrival']}"
            if t.get("days", 0) > 0:
                result += f" (+{t['days']} дн.)"
            if t["duration"] and t["duration"] != "N/A":
                result += f"\n   В пути: {t['duration']}"
            if t["cars"]:
                result += "\n   💰 ЦЕНЫ ПО ТИПАМ ВАГОНОВ:"
                for car_type, price in t["cars"].items():
                    icon = {"Сидячий": "💺", "Плацкарт": "🛏️", "Купе": "🚪",
                            "СВ": "⭐", "Люкс": "👑"}.get(car_type, "•")
                    result += f"\n      {icon} {car_type}: {price}₽"
            else:
                result += "\n   💰 Цены: см. блок минимальных цен выше"
        
        result += f"\n\n{'─' * 50}\n🔗 Покупка: https://www.rzd.ru/\n"
        return result
        
    except Exception as e:
        return f"❌ Ошибка поиска поездов: {str(e)}"


@tool("Get price breakdown")
def get_price_breakdown(from_city: str, to_city: str) -> str:
    """Быстрая справка по ценам между городами без даты"""
    distance = _get_distance(from_city, to_city)
    result = f"""💰 ЦЕНЫ {from_city.upper()} → {to_city.upper()} (~{distance} км)

Диапазон цен по типам вагонов:
"""
    for ct in ["Сидячий", "Плацкарт", "Купе", "СВ"]:
        result += f"   {ct}: {_calc_price(ct, distance, 1.0)}–{_calc_price(ct, distance, 1.3)}₽\n"
    return result