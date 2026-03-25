from flask import Flask, render_template, jsonify, request
import pandas as pd
import numpy as np
import random
import os
import google.generativeai as genai

app = Flask(__name__)

# --- CONFIGURAÇÃO DA JURITY IA ---
GEMINI_KEY = os.environ.get("GEMINI_KEY")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY, transport='rest')
else:
    print("ERRO: Variável GEMINI_KEY não encontrada no sistema.")

# --- VARIÁVEIS GLOBAIS E HISTÓRICO ---
# Armazenamos os últimos precos para calcular volatilidade e médias reais
historico_precos = {"WIN": [], "WDO": []}
dados_reais = {
    "WIN": {"preco": 0, "bid": 0, "ask": 0, "status": "Aguardando MT5..."},
    "WDO": {"preco": 0, "bid": 0, "ask": 0, "status": "Aguardando MT5..."}
}

# --- FUNÇÕES AUXILIARES TÉCNICAS ---
def calcular_metricas_avancadas(ativo):
    precos = historico_precos[ativo]
    if len(precos) < 20:
        # Fallback caso o histórico ainda esteja sendo preenchido
        return {"tendencia": "NEUTRA", "rsi": 50, "volatilidade": 0, "ma20": 0}
    
    df = pd.DataFrame(precos, columns=['close'])
    
    # Médias Móveis
    ma9 = df['close'].tail(9).mean()
    ma20 = df['close'].tail(20).mean()
    tendencia = "ALTA" if ma9 > ma20 else "BAIXA"
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs.iloc[-1]))
    
    # Volatilidade (Aproximação de desvio para calculo de alvos)
    volatilidade = df['close'].tail(15).std()
    
    return {
        "tendencia": tendencia,
        "rsi": rsi,
        "volatilidade": volatilidade,
        "ma20": ma20
    }

# --- ROTAS ---

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
        dados_reais[ativo]["preco"] = preco
        dados_reais[ativo]["bid"] = content.get('bid', 0)
        dados_reais[ativo]["ask"] = content.get('ask', 0)
        dados_reais[ativo]["status"] = "CONECTADO"
        
        # Alimenta o histórico para cálculos reais
        historico_precos[ativo].append(preco)
        if len(historico_precos[ativo]) > 100:
            historico_precos[ativo].pop(0)
    
    return "OK", 200

@app.route('/get_signal')
def get_signal():
    ativo = request.args.get('ativo', 'WIN')
    info = dados_reais.get(ativo, dados_reais["WIN"])
    
    # Obtém métricas reais baseadas no histórico
    metricas = calcular_metricas_avancadas(ativo)
    
    if metricas["rsi"] < 35:
        sinal, cor = f"COMPRA {ativo}", "#00ff88"
    elif metricas["rsi"] > 65:
        sinal, cor = f"VENDA {ativo}", "#ff3b3b"
    else:
        sinal, cor = f"TENDÊNCIA: {metricas['tendencia']}", "#f0b90b"

    return jsonify({
        "sinal": sinal,
        "cor": cor,
        "preco": info["preco"],
        "rsi": f"{metricas['rsi']:.2f}",
        "status": info["status"]
    })

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('mensagem')
    
    # Coleta métricas para os dois ativos
    m_win = calcular_metricas_avancadas("WIN")
    m_wdo = calcular_metricas_avancadas("WDO")
    
    # Lógica de Alvos baseada em volatilidade (WIN)
    # Alvo médio de 1.5x a volatilidade recente
    alvo_win = m_win["volatilidade"] * 1.5 if m_win["volatilidade"] > 0 else 100
    stop_win = m_win["volatilidade"] * 1.0 if m_win["volatilidade"] > 0 else 70
    
    # Lógica de Alvos (WDO)
    alvo_wdo = m_wdo["volatilidade"] * 1.5 if m_wdo["volatilidade"] > 0 else 5
    stop_wdo = m_wdo["volatilidade"] * 1.0 if m_wdo["volatilidade"] > 0 else 3

    prompt = f"""
    Você é a Jurity IA, Consultora Senior de Risco e Price Action na B3.
    
    DADOS ATUAIS WIN: Preço {dados_reais['WIN']['preco']}, Tendência {m_win['tendencia']}, RSI {m_win['rsi']:.2f}
    ALVO SUGERIDO WIN: {alvo_win:.0f} pontos | STOP: {stop_win:.0f} pontos.

    DADOS ATUAIS WDO: Preço {dados_reais['WDO']['preco']}, Tendência {m_wdo['tendencia']}, RSI {m_wdo['rsi']:.2f}
    ALVO SUGERIDO WDO: {alvo_wdo:.1f} pontos | STOP: {stop_wdo:.1f} pontos.

    PERGUNTA DO TRADER: {user_msg}
    
    INSTRUÇÕES:
    1. Se o trader perguntar sobre "alvo", "entrada" ou "onde sair", use os dados de volatilidade acima.
    2. Dê uma NOTA de 0 a 10. Se o RSI estiver esticado contra a tendência, a nota deve ser baixa.
    3. Analise a correlação: se WIN e WDO estiverem subindo juntos, avise que o mercado está perigoso (sem correlação clara).
    4. Seja ultra-curta, técnica e use termos como 'Take Profit', 'Stop Loss' e 'Payoff'.
    """
    
    modelos_para_tentar = ['gemini-1.5-flash', 'gemini-2.5-flash', 'gemini-pro']
    
    for nome_modelo in modelos_para_tentar:
        try:
            model = genai.GenerativeModel(nome_modelo)
            response = model.generate_content(prompt)
            return jsonify({"resposta": response.text})
        except Exception:
            continue
            
    return jsonify({"resposta": "Jurity está processando os alvos. Tente novamente em instantes."})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
