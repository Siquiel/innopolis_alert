import requests
from datetime import datetime, timedelta

class WeatherService:
    def __init__(self):
        self.city = "Innopolis"
        self.lat = 55.751244  # Координаты Иннополиса
        self.lon = 48.732884
    
    def get_current_weather(self):
        """Получить текущую погоду (Open-Meteo - без API ключа!)"""
        try:
            # Open-Meteo API (бесплатно, без ключа)
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                'latitude': self.lat,
                'longitude': self.lon,
                'current_weather': True,
                'temperature_unit': 'celsius',
                'wind_speed_unit': 'ms'
            }
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            # Получаем дополнительные данные
            weather_code = data['current_weather']['weathercode']
            
            return {
                'temp': round(data['current_weather']['temperature'], 1),
                'feels_like': round(data['current_weather']['temperature'], 1),  # Open-Meteo не даёт feels_like
                'humidity': 65,  # Open-Meteo в current_weather не даёт влажность
                'wind_speed': round(data['current_weather']['windspeed'], 1),
                'pressure': 760,  # Не доступно в бесплатной версии
                'visibility': 10,
                'description': self._get_weather_description(weather_code),
                'icon': self._get_icon(weather_code)
            }
        except Exception as e:
            print(f"Ошибка погоды: {e}")
            return None
    
    def get_forecast(self):
        """Прогноз на 2 дня (Open-Meteo)"""
        try:
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                'latitude': self.lat,
                'longitude': self.lon,
                'daily': 'temperature_2m_max,temperature_2m_min,weathercode',
                'timezone': 'Europe/Moscow'
            }
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            forecast = []
            dates = data['daily']['time']
            temps_max = data['daily']['temperature_2m_max']
            temps_min = data['daily']['temperature_2m_min']
            weather_codes = data['daily']['weathercode']
            
            # Берём завтра и послезавтра (индексы 1 и 2)
            for i in range(1, 3):
                if i < len(dates):
                    forecast.append({
                        'date': dates[i],
                        'temp_max': round(temps_max[i], 1),
                        'temp_min': round(temps_min[i], 1),
                        'condition': self._get_condition_name(weather_codes[i]),
                        'description': self._get_weather_description(weather_codes[i]),
                        'icon': self._get_icon(weather_codes[i])
                    })
            
            return forecast
        except Exception as e:
            print(f"Ошибка прогноза: {e}")
            return []
    
    def get_dangerous_weather(self):
        """Проверить опасную погоду"""
        weather = self.get_current_weather()
        if not weather:
            return []
        
        dangers = []
        
        if weather['temp'] < -20:
            dangers.append({
                'type': 'cold',
                'message': f"Сильный мороз: {weather['temp']}°C",
                'level': 'warning'
            })
        elif weather['temp'] > 30:
            dangers.append({
                'type': 'heat',
                'message': f"Сильная жара: {weather['temp']}°C",
                'level': 'warning'
            })
        
        if weather['wind_speed'] > 15:
            dangers.append({
                'type': 'wind',
                'message': f"Сильный ветер: {weather['wind_speed']} м/с",
                'level': 'danger'
            })
        
        return dangers
    
    def _get_weather_description(self, code):
        """WMO Weather interpretation codes"""
        descriptions = {
            0: 'Ясно',
            1: 'Преимущественно ясно',
            2: 'Переменная облачность',
            3: 'Пасмурно',
            45: 'Туман',
            48: 'Иней',
            51: 'Слабая морось',
            53: 'Умеренная морось',
            55: 'Сильная морось',
            61: 'Слабый дождь',
            63: 'Умеренный дождь',
            65: 'Сильный дождь',
            71: 'Слабый снег',
            73: 'Умеренный снег',
            75: 'Сильный снег',
            77: 'Снежные зёрна',
            80: 'Слабый ливень',
            81: 'Умеренный ливень',
            82: 'Сильный ливень',
            85: 'Слабый снегопад',
            86: 'Сильный снегопад',
            95: 'Гроза',
            96: 'Гроза с градом',
            99: 'Сильная гроза с градом'
        }
        return descriptions.get(code, 'Неизвестно')
    
    def _get_condition_name(self, code):
        """Короткое название условия"""
        if code == 0:
            return 'clear'
        elif code in [1, 2]:
            return 'partly_cloudy'
        elif code in [3, 45, 48]:
            return 'clouds'
        elif code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
            return 'rain'
        elif code in [71, 73, 75, 77, 85, 86]:
            return 'snow'
        elif code in [95, 96, 99]:
            return 'thunderstorm'
        return 'clear'
    
    def _get_icon(self, code):
        """WMO codes to emoji"""
        icons = {
            0: '☀️',    # Ясно
            1: '🌤',    # Преимущественно ясно
            2: '⛅',    # Переменная облачность
            3: '☁️',    # Пасмурно
            45: '🌫',   # Туман
            48: '🌫',   # Иней
            51: '🌦',   # Слабая морось
            53: '🌦',   # Умеренная морось
            55: '🌧',   # Сильная морось
            61: '🌦',   # Слабый дождь
            63: '🌧',   # Умеренный дождь
            65: '🌧',   # Сильный дождь
            71: '🌨',   # Слабый снег
            73: '🌨',   # Умеренный снег
            75: '❄️',   # Сильный снег
            77: '🌨',   # Снежные зёрна
            80: '🌦',   # Слабый ливень
            81: '🌧',   # Умеренный ливень
            82: '⛈',   # Сильный ливень
            85: '🌨',   # Слабый снегопад
            86: '❄️',   # Сильный снегопад
            95: '⛈',   # Гроза
            96: '⛈',   # Гроза с градом
            99: '⛈'    # Сильная гроза
        }
        return icons.get(code, '🌡️')

# Создание экземпляра
weather_service = WeatherService()