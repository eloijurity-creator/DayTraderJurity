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

# --- VARIÁVEIS GLOBAIS ---
# Estrutura atualizada para suportar os dois ativos
dados_reais = {
    "WIN": {"preco": 0, "bid": 0, "ask": 0, "status": "Aguardando MT5..."},
    "WDO": {"preco": 0, "bid": 0, "ask": 0, "status": "Aguardando MT5..."}
}

# --- FUNÇÕES AUXILIARES ---
def calcular_rsi(series, period=14):
    if len(series) < period: return 50
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- ROTAS ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/atualizar_dados', methods=['POST'])
def atualizar():
    global dados_reais
    content = request.json
    ativo = content.get('ativo', 'WIN') # O script ponte_mt5.py deve enviar o campo 'ativo'
    
    if ativo in dados_reais:
        dados_reais[ativo]["preco"] = content.get('preco', 0)
        dados_reais[ativo]["bid"] = content.get('bid', 0)
        dados_reais[ativo]["ask"] = content.get('ask', 0)
        dados_reais[ativo]["status"] = "CONECTADO"
    
    return "OK", 200

@app.route('/get_signal')
def get_signal():
    # Retorna sinais baseados no ativo solicitado (padrão WIN)
    ativo = request.args.get('ativo', 'WIN')
    info = dados_reais.get(ativo, dados_reais["WIN"])
    
    preco_base = info["preco"] if info["preco"] > 0 else (120000 if ativo == "WIN" else 5000)
    precos_simulados = [preco_base + random.uniform(-50, 50) for _ in range(30)]
    df = pd.DataFrame(precos_simulados, columns=['close'])
    
    rsi_val = calcular_rsi(df['close']).iloc[-1]
    
    if rsi_val < 35:
        sinal, cor = f"COMPRA {ativo} (JURITY)", "#00ff88"
    elif rsi_val > 65:
        sinal, cor = f"VENDA {ativo} (JURITY)", "#ff3b3b"
    else:
        sinal, cor = "AGUARDAR", "#f0b90b"

    return jsonify({
        "sinal": sinal,
        "cor": cor,
        "preco": info["preco"],
        "status": info["status"]
    })

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('mensagem')
    
    # Dados para a IA
    win_p = dados_reais["WIN"]["preco"]
    wdo_p = dados_reais["WDO"]["preco"]
    
    # Gera indicadores rápidos para o Índice (WIN) como exemplo de contexto
    precos_win = [win_p + random.uniform(-100, 100) for _ in range(20)]
    df_win = pd.DataFrame(precos_win, columns=['close'])
    rsi_win = calcular_rsi(df_win['close']).iloc[-1]

    # O COMANDO MESTRE: Agora com contexto de Índice e Dólar
    prompt = f"""
    Você é a Jurity IA, Consultora Senior de Risco na B3.
    MERCADO AGORA:
    - Mini Índice (WIN): {win_p} (RSI: {rsi_win:.2f})
    - Mini Dólar (WDO): {wdo_p}
    
    PERGUNTA DO TRADER: {user_msg}
    
    INSTRUÇÃO: Analise os dados. Se for sobre entrada, dê nota 0 a 10. 
    Lembre-se da correlação: geralmente quando o Índice sobe, o Dólar cai.
    Responda de forma técnica, ultra-curta e profissional.
    """
    
    modelos_para_tentar = ['gemini-1.5-flash', 'gemini-2.5-flash', 'gemini-pro']
    
    for nome_modelo in modelos_para_tentar:
        try:
            model = genai.GenerativeModel(nome_modelo)
            response = model.generate_content(prompt)
            return jsonify({"resposta": response.text})
        except Exception:
            continue
            
    return jsonify({"resposta": "Jurity está processando dados. Tente novamente."})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
