import network
import socket
import json
from machine import CAN
import _thread
import time
from collections import deque

# Configurações
MAX_HISTORICO = 1000  # Número máximo de mensagens no histórico
FILTROS_PGN = {
    'motor': [61444, 65262, 65263],  # Engine data
    'posicao': [65267],              # Position data
    'ambiente': [65269],             # Ambient conditions
    'implemento': [65097, 65098]     # Implement data
}

# Estrutura de dados
dados_can = {
    'engine_data': {
        'rpm': 0,
        'engine_load': 0,
        'torque': 0,
        'coolant_temp': 0,
        'fuel_temp': 0,
        'oil_pressure': 0,
        'fuel_pressure': 0,
        'ultima_atualizacao': 0
    },
    'position_data': {
        'latitude': 0,
        'longitude': 0,
        'altitude': 0,
        'velocidade': 0,
        'ultima_atualizacao': 0
    },
    'ambient_data': {
        'temperatura_ambiente': 0,
        'temperatura_ar': 0,
        'ultima_atualizacao': 0
    },
    'implement_data': {
        'status': {},
        'ultima_atualizacao': 0
    },
    'estatisticas': {
        'mensagens_total': 0,
        'mensagens_por_pgn': {},
        'ultima_atualizacao': 0
    }
}

# Fila circular para histórico de mensagens por categoria
historico = {
    'motor': deque(maxlen=MAX_HISTORICO),
    'posicao': deque(maxlen=MAX_HISTORICO),
    'ambiente': deque(maxlen=MAX_HISTORICO),
    'implemento': deque(maxlen=MAX_HISTORICO)
}

def setup_wifi():
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.connect('sua_rede', 'sua_senha')
        
        # Aguarda conexão com timeout
        timeout = 0
        while not wlan.isconnected() and timeout < 10:
            time.sleep(1)
            timeout += 1
            
        if wlan.isconnected():
            print('Conectado! IP:', wlan.ifconfig()[0])
            return True
        else:
            print('Falha na conexão WiFi')
            return False
            
    except Exception as e:
        print(f'Erro na configuração WiFi: {e}')
        return False

def atualizar_dados(decoded_msg):
    """Atualiza os dados com base no PGN recebido"""
    try:
        pgn = decoded_msg['pgn']
        valores = decoded_msg['spn_vals']
        timestamp = time.time()
        
        # Atualiza estatísticas
        dados_can['estatisticas']['mensagens_total'] += 1
        dados_can['estatisticas']['mensagens_por_pgn'][pgn] = \
            dados_can['estatisticas']['mensagens_por_pgn'].get(pgn, 0) + 1
        
        # Processa dados do motor
        if pgn in FILTROS_PGN['motor']:
            if pgn == 61444:  # EEC1
                dados_can['engine_data'].update({
                    'rpm': valores.get('Engine_Speed', dados_can['engine_data']['rpm']),
                    'engine_load': valores.get('Engine_Percent_Load', dados_can['engine_data']['engine_load']),
                    'torque': valores.get('Actual_Engine_Percent_Torque', dados_can['engine_data']['torque'])
                })
            elif pgn == 65262:  # Engine Temperature
                dados_can['engine_data'].update({
                    'coolant_temp': valores.get('Engine_Coolant_Temperature', dados_can['engine_data']['coolant_temp']),
                    'fuel_temp': valores.get('Fuel_Temperature', dados_can['engine_data']['fuel_temp'])
                })
            elif pgn == 65263:  # Engine Pressures
                dados_can['engine_data'].update({
                    'oil_pressure': valores.get('Engine_Oil_Pressure', dados_can['engine_data']['oil_pressure']),
                    'fuel_pressure': valores.get('Fuel_Delivery_Pressure', dados_can['engine_data']['fuel_pressure'])
                })
            dados_can['engine_data']['ultima_atualizacao'] = timestamp
            historico['motor'].append({'timestamp': timestamp, 'dados': valores})
            
        # Processa dados de posição
        elif pgn in FILTROS_PGN['posicao']:
            dados_can['position_data'].update({
                'latitude': valores.get('Latitude', dados_can['position_data']['latitude']),
                'longitude': valores.get('Longitude', dados_can['position_data']['longitude'])
            })
            dados_can['position_data']['ultima_atualizacao'] = timestamp
            historico['posicao'].append({'timestamp': timestamp, 'dados': valores})
            
        # Processa dados ambientais
        elif pgn in FILTROS_PGN['ambiente']:
            dados_can['ambient_data'].update({
                'temperatura_ambiente': valores.get('Ambient_Air_Temperature', dados_can['ambient_data']['temperatura_ambiente']),
                'temperatura_ar': valores.get('Air_Inlet_Temperature', dados_can['ambient_data']['temperatura_ar'])
            })
            dados_can['ambient_data']['ultima_atualizacao'] = timestamp
            historico['ambiente'].append({'timestamp': timestamp, 'dados': valores})
            
        # Processa dados do implemento
        elif pgn in FILTROS_PGN['implemento']:
            dados_can['implement_data']['status'].update(valores)
            dados_can['implement_data']['ultima_atualizacao'] = timestamp
            historico['implemento'].append({'timestamp': timestamp, 'dados': valores})
            
    except Exception as e:
        print(f"Erro ao atualizar dados: {e}")

def processar_requisicao(request):
    """Processa requisições HTTP com filtros"""
    try:
        # Verifica se há parâmetros de filtro na URL
        if '?' in request:
            path, params = request.split('?', 1)
            params = dict(param.split('=') for param in params.split('&'))
        else:
            params = {}
        
        response_data = {}
        
        # Filtra por categoria
        if 'categoria' in params:
            categorias = params['categoria'].split(',')
            for cat in categorias:
                if cat == 'motor':
                    response_data['engine_data'] = dados_can['engine_data']
                elif cat == 'posicao':
                    response_data['position_data'] = dados_can['position_data']
                elif cat == 'ambiente':
                    response_data['ambient_data'] = dados_can['ambient_data']
                elif cat == 'implemento':
                    response_data['implement_data'] = dados_can['implement_data']
        else:
            response_data = dados_can
            
        # Filtra histórico
        if 'historico' in params:
            response_data['historico'] = {}
            categorias_hist = params['historico'].split(',')
            for cat in categorias_hist:
                if cat in historico:
                    response_data['historico'][cat] = list(historico[cat])
                    
        # Adiciona estatísticas se solicitado
        if 'estatisticas' in params:
            response_data['estatisticas'] = dados_can['estatisticas']
            
        return response_data
        
    except Exception as e:
        print(f"Erro ao processar requisição: {e}")
        return {'erro': str(e)}

def web_server():
    if not setup_wifi():
        return
        
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 80))
    s.listen(5)
    
    while True:
        try:
            conn, addr = s.accept()
            request = conn.recv(1024).decode('utf-8').split('\r\n')[0]
            
            # Processa a requisição com filtros
            response_data = processar_requisicao(request)
            
            # Envia resposta
            response = json.dumps(response_data)
            conn.send('HTTP/1.1 200 OK\n')
            conn.send('Content-Type: application/json\n')
            conn.send('Access-Control-Allow-Origin: *\n')
            conn.send('Connection: close\n\n')
            conn.send(response.encode())
            conn.close()
            
        except Exception as e:
            print(f"Erro no servidor web: {e}")
            time.sleep(1)

# Inicia o servidor em uma thread separada
_thread.start_new_thread(web_server, ()) 