from flask import Flask, render_template, jsonify, request
from datetime import datetime
import random

app = Flask(__name__)

# Dados para WIN e WDO
dados_mercado = {
    "WIN": {"preco": 0, "sugestao": "NEUTRO", "status": "Offline"},
    "WDO": {"preco": 0, "sugestao": "NEUTRO", "status": "Offline"}
}
financeiro = {"resultado_dia": 0, "saldo_atual": 0, "conta": "Desconectado", "posicoes": []}
historico_equity = []
fila_comandos = []

@app.route('/')
def index(): return render_template('index.html')

@app.route('/atualizar_dados', methods=['POST'])
def atualizar_dados():
    data = request.json
    ativo = data.get('ativo')
    if ativo in dados_mercado:
        dados_mercado[ativo]['preco'] = data.get('preco')
        dados_mercado[ativo]['status'] = "Conectado"
        # Lógica de Sugestão IA (Simulada)
        sorteio = random.random()
        if sorteio > 0.97: dados_mercado[ativo]['sugestao'] = "COMPRA"
        elif sorteio < 0.03: dados_mercado[ativo]['sugestao'] = "VENDA"
        else: dados_mercado[ativo]['sugestao'] = "NEUTRO"
    return jsonify({"status": "ok"})

@app.route('/atualizar_financeiro', methods=['POST'])
def atualizar_financeiro():
    global financeiro, historico_equity
    data = request.json
    financeiro.update(data)
    agora = datetime.now().strftime('%H:%M:%S')
    saldo = data.get('saldo_atual', 0)
    # Fix do Gráfico: Limite de 30 pontos
    if not historico_equity or (historico_equity[-1]['y'] != saldo):
        historico_equity.append({'x': agora, 'y': saldo})
    if len(historico_equity) > 30: historico_equity.pop(0)
    return jsonify({"status": "ok"})

@app.route('/get_signal')
def get_signal():
    ativo = request.args.get('ativo')
    return jsonify(dados_mercado.get(ativo, {}))

@app.route('/get_financeiro')
def get_financeiro(): return jsonify(financeiro)

@app.route('/get_historico')
def get_historico(): return jsonify(historico_equity)

@app.route('/order', methods=['POST'])
def order():
    fila_comandos.append(request.json)
    return jsonify({"status": "ok"})

@app.route('/get_orders')
def get_orders():
    return jsonify(fila_comandos.pop(0)) if fila_comandos else jsonify({})

@app.route('/chat', methods=['POST'])
def chat():
    msg = request.json.get('mensagem', '').lower()
    resp = "Analisando o fluxo... O mercado apresenta volatilidade estável nos contratos vigentes."
    if "win" in msg: resp = "O Mini Índice está em zona de suporte. Observe o volume."
    if "wdo" in msg: resp = "O Dólar mostra pressão vendedora no curto prazo."
    return jsonify({"resposta": resp})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
