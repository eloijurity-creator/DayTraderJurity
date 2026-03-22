from flask import Flask, render_template, jsonify
import pandas as pd
import numpy as np
import random

app = Flask(__name__)

def calcular_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_signal')
def get_signal():
    # Simulando dados de fechamento (Close)
    precos = [random.uniform(120000, 121000) for _ in range(50)]
    df = pd.DataFrame(precos, columns=['close'])
    
    # Cálculos da IA Falcon (Manuais)
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['rsi'] = calcular_rsi(df['close'])
    
    last_close = df['close'].iloc[-1]
    last_rsi = df['rsi'].iloc[-1]
    last_ma = df['ma20'].iloc[-1]
    
    # Lógica de Decisão
    if last_rsi < 35 and last_close > last_ma:
        sinal, cor = "COMPRA FORTE", "#00ff88"
    elif last_rsi > 65 and last_close < last_ma:
        sinal, cor = "VENDA FORTE", "#ff3b3b"
    else:
        sinal, cor = "AGUARDAR", "#f0b90b"

    return jsonify({
        "sinal": sinal, "cor": cor, "ativo": "WINJ26",
        "rsi": round(last_rsi, 2) if not np.isnan(last_rsi) else 50,
        "preco": round(last_close, 2)
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
