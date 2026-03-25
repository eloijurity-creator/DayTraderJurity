from flask import Flask, render_template, jsonify, request
from ponte_mt5 import PonteMT5

app = Flask(__name__)
ponte = PonteMT5()

@app.route('/')
def home(): return render_template('index.html')

@app.route('/api/dados')
def dados(): return jsonify(ponte.obter_dados_completos())

@app.route('/api/analise')
def analise(): return jsonify({"conselho": ponte.analisar_mercado()})

@app.route('/api/panic', methods=['POST'])
def panic(): 
    ponte.fechar_tudo()
    return jsonify({"status": "OFF"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
