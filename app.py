from flask import Flask, render_template, jsonify, request
from datetime import datetime

app = Flask(__name__)

# Memória global para o Dashboard
dados_mercado = {
    "WIN": {"preco": 0, "sinal": "NEUTRO", "cor": "#f0b90b", "status": "Offline"},
    "WDO": {"preco": 0, "sinal": "NEUTRO", "cor": "#f0b90b", "status": "Offline"}
}
financeiro = {
    "resultado_dia": 0, "saldo_atual": 0, "conta": "Desconectado", "posicoes": []
}
historico_equity = []
fila_comandos = []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/atualizar_dados', methods=['POST'])
def atualizar_dados():
    data = request.json
    ativo = data.get('ativo')
    if ativo in dados_mercado:
        dados_mercado[ativo].update({"preco": data.get('preco'), "status": "Conectado"})
    return jsonify({"status": "ok"})

@app.route('/atualizar_financeiro', methods=['POST'])
def atualizar_financeiro():
    global financeiro, historico_equity
    data = request.json
    financeiro.update(data)
    
    # Atualiza gráfico de performance
    agora = datetime.now().strftime('%H:%M:%S')
    saldo = data.get('saldo_atual', 0)
    if not historico_equity or historico_equity[-1]['y'] != saldo:
        historico_equity.append({'x': agora, 'y': saldo})
    if len(historico_equity) > 50: historico_equity.pop(0)
    
    return jsonify({"status": "ok"})

@app.route('/get_financeiro')
def get_financeiro(): return jsonify(financeiro)

@app.route('/get_historico')
def get_historico(): return jsonify(historico_equity)

@app.route('/get_signal')
def get_signal():
    ativo = request.args.get('ativo')
    return jsonify(dados_mercado.get(ativo, {}))

@app.route('/order', methods=['POST'])
def order():
    fila_comandos.append(request.json)
    return jsonify({"status": "comando_recebido"})

@app.route('/get_orders')
def get_orders():
    return jsonify(fila_comandos.pop(0)) if fila_comandos else jsonify({})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
