import os
import random
import pandas as pd
import numpy as np
from datetime import datetime
from flask import Flask, render_template, jsonify, request
import google.generativeai as genai

app = Flask(__name__)

# --- CONFIGURAÇÃO GEMINI 2.5 FLASH ---
# Certifique-se de configurar a variável GEMINI_KEY no painel do Render
GEMINI_KEY = os.environ.get("GEMINI_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY, transport='rest')

# --- BANCO DE DADOS EM MEMÓRIA ---
dados_mercado = {
    "WIN": {"preco": 0, "alvos": {}, "status": "Offline"},
    "WDO": {"preco": 0, "alvos": {}, "status": "Offline"}
}
# Histórico para os cálculos de média e volatilidade (Pandas)
historico_ticks = {"WIN": [], "WDO": []}

# Dados Financeiros (Lucro Hoje corrigido via Ponte MT5)
financeiro = {
    "resultado_dia": 0, 
    "saldo_atual": 0, 
    "conta": "Desconectado", 
    "posicoes": []
}
historico_equity = []
fila_comandos = []

# --- LÓGICA DE INTELIGÊNCIA ESTRATÉGICA (ALVOS + NOTA) ---
def calcular_alvos_estrategicos(ativo, preco):
    historico_ticks[ativo].append(preco)
    # Mantém 60 registros para ter base de cálculo estável
    if len(historico_ticks[ativo]) > 60: 
        historico_ticks[ativo].pop(0)
    
    if len(historico_ticks[ativo]) < 21: 
        return {"t1": "Calculando...", "t2": "Calculando...", "t3": "Calculando...", "score": 0, "sinal": "AGUARDANDO"}

    # Transforma em DataFrame para usar Pandas
    df = pd.DataFrame(historico_ticks[ativo], columns=['Close'])
    
    # Cálculos Técnicos
    df['EMA9'] = df['Close'].ewm(span=9).mean()
    df['EMA21'] = df['Close'].ewm(span=21).mean()
    df['VWAP'] = df['Close'].expanding().mean() # Média acumulada como simulador de VWAP
    
    # Volatilidade (ATR Simulado para ticks)
    df['TR'] = (df['Close'] * 0.0005).rolling(14).mean() # Estimativa de range
    
    last = df.iloc[-1]
    atr = last['TR'] if not np.isnan(last['TR']) else (preco * 0.0002)
    
    # Nota de Confiança (0-10)
    dist_vwap = abs(last['Close'] - last['VWAP'])
    score = min(10, round((dist_vwap / (atr + 0.01)) * 1.8, 1))
    
    # Direção da Tendência
    trend_up = last['Close'] > last['EMA9'] and last['EMA9'] > last['EMA21']
    trend_down = last['Close'] < last['EMA9'] and last['EMA9'] < last['EMA21']
    
    sinal = "NEUTRO"
    if trend_up and score > 4: sinal = "COMPRA"
    elif trend_down and score > 4: sinal = "VENDA"

    # Definição de Alvos (T1=1xATR, T2=2xATR, T3=3.5xATR)
    multiplicador = 1 if trend_up or (not trend_up and not trend_down and last['Close'] > last['VWAP']) else -1
    
    return {
        "t1": round(last['Close'] + (multiplicador * atr), 2 if ativo == "WDO" else 0),
        "t2": round(last['Close'] + (multiplicador * atr * 2), 2 if ativo == "WDO" else 0),
        "t3": round(last['Close'] + (multiplicador * atr * 3.5), 2 if ativo == "WDO" else 0),
        "score": score,
        "sinal": sinal,
        "trend": "ALTA" if trend_up else "BAIXA" if trend_down else "LATERAL"
    }

@app.route('/')
def index():
    return render_template('index.html')

# --- ROTAS DE COMUNICAÇÃO COM O PC (MT5) ---
@app.route('/atualizar_dados', methods=['POST'])
def atualizar_dados():
    data = request.json
    at = data.get('ativo')
    if at in dados_mercado:
        preco = data.get('preco')
        dados_mercado[at]['preco'] = preco
        dados_mercado[at]['status'] = "Conectado"
        dados_mercado[at]['alvos'] = calcular_alvos_estrategicos(at, preco)
    return jsonify({"status": "ok"})

@app.route('/atualizar_financeiro', methods=['POST'])
def atualizar_financeiro():
    global financeiro, historico_equity
    data = request.json
    # Recebe resultado_dia (fechado), saldo_atual (equity) e posicoes
    financeiro.update(data)
    
    # Atualiza Gráfico de Performance (Máximo 30 pontos)
    agora = datetime.now().strftime('%H:%M:%S')
    saldo = data.get('saldo_atual', 0)
    if not historico_equity or historico_equity[-1]['y'] != saldo:
        historico_equity.append({'x': agora, 'y': saldo})
    if len(historico_equity) > 30: 
        historico_equity.pop(0)
    return jsonify({"status": "ok"})

# --- CHAT COM IA (GEMINI 2.5 FLASH) ---
@app.route('/chat', methods=['POST'])
def chat():
    pergunta = request.json.get('mensagem', '')
    
    # Contexto em tempo real para o Gemini
    prompt = f"""
    Você é a Jurity IA Analista v2.5. 
    STATUS MERCADO: WIN {dados_mercado['WIN']['preco']} | WDO {dados_mercado['WDO']['preco']}.
    STATUS CONTA: Saldo Equity R$ {financeiro['saldo_atual']} | Lucro Hoje (Fechado) R$ {financeiro['resultado_dia']}.
    Ordens em aberto: {len(financeiro['posicoes'])}.
    Responda em Português-BR de forma curta, técnica e objetiva.
    Pergunta: {pergunta}
    """
    
    modelos_para_tentar = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-pro']
    
    for nome_modelo in modelos_para_tentar:
        try:
            model = genai.GenerativeModel(nome_modelo)
            response = model.generate_content(prompt)
            return jsonify({"resposta": response.text})
        except:
            continue
            
    return jsonify({"resposta": "Jurity processando... tente novamente."})

# --- GESTÃO DE COMANDOS (ORDENS) ---
@app.route('/order', methods=['POST'])
def order():
    fila_comandos.append(request.json)
    return jsonify({"status": "comando_recebido"})

@app.route('/get_orders')
def get_orders():
    # O PC chama essa rota para executar no MT5
    return jsonify(fila_comandos.pop(0)) if fila_comandos else jsonify({})

# --- ROTAS DE CONSULTA PARA O DASHBOARD ---
@app.route('/get_signal')
def get_signal():
    return jsonify(dados_mercado.get(request.args.get('ativo'), {}))

@app.route('/get_financeiro')
def get_financeiro():
    return jsonify(financeiro)

@app.route('/get_historico')
def get_historico():
    return jsonify(historico_equity)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
