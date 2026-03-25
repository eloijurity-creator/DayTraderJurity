from flask import Flask, render_template, jsonify, request
import pandas as pd
import os
import datetime
import google.generativeai as genai

app = Flask(__name__)

# --- IA CONFIG ---
GEMINI_KEY = os.environ.get("GEMINI_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# --- MEMÓRIA DO SISTEMA ---
historico_precos = {"WIN": [], "WDO": []}
dados_reais = {"WIN": {"preco": 0}, "WDO": {"preco": 0}}
financeiro = {"resultado_dia": 0.0, "em_aberto": 0.0, "saldo_atual": 0.0, "conta": "Desconectado"}
posicoes_abertas = [] 
historico_performance = []
fila_ordens = {"WIN": None, "WDO": None, "PANIC": False}

def calcular_ia(ativo):
    precos = historico_precos[ativo]
    if len(precos) < 20: return {"tendencia": "NEUTRA", "rsi": 50.0, "forca": 0}
    df = pd.DataFrame(precos, columns=['close'])
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, 0.001)
    rsi = 100 - (100 / (1 + rs.iloc[-1]))
    ma10, ma30 = df['close'].tail(10).mean(), df['close'].tail(30).mean()
    tend = "ALTA" if ma10 > ma30 else "BAIXA"
    
    forca = 0
    if tend == "ALTA" and rsi < 35: forca = 80 + (35 - rsi)
    if tend == "BAIXA" and rsi > 65: forca = 80 + (rsi - 65)
    return {"tendencia": tend, "rsi": rsi, "forca": min(int(forca), 100)}

@app.route('/')
def index(): return render_template('index.html')

@app.route('/atualizar_dados', methods=['POST'])
def atualizar():
    data = request.json
    ativo = data.get('ativo')
    if ativo in dados_reais:
        dados_reais[ativo]["preco"] = data.get('preco')
        historico_precos[ativo].append(data.get('preco'))
        if len(historico_precos[ativo]) > 100: historico_precos[ativo].pop(0)
    return "OK"

@app.route('/atualizar_financeiro', methods=['POST'])
def atualizar_fin():
    global financeiro, posicoes_abertas, historico_performance
    data = request.json
    financeiro.update(data)
    posicoes_abertas = data.get('posicoes', [])
    agora = datetime.datetime.now().strftime("%H:%M:%S")
    if not historico_performance or (len(historico_performance) == 0 or historico_performance[-1]["acumulado"] != data['saldo_atual']):
        historico_performance.append({"horario": agora, "acumulado": data['saldo_atual']})
        if len(historico_performance) > 50: historico_performance.pop(0)
    return "OK"

@app.route('/get_signal')
def get_signal():
    m_win, m_wdo = calcular_ia("WIN"), calcular_ia("WDO")
    def gerar_sugestao(m):
        if m['forca'] >= 80:
            tipo = "BUY" if m['tendencia'] == "ALTA" else "SELL"
            return {"tipo": tipo, "texto": f"IA SUGERE {tipo} ({m['forca']}% CONF.)", "forca": m['forca']}
        return None

    return jsonify({
        "win": {"preco": dados_reais["WIN"]["preco"], "rsi": round(m_win['rsi'],1), "tend": m_win['tendencia'], "sugestao": gerar_sugestao(m_win)},
        "wdo": {"preco": dados_reais["WDO"]["preco"], "rsi": round(m_wdo['rsi'],1), "tend": m_wdo['tendencia'], "sugestao": gerar_sugestao(m_wdo)},
        "fin": financeiro, "posicoes": posicoes_abertas, "historico": historico_performance
    })

@app.route('/chat', methods=['POST'])
def chat():
    msg = request.json.get('mensagem')
    prompt = f"Você é a Jurity IA 2.5 Flash. Trader pergunta: {msg}. Contexto: WIN={dados_reais['WIN']['preco']}, Saldo=R${financeiro['saldo_atual']}. Responda curto e técnico em PT-BR."
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        res = model.generate_content(prompt)
        return jsonify({"resposta": res.text})
    except: return jsonify({"resposta": "IA Offline."})

@app.route('/set_order', methods=['POST'])
def set_order():
    global fila_ordens
    data = request.json
    if data.get('tipo') == 'PANIC': fila_ordens["PANIC"] = True
    else: fila_ordens[data['ativo']] = data
    return jsonify({"status": "OK"})

@app.route('/get_orders')
def get_orders():
    global fila_ordens
    if fila_ordens["PANIC"]:
        fila_ordens["PANIC"] = False
        return jsonify({"tipo": "PANIC"})
    ordem = fila_ordens.get(request.args.get('ativo'))
    fila_ordens[request.args.get('ativo')] = None
    return jsonify(ordem)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
