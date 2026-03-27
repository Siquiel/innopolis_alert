from flask import Flask, render_template, jsonify, url_for, request, send_file
from datetime import datetime
from weather import weather_service
import pandas as pd
from io import BytesIO
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Хранилище ЧС (4 тестовых ЧС включая БПЛА)
emergencies = [
    {
        'id': 1,
        'type': 'fire',
        'title': 'Пожар в жилом доме',
        'description': 'Горит квартира на 3 этаже, требуется эвакуация',
        'lat': 55.751244,
        'lon': 48.732884,
        'timestamp': datetime.now().isoformat(),
        'status': 'active'
    },
    {
        'id': 2,
        'type': 'drone',
        'title': 'Угроза атаки БПЛА',
        'description': 'Обнаружен беспилотник в воздушном пространстве',
        'timestamp': datetime.now().isoformat(),
        'status': 'active'
    },
    {
        'id': 3,
        'type': 'accident',
        'title': 'Крупное ДТП',
        'description': 'Столкнулись 3 автомобиля, перекрыта полоса движения',
        'lat': 55.750500,
        'lon': 48.734000,
        'timestamp': datetime.now().isoformat(),
        'status': 'active'
    },
    {
        'id': 4,
        'type': 'gas',
        'title': 'Утечка газа',
        'description': 'Повреждение газопровода, ведётся ремонт',
        'lat': 55.753000,
        'lon': 48.735000,
        'timestamp': datetime.now().isoformat(),
        'status': 'active'
    }
]

# === СТРАНИЦЫ ===

@app.route('/')
def index():
    """Главная страница - карта"""
    return render_template('map.html')

# === API ===

@app.route('/api/emergencies')
def get_emergencies():
    """Получить все ЧС"""
    return jsonify(emergencies)

@app.route('/api/emergency', methods=['POST'])
def add_emergency():
    """Добавить новую ЧС"""
    data = request.json
    data['id'] = len(emergencies) + 1
    data['timestamp'] = datetime.now().isoformat()
    data['status'] = 'active'
    emergencies.append(data)
    return jsonify({'success': True, 'id': data['id']})

@app.route('/api/weather')
def api_weather():
    """Получить погоду и прогноз"""
    weather = weather_service.get_current_weather()
    dangers = weather_service.get_dangerous_weather()
    forecast = weather_service.get_forecast()
    return jsonify({
        'weather': weather,
        'dangers': dangers,
        'forecast': forecast,
        'timestamp': datetime.now().isoformat()
    })

# === ЭКСПОРТ ===

@app.route('/export/excel')
def export_excel():
    """Экспорт всех ЧС в Excel"""
    if not emergencies:
        return jsonify({'error': 'Нет данных'}), 400
    
    df = pd.DataFrame(emergencies)
    type_names = {'fire': 'Пожар', 'power': 'Отключение электричества', 'gas': 'Утечка газа', 'accident': 'ДТП', 'drone': 'Угроза БПЛА', 'weather': 'Погода', 'other': 'Прочее'}
    df['type_name'] = df['type'].map(type_names)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='ЧС', index=False)
    
    output.seek(0)
    filename = f'otchet_CHS_{datetime.now().strftime("%Y%m%d")}.xlsx'
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

@app.route('/export/stats')
def export_stats():
    """Экспорт статистики в Excel"""
    stats = {
        'total': len(emergencies),
        'active': len([e for e in emergencies if e.get('status') == 'active']),
        'by_type': {}
    }
    
    for emi in emergencies:
        t = emi.get('type', 'unknown')
        stats['by_type'][t] = stats['by_type'].get(t, 0) + 1
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pd.DataFrame({
            'Показатель': ['Всего ЧС', 'Активных'],
            'Значение': [stats['total'], stats['active']]
        }).to_excel(writer, sheet_name='Статистика', index=False)
        
        pd.DataFrame({
            'Тип': list(stats['by_type'].keys()),
            'Количество': list(stats['by_type'].values())
        }).to_excel(writer, sheet_name='По типам', index=False)
    
    output.seek(0)
    filename = f'statistika_{datetime.now().strftime("%Y%m%d")}.xlsx'
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)