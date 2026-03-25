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
    genai.configure(api_key=GEMINI_KEY)

# --- ESTADO DO SISTEMA ---
historico_precos = {"WIN": [], "WDO": []}
dados_reais = {"WIN": {"preco": 0}, "WDO": {"preco": 0}}
financeiro = {"resultado_dia": 0.0, "em_aberto": 0.0, "saldo_atual": 0.0, "conta": "Desconectado"}
posicoes_abertas = [] 
historico_performance = []
fila_ordens = {"WIN": None, "WDO": None, "PANIC": False}

def calcular_metricas(ativo):
    precos = historico_precos[ativo]
    if len(precos) < 20: return {"tendencia": "LATERAL", "rsi": 50.0, "forca": 0}
    
    df = pd.DataFrame(precos, columns=['close'])
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, 0.001)
    rsi = 100 - (100 / (1 + rs.iloc[-1]))
    
    ma10, ma30 = df['close'].tail(10).mean(), df['close'].tail(30).mean()
    tendencia = "ALTA" if ma10 > ma30 else "BAIXA"
    
    # Cálculo de Confiança (0-100%)
    forca = 0
    if tendencia == "ALTA" and rsi < 40: forca = 70 + (40 - rsi)
    if tendencia == "BAIXA" and rsi > 60: forca = 70 + (rsi - 60)
    
    return {"tendencia": tendencia, "rsi": rsi, "forca": min(int(forca), 100)}

def gerar_decisao_ia(m):
    """Gera o gatilho para o botão One-Click"""
    if m['forca'] >= 75:
        acao = "BUY" if m['tendencia'] == "ALTA" else "SELL"
        msg = f"IA: {m['forca']}% CONFIANÇA EM {acao}"
        return {"acao": acao, "msg": msg, "confianca": m['forca']}
    return None

@app.route('/')
def index(): return render_template('index.html')

@app.route('/atualizar_dados', methods=['POST'])
def atualizar():
    data = request.json
    ativo = data.get('ativo')
    if ativo in dados_reais:
        dados_reais[ativo]["preco"] = data.get('preco')
        historico_precos[ativo].append(data.get('preco'))
        if len(historico_precos[ativo]) > 100: historico_precos[ativo].pop(0)
    return "OK"

@app.route('/atualizar_financeiro', methods=['POST'])
def atualizar_fin():
    global financeiro, posicoes_abertas, historico_performance
    data = request.json
    financeiro.update(data)
    posicoes_abertas = data.get('posicoes', [])
    agora = datetime.datetime.now().strftime("%H:%M:%S")
    if not historico_performance or historico_performance[-1]["acumulado"] != data.get('saldo_atual'):
        historico_performance.append({"horario": agora, "acumulado": data.get('saldo_atual')})
        if len(historico_performance) > 60: historico_performance.pop(0)
    return "OK"

@app.route('/get_signal')
def get_signal():
    m_win, m_wdo = calcular_metricas("WIN"), calcular_metricas("WDO")
    return jsonify({
        "win": {"preco": dados_reais["WIN"]["preco"], "rsi": round(m_win['rsi'],1), "tend": m_win['tendencia'], "decisao": gerar_decisao_ia(m_win)},
        "wdo": {"preco": dados_reais["WDO"]["preco"], "rsi": round(m_wdo['rsi'],1), "tend": m_wdo['tendencia'], "decisao": gerar_decisao_ia(m_wdo)},
        "fin": financeiro, "posicoes": posicoes_abertas, "historico": historico_performance
    })

@app.route('/set_order', methods=['POST'])
def set_order():
    global fila_ordens
    data = request.json
    if data.get('tipo') == 'PANIC': fila_ordens["PANIC"] = True
    else: fila_ordens[data['ativo']] = data
    return jsonify({"status": "OK"})

@app.route('/get_orders')
def get_orders():
    global fila_ordens
    if fila_ordens["PANIC"]:
        fila_ordens["PANIC"] = False
        return jsonify({"tipo": "PANIC"})
    ordem = fila_ordens.get(request.args.get('ativo'))
    fila_ordens[request.args.get('ativo')] = None
    return jsonify(ordem)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
