from flask import Flask, render_template, jsonify, request
from datetime import datetime
import google.generativeai as genai
import os
import random

app = Flask(__name__)

# --- CONFIGURAÇÃO DA JURITY IA (GEMINI) ---
GEMINI_KEY = os.environ.get("GEMINI_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY, transport='rest')
else:
    print("ERRO: Variável GEMINI_KEY não encontrada no sistema.")

# Dados Globais
dados_mercado = {
    "WIN": {"preco": 0, "sugestao": "NEUTRO", "status": "Offline"},
    "WDO": {"preco": 0, "sugestao": "NEUTRO", "status": "Offline"}
}
financeiro = {"resultado_dia": 0, "saldo_atual": 0, "conta": "Desconectado", "posicoes": []}
historico_equity = []
fila_comandos = []

@app.route('/')
def index(): return render_template('index.html')

@app.route('/atualizar_dados', methods=['POST'])
def atualizar_dados():
    data = request.json
    ativo = data.get('ativo')
    if ativo in dados_mercado:
        dados_mercado[ativo]['preco'] = data.get('preco')
        dados_mercado[ativo]['status'] = "Conectado"
        # Simulação de gatilho estratégico (Pode ser substituído por lógica técnica)
        sorteio = random.random()
        if sorteio > 0.98: dados_mercado[ativo]['sugestao'] = "COMPRA"
        elif sorteio < 0.02: dados_mercado[ativo]['sugestao'] = "VENDA"
        else: dados_mercado[ativo]['sugestao'] = "NEUTRO"
    return jsonify({"status": "ok"})

@app.route('/atualizar_financeiro', methods=['POST'])
def atualizar_financeiro():
    global financeiro, historico_equity
    data = request.json
    financeiro.update(data)
    agora = datetime.now().strftime('%H:%M:%S')
    saldo = data.get('saldo_atual', 0)
    if not historico_equity or (historico_equity[-1]['y'] != saldo):
        historico_equity.append({'x': agora, 'y': saldo})
    if len(historico_equity) > 30: historico_equity.pop(0)
    return jsonify({"status": "ok"})

@app.route('/chat', methods=['POST'])
def chat():
    pergunta = request.json.get('mensagem', '')
    
    # Criando o contexto para o Gemini
    contexto = f"""
    Você é a Jurity IA, uma assistente especializada em Day Trade.
    Dados atuais:
    - Mini Índice (WIN): {dados_mercado['WIN']['preco']}
    - Mini Dólar (WDO): {dados_mercado['WDO']['preco']}
    - Saldo Equity: R$ {financeiro['saldo_atual']}
    - Resultado do Dia: R$ {financeiro['resultado_dia']}
    - Ordens abertas: {len(financeiro['posicoes'])}
    
    Responda de forma técnica, porém objetiva e encorajadora. 
    Se o usuário perguntar sobre o mercado, analise com base nesses números.
    Pergunta do usuário: {pergunta}
    """

    modelos_para_tentar = ['gemini-1.5-flash', 'gemini-2.5-flash', 'gemini-pro']
    
    for nome_modelo in modelos_para_tentar:
        try:
            model = genai.GenerativeModel(nome_modelo)
            response = model.generate_content(contexto)
            return jsonify({"resposta": response.text})
        except Exception as e:
            print(f"Erro no modelo {nome_modelo}: {e}")
            continue
            
    return jsonify({"resposta": "Jurity está processando os alvos. Tente novamente em instantes."})

# Rotas de suporte
@app.route('/get_signal')
def get_signal(): return jsonify(dados_mercado.get(request.args.get('ativo'), {}))
@app.route('/get_financeiro')
def get_financeiro(): return jsonify(financeiro)
@app.route('/get_historico')
def get_historico(): return jsonify(historico_equity)
@app.route('/order', methods=['POST'])
def order(): 
    fila_comandos.append(request.json)
    return jsonify({"status": "ok"})
@app.route('/get_orders')
def get_orders(): return jsonify(fila_comandos.pop(0)) if fila_comandos else jsonify({})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
