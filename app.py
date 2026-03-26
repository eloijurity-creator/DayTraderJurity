import os
import random
from datetime import datetime
from flask import Flask, render_template, jsonify, request
import google.generativeai as genai

app = Flask(__name__)

# --- CONFIGURAÇÃO DA JURITY IA (GEMINI 2.5 FLASH) ---
# Certifique-se de adicionar GEMINI_KEY nas "Environment Variables" do Render
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

# --- CHAT INTELIGENTE COM LOOP DE MODELOS (ORDEM DE PREFERÊNCIA) ---
@app.route('/chat', methods=['POST'])
def chat():
    pergunta = request.json.get('mensagem', '')
    if not GEMINI_KEY:
        return jsonify({"resposta": "Chave Gemini não configurada no Render."})

    prompt = f"""
    Você é a Jurity IA Analista.
    DADOS ATUAIS DA CONTA:
    - WIN: {dados_mercado['WIN']['preco']} | WDO: {dados_mercado['WDO']['preco']}
    - Saldo Equity: R$ {financeiro['saldo_atual']}
    - Lucro Hoje: R$ {financeiro['resultado_dia']}
    - Ordens Ativas: {len(financeiro['posicoes'])}
    
    Instrução: Responda em Português-BR de forma técnica, curta e direta.
    Pergunta do usuário: {pergunta}
    """

    # Modelos para tentativa (priorizando a sua API 2.5 Flash)
    modelos_para_tentar = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-pro']
    
    for nome_modelo in modelos_para_tentar:
        try:
            model = genai.GenerativeModel(nome_modelo)
            response = model.generate_content(prompt)
            return jsonify({"resposta": response.text})
        except Exception:
            continue
            
    return jsonify({"resposta": "Jurity está a processar os alvos. Tente novamente em instantes."})

# --- GESTÃO DE DADOS (RECEBIDOS DA PONTE_MT5 NO PC) ---
@app.route('/atualizar_dados', methods=['POST'])
def atualizar_dados():
    data = request.json
    ativo = data.get('ativo')
    if ativo in dados_mercado:
        dados_mercado[ativo]['preco'] = data.get('preco')
        dados_mercado[ativo]['status'] = "Conectado"
    return jsonify({"status": "ok"})

@app.route('/atualizar_financeiro', methods=['POST'])
def atualizar_financeiro():
    global financeiro, historico_equity
    data = request.json
    financeiro.update(data)
    
    # Atualização do Gráfico (Máximo 30 pontos para evitar "estouro")
    agora = datetime.now().strftime('%H:%M:%S')
    saldo = data.get('saldo_atual', 0)
    if not historico_equity or (historico_equity[-1]['y'] != saldo):
        historico_equity.append({'x': agora, 'y': saldo})
    if len(historico_equity) > 30: 
        historico_equity.pop(0)
    return jsonify({"status": "ok"})

# --- GESTÃO DE ORDENS (DASHBOARD -> MT5) ---
@app.route('/order', methods=['POST'])
def order():
    # Recebe: tipo (BUY/SELL/PANIC), lotes, sl_pontos, tp_pontos
    fila_comandos.append(request.json)
    return jsonify({"status": "comando_recebido"})

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
