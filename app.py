
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from datetime import datetime
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash # Para hashing de senhas
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user # Flask-Login

# Inicializa o aplicativo Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'ouropretomineracaopomerodesc' # Mude isso para uma chave real e segura!

# --- Configuração do MongoDB (Mantenha o que você já tem) ---
uri = os.environ.get("MONGODB_URI") # Busca a URI da variável de ambiente

if not uri:
    print("Erro: Variável de ambiente MONGODB_URI não configurada!")
    # Você pode definir uma URI local para desenvolvimento aqui, se quiser
    # uri = "mongodb://localhost:27017/manutencao_db_local"
    # Ou apenas encerrar o aplicativo se não encontrar a URI
    exit(1) # Sai se a URI não estiver configurada
client = MongoClient(uri, server_api=ServerApi('1'))

try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

db = client.manutencao_db
chamados_collection = db.chamados
users_collection = db.users # Nova coleção para usuários
# --- Fim da Configuração do MongoDB ---

# --- Configuração do Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Define a rota para onde o usuário será redirecionado se não estiver logado

# Classe User para Flask-Login
class User(UserMixin):
    def __init__(self, user_data):
        self.user_data = user_data # Dicionário com os dados do usuário do MongoDB
        self.id = str(user_data['_id']) # Flask-Login precisa de um 'id' em string

    @property
    def is_admin(self):
        # Propriedade para verificar se o usuário é administrador
        return self.user_data.get('role') == 'admin'

@login_manager.user_loader
def load_user(user_id):
    # Esta função é chamada pelo Flask-Login para recarregar o usuário
    # a partir do ID armazenado na sessão.
    user_data = users_collection.find_one({"_id": ObjectId(user_id)})
    if user_data:
        return User(user_data)
    return None

# --- Fim da Configuração do Flask-Login ---


# Rota principal (Home Page)
@app.route('/')
def index():
    return render_template('index.html')

# Rota para Abrir Novo Chamado
@app.route('/abrir_chamado', methods=['GET', 'POST'])
@login_required # Protege esta rota: exige login
def abrir_chamado():
    if request.method == 'POST':
        titulo = request.form['titulo']
        descricao = request.form['descricao']
        maquina = request.form['maquina']
        localizacao = request.form['localizacao']
        prioridade = request.form['prioridade']
        equipe_responsavel = request.form['equipe_responsavel']
        # O solicitante e contato agora podem vir do usuário logado se for o caso,
        # ou ainda do formulário, dependendo da sua regra de negócio.
        # Por enquanto, vamos manter do formulário.
        solicitante = request.form['solicitante']
        contato_solicitante = request.form['contato_solicitante']

        novo_chamado = {
            "titulo": titulo,
            "descricao": descricao,
            "maquina": maquina,
            "localizacao": localizacao,
            "prioridade": prioridade,
            "equipe_responsavel": equipe_responsavel,
            "data_abertura": datetime.now(),
            "status": "Aberto",
            "historico_status": [{"status": "Aberto", "data": datetime.now(), "por": current_user.user_data.get('username', solicitante)}], # Usa o nome do usuário logado
            "comentarios": [{"texto": descricao, "data": datetime.now(), "por": current_user.user_data.get('username', solicitante)}],
            "solicitante": solicitante,
            "contato_solicitante": contato_solicitante
        }

        chamados_collection.insert_one(novo_chamado)
        flash('Chamado aberto com sucesso!', 'success') # Mensagem de sucesso
        return redirect(url_for('listar_chamados')) # Redireciona para a lista
    return render_template('abrir_chamado.html')

# Rota para Listar Chamados
@app.route('/chamados')
@login_required # Protege esta rota: exige login
def listar_chamados():
    chamados = list(chamados_collection.find({}).sort("data_abertura", -1))
    return render_template('lista_chamados.html', chamados=chamados)

# Rota para Detalhes do Chamado
@app.route('/chamado/<chamado_id>')
@login_required # Protege esta rota: exige login
def detalhes_chamado(chamado_id):
    try:
        chamado = chamados_collection.find_one({"_id": ObjectId(chamado_id)})
        if chamado:
            return render_template('detalhes_chamado.html', chamado=chamado)
        else:
            flash("Chamado não encontrado.", 'error')
            return redirect(url_for('listar_chamados'))
    except Exception as e:
        flash(f"Erro ao buscar chamado: {e}", 'error')
        return redirect(url_for('listar_chamados'))

# Rota para Atualizar Status e Comentários
@app.route('/atualizar_chamado/<chamado_id>', methods=['POST'])
@login_required # Protege esta rota: exige login
def atualizar_chamado(chamado_id):
    if request.method == 'POST':
        novo_status = request.form.get('novo_status')
        novo_comentario_texto = request.form.get('novo_comentario')
        quem_atualizou = current_user.user_data.get('username', 'Usuário Desconhecido') # Agora pegamos o nome do usuário logado

        try:
            chamado_existente = chamados_collection.find_one({"_id": ObjectId(chamado_id)})

            if not chamado_existente:
                flash("Chamado não encontrado.", 'error')
                return redirect(url_for('listar_chamados'))

            updates = {}

            if novo_status and novo_status != chamado_existente.get('status'):
                updates['status'] = novo_status
                novo_historico = {
                    "status": novo_status,
                    "data": datetime.now(),
                    "por": quem_atualizou
                }
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
                chamados_collection.update_one(
                    {"_id": ObjectId(chamado_id)},
                    {"$push": {"comentarios": novo_comentario}}
                )

            if updates:
                chamados_collection.update_one(
                    {"_id": ObjectId(chamado_id)},
                    {"$set": updates}
                )
            
            flash('Chamado atualizado com sucesso!', 'success')
            return redirect(url_for('detalhes_chamado', chamado_id=chamado_id))

        except Exception as e:
            flash(f"Erro ao processar atualização: {e}", 'error')
            return redirect(url_for('detalhes_chamado', chamado_id=chamado_id))
    return redirect(url_for('index'))

# --- Novas Rotas de Autenticação ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index')) # Se já logado, vai para a home

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user_data = users_collection.find_one({"username": username})

        if user_data and check_password_hash(user_data['password'], password):
            user = User(user_data)
            login_user(user)
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Nome de usuário ou senha inválidos.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required # Só pode fazer logout se estiver logado
def logout():
    logout_user()
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('index'))

# Rota para criar o primeiro usuário admin (REMOVER EM PRODUÇÃO!)
# Esta rota deve ser usada APENAS UMA VEZ para criar o primeiro administrador
# Depois de criar, você deve COMENTAR OU REMOVER esta rota por segurança.
@app.route('/criar_admin')
def criar_admin():
    username = "admin"
    password = "ouropreto" # Mude para uma senha forte!
    hashed_password = generate_password_hash(password)

    # Verifica se o usuário já existe
    if users_collection.find_one({"username": username}):
        flash(f'Usuário "{username}" já existe.', 'info')
        return redirect(url_for('login'))

    user_data = {
        "username": username,
        "password": hashed_password,
        "role": "admin" # Define como admin
    }
    users_collection.insert_one(user_data)
    flash(f'Usuário admin "{username}" criado com sucesso! Senha: {password}', 'success')
    return redirect(url_for('login'))


# Garante que o aplicativo só rode se este arquivo for executado diretamente
if __name__ == '__main__':
    app.run(debug=True)