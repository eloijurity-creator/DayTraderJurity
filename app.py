from flask import Flask, render_template, jsonify, request
import pandas as pd
import numpy as np
import os
import datetime
import google.generativeai as genai

app = Flask(__name__)

# --- CONFIGURAÇÃO IA JURITY 2.5 ---
GEMINI_KEY = os.environ.get("GEMINI_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
else:
    print("AVISO: Chave GEMINI_KEY não encontrada nas variáveis de ambiente!")

# --- VARIÁVEIS GLOBAIS ---
historico_precos = {"WIN": [], "WDO": []}
dados_reais = {"WIN": {"preco": 0}, "WDO": {"preco": 0}}
financeiro = {
    "resultado_dia": 0.0, 
    "em_aberto": 0.0, 
    "saldo_atual": 0.0, 
    "conta": "Desconectado"
}
posicoes_abertas = [] 
historico_performance = []
fila_ordens = {"WIN": None, "WDO": None, "PANIC": False}

def calcular_metricas(ativo):
    precos = historico_precos[ativo]
    if len(precos) < 20: return {"tendencia": "LATERAL", "rsi": 50.0}
    df = pd.DataFrame(precos, columns=['close'])
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, 0.001)
    rsi = 100 - (100 / (1 + rs.iloc[-1]))
    ma10, ma30 = df['close'].tail(10).mean(), df['close'].tail(30).mean()
    return {"tendencia": "ALTA" if ma10 > ma30 else "BAIXA", "rsi": rsi}

def gerar_sugestao(m):
    rsi, tend = m['rsi'], m['tendencia']
    if rsi < 30: return "FORTE COMPRA" if tend == "ALTA" else "COMPRA (EXAUSTÃO)"
    if rsi > 70: return "FORTE VENDA" if tend == "BAIXA" else "VENDA (EXAUSTÃO)"
    return "AGUARDAR" if 45 < rsi < 55 else "NEUTRO"

@app.route('/')
def index(): return render_template('index.html')

@app.route('/atualizar_dados', methods=['POST'])
def atualizar():
    data = request.json
    ativo = data.get('ativo')
    if ativo in dados_reais:
        preco = data.get('preco')
        dados_reais[ativo]["preco"] = preco
        historico_precos[ativo].append(preco)
        if len(historico_precos[ativo]) > 100: historico_precos[ativo].pop(0)
    return "OK"

@app.route('/atualizar_financeiro', methods=['POST'])
def atualizar_fin():
    global financeiro, posicoes_abertas, historico_performance
    data = request.json
    financeiro.update({
        "resultado_dia": data.get('resultado_dia', 0.0),
        "em_aberto": data.get('em_aberto', 0.0),
        "saldo_atual": data.get('saldo_atual', 0.0),
        "conta": data.get('conta', "Desconectado")
    })
    posicoes_abertas = data.get('posicoes', [])
    agora = datetime.datetime.now().strftime("%H:%M:%S")
    if not historico_performance or historico_performance[-1]["acumulado"] != financeiro["saldo_atual"]:
        historico_performance.append({"horario": agora, "acumulado": financeiro["saldo_atual"]})
        if len(historico_performance) > 60: historico_performance.pop(0)
    return "OK"

@app.route('/get_signal')
def get_signal():
    m_win, m_wdo = calcular_metricas("WIN"), calcular_metricas("WDO")
    return jsonify({
        "win": {"preco": dados_reais["WIN"]["preco"], "rsi": round(m_win['rsi'],1), "tend": m_win['tendencia'], "sug": gerar_sugestao(m_win)},
        "wdo": {"preco": dados_reais["WDO"]["preco"], "rsi": round(m_wdo['rsi'],1), "tend": m_wdo['tendencia'], "sug": gerar_sugestao(m_wdo)},
        "fin": financeiro, 
        "posicoes": posicoes_abertas, 
        "historico": historico_performance
    })

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('mensagem')
    m_win, m_wdo = calcular_metricas("WIN"), calcular_metricas("WDO")
    
    # Prompt rico em contexto para a Gemini 2.5 Flash
    prompt = (
        f"Você é a Jurity IA 2.5 Flash, especialista em Day Trade. "
        f"CONTEXTO ATUAL: WIN: {dados_reais['WIN']['preco']} (RSI {m_win['rsi']:.1f}, {m_win['tendencia']}), "
        f"WDO: {dados_reais['WDO']['preco']} (RSI {m_wdo['rsi']:.1f}, {m_wdo['tendencia']}). "
        f"FINANCEIRO: Saldo R$ {financeiro['saldo_atual']:.2f}, Resultado do Dia R$ {financeiro['resultado_dia']:.2f}. "
        f"Posições Abertas: {len(posicoes_abertas)}. "
        f"Pergunta do usuário: {user_msg}"
    )
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        res = model.generate_content(prompt)
        return jsonify({"resposta": res.text})
    except Exception as e:
        return jsonify({"resposta": f"Erro na Jurity 2.5: {str(e)}"})

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
