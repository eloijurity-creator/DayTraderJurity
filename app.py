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
financeiro = {
    "resultado_dia": 0.0, 
    "em_aberto": 0.0, 
    "saldo_atual": 0.0, 
    "conta": "Desconectado"
}
posicoes_abertas = [] 
log_performance = []
proximo_snapshot = datetime.datetime.now()
fila_ordens = {"WIN": None, "WDO": None, "PANIC": False}

def calcular_metricas(ativo):
    precos = historico_precos[ativo]
    if len(precos) < 30: 
        return {"tendencia": "AGUARDANDO", "rsi": 50.0}
    
    df = pd.DataFrame(precos, columns=['close'])
    # Médias Móveis para Tendência
    ma_curta = df['close'].tail(10).mean()
    ma_longa = df['close'].tail(30).mean()
    tendencia = "ALTA" if ma_curta > ma_longa else "BAIXA"
    
    # RSI Simples
    delta = df['close'].diff()
    ganho = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    perda = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = ganho / perda.replace(0, 0.001)
    rsi = 100 - (100 / (1 + rs.iloc[-1]))
    
    return {"tendencia": tendencia, "rsi": rsi}

@app.route('/')
def index(): 
    return render_template('index.html')

@app.route('/atualizar_dados', methods=['POST'])
def atualizar():
    global proximo_snapshot
    data = request.json
    ativo = data.get('ativo')
    if ativo in dados_reais:
        preco = data.get('preco')
        dados_reais[ativo]["preco"] = preco
        historico_precos[ativo].append(preco)
        if len(historico_precos[ativo]) > 100: historico_precos[ativo].pop(0)
        
        # Log de Performance Automático a cada 15 min
        agora = datetime.datetime.now()
        if agora >= proximo_snapshot:
            m = calcular_metricas(ativo)
            log_performance.insert(0, {
                "horario": agora.strftime("%H:%M"), 
                "ativo": ativo, 
                "preco": preco, 
                "tendencia": m["tendencia"],
                "rsi": f"{m['rsi']:.1f}"
            })
            proximo_snapshot = agora + datetime.timedelta(minutes=15)
    return "OK"

@app.route('/atualizar_financeiro', methods=['POST'])
def atualizar_fin():
    global financeiro, posicoes_abertas
    data = request.json
    financeiro.update({
        "resultado_dia": data.get('resultado_dia'),
        "em_aberto": data.get('em_aberto'),
        "saldo_atual": data.get('saldo_atual'),
        "conta": data.get('conta')
    })
    posicoes_abertas = data.get('posicoes', [])
    return "OK"

@app.route('/get_signal')
def get_signal():
    ativo = request.args.get('ativo')
    m = calcular_metricas(ativo)
    return jsonify({
        "preco": dados_reais[ativo]["preco"], 
        "rsi": f"{m['rsi']:.1f}",
        "tendencia": m['tendencia'],
        "fin": financeiro, 
        "posicoes": posicoes_abertas,
        "logs": log_performance[:5]
    })

@app.route('/set_order', methods=['POST'])
def set_order():
    global fila_ordens
    data = request.json
    if data.get('tipo') == 'PANIC': 
        fila_ordens["PANIC"] = True
    else: 
        fila_ordens[data['ativo']] = data
    return jsonify({"status": "OK"})

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

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('mensagem')
    m_win = calcular_metricas("WIN")
    m_wdo = calcular_metricas("WDO")
    
    prompt = f"""
    Você é a Jurity IA.
    Contexto: 
    WIN: Preço {dados_reais['WIN']['preco']}, Tendência {m_win['tendencia']}, RSI {m_win['rsi']:.1f}
    WDO: Preço {dados_reais['WDO']['preco']}, Tendência {m_wdo['tendencia']}, RSI {m_wdo['rsi']:.1f}
    Financeiro: Saldo {financeiro['saldo_atual']}, Aberto {financeiro['em_aberto']}
    Pergunta: {user_msg}
    Responda de forma curta e técnica.
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        res = model.generate_content(prompt)
        return jsonify({"resposta": res.text})
    except:
        return jsonify({"resposta": "Erro na API Gemini."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
