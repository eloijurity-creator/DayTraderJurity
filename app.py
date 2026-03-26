import os
import random
from datetime import datetime
from flask import Flask, render_template, jsonify, request
import google.generativeai as genai
import pandas as pd
import numpy as np

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
        preco = data.get('preco')
        dados_mercado[ativo]['preco'] = preco
        # Novo: Calcula alvos em tempo real
        dados_mercado[ativo]['alvos'] = calcular_alvos_estrategicos(ativo, preco)
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
# Armazenamento para histórico de cálculos (últimos 100 ticks)
historico_ticks = {"WIN": [], "WDO": []}

# Calcula alvos
def calcular_alvos_estrategicos(ativo, preco_atual):
    # Mantém um pequeno histórico para as EMAs e ATR
    historico_ticks[ativo].append(preco_atual)
    if len(historico_ticks[ativo]) > 50: historico_ticks[ativo].pop(0)
    
    if len(historico_ticks[ativo]) < 21: # Aguarda ter dados suficientes
        return {"t1": "Calculando...", "t2": "Calculando...", "t3": "Calculando...", "sentido": "Neutro"}

    df = pd.DataFrame(historico_ticks[ativo], columns=['Close'])
    # Simulando High/Low/Volume para o cálculo funcionar com tick único
    df['High'] = df['Close'] * 1.0002 
    df['Low'] = df['Close'] * 0.9998
    df['Volume'] = 100 

    # Lógica enviada por você
    df['EMA9'] = df['Close'].ewm(span=9).mean()
    df['EMA21'] = df['Close'].ewm(span=21).mean()
    df['VWAP'] = (df['Close'] * df['Volume']).cumsum() / df['Volume'].cumsum()
    df['TR'] = df['High'] - df['Low']
    df['ATR'] = df['TR'].rolling(14).mean().fillna(df['TR'].mean())

    last_close = df['Close'].iloc[-1]
    last_atr = df['ATR'].iloc[-1]
    trend = 1 if last_close > df['EMA9'].iloc[-1] else -1

    # Definição de Alvos
    t1 = last_close + (trend * last_atr)
    t2 = last_close + (trend * last_atr * 2)
    vwap_dev = abs(last_close - df['VWAP'].iloc[-1])
    t3 = last_close + (trend * (last_atr * 3 + vwap_dev))

    return {
        "t1": round(t1, 2 if ativo == "WDO" else 0),
        "t2": round(t2, 2 if ativo == "WDO" else 0),
        "t3": round(t3, 2 if ativo == "WDO" else 0),
        "sentido": "ALTA" if trend == 1 else "BAIXA"
    }

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
