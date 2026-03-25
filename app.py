from flask import Flask, render_template, jsonify, request
from datetime import datetime
import random # Para simular oscilação da estratégia se não houver dados

app = Flask(__name__)

dados_mercado = {
    "WIN": {"preco": 0, "sinal": "AGUARDANDO", "cor": "#f0b90b", "status": "Offline", "sugestao": "NEUTRO"},
    "WDO": {"preco": 0, "sinal": "AGUARDANDO", "cor": "#f0b90b", "status": "Offline", "sugestao": "NEUTRO"}
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
        preco = data.get('preco')
        dados_mercado[ativo]['preco'] = preco
        dados_mercado[ativo]['status'] = "Conectado"
        
        # Lógica de Inteligência Estratégica (Exemplo: Baseado em preço redondo ou aleatório para teste)
        # Aqui você pode integrar com seu modelo de sinais real
        sorteio = random.random()
        if sorteio > 0.95: dados_mercado[ativo]['sugestao'] = "COMPRA"
        elif sorteio < 0.05: dados_mercado[ativo]['sugestao'] = "VENDA"
        else: dados_mercado[ativo]['sugestao'] = "NEUTRO"
        
    return jsonify({"status": "ok"})

@app.route('/atualizar_financeiro', methods=['POST'])
def atualizar_financeiro():
    global financeiro, historico_equity
    data = request.json
    financeiro.update(data)
    agora = datetime.now().strftime('%H:%M:%S')
    saldo = data.get('saldo_atual', 0)
    
    # FIX DO GRÁFICO: Só adiciona se o saldo mudar ou passar tempo, e limita o tamanho
    if not historico_equity or (historico_equity[-1]['y'] != saldo):
        historico_equity.append({'x': agora, 'y': saldo})
    if len(historico_equity) > 30: historico_equity.pop(0)
    return jsonify({"status": "ok"})

@app.route('/get_historico')
def get_historico(): return jsonify(historico_equity)

@app.route('/get_signal')
def get_signal():
    ativo = request.args.get('ativo')
    return jsonify(dados_mercado.get(ativo, {}))

@app.route('/get_financeiro')
def get_financeiro(): return jsonify(financeiro)

@app.route('/order', methods=['POST'])
def order():
    # Recebe ordens do dashboard (Compra/Venda/Pânico)
    fila_comandos.append(request.json)
    return jsonify({"status": "comando_enviado"})

@app.route('/get_orders')
def get_orders():
    return jsonify(fila_comandos.pop(0)) if fila_comandos else jsonify({})

@app.route('/chat', methods=['POST'])
def chat():
    msg = request.json.get('mensagem', '').lower()
    return jsonify({"resposta": "Analisando o fluxo de ordens... Tendência de alta no curto prazo."})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
