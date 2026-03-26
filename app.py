import os
import random
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

# Bancos de Dados
dados_mercado = {"WIN": {"preco": 0, "alvos": {}}, "WDO": {"preco": 0, "alvos": {}}}
historico_ticks = {"WIN": [], "WDO": []}
financeiro = {"resultado_dia": 0, "saldo_atual": 0, "conta": "---", "posicoes": []}
historico_equity = []
fila_comandos = []
estrategia_ativa = "vortex"

# Modelo ML global para não treinar em todo tick (otimização)
model_ml = RandomForestClassifier(n_estimators=50)
ml_treinado = False

def processar_inteligencia(ativo, preco):
    global ml_treinado
    # Simula colunas necessárias
    tick = {"Close": preco, "High": preco*1.0002, "Low": preco*0.9998, "Volume": 100, "AggBuy": 200, "AggSell": 150}
    historico_ticks[ativo].append(tick)
    
    if len(historico_ticks[ativo]) > 100: historico_ticks[ativo].pop(0)
    if len(historico_ticks[ativo]) < 30: return None

    df = pd.DataFrame(historico_ticks[ativo])
    df['EMA9'] = df['Close'].ewm(span=9).mean()
    df['EMA72'] = df['Close'].ewm(span=72).mean()
    df['TR'] = df['High'] - df['Low']
    df['ATR'] = df['TR'].rolling(14).mean().fillna(preco * 0.0005)
    
    # Vortex
    tr_s = df['TR'].rolling(14).sum()
    vi_p = (abs(df['High'] - df['Low'].shift(1)).rolling(14).sum() / tr_s).iloc[-1]
    vi_m = (abs(df['Low'] - df['High'].shift(1)).rolling(14).sum() / tr_s).iloc[-1]

    sinal, score = "NEUTRO", 0.0

    if estrategia_ativa == "vortex":
        if vi_p > vi_m and preco > df['EMA72'].iloc[-1]: sinal = "COMPRA"
        elif vi_m > vi_p and preco < df['EMA72'].iloc[-1]: sinal = "VENDA"
        score = round(abs(vi_p - vi_m) * 15, 1)

    elif estrategia_ativa == "ml":
        df['Ret'] = df['Close'].pct_change()
        df['Target'] = (df['Close'].shift(-1) > df['Close']).astype(int)
        df_ml = df.dropna()
        if len(df_ml) > 30:
            X = df_ml[['Ret']].values.reshape(-1, 1)
            y = df_ml['Target']
            model_ml.fit(X, y) # Treino rápido
            prob = model_ml.predict_proba([[df['Ret'].iloc[-1]]])[0][1]
            score = round(prob * 10, 1)
            if prob > 0.62: sinal = "COMPRA"
            elif prob < 0.38: sinal = "VENDA"

    trend = 1 if sinal == "COMPRA" or preco > df['EMA9'].iloc[-1] else -1
    return {
        "t1": round(preco + (trend * df['ATR'].iloc[-1]), 2 if ativo == "WDO" else 0),
        "t2": round(preco + (trend * df['ATR'].iloc[-1] * 2.5), 2 if ativo == "WDO" else 0),
        "score": min(10, score),
        "sinal": sinal
    }

@app.route('/')
def index(): return render_template('index.html')

@app.route('/set_estrategia', methods=['POST'])
def set_estrategia():
    global estrategia_ativa
    estrategia_ativa = request.json.get('estrategia')
    return jsonify({"status": "ok"})

@app.route('/atualizar_dados', methods=['POST'])
def atualizar_dados():
    data = request.json
    at = data.get('ativo')
    if at in dados_mercado:
        dados_mercado[at]['preco'] = data.get('preco')
        dados_mercado[at]['alvos'] = processar_inteligencia(at, data.get('preco'))
    return jsonify({"status": "ok"})

@app.route('/atualizar_financeiro', methods=['POST'])
def atualizar_financeiro():
    global financeiro, historico_equity
    data = request.json
    financeiro.update(data)
    if not historico_equity or historico_equity[-1]['y'] != data['saldo_atual']:
        historico_equity.append({'x': datetime.now().strftime('%H:%M:%S'), 'y': data['saldo_atual']})
    if len(historico_equity) > 30: historico_equity.pop(0)
    return jsonify({"status": "ok"})

@app.route('/chat', methods=['POST'])
def chat():
    pergunta = request.json.get('mensagem', '')
    prompt = f"Jurity IA 2.5. WIN: {dados_mercado['WIN']['preco']}, WDO: {dados_mercado['WDO']['preco']}. Saldo: {financeiro['saldo_atual']}. Pergunta: {pergunta}"
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        return jsonify({"resposta": response.text})
    except: return jsonify({"resposta": "IA Ocupada."})

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

if __name__ == "__main__":
    # Render usa a porta 10000 por padrão, mas o Flask/Gunicorn deve ouvir em 0.0.0.0
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
