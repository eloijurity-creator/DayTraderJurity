from flask import Flask, render_template, jsonify, request
import pandas as pd
import os
import datetime
import google.generativeai as genai

app = Flask(__name__)

# --- CONFIGURAÇÃO IA ---
GEMINI_KEY = os.environ.get("GEMINI_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY, transport='rest')

# --- VARIÁVEIS GLOBAIS ---
historico_precos = {"WIN": [], "WDO": []}
dados_reais = {"WIN": {"preco": 0}, "WDO": {"preco": 0}}
financeiro = {"lucro_hoje": 0.0, "em_aberto": 0.0, "qtd_ordens": 0, "conta": "Desconectado"}
posicoes_abertas = [] # NOVA LISTA DETALHADA
log_performance = []
proximo_snapshot = datetime.datetime.now()
fila_ordens = {"WIN": None, "WDO": None, "PANIC": False}

def calcular_metricas(ativo):
    precos = historico_precos[ativo]
    if len(precos) < 50: return {"tendencia": "AGUARDANDO", "rsi": 50}
    df = pd.DataFrame(precos, columns=['close'])
    ma20, ma50 = df['close'].tail(20).mean(), df['close'].tail(50).mean()
    rsi = 50 # Simplificado para performance
    return {"tendencia": "ALTA" if ma20 > ma50 else "BAIXA", "rsi": rsi}

@app.route('/')
def index(): return render_template('index.html')

@app.route('/atualizar_dados', methods=['POST'])
def atualizar():
    data = request.json
    ativo = data.get('ativo')
    if ativo in dados_reais:
        dados_reais[ativo]["preco"] = data.get('preco')
        historico_precos[ativo].append(data.get('preco'))
        if len(historico_precos[ativo]) > 150: historico_precos[ativo].pop(0)
    return "OK"

@app.route('/atualizar_financeiro', methods=['POST'])
def atualizar_fin():
    global financeiro, posicoes_abertas
    data = request.json
    financeiro.update({
        "lucro_hoje": data.get('lucro_hoje'),
        "em_aberto": data.get('em_aberto'),
        "conta": data.get('conta'),
        "qtd_ordens": data.get('qtd_ordens')
    })
    posicoes_abertas = data.get('posicoes', []) # Recebe a lista do MT5
    return "OK"

@app.route('/get_signal')
def get_signal():
    ativo = request.args.get('ativo')
    m = calcular_metricas(ativo)
    return jsonify({
        "preco": dados_reais[ativo]["preco"], 
        "fin": financeiro, 
        "posicoes": posicoes_abertas,
        "rsi": f"{m['rsi']:.1f}",
        "tendencia": m['tendencia']
    })

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
    ativo = request.args.get('ativo')
    ordem = fila_ordens.get(ativo)
    fila_ordens[ativo] = None
    return jsonify(ordem)

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('mensagem')
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        res = model.generate_content(f"Trader pergunta: {user_msg}. Responda de forma curta.")
        return jsonify({"resposta": res.text})
    except: return jsonify({"resposta": "IA Indisponível."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
