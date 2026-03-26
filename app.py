import os
import random
from datetime import datetime
from flask import Flask, render_template, jsonify, request
import google.generativeai as genai

app = Flask(__name__)

# --- CONFIGURAÇÃO DA JURITY IA (GEMINI) ---
GEMINI_KEY = os.environ.get("GEMINI_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY, transport='rest')

# Dados Globais de Controle
dados_mercado = {
    "WIN": {"preco": 0, "sugestao": "NEUTRO", "status": "Offline"},
    "WDO": {"preco": 0, "sugestao": "NEUTRO", "status": "Offline"}
}
financeiro = {
    "resultado_dia": 0, 
    "saldo_atual": 0, 
    "conta": "Desconectado", 
    "posicoes": []
}
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
        # Lógica de Sugestão (Simulada para demonstração)
        sorteio = random.random()
        if sorteio > 0.99: dados_mercado[ativo]['sugestao'] = "COMPRA"
        elif sorteio < 0.01: dados_mercado[ativo]['sugestao'] = "VENDA"
        else: dados_mercado[ativo]['sugestao'] = "NEUTRO"
    return jsonify({"status": "ok"})

@app.route('/atualizar_financeiro', methods=['POST'])
def atualizar_financeiro():
    global financeiro, historico_equity
    data = request.json
    financeiro.update(data)
    
    # Registro de histórico para o gráfico (Máximo 30 pontos)
    agora = datetime.now().strftime('%H:%M:%S')
    saldo = data.get('saldo_atual', 0)
    if not historico_equity or (historico_equity[-1]['y'] != saldo):
        historico_equity.append({'x': agora, 'y': saldo})
    if len(historico_equity) > 30: historico_equity.pop(0)
    return jsonify({"status": "ok"})

@app.route('/chat', methods=['POST'])
def chat():
    pergunta = request.json.get('mensagem', '')
    contexto = f"""
    Você é a Jurity IA Analista. Dados de mercado atuais:
    WIN: {dados_mercado['WIN']['preco']} | WDO: {dados_mercado['WDO']['preco']}
    Saldo: R$ {financeiro['saldo_atual']} | Resultado hoje: R$ {financeiro['resultado_dia']}
    Posições abertas: {len(financeiro['posicoes'])}
    Responda em Português-BR de forma técnica e curta sobre o mercado ou conta.
    Pergunta: {pergunta}
    """
    modelos = ['gemini-1.5-flash', 'gemini-pro']
    for m in modelos:
        try:
            model = genai.GenerativeModel(m)
            response = model.generate_content(contexto)
            return jsonify({"resposta": response.text})
        except: continue
    return jsonify({"resposta": "Jurity está processando os alvos. Tente novamente."})

# Rotas de Integração Dashboard <-> MT5
@app.route('/get_signal')
def get_signal(): return jsonify(dados_mercado.get(request.args.get('ativo'), {}))
@app.route('/get_financeiro')
def get_financeiro(): return jsonify(financeiro)
@app.route('/get_historico')
def get_historico(): return jsonify(historico_equity)
@app.route('/order', methods=['POST'])
def order(): 
    fila_comandos.append(request.json)
    return jsonify({"status": "comando_enviado"})
@app.route('/get_orders')
def get_orders(): return jsonify(fila_comandos.pop(0)) if fila_comandos else jsonify({})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
