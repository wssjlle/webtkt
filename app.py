# mongodb+srv://webtkt:Alicia29012019@cluster0.zip50.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0
import os # Adicione esta importação no topo
from flask import Flask, render_template, request, redirect, url_for
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from datetime import datetime
from bson.objectid import ObjectId # Importar para lidar com IDs do MongoDB

# Inicializa o aplicativo Flask
app = Flask(__name__)

# --- Configuração do MongoDB ---
# COLOQUE SUA STRING DE CONEXÃO AQUI
# Lembre-se de substituir <username> e <password>
#uri = "mongodb+srv://webtkt:A29012019@cluster0.zip50.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
uri = os.environ.get("MONGODB_URI") # Busca a URI da variável de ambiente

if not uri:
    print("Erro: Variável de ambiente MONGODB_URI não configurada!")
    # Você pode definir uma URI local para desenvolvimento aqui, se quiser
    # uri = "mongodb://localhost:27017/manutencao_db_local"
    # Ou apenas encerrar o aplicativo se não encontrar a URI
    exit(1) # Sai se a URI não estiver configurada

# Cria um novo cliente e conecta ao servidor
client = MongoClient(uri, server_api=ServerApi('1'))

# Tenta enviar um ping para confirmar uma conexão bem-sucedida
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

# Define o banco de dados e a coleção que vamos usar
# O nome do banco de dados (ex: 'manutencao_db') e da coleção (ex: 'chamados')
# serão criados automaticamente se não existirem quando você inserir dados.
db = client.manutencao_db # Nome do seu banco de dados
chamados_collection = db.chamados # Nome da sua coleção (onde os chamados serão armazenados)
# --- Fim da Configuração do MongoDB ---

# Define a rota principal (home page)
@app.route('/')
def index():
    # Por enquanto, apenas renderiza o template.
    # Futuramente, podemos passar dados do MongoDB para a página inicial.
    return render_template('index.html')

# --- Rota para Abrir Novo Chamado ---
@app.route('/abrir_chamado', methods=['GET', 'POST'])
def abrir_chamado():
    if request.method == 'POST':
        # Se o formulário foi submetido (método POST)
        titulo = request.form['titulo']
        descricao = request.form['descricao']
        maquina = request.form['maquina']
        localizacao = request.form['localizacao']
        prioridade = request.form['prioridade']
        equipe_responsavel = request.form['equipe_responsavel']
        solicitante = request.form['solicitante']
        contato_solicitante = request.form['contato_solicitante']

        # Criar o documento do chamado
        novo_chamado = {
            "titulo": titulo,
            "descricao": descricao,
            "maquina": maquina,
            "localizacao": localizacao,
            "prioridade": prioridade,
            "equipe_responsavel": equipe_responsavel,
            "data_abertura": datetime.now(), # Data e hora atuais
            "status": "Aberto", # Status inicial
            "historico_status": [{"status": "Aberto", "data": datetime.now(), "por": solicitante}],
            "comentarios": [{"texto": descricao, "data": datetime.now(), "por": solicitante}], # Comentário inicial é a própria descrição
            "solicitante": solicitante,
            "contato_solicitante": contato_solicitante
        }

        # Inserir o documento na coleção de chamados
        chamados_collection.insert_one(novo_chamado)

        # Redirecionar para a página principal ou uma página de sucesso
        return redirect(url_for('index')) # Redireciona para a home após abrir o chamado

    # Se a requisição for GET, apenas exibe o formulário
    return render_template('abrir_chamado.html')

# --- Nova Rota para Listar Chamados ---
@app.route('/chamados')
def listar_chamados():
    # Busca todos os chamados na coleção, ordenando pelos mais recentes (data_abertura decrescente)
    # .find({}) significa "encontre todos os documentos"
    # .sort("campo", -1) ordena decrescente, .sort("campo", 1) ordena crescente
    chamados = list(chamados_collection.find({}).sort("data_abertura", -1))

    # Passa a lista de chamados para o template
    return render_template('lista_chamados.html', chamados=chamados)

# --- Nova Rota para Detalhes do Chamado ---
@app.route('/chamado/<chamado_id>')
def detalhes_chamado(chamado_id):
    try:
        # Busca o chamado pelo ID. Usamos ObjectId para converter a string do ID
        # para o formato que o MongoDB espera.
        chamado = chamados_collection.find_one({"_id": ObjectId(chamado_id)})
        if chamado:
            return render_template('detalhes_chamado.html', chamado=chamado)
        else:
            return "Chamado não encontrado", 404 # Retorna erro 404 se não achar
    except Exception as e:
        print(f"Erro ao buscar chamado: {e}")
        return "Erro ao buscar chamado", 500

# --- Nova Rota para Atualizar Status e Comentários ---
@app.route('/atualizar_chamado/<chamado_id>', methods=['POST'])
def atualizar_chamado(chamado_id):
    if request.method == 'POST':
        novo_status = request.form.get('novo_status')
        novo_comentario_texto = request.form.get('novo_comentario')
        quem_atualizou = request.form.get('quem_atualizou', 'Usuário Desconhecido') # Adiciona campo para quem atualizou

        try:
            # Busca o chamado para garantir que existe
            chamado_existente = chamados_collection.find_one({"_id": ObjectId(chamado_id)})

            if not chamado_existente:
                return "Chamado não encontrado", 404

            # Atualizações a serem feitas
            updates = {}

            if novo_status and novo_status != chamado_existente.get('status'):
                updates['status'] = novo_status
                # Adiciona ao histórico de status
                novo_historico = {
                    "status": novo_status,
                    "data": datetime.now(),
                    "por": quem_atualizou
                }
                # $push adiciona um elemento a um array
                chamados_collection.update_one(
                    {"_id": ObjectId(chamado_id)},
                    {"$push": {"historico_status": novo_historico}}
                )

            if novo_comentario_texto:
                novo_comentario = {
                    "texto": novo_comentario_texto,
                    "data": datetime.now(),
                    "por": quem_atualizou
                }
                # $push adiciona um elemento a um array
                chamados_collection.update_one(
                    {"_id": ObjectId(chamado_id)},
                    {"$push": {"comentarios": novo_comentario}}
                )

            # Aplica outras atualizações no documento principal (como o status)
            if updates:
                chamados_collection.update_one(
                    {"_id": ObjectId(chamado_id)},
                    {"$set": updates} # $set atualiza campos existentes ou adiciona novos
                )

            return redirect(url_for('detalhes_chamado', chamado_id=chamado_id))

        except Exception as e:
            print(f"Erro ao atualizar chamado: {e}")
            return "Erro ao processar atualização", 500
    return redirect(url_for('index')) # Se não for POST, redireciona para a home


# Garante que o aplicativo só rode se este arquivo for executado diretamente
if __name__ == '__main__':
    #app.run(debug=True)
    app.run()