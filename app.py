from flask import Flask, render_template, jsonify, request
import pandas as pd
import numpy as np
import random
import os
import google.generativeai as genai

app = Flask(__name__)

# --- CONFIGURAÇÃO DA JURITY IA ---
# REMOVA QUALQUER ESPAÇO ANTES DA LINHA ABAIXO:
GEMINI_KEY = "AIzaSyAMg1aMjn3LMQAyUI2D2LP-If7hrIzALd4"
genai.configure(api_key=GEMINI_KEY)

# Usando o nome direto do modelo para evitar o erro 404
model = genai.GenerativeModel('gemini-2.5-flash')

# --- VARIÁVEIS GLOBAIS ---
dados_reais = {
    "preco": 0,
    "bid": 0,
    "ask": 0,
    "status": "Aguardando MT5..."
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
    dados_reais["preco"] = content.get('preco', 0)
    dados_reais["bid"] = content.get('bid', 0)
    dados_reais["ask"] = content.get('ask', 0)
    dados_reais["status"] = "CONECTADO"
    return "OK", 200

@app.route('/get_signal')
def get_signal():
    preco_base = dados_reais["preco"] if dados_reais["preco"] > 0 else 120000
    precos_simulados = [preco_base + random.uniform(-50, 50) for _ in range(30)]
    df = pd.DataFrame(precos_simulados, columns=['close'])
    
    rsi_val = calcular_rsi(df['close']).iloc[-1]
    
    if rsi_val < 35:
        sinal, cor = "COMPRA (JURITY IA)", "#00ff88"
    elif rsi_val > 65:
        sinal, cor = "VENDA (JURITY IA)", "#ff3b3b"
    else:
        sinal, cor = "AGUARDAR", "#f0b90b"

    return jsonify({
        "sinal": sinal,
        "cor": cor,
        "preco": dados_reais["preco"],
        "status": dados_reais["status"]
    })

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('mensagem')
    preco_atual = dados_reais.get("preco", "aguardando dados")
    
    # Prompt com a personalidade Jurity
    prompt = f"""
    Você é a Jurity IA, uma assistente senior de Day Trade na B3, especializada em Mini Índice.
    Contexto Atual do Mercado: O preço está em {preco_atual} pontos.
    Instrução: Responda ao trader de forma técnica, curta e direta. Não use saudações longas.
    Pergunta do Trader: {user_msg}
    """
    
    try:
        response = model.generate_content(prompt)
        return jsonify({"resposta": response.text})
    except Exception as e:
        # Fallback para o modelo Pro se o Flash der erro 404
        try:
            fallback_model = genai.GenerativeModel('gemini-pro')
            res = fallback_model.generate_content(prompt)
            return jsonify({"resposta": res.text})
        except:
            return jsonify({"resposta": "Jurity está offline. Verifique a chave API no Render."})

# --- INICIALIZAÇÃO COM INDENTAÇÃO CORRETA ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
