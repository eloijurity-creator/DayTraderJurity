import os
import random
from datetime import datetime
from flask import Flask, render_template, jsonify, request
import google.generativeai as genai

app = Flask(__name__)

# --- CONFIGURAÇÃO DA JURITY IA (GEMINI) ---
# Lembre-se de configurar a variável GEMINI_KEY no painel do Render (Environment)
GEMINI_KEY = os.environ.get("GEMINI_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY, transport='rest')

# --- BANCO DE DADOS EM MEMÓRIA ---
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
def index():
    return render_template('index.html')

# --- RECEBE PREÇOS DO MT5 (PC) ---
@app.route('/atualizar_dados', methods=['POST'])
def atualizar_dados():
    data = request.json
    ativo = data.get('ativo')
    if ativo in dados_mercado:
        dados_mercado[ativo]['preco'] = data.get('preco')
        dados_mercado[ativo]['status'] = "Conectado"
        
        # Inteligência Estratégica Simbolizada (Sugestão Dourada)
        sorteio = random.random()
        if sorteio > 0.99: dados_mercado[ativo]['sugestao'] = "COMPRA"
        elif sorteio < 0.01: dados_mercado[ativo]['sugestao'] = "VENDA"
        else: dados_mercado[ativo]['sugestao'] = "NEUTRO"
    return jsonify({"status": "ok"})

# --- RECEBE FINANCEIRO DO MT5 (PC) ---
@app.route('/atualizar_financeiro', methods=['POST'])
def atualizar_financeiro():
    global financeiro, historico_equity
    data = request.json
    financeiro.update(data)
    
    # Gestão do Gráfico (Máximo 30 pontos para não estourar)
    agora = datetime.now().strftime('%H:%M:%S')
    saldo = data.get('saldo_atual', 0)
    if not historico_equity or (historico_equity[-1]['y'] != saldo):
        historico_equity.append({'x': agora, 'y': saldo})
    if len(historico_equity) > 30:
        historico_equity.pop(0)
    return jsonify({"status": "ok"})

# --- CHAT INTELIGENTE (GEMINI) ---
@app.route('/chat', methods=['POST'])
def chat():
    pergunta = request.json.get('mensagem', '')
    if not GEMINI_KEY:
        return jsonify({"resposta": "Chave Gemini não configurada. Verifique as variáveis de ambiente."})

    contexto = f"""
    Você é a Jurity IA. Assistente de Day Trade.
    Dados: WIN: {dados_mercado['WIN']['preco']} | WDO: {dados_mercado['WDO']['preco']}
    Conta: {financeiro['conta']} | Saldo: R$ {financeiro['saldo_atual']}
    Resultado Hoje: R$ {financeiro['resultado_dia']} | Ordens: {len(financeiro['posicoes'])}
    Instrução: Responda em Português-BR, seja técnica e curta.
    Pergunta: {pergunta}
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(contexto)
        return jsonify({"resposta": response.text})
    except:
        return jsonify({"resposta": "Estou processando os dados, tente novamente em breve."})

# --- GESTÃO DE ORDENS (DASHBOARD -> MT5) ---
@app.route('/order', methods=['POST'])
def order():
    # Agora recebe lotes, sl_pontos e tp_pontos da boleta
    fila_comandos.append(request.json)
    return jsonify({"status": "enviado"})

@app.route('/get_orders')
def get_orders():
    if fila_comandos:
        return jsonify(fila_comandos.pop(0))
    return jsonify({})

# --- ROTAS DE CONSULTA PARA O INDEX.HTML ---
@app.route('/get_signal')
def get_signal(): return jsonify(dados_mercado.get(request.args.get('ativo'), {}))

@app.route('/get_financeiro')
def get_financeiro(): return jsonify(financeiro)

@app.route('/get_historico')
def get_historico(): return jsonify(historico_equity)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
