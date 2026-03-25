from flask import Flask, render_template, jsonify, request
import pandas as pd
import numpy as np
import random
import os
import datetime
import google.generativeai as genai

app = Flask(__name__)

# --- CONFIGURAÇÃO DA JURITY IA ---
# Certifique-se de configurar a variável de ambiente GEMINI_KEY no Render
GEMINI_KEY = os.environ.get("GEMINI_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY, transport='rest')
else:
    print("AVISO: GEMINI_KEY não configurada.")

# --- CONFIGURAÇÕES DE BANCA E MERCADO ---
BANCA_TOTAL = 1000.00  # R$ Saldo Inicial
RISCO_POR_TRADE = 0.05  # 5% de risco por operação
VALOR_PONTO_WIN = 0.20  # R$ 0,20 por ponto
VALOR_PONTO_WDO = 10.00 # R$ 10,00 por ponto

# --- VARIÁVEIS GLOBAIS DE CONTROLE ---
historico_precos = {"WIN": [], "WDO": []}
dados_reais = {
    "WIN": {"preco": 0, "bid": 0, "ask": 0, "status": "OFFLINE"},
    "WDO": {"preco": 0, "bid": 0, "ask": 0, "status": "OFFLINE"}
}
log_performance = []
proximo_snapshot = datetime.datetime.now()

# --- MOTOR TÉCNICO E MATEMÁTICO ---

def calcular_metricas_avancadas(ativo):
    """Calcula indicadores reais baseados no histórico recebido do MT5"""
    precos = historico_precos[ativo]
    if len(precos) < 20:
        return {"tendencia": "NEUTRA", "rsi": 50, "volatilidade": 0, "ma20": 0}
    
    df = pd.DataFrame(precos, columns=['close'])
    
    # Médias Móveis (Cruzamento 9/20)
    ma9 = df['close'].tail(9).mean()
    ma20 = df['close'].tail(20).mean()
    tendencia = "ALTA" if ma9 > ma20 else "BAIXA"
    
    # RSI (Índice de Força Relativa)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs.iloc[-1]))
    
    # Volatilidade (Desvio padrão para cálculo de alvos)
    volatilidade = df['close'].tail(15).std()
    
    return {
        "tendencia": tendencia, 
        "rsi": rsi, 
        "volatilidade": volatilidade, 
        "ma20": ma20
    }

def registrar_log_automatico():
    """Gera uma linha de log na tabela a cada 15 minutos"""
    global proximo_snapshot, log_performance
    agora = datetime.datetime.now()
    
    if agora >= proximo_snapshot:
        for ativo in ["WIN", "WDO"]:
            m = calcular_metricas_avancadas(ativo)
            if dados_reais[ativo]["preco"] > 0:
                snapshot = {
                    "horario": agora.strftime("%H:%M"),
                    "ativo": ativo,
                    "preco": dados_reais[ativo]["preco"],
                    "tendencia": m["tendencia"],
                    "rsi": f"{m['rsi']:.1f}",
                    "alvo": f"{m['volatilidade'] * 1.5:.0f}" if ativo == "WIN" else f"{m['volatilidade'] * 1.5:.1f}",
                    "analise": "ALERTA" if m['rsi'] > 70 or m['rsi'] < 30 else "Normal"
                }
                log_performance.insert(0, snapshot)
        
        # Agenda o próximo snapshot para daqui a 15 minutos
        proximo_snapshot = agora + datetime.timedelta(minutes=15)
        
        # Limita o log para não sobrecarregar (últimas 40 entradas)
        if len(log_performance) > 40:
            log_performance = log_performance[:40]

# --- ROTAS FLASK ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/atualizar_dados', methods=['POST'])
def atualizar():
    """Recebe os dados do script ponte_mt5.py no PC"""
    global dados_reais, historico_precos
    content = request.json
    ativo = content.get('ativo', 'WIN')
    
    if ativo in dados_reais:
        preco = content.get('preco', 0)
        dados_reais[ativo].update({
            "preco": preco, 
            "bid": content.get('bid', 0), 
            "ask": content.get('ask', 0), 
            "status": "CONECTADO"
        })
        
        # Adiciona ao histórico para cálculos técnicos
        historico_precos[ativo].append(preco)
        if len(historico_precos[ativo]) > 100:
            historico_precos[ativo].pop(0)
            
        registrar_log_automatico()
    
    return "OK", 200

@app.route('/get_signal')
def get_signal():
    """Envia os dados de preço e sinal visual para o dashboard"""
    ativo = request.args.get('ativo', 'WIN')
    m = calcular_metricas_avancadas(ativo)
    
    # Lógica de cor baseada no RSI
    if m['rsi'] < 35:
        cor = "#00ff88" # Compra
        sinal = "SOBREVENDIDO (COMPRA)"
    elif m['rsi'] > 65:
        cor = "#ff3b3b" # Venda
        sinal = "SOBRECOMPRADO (VENDA)"
    else:
        cor = "#f0b90b" # Neutro
        sinal = f"TENDÊNCIA {m['tendencia']}"

    return jsonify({
        "preco": dados_reais[ativo]["preco"],
        "sinal": sinal,
        "cor": cor,
        "status": dados_reais[ativo]["status"],
        "rsi": f"{m['rsi']:.1f}"
    })

@app.route('/get_log')
def get_log():
    """Retorna a lista de logs para a tabela no index"""
    return jsonify(log_performance)

@app.route('/chat', methods=['POST'])
def chat():
    """Inteligência Artificial que analisa risco e sugere alvos"""
    user_msg = request.json.get('mensagem')
    m_win = calcular_metricas_avancadas("WIN")
    m_wdo = calcular_metricas_avancadas("WDO")
    
    # Cálculo de Lote/Contratos Sugeridos
    risco_financeiro = BANCA_TOTAL * RISCO_POR_TRADE
    lote_sugerido = max(1, int(risco_financeiro / (150 * VALOR_PONTO_WIN)))

    prompt = f"""
    Você é a Jurity IA, Consultora Senior de Risco e Price Action.
    STATUS DA CONTA: Saldo R$ {BANCA_TOTAL:.2f} | Risco Máx: R$ {risco_financeiro:.2f} | Lote Sugerido: {lote_sugerido} contratos.
    
    WIN AGORA: {dados_reais['WIN']['preco']} (Tendência: {m_win['tendencia']}, RSI: {m_win['rsi']:.1f})
    WDO AGORA: {dados_reais['WDO']['preco']} (Tendência: {m_wdo['tendencia']}, RSI: {m_wdo['rsi']:.1f})
    
    ALVOS TÉCNICOS:
    - WIN: Alvo {m_win['volatilidade']*1.5:.0f} pts / Stop {m_win['volatilidade']*1.0:.0f} pts.
    - WDO: Alvo {m_wdo['volatilidade']*1.5:.1f} pts / Stop {m_wdo['volatilidade']*1.0:.1f} pts.

    PERGUNTA DO TRADER: {user_msg}
    
    INSTRUÇÕES: Seja ultra-curta e profissional. Dê uma nota de 0 a 10 para entradas baseadas no RSI e correlação (geralmente opostos). Use gírias: 'Payoff', 'Stop Loss', 'Gain'.
    """

    modelos = ['gemini-1.5-flash', 'gemini-2.5-flash', 'gemini-pro']
    for modelo in modelos:
        try:
            model = genai.GenerativeModel(modelo)
            response = model.generate_content(prompt)
            return jsonify({"resposta": response.text})
        except:
            continue
            
    return jsonify({"resposta": "Jurity está analisando o fluxo... tente em breve."})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
