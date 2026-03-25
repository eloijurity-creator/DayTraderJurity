from flask import Flask, render_template, jsonify, request
import pandas as pd
import numpy as np
import os
import datetime
import google.generativeai as genai

app = Flask(__name__)

# --- CONFIGURAÇÃO DA JURITY IA ---
GEMINI_KEY = os.environ.get("GEMINI_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY, transport='rest')

# --- CONFIGURAÇÕES DE BANCA E MERCADO ---
BANCA_TOTAL = 1000.00  
RISCO_POR_TRADE = 0.05  
VALOR_PONTO_WIN = 0.20  
VALOR_PONTO_WDO = 10.00 

# --- VARIÁVEIS GLOBAIS ---
# Histórico de 150 para suportar média móvel de 50 períodos (Day Trade)
historico_precos = {"WIN": [], "WDO": []}
dados_reais = {
    "WIN": {"preco": 0, "bid": 0, "ask": 0, "status": "OFFLINE"},
    "WDO": {"preco": 0, "bid": 0, "ask": 0, "status": "OFFLINE"}
}
log_performance = []
proximo_snapshot = datetime.datetime.now()

# --- MOTOR TÉCNICO DAY TRADE (15-60 MIN) ---

def calcular_metricas_avancadas(ativo):
    precos = historico_precos[ativo]
    if len(precos) < 50:
        return {"tendencia": "AGUARDANDO", "rsi": 50, "volatilidade": 0}
    
    df = pd.DataFrame(precos, columns=['close'])
    
    # Médias Móveis de 20 e 50 (Filtro de Day Trade)
    ma20 = df['close'].tail(20).mean()
    ma50 = df['close'].tail(50).mean()
    
    # Filtro de Tendência com zona morta (lateralização)
    diff = (ma20 / ma50) - 1
    if diff > 0.0006: tendencia = "ALTA"
    elif diff < -0.0006: tendencia = "BAIXA"
    else: tendencia = "LATERAL"
    
    # RSI de 20 períodos (suavizado)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=20).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=20).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs.iloc[-1]))
    
    # Volatilidade (ATR Simples para alvos)
    volatilidade = df['close'].tail(60).std()
    
    return {"tendencia": tendencia, "rsi": rsi, "volatilidade": volatilidade}

def registrar_log_automatico():
    """Lógica de Auditoria: Verifica o snapshot anterior e marca GAIN ou LOSS"""
    global proximo_snapshot, log_performance
    agora = datetime.datetime.now()
    
    if agora >= proximo_snapshot:
        for ativo in ["WIN", "WDO"]:
            m = calcular_metricas_avancadas(ativo)
            preco_atual = dados_reais[ativo]["preco"]
            
            if preco_atual > 0:
                # AUDITORIA: Procura o último registro 'AGUARDANDO' deste ativo
                for antigo in log_performance:
                    if antigo["ativo"] == ativo and antigo["resultado"] == "AGUARDANDO...":
                        if antigo["tendencia"] == "ALTA":
                            antigo["resultado"] = "✅ GAIN" if preco_atual > antigo["preco"] else "❌ LOSS"
                        elif antigo["tendencia"] == "BAIXA":
                            antigo["resultado"] = "✅ GAIN" if preco_atual < antigo["preco"] else "❌ LOSS"
                        else:
                            antigo["resultado"] = "⚪ NEUTRO"
                        break

                # NOVO SNAPSHOT
                snapshot = {
                    "horario": agora.strftime("%H:%M"),
                    "ativo": ativo,
                    "preco": preco_atual,
                    "tendencia": m["tendencia"],
                    "rsi": f"{m['rsi']:.1f}",
                    "alvo": f"{m['volatilidade'] * 2:.0f}" if ativo == "WIN" else f"{m['volatilidade'] * 2:.1f}",
                    "resultado": "AGUARDANDO..."
                }
                log_performance.insert(0, snapshot)
        
        # Próxima análise em 15 minutos
        proximo_snapshot = agora + datetime.timedelta(minutes=15)
        if len(log_performance) > 40: log_performance = log_performance[:40]

# --- ROTAS FLASK ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/atualizar_dados', methods=['POST'])
def atualizar():
    global dados_reais, historico_precos
    content = request.json
    ativo = content.get('ativo', 'WIN')
    
    if ativo in dados_reais:
        preco = content.get('preco', 0)
        dados_reais[ativo].update({
            "preco": preco, "bid": content.get('bid', 0), 
            "ask": content.get('ask', 0), "status": "CONECTADO"
        })
        
        historico_precos[ativo].append(preco)
        if len(historico_precos[ativo]) > 150: historico_precos[ativo].pop(0)
            
        registrar_log_automatico()
    
    return "OK", 200

@app.route('/get_signal')
def get_signal():
    ativo = request.args.get('ativo', 'WIN')
    m = calcular_metricas_avancadas(ativo)
    
    # Cores dinâmicas para o Dashboard
    if m['rsi'] < 35: cor, sinal = "#00ff88", "SOBREVENDIDO (COMPRA)"
    elif m['rsi'] > 65: cor, sinal = "#ff3b3b", "SOBRECOMPRADO (VENDA)"
    else: cor, sinal = "#f0b90b", f"TENDÊNCIA: {m['tendencia']}"

    return jsonify({
        "preco": dados_reais[ativo]["preco"],
        "sinal": sinal,
        "cor": cor,
        "status": dados_reais[ativo]["status"],
        "rsi": f"{m['rsi']:.1f}"
    })

@app.route('/get_log')
def get_log():
    return jsonify(log_performance)

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('mensagem')
    m_win = calcular_metricas_avancadas("WIN")
    m_wdo = calcular_metricas_avancadas("WDO")
    
    prompt = f"""
    Você é a Jurity IA, focada em Day Trade (15-60 min).
    WIN: {dados_reais['WIN']['preco']} | Tendência: {m_win['tendencia']} | RSI: {m_win['rsi']:.1f}
    WDO: {dados_reais['WDO']['preco']} | Tendência: {m_wdo['tendencia']} | RSI: {m_wdo['rsi']:.1f}
    
    Pergunta: {user_msg}
    
    Instrução: Dê alvos baseados na volatilidade (WIN: {m_win['volatilidade']*2:.0f} pts). 
    Analise o payoff para os próximos 20 minutos. Seja curta.
    """
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return jsonify({"resposta": response.text})
    except:
        return jsonify({"resposta": "Conexão com cérebro IA instável."})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
