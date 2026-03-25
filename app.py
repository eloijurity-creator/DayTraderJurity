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

# --- VARIÁVEIS GLOBAIS ---
historico_precos = {"WIN": [], "WDO": []}
dados_reais = {"WIN": {"preco": 0}, "WDO": {"preco": 0}}
financeiro = {"lucro_hoje": 0.0, "em_aberto": 0.0, "qtd_ordens": 0, "conta": "Desconectado"}
log_performance = []
proximo_snapshot = datetime.datetime.now()
fila_ordens = {"WIN": None, "WDO": None, "PANIC": False}

def calcular_metricas(ativo):
    precos = historico_precos[ativo]
    if len(precos) < 50: return {"tendencia": "AGUARDANDO", "rsi": 50}
    df = pd.DataFrame(precos, columns=['close'])
    ma20, ma50 = df['close'].tail(20).mean(), df['close'].tail(50).mean()
    tendencia = "ALTA" if ma20 > ma50 else "BAIXA"
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=20).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=20).mean()
    rsi = 100 - (100 / (1 + (gain / loss).iloc[-1]))
    return {"tendencia": tendencia, "rsi": rsi}

@app.route('/')
def index(): return render_template('index.html')

@app.route('/atualizar_dados', methods=['POST'])
def atualizar():
    global proximo_snapshot
    data = request.json
    ativo = data.get('ativo')
    if ativo in dados_reais:
        preco = data.get('preco')
        dados_reais[ativo]["preco"] = preco
        historico_precos[ativo].append(preco)
        if len(historico_precos[ativo]) > 150: historico_precos[ativo].pop(0)
        
        agora = datetime.datetime.now()
        if agora >= proximo_snapshot:
            m = calcular_metricas(ativo)
            log_performance.insert(0, {"horario": agora.strftime("%H:%M"), "ativo": ativo, "preco": preco, "tendencia": m["tendencia"], "resultado": "AGUARDANDO..."})
            proximo_snapshot = agora + datetime.timedelta(minutes=15)
    return "OK"

@app.route('/atualizar_financeiro', methods=['POST'])
def atualizar_fin():
    global financeiro
    financeiro.update(request.json)
    return "OK"

@app.route('/set_order', methods=['POST'])
def set_order():
    global fila_ordens
    data = request.json
    if data.get('tipo') == 'PANIC': 
        fila_ordens["PANIC"] = True
    else: 
        fila_ordens[data['ativo']] = data
    return jsonify({"status": "COMANDO RECEBIDO"})

@app.route('/get_orders')
def get_orders():
    global fila_ordens
    if fila_ordens["PANIC"]:
        fila_ordens["PANIC"] = False
        return jsonify({"tipo": "PANIC"})
    ativo = request.args.get('ativo')
    ordem = fila_ordens.get(ativo)
    fila_ordens[ativo] = None
    return jsonify(ordem)

@app.route('/get_signal')
def get_signal():
    ativo = request.args.get('ativo')
    m = calcular_metricas(ativo)
    return jsonify({"preco": dados_reais[ativo]["preco"], "rsi": f"{m['rsi']:.1f}", "tendencia": m['tendencia'], "fin": financeiro, "logs": log_performance[:5]})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
