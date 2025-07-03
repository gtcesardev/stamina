from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from datetime import datetime, timedelta
import os

app = Flask(__name__)
CORS(app)

class StaminaCalculator:
    def __init__(self):
        self.limite_laranja = 39.0
        self.max_stamina = 42.0
    
    def parse_stamina(self, stamina_str):
        """Parse stamina string no formato HH:MM"""
        try:
            if ':' not in stamina_str:
                raise ValueError("Use o formato HH:MM")
            h, m = map(int, stamina_str.split(':'))
            if not (0 <= m < 60 and h >= 0):
                raise ValueError("Valores inválidos")
            if h > 42 or (h == 42 and m > 0):
                raise ValueError("Stamina máxima é 42:00!")
            return h, m
        except ValueError as e:
            raise ValueError(f"Formato de stamina inválido! {str(e)}")
    
    def parse_datetime(self, date_str, time_str):
        """Parse data e hora strings"""
        try:
            date = datetime.strptime(date_str, "%d/%m/%Y")
            time = datetime.strptime(time_str, "%H:%M")
            return datetime.combine(date.date(), time.time())
        except:
            raise ValueError("Data/hora inválida! Use DD/MM/AAAA e HH:MM")
    
    def calculate_offline_time(self, current_stamina):
        """Calcula tempo offline necessário para recuperar stamina"""
        if current_stamina >= self.max_stamina:
            raise ValueError("Stamina já está cheia!")
        
        if current_stamina < self.limite_laranja:
            orange = self.limite_laranja - current_stamina
            green = self.max_stamina - self.limite_laranja
        else:
            orange = 0.0
            green = self.max_stamina - current_stamina
        
        total_offline = (orange * 3) + (green * 6)
        return orange, green, total_offline
    
    def calculate_exact_stamina(self, current_stamina, offline_hours):
        """Calcula stamina exata após tempo offline"""
        if offline_hours is None:
            return None
        
        if current_stamina < self.limite_laranja:
            orange_time = (self.limite_laranja - current_stamina) * 3
            if offline_hours <= orange_time:
                return current_stamina + (offline_hours / 3)
            else:
                recovered_orange = self.limite_laranja - current_stamina
                remaining_time = offline_hours - orange_time
                recovered_green = remaining_time / 6
                return min(self.limite_laranja + recovered_green, self.max_stamina)
        else:
            recovered_green = offline_hours / 6
            return min(current_stamina + recovered_green, self.max_stamina)
    
    def hours_to_hhmm(self, hours):
        """Converte horas decimais para formato HH:MM"""
        h = int(hours)
        m = int((hours - h) * 60)
        return f"{h:02d}:{m:02d}"
    
    def hours_to_ddhh(self, hours):
        """Converte horas para formato DDd HHh MMm"""
        days = int(hours // 24)
        h = hours % 24
        m = int((h - int(h)) * 60)
        if days > 0:
            return f"{days}d {int(h):02d}h {m:02d}m"
        else:
            return f"{int(h):02d}h {m:02d}m"

calculator = StaminaCalculator()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/calculate', methods=['POST'])
def calculate_stamina():
    try:
        data = request.json
        
        # Validar dados obrigatórios
        required_fields = ['current_stamina', 'logout_date', 'logout_time']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Campo {field} é obrigatório'}), 400
        
        # Parse stamina atual
        stamina_str = data['current_stamina'].strip()
        horas, minutos = calculator.parse_stamina(stamina_str)
        current_stamina = horas + minutos / 60
        
        # Parse logout
        logout_date_str = data['logout_date'].strip()
        logout_time_str = data['logout_time'].strip()
        logout_time = calculator.parse_datetime(logout_date_str, logout_time_str)
        
        # Parse login opcional
        login_date_str = data.get('login_date', '').strip()
        login_time_str = data.get('login_time', '').strip()
        has_login_time = login_date_str and login_time_str
        
        offline_hours = None
        login_time = None
        
        if has_login_time:
            login_time = calculator.parse_datetime(login_date_str, login_time_str)
            if login_time <= logout_time:
                return jsonify({'error': 'Login deve ser após o logout!'}), 400
            offline_hours = (login_time - logout_time).total_seconds() / 3600
        
        # Calcular recuperação
        orange, green, total_offline = calculator.calculate_offline_time(current_stamina)
        exact_recovery = calculator.calculate_exact_stamina(current_stamina, offline_hours)
        
        # Calcular tempo para stamina cheia
        full_time = logout_time + timedelta(hours=total_offline)
        
        # Preparar resposta
        response = {
            'current_stamina': {
                'hours': horas,
                'minutes': minutos,
                'formatted': f"{horas:02d}:{minutos:02d}"
            },
            'recovery': {
                'orange_hours': orange,
                'green_hours': green,
                'orange_formatted': calculator.hours_to_hhmm(orange),
                'green_formatted': calculator.hours_to_hhmm(green),
                'orange_offline_time': calculator.hours_to_hhmm(orange * 3),
                'green_offline_time': calculator.hours_to_hhmm(green * 6),
                'total_offline_hours': total_offline,
                'total_offline_formatted': calculator.hours_to_ddhh(total_offline)
            },
            'full_stamina_time': {
                'datetime': full_time.strftime('%d/%m/%Y %H:%M'),
                'timestamp': full_time.timestamp()
            }
        }
        
        # Adicionar stamina futura se calculada
        if exact_recovery is not None:
            stamina_future = min(exact_recovery, 42.0)
            h_future = int(stamina_future)
            m_future = int((stamina_future - h_future) * 60)
            response['future_stamina'] = {
                'hours': h_future,
                'minutes': m_future,
                'formatted': f"{h_future:02d}:{m_future:02d}",
                'login_time': login_time.strftime('%d/%m/%Y %H:%M')
            }
        
        return jsonify(response)
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'OK', 'message': 'Tibia Stamina Calculator API'})

if __name__ == '__main__':
    # Criar diretório templates se não existir
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    app.run(debug=True, host='0.0.0.0', port=5000)