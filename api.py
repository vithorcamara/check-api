# Autenticação global para evitar repetir a autorização em cada chamada
from flask import Flask, jsonify, Response, request
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from flask_cors import CORS, cross_origin
import json
import dotenv
# Carrega as variáveis de ambiente do arquivo .env
dotenv.load_dotenv()

app = Flask(__name__)
CORS(app, origins=["https://checklab.vercel.app"])  # Permite CORS de qualquer origem

SPREADSHEET_NAME = "CheckLab"
SCOPE = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive',
]
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON")
if not GOOGLE_CREDENTIALS_JSON:
    raise ValueError("Variável de ambiente GOOGLE_CREDENTIALS_JSON não está definida")

# Converte a string JSON da variável de ambiente para dicionário
credentials_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, SCOPE)
client = gspread.authorize(creds)


def get_google_sheet_data(pagina):
    spreadsheet = client.open(SPREADSHEET_NAME)
    if not spreadsheet:
        raise ValueError(f"Planilha '{SPREADSHEET_NAME}' não encontrada.")
    
    if pagina == "dados":
        worksheets = spreadsheet.worksheets()[1:]  # exceto a primeira aba
    elif pagina == "resumo":
        worksheets = [spreadsheet.worksheets()[0]]  # apenas a primeira aba
    else:
        raise ValueError("Parâmetro inválido para 'pagina'")

    dfs = []
    for sheet in worksheets:
        data = sheet.get_all_records()
        if data:
            df = pd.DataFrame(data)
            first_col = df.columns[0]
            df = df[df[first_col].astype(str).str.strip() != '']
            if not df.empty:
                dfs.append(df)

    if dfs:
        final_df = pd.concat(dfs, ignore_index=True)
        final_df = final_df.sort_values(by=final_df.columns[0])
        return final_df
    else:
        return pd.DataFrame()

def get_google_spreadsheet():
    return client.open(SPREADSHEET_NAME)

@app.route("/dados", methods=["GET"])
def dados():
    df = get_google_sheet_data("dados")
    if df.empty:
        return jsonify({"mensagem": "Nenhuma aba (exceto a primeira) contém dados."}), 404
    else:
        json_data = json.dumps(df.to_dict(orient="records"), ensure_ascii=False)
        return Response(json_data, content_type='application/json; charset=utf-8')

@app.route('/addAluno', methods=['POST'])
def add_aluno():
    dados = request.json

    campos_necessarios = ["ID", "Nome Social", "Matrícula", "IES", "Curso", "Turno", "E-mail", "Ticket", "Data", "Usuário"]
    for campo in campos_necessarios:
        if campo not in dados:
            return jsonify({"erro": f"Campo '{campo}' é obrigatório"}), 400

    try:
        spreadsheet = get_google_spreadsheet()
        try:
            worksheet = spreadsheet.worksheet("Registro")
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title="Registro", rows="1000", cols="10")
            worksheet.append_row(campos_necessarios)

        linha = [
            dados["ID"],
            dados["Nome Social"],
            dados["Matrícula"],
            dados["IES"],
            dados["Curso"],
            dados["Turno"],
            dados["E-mail"],
            dados["Ticket"],
            dados["Data"],
            dados["Usuário"]
        ]

        worksheet.append_row(linha)

        return jsonify({"mensagem": "Presença registrada com sucesso!"}), 200

    except Exception as e:
        return jsonify({"erro": "Falha ao salvar presença", "detalhes": str(e)}), 500

@app.route("/resumo", methods=["GET"])
@cross_origin()
def resumo():
    spreadsheet = get_google_spreadsheet()
    worksheet = spreadsheet.get_worksheet(0)  # Primeira aba
    data = worksheet.get_all_records()
    if not data:
        return jsonify({"mensagem": "Resumo vazio."}), 404

    df = pd.DataFrame(data)
    json_data = json.dumps(df.to_dict(orient="records"), ensure_ascii=False)
    return Response(json_data, content_type='application/json; charset=utf-8')