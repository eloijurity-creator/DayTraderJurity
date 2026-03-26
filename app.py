import os
import pandas as pd
import numpy as np
from datetime import datetime
from flask import Flask, render_template, jsonify, request
import google.generativeai as genai
from sklearn.ensemble import RandomForestClassifier

app = Flask(__name__)

# --- CONFIGURAÇÃO GEMINI 2.5 FLASH ---
GEMINI_KEY = os.environ.get("GEMINI_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY, transport='rest')

# --- BANCOS DE DADOS EM MEMÓRIA ---
dados_mercado = {"WIN": {"preco": 0, "alvos": {}}, "WDO": {"preco": 0, "alvos": {}}}
historico_ticks = {"WIN": [], "WDO": []}
financeiro = {"resultado_dia": 0, "saldo_atual": 0, "conta": "---", "posicoes": []}
historico_equity = []
fila_comandos = []
estrategia_ativa = "vortex" 

# ================================================================
# LÓGICA DE INDICADORES E ESTRATÉGIAS (Sua Inteligência)
# ================================================================

def processar_inteligencia(ativo, preco):
    # Simulando colunas de High/Low/Volume/Agressão para os cálculos funcionarem
    novo_tick = {
        "Close": preco, 
        "High": preco * 1.0002, 
        "Low": preco * 0.9998, 
        "Volume": random.randint(100, 500),
        "AggBuy": random.randint(50, 400),
        "AggSell": random.randint(50, 400),
        "Time": datetime.now()
    }
    historico_ticks[ativo].append(novo_tick)
    
    if len(historico_ticks[ativo]) > 100: historico_ticks[ativo].pop(0)
    if len(historico_ticks[ativo]) < 30: return None

    df = pd.DataFrame(historico_ticks[ativo])

    # 1) Indicadores Gerais
    df['EMA9'] = df['Close'].ewm(span=9).mean()
    df['EMA21'] = df['Close'].ewm(span=21).mean()
    df['EMA72'] = df['Close'].ewm(span=72).mean()
    df['VWAP'] = (df['Close'] * df['Volume']).cumsum() / df['Volume'].cumsum()
    df['TR'] = df['High'] - df['Low']
    df['ATR'] = df['TR'].rolling(14).mean().fillna(preco * 0.0005)
    
    # 2) Vortex Indicator
    tr_sum = df['TR'].rolling(14).sum()
    vm_plus = abs(df['High'] - df['Low'].shift(1)).rolling(14).sum()
    vm_minus = abs(df['Low'] - df['High'].shift(1)).rolling(14).sum()
    vi_plus = (vm_plus / tr_sum).iloc[-1]
    vi_minus = (vm_minus / tr_sum).iloc[-1]

    # 3) Delta (Order Flow)
    df["Delta"] = df["AggBuy"] - df["AggSell"]

    sinal = "NEUTRO"
    score = 0.0

    # SELEÇÃO DE ESTRATÉGIA
    if estrategia_ativa == "vortex":
        if vi_plus > vi_minus and preco > df['EMA72'].iloc[-1]: sinal = "COMPRA"
        elif vi_minus > vi_plus and preco < df['EMA72'].iloc[-1]: sinal = "VENDA"
        score = round(abs(vi_plus - vi_minus) * 12, 1)

    elif estrategia_ativa == "ml":
        df['Ret'] = df['Close'].pct_change()
        df['Target'] = (df['Close'].shift(-1) > df['Close']).astype(int)
        train = df.dropna()
        if len(train) > 25:
            model = RandomForestClassifier(n_estimators=100)
            X = train[['Ret']].values.reshape(-1, 1)
            y = train['Target']
            model.fit(X, y)
            prob = model.predict_proba([[df['Ret'].iloc[-1]]])[0][1]
            score = round(prob * 10, 1)
            if prob > 0.60: sinal = "COMPRA"
            elif prob < 0.40: sinal = "VENDA"

    elif estrategia_ativa == "of":
        last_delta = df["Delta"].iloc[-1]
        if last_delta > 300 and preco > df['EMA9'].iloc[-1]: sinal = "COMPRA"
        elif last_delta < -300 and preco < df['EMA9'].iloc[-1]: sinal = "VENDA"
        score = min(10, abs(last_delta) / 100)

    # 4) Alvos (ATR + Tendência)
    trend = 1 if sinal == "COMPRA" or preco > df['EMA9'].iloc[-1] else -1
    return {
        "t1": round(preco + (trend * df['ATR'].iloc[-1]), 2 if ativo == "WDO" else 0),
        "t2": round(preco + (trend * df['ATR'].iloc[-1] * 2.5), 2 if ativo == "WDO" else 0),
        "score": min(10, score),
        "sinal": sinal,
        "trend_label": "ALTA" if trend == 1 else "BAIXA"
    }

# ================================================================
# ROTAS FLASK
# ================================================================

@app.route('/')
def index(): return render_template('index.html')

@app.route('/set_estrategia', methods=['POST'])
def set_estrategia():
    global estrategia_ativa
    estrategia_ativa = request.json.get('estrategia')
    return jsonify({"status": "ok", "ativa": estrategia_ativa})

@app.route('/atualizar_dados', methods=['POST'])
def atualizar_dados():
    data = request.json
    at = data.get('ativo')
    if at in dados_mercado:
        dados_mercado[at]['preco'] = data.get('preco')
        # Processa os cálculos técnicos a cada novo tick
        dados_mercado[at]['alvos'] = processar_inteligencia(at, data.get('preco'))
    return jsonify({"status": "ok"})

@app.route('/atualizar_financeiro', methods=['POST'])
def atualizar_financeiro():
    global financeiro, historico_equity
    data = request.json
    financeiro.update(data)
    agora = datetime.now().strftime('%H:%M:%S')
    if not historico_equity or historico_equity[-1]['y'] != data['saldo_atual']:
        historico_equity.append({'x': agora, 'y': data['saldo_atual']})
    if len(historico_equity) > 30: historico_equity.pop(0)
    return jsonify({"status": "ok"})

@app.route('/chat', methods=['POST'])
def chat():
    pergunta = request.json.get('mensagem', '')
    prompt = f"Você é a Jurity IA v2.6. WIN: {dados_mercado['WIN']['preco']}, WDO: {dados_mercado['WDO']['preco']}. Saldo: {financeiro['saldo_atual']}. Pergunta: {pergunta}"
    modelos = ['gemini-2.5-flash', 'gemini-1.5-flash']
    for m in modelos:
        try:
            model = genai.GenerativeModel(m)
            response = model.generate_content(prompt)
            return jsonify({"resposta": response.text})
        except: continue
    return jsonify({"resposta": "Jurity está analisando o fluxo de ordens. Tente novamente."})

@app.route('/order', methods=['POST'])
def order(): 
    fila_comandos.append(request.json)
    return jsonify({"status": "ok"})

@app.route('/get_orders')
def get_orders(): return jsonify(fila_comandos.pop(0)) if fila_comandos else jsonify({})

@app.route('/get_signal')
def get_signal(): return jsonify(dados_mercado.get(request.args.get('ativo'), {}))

@app.route('/get_financeiro')
def get_financeiro(): return jsonify(financeiro)

@app.route('/get_historico')
def get_historico(): return jsonify(historico_equity)

import random # Para a simulação de ticks
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
