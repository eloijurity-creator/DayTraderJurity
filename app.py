from flask import Flask, render_template, jsonify, request
import pandas as pd
import numpy as np
import random
import os
import google.generativeai as genai

app = Flask(__name__)

# --- CONFIGURAÇÃO DO GEMINI ---
GEMINI_KEY = os.environ.get("GEMINI_KEY")
if not GEMINI_KEY:
    print("ERRO: A chave GEMINI_KEY não foi encontrada nas variáveis de ambiente!")
genai.configure(api_key=GEMINI_KEY)
# Tente este bloco no lugar da definição do model
try:
    # Teste 1: Nome direto (o mais comum para v1)
    model = genai.GenerativeModel('gemini-1.5-flash')
except:
    try:
        # Teste 2: Com sufixo latest
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
    except:
        # Teste 3: Modelo Pro estável (garantia de funcionamento)
        model = genai.GenerativeModel('gemini-pro')
# --- VARIÁVEIS GLOBAIS ---
# Armazena os últimos dados recebidos do MetaTrader 5
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

# Rota que recebe os dados do script Python que está no seu PC (MT5)
@app.route('/atualizar_dados', methods=['POST'])
def atualizar():
    global dados_reais
    content = request.json
    dados_reais["preco"] = content.get('preco', 0)
    dados_reais["bid"] = content.get('bid', 0)
    dados_reais["ask"] = content.get('ask', 0)
    dados_reais["status"] = "CONECTADO"
    return "OK", 200

# Rota que o seu index.html consulta para mostrar o sinal na tela
@app.route('/get_signal')
def get_signal():
    # Usamos o preço real vindo do MT5 para simular um histórico curto
    # Em um cenário real mais avançado, você acumularia esses preços em uma lista
    preco_base = dados_reais["preco"] if dados_reais["preco"] > 0 else 120000
    precos_simulados = [preco_base + random.uniform(-50, 50) for _ in range(30)]
    df = pd.DataFrame(precos_simulados, columns=['close'])
    
    rsi = calcular_rsi(df['close']).iloc[-1]
    
    # Lógica Simples de Exaustão
    if rsi < 30:
        sinal, cor = "COMPRA (RSI ESTICADO)", "#00ff88"
    elif rsi > 70:
        sinal, cor = "VENDA (RSI ESTICADO)", "#ff3b3b"
    else:
        sinal, cor = "AGUARDAR", "#f0b90b"

    return jsonify({
        "sinal": sinal,
        "cor": cor,
        "preco": dados_reais["preco"],
        "status": dados_reais["status"]
    })

# Rota do Chat com Inteligência Artificial (Gemini)
@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('mensagem')
    preco_atual = dados_reais.get("preco", "aguardando dados")
    
    # Prompt otimizado
    prompt = f"Trader pergunta: {user_msg}. Preço atual: {preco_atual}. Responda como Jurity IA."
    
    try:
        # Tentamos com o nome mais comum primeiro
        response = model.generate_content(prompt)
        return jsonify({"resposta": response.text})
    except Exception as e:
        # Se falhar o 404, tentamos o modelo estável antigo como backup
        try:
            backup_model = genai.GenerativeModel('gemini-pro')
            response = backup_model.generate_content(prompt)
            return jsonify({"resposta": response.text})
        except:
            return jsonify({"resposta": f"Erro Técnico: {str(e)}. Verifique se a biblioteca google-generativeai está na versão 0.7.2 no requirements.txt"})
# Certifique-se que não há espaços antes do 'if' abaixo
if __name__ == '__main__':
    # Aqui deve haver exatamente 4 espaços ou 1 TAB
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
