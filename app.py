from flask import Flask, render_template, jsonify, request
import pandas as pd
import numpy as np
import os
import datetime
import google.generativeai as genai

app = Flask(__name__)

# --- CONFIGURAÇÃO IA ---
GEMINI_KEY = os.environ.get("GEMINI_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY, transport='rest')

# --- BANCA E RISCO ---
BANCA_TOTAL = 1000.00
RISCO_POR_TRADE = 0.05

# --- VARIÁVEIS GLOBAIS ---
historico_precos = {"WIN": [], "WDO": []}
dados_reais = {"WIN": {"preco": 0, "status": "OFFLINE"}, "WDO": {"preco": 0, "status": "OFFLINE"}}
log_performance = []
proximo_snapshot = datetime.datetime.now()
fila_ordens = {"WIN": None, "WDO": None} # FILA DE EXECUÇÃO

def calcular_metricas(ativo):
    precos = historico_precos[ativo]
    if len(precos) < 50: return {"tendencia": "AGUARDANDO", "rsi": 50, "volat": 0}
    df = pd.DataFrame(precos, columns=['close'])
    ma20 = df['close'].tail(20).mean()
    ma50 = df['close'].tail(50).mean()
    diff = (ma20 / ma50) - 1
    tendencia = "ALTA" if diff > 0.0006 else "BAIXA" if diff < -0.0006 else "LATERAL"
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=20).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=20).mean()
    rsi = 100 - (100 / (1 + (gain / loss).iloc[-1]))
    return {"tendencia": tendencia, "rsi": rsi, "volat": df['close'].tail(60).std()}

@app.route('/')
def index(): return render_template('index.html')

@app.route('/atualizar_dados', methods=['POST'])
def atualizar():
    global dados_reais, historico_precos
    content = request.json
    ativo = content.get('ativo')
    if ativo in dados_reais:
        preco = content.get('preco')
        dados_reais[ativo].update({"preco": preco, "status": "CONECTADO"})
        historico_precos[ativo].append(preco)
        if len(historico_precos[ativo]) > 150: historico_precos[ativo].pop(0)
        
        # Lógica de Snapshot 15min e Auditoria
        global proximo_snapshot, log_performance
        agora = datetime.datetime.now()
        if agora >= proximo_snapshot:
            m = calcular_metricas(ativo)
            for antigo in log_performance:
                if antigo["ativo"] == ativo and antigo["resultado"] == "AGUARDANDO...":
                    if antigo["tendencia"] == "ALTA": antigo["resultado"] = "✅ GAIN" if preco > antigo["preco"] else "❌ LOSS"
                    elif antigo["tendencia"] == "BAIXA": antigo["resultado"] = "✅ GAIN" if preco < antigo["preco"] else "❌ LOSS"
                    break
            log_performance.insert(0, {"horario": agora.strftime("%H:%M"), "ativo": ativo, "preco": preco, "tendencia": m["tendencia"], "rsi": f"{m['rsi']:.1f}", "resultado": "AGUARDANDO..."})
            proximo_snapshot = agora + datetime.timedelta(minutes=15)
    return "OK"

@app.route('/set_order', methods=['POST'])
def set_order():
    global fila_ordens
    data = request.json
    fila_ordens[data['ativo']] = data
    return jsonify({"status": "ORDEM ENVIADA AO MT5"})

@app.route('/get_orders')
def get_orders():
    global fila_ordens
    ativo = request.args.get('ativo')
    ordem = fila_ordens.get(ativo)
    fila_ordens[ativo] = None
    return jsonify(ordem)

@app.route('/get_signal')
def get_signal():
    ativo = request.args.get('ativo')
    m = calcular_metricas(ativo)
    return jsonify({"preco": dados_reais[ativo]["preco"], "sinal": f"TENDÊNCIA: {m['tendencia']}", "rsi": f"{m['rsi']:.1f}", "volat": m['volat']})

@app.route('/get_log')
def get_log(): return jsonify(log_performance[:10])

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('mensagem')
    model = genai.GenerativeModel('gemini-1.5-flash')
    res = model.generate_content(f"Trader: {user_msg}. Analise Day Trade curta e técnica.")
    return jsonify({"resposta": res.text})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
