from flask import Flask, render_template, jsonify
import random
import pandas as pd
import pandas_ta as ta

app = Flask(__name__)

# Simulação de base de dados da B3 (Em um cenário real, você conectaria via API)
def get_market_data():
    data = {
        'close': [random.uniform(120000, 121000) for _ in range(50)],
        'high': [random.uniform(121000, 121500) for _ in range(50)],
        'low': [random.uniform(119500, 120000) for _ in range(50)],
        'open': [random.uniform(120000, 121000) for _ in range(50)]
    }
    return pd.DataFrame(data)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_signal')
def get_signal():
    df = get_market_data()
    
    # Lógica da IA Falcon: RSI + Médias Móveis
    df['RSI'] = ta.rsi(df['close'], length=14)
    df['EMA_20'] = ta.ema(df['close'], length=20)
    
    last_rsi = df['RSI'].iloc[-1]
    last_close = df['close'].iloc[-1]
    ema_20 = df['EMA_20'].iloc[-1]
    
    # Critério de sinal
    if last_rsi < 35 and last_close > ema_20:
        sinal = "COMPRA FORTE"
        cor = "#00ff88"
    elif last_rsi > 65 and last_close < ema_20:
        sinal = "VENDA FORTE"
        cor = "#ff3b3b"
    else:
        sinal = "AGUARDAR CONFIRMAÇÃO"
        cor = "#f0b90b"

    return jsonify({
        "sinal": sinal,
        "cor": cor,
        "ativo": "WINJ26",
        "rsi": round(last_rsi, 2),
        "preco": round(last_close, 2)
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)