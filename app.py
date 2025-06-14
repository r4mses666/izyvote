from flask import Flask, request, jsonify, render_template_string, render_template
from flask_cors import CORS
import hashlib
import json
import time
import os
from collections import defaultdict

# ---- Clases de Blockchain ----
class Voto:
    def __init__(self, votante_id, candidato):
        self.votante_id = votante_id
        self.candidato = candidato
        self.timestamp = time.time()

    def to_dict(self):
        return {
            'votante_id': self.votante_id,
            'candidato': self.candidato,
            'timestamp': self.timestamp
        }

class Bloque:
    def __init__(self, indice, votos, hash_anterior):
        self.indice = indice
        self.timestamp = time.time()
        self.votos = votos
        self.hash_anterior = hash_anterior
        self.nonce = 0
        self.hash = self.calcular_hash()

    def calcular_hash(self):
        bloque_str = json.dumps({
            'indice': self.indice,
            'timestamp': self.timestamp,
            'votos': [v.to_dict() for v in self.votos],
            'hash_anterior': self.hash_anterior,
            'nonce': self.nonce
        }, sort_keys=True).encode()
        return hashlib.sha256(bloque_str).hexdigest()

    def minar_bloque(self, dificultad):
        objetivo = '0' * dificultad
        while self.hash[:dificultad] != objetivo:
            self.nonce += 1
            self.hash = self.calcular_hash()
        print(f"✅ Bloque minado: {self.hash}")
        return self.hash

class BlockchainVotos:
    def __init__(self):
        self.dificultad = 2
        self.cadena = [self._crear_bloque_genesis()]
        self.votos_pendientes = []
        self.votantes_ya_votaron = set()

    def _crear_bloque_genesis(self):
        return Bloque(0, [], '0')

    def obtener_ultimo_bloque(self):
        return self.cadena[-1]

    def agregar_voto(self, votante_id, candidato):
        if votante_id in self.votantes_ya_votaron:
            print(f"❌ Voto rechazado: {votante_id} ya votó")
            return False
        voto = Voto(votante_id, candidato)
        self.votos_pendientes.append(voto)
        self.votantes_ya_votaron.add(votante_id)
        print(f"✅ Voto agregado: {votante_id} -> {candidato}")
        return True

    def minar_votos_pendientes(self):
        if not self.votos_pendientes:
            print("ℹ️ No hay votos pendientes para minar")
            return None
        
        print(f"⛏️ Minando {len(self.votos_pendientes)} votos...")
        nuevo_bloque = Bloque(
            len(self.cadena),
            self.votos_pendientes.copy(),
            self.obtener_ultimo_bloque().hash
        )
        nuevo_bloque.minar_bloque(self.dificultad)
        self.cadena.append(nuevo_bloque)
        self.votos_pendientes = []
        print(f"🔗 Nuevo bloque agregado a la cadena: #{nuevo_bloque.indice}")
        return nuevo_bloque

    def contar_votos(self):
        resultados = defaultdict(int)
        for bloque in self.cadena:
            for voto in bloque.votos:
                resultados[voto.candidato] += 1
        return dict(resultados)

    def buscar_voto_por_dni(self, dni):
        """Busca si un DNI ya votó y devuelve información del voto"""
        for bloque in self.cadena:
            for voto in bloque.votos:
                if voto.votante_id == dni:
                    return {
                        'voto': voto,
                        'bloque_indice': bloque.indice,
                        'bloque_hash': bloque.hash,
                        'timestamp': bloque.timestamp
                    }
        return None

    def get_stats(self):
        """Obtiene estadísticas generales de la blockchain"""
        total_votos = sum(len(bloque.votos) for bloque in self.cadena)
        return {
            'total_bloques': len(self.cadena),
            'total_votos': total_votos,
            'votos_pendientes': len(self.votos_pendientes),
            'ultimo_bloque': self.cadena[-1].indice if self.cadena else 0,
            'ultimo_hash': self.cadena[-1].hash if self.cadena else '0'
        }

# ---- Aplicación Flask ----
app = Flask(__name__)
CORS(app, origins="*")  # Permitir todos los orígenes para desarrollo
blockchain = BlockchainVotos()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/vote', methods=['POST'])
def vote():
    try:
        data = request.get_json()
        print(f'📨 Datos recibidos en /vote: {data}')
        
        if not data:
            return jsonify({'mensaje': 'No se recibieron datos JSON'}), 400
            
        votante = data.get('votante_id')
        candidato = data.get('candidato')
        
        if not votante or not candidato:
            return jsonify({'mensaje': 'Faltan parámetros: votante_id y candidato son requeridos'}), 400
        
        # Validar DNI
        if not votante.isdigit() or len(votante) != 7:
            return jsonify({'mensaje': 'DNI debe tener exactamente 7 dígitos numéricos'}), 400
        
        # Intentar agregar el voto
        voto_agregado = blockchain.agregar_voto(votante, candidato)
        
        if not voto_agregado:
            return jsonify({'mensaje': f'El votante {votante} ya emitió su voto anteriormente'}), 409
        
        return jsonify({
            'mensaje': 'Voto registrado exitosamente',
            'votante_id': votante,
            'candidato': candidato,
            'timestamp': time.time()
        }), 201
        
    except Exception as e:
        print(f"❌ Error en /vote: {str(e)}")
        return jsonify({'mensaje': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/mine', methods=['POST'])
def mine():
    try:
        bloque = blockchain.minar_votos_pendientes()
        if not bloque:
            return jsonify({'mensaje': 'No hay votos pendientes para minar'}), 200
        
        return jsonify({
            'mensaje': 'Bloque minado exitosamente',
            'indice': bloque.indice,
            'timestamp': bloque.timestamp,
            'hash_anterior': bloque.hash_anterior,
            'hash': bloque.hash,
            'nonce': bloque.nonce,
            'votos_count': len(bloque.votos),
            'votos': [v.to_dict() for v in bloque.votos]
        }), 201
        
    except Exception as e:
        print(f"❌ Error en /mine: {str(e)}")
        return jsonify({'mensaje': f'Error al minar: {str(e)}'}), 500

@app.route('/last_block', methods=['GET'])
def last_block():
    try:
        bloque = blockchain.obtener_ultimo_bloque()
        return jsonify({
            'indice': bloque.indice,
            'timestamp': bloque.timestamp,
            'hash_anterior': bloque.hash_anterior,
            'hash': bloque.hash,
            'nonce': bloque.nonce,
            'votos': [v.to_dict() for v in bloque.votos]
        })
    except Exception as e:
        print(f"❌ Error en /last_block: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/chain', methods=['GET'])
def full_chain():
    try:
        chain_data = []
        for bloque in blockchain.cadena:
            chain_data.append({
                'indice': bloque.indice,
                'timestamp': bloque.timestamp,
                'hash_anterior': bloque.hash_anterior,
                'hash': bloque.hash,
                'nonce': bloque.nonce,
                'votos': [v.to_dict() for v in bloque.votos]
            })
        
        return jsonify({
            'cadena': chain_data,
            'longitud': len(chain_data),
            'ultimo_hash': blockchain.obtener_ultimo_bloque().hash
        })
        
    except Exception as e:
        print(f"❌ Error en /chain: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/status/<dni>', methods=['GET'])
def check_vote_status(dni):
    """Endpoint para verificar si un DNI ya votó"""
    try:
        if not dni.isdigit() or len(dni) != 7:
            return jsonify({'mensaje': 'DNI inválido'}), 400
        # Buscar en votos pendientes primero
        for voto in blockchain.votos_pendientes:
            if voto.votante_id == dni:
                return jsonify({
                    'ya_voto': True,
                    'candidato': voto.candidato,
                    'bloque_indice': 'pendiente',
                    'timestamp': voto.timestamp,
                    'estado': 'Voto registrado pero aún no minado'
                })
        
        # Buscar en la cadena de bloque
        resultado = blockchain.buscar_voto_por_dni(dni)
        
        if resultado:
            return jsonify({
                'ya_voto': True,
                'candidato': resultado['voto'].candidato,
                'bloque_indice': resultado['bloque_indice'],
                'timestamp': resultado['timestamp']
            })
        else:
            return jsonify({
                'ya_voto': False,
                'mensaje': 'Este DNI no ha votado aún'
            })
            
    except Exception as e:
        print(f"❌ Error en /status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/results', methods=['GET'])
def get_results():
    """Endpoint dedicado para obtener resultados"""
    try:
        resultados = blockchain.contar_votos()
        total_votos = sum(resultados.values())
        
        return jsonify({
            'resultados': resultados,
            'total_votos': total_votos,
            'bloques_total': len(blockchain.cadena),
            'votos_pendientes': len(blockchain.votos_pendientes),
            'stats': blockchain.get_stats()
        })
    except Exception as e:
        print(f"❌ Error en /results: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint para verificar que el servidor está funcionando"""
    return jsonify({
        'status': 'OK',
        'mensaje': 'Servidor IzyVote funcionando correctamente',
        'timestamp': time.time(),
        'blockchain_activo': True,
        'total_bloques': len(blockchain.cadena),
        'total_votos': sum(blockchain.contar_votos().values())
    })

# ---- Manejo de errores ----
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint no encontrado'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Error interno del servidor'}), 500

# ---- Inicialización ----
def inicializar_sistema():
    """Inicialización del sistema sin votos de demostración"""
    print('\n🚀 === Inicializando IzyVote ===')
    print('📊 Sistema iniciado sin votos de demostración...')
    print(f'\n✅ Sistema listo con {len(blockchain.cadena)} bloques')
    print('=' * 50)

if __name__ == '__main__':
    # Inicializar sistema vacío
    inicializar_sistema()
    
    # Determinar configuración según el entorno
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    
    print(f'\n🌐 Iniciando servidor IzyVote...')
    print(f'📍 Puerto: {port}')
    print(f'🔧 Modo debug: {debug_mode}')
    print(f'🔗 URL local: http://localhost:{port}')
    print('\n⚡ ¡Servidor listo para recibir votos!')
    
    # Iniciar el servidor
    app.run(
        host='0.0.0.0', 
        port=port, 
        debug=debug_mode,
        threaded=True
    )
