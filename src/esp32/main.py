from machine import CAN, Pin
import time
from j1939_parser import J1939Parser

# Configuração do CAN bus
try:
    can = CAN(0,                            
              mode=CAN.NORMAL,              
              baudrate=250000,              
              tx_pin=Pin(5),                
              rx_pin=Pin(4))
    print("CAN bus inicializado com sucesso!")
except Exception as e:
    print(f"Erro ao inicializar CAN bus: {e}")
    raise e

# Inicializa o parser J1939
parser = J1939Parser()

def decode_can_message(msg_id, data):
    """Decodifica mensagens usando J1939Parser"""
    try:
        # Log dos dados brutos recebidos
        print(f"Dados brutos - ID: {hex(msg_id)}, Data: {bytes(data).hex()}")
        
        decoded = parser.parse_message(msg_id, data)
        if decoded:
            print(f"Mensagem decodificada: {decoded}")
            return decoded
            
        # Se não conseguiu decodificar, retorna dados brutos
        raw_result = {
            'pgn': (msg_id >> 8) & 0x1FFFF,
            'spn_vals': {},
            'raw_data': bytes(data).hex()
        }
        print(f"Mensagem não reconhecida: {raw_result}")
        return raw_result
        
    except Exception as e:
        print(f"Erro ao decodificar: {e}")
        return None

def main():
    print("Iniciando monitoramento CAN...")
    mensagens_recebidas = 0
    ultima_impressao = time.time()
    
    while True:
        try:
            msg = can.recv(timeout=1000)
            if msg:
                mensagens_recebidas += 1
                msg_id, _, _, data = msg
                
                # Imprime estatísticas a cada 5 segundos
                if time.time() - ultima_impressao >= 5:
                    print(f"Mensagens recebidas nos últimos 5s: {mensagens_recebidas}")
                    mensagens_recebidas = 0
                    ultima_impressao = time.time()
                
                decoded = decode_can_message(msg_id, data)
                if decoded and 'spn_vals' in decoded and decoded['spn_vals']:
                    print("-" * 40)
                    print(f"PGN: {decoded['pgn']}")
                    for nome, valor in decoded['spn_vals'].items():
                        print(f"{nome}: {valor}")
                    print("-" * 40)
                    
        except Exception as e:
            print(f"Erro no loop principal: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main() 