import os
from flask import Flask, render_template, request, redirect, url_for, flash
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from datetime import datetime
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

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
users_collection = db.users
equipamentos_collection = db.equipamentos # Nova coleção para equipamentos
setores_collection = db.setores       # Nova coleção para setores
# --- Fim da Configuração do MongoDB ---

# --- Configuração do Flask-Login (sem alterações aqui) ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, user_data):
        self.user_data = user_data
        self.id = str(user_data['_id'])

    @property
    def is_admin(self):
        return self.user_data.get('role') == 'admin'

@login_manager.user_loader
def load_user(user_id):
    user_data = users_collection.find_one({"_id": ObjectId(user_id)})
    if user_data:
        return User(user_data)
    return None
# --- Fim da Configuração do Flask-Login ---


# Decorador para verificar se o usuário é admin
def admin_required(f):
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('Acesso negado. Apenas administradores podem acessar esta página.', 'error')
            return redirect(url_for('index')) # Ou redirecione para uma página de erro
        return f(*args, **kwargs)
    return decorated_function

# Rota principal (Home Page)
@app.route('/')
def index():
    return render_template('index.html')

# Rota para Abrir Novo Chamado
@app.route('/abrir_chamado', methods=['GET', 'POST'])
@login_required
def abrir_chamado():
    # Buscar equipamentos e setores para preencher os <select>
    equipamentos = list(equipamentos_collection.find({}).sort("nome", 1))
    setores = list(setores_collection.find({}).sort("nome", 1))

    if request.method == 'POST':
        titulo = request.form['titulo']
        descricao = request.form['descricao']
        # Agora maquina e localizacao virão dos selects
        maquina = request.form['maquina']
        localizacao = request.form['localizacao']
        prioridade = request.form['prioridade']
        equipe_responsavel = request.form['equipe_responsavel']
        solicitante = current_user.user_data.get('username', 'Usuário Desconhecido') # Solicitante é o usuário logado
        contato_solicitante = current_user.user_data.get('contato', 'Não informado') # Adicione um campo 'contato' no user se quiser

        novo_chamado = {
            "titulo": titulo,
            "descricao": descricao,
            "maquina": maquina,
            "localizacao": localizacao,
            "prioridade": prioridade,
            "equipe_responsavel": equipe_responsavel,
            "data_abertura": datetime.now(),
            "status": "Aberto",
            "historico_status": [{"status": "Aberto", "data": datetime.now(), "por": solicitante}],
            "comentarios": [{"texto": descricao, "data": datetime.now(), "por": solicitante}],
            "solicitante": solicitante,
            "contato_solicitante": contato_solicitante
        }

        chamados_collection.insert_one(novo_chamado)
        flash('Chamado aberto com sucesso!', 'success')
        return redirect(url_for('listar_chamados'))
    
    # Passa os equipamentos e setores para o template GET
    return render_template('abrir_chamado.html', equipamentos=equipamentos, setores=setores)

# Rota para Listar Chamados (sem alterações aqui)
@app.route('/chamados')
@login_required
def listar_chamados():
    chamados = list(chamados_collection.find({}).sort("data_abertura", -1))
    return render_template('lista_chamados.html', chamados=chamados)

# Rota para Detalhes do Chamado (sem alterações aqui)
@app.route('/chamado/<chamado_id>')
@login_required
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

# Rota para Atualizar Status e Comentários (sem alterações aqui)
@app.route('/atualizar_chamado/<chamado_id>', methods=['POST'])
@login_required
def atualizar_chamado(chamado_id):
    if request.method == 'POST':
        novo_status = request.form.get('novo_status')
        novo_comentario_texto = request.form.get('novo_comentario')
        quem_atualizou = current_user.user_data.get('username', 'Usuário Desconhecido')

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

# Rotas de Autenticação (sem alterações aqui)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

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
@login_required
def logout():
    logout_user()
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('index'))

# Rota para criar o primeiro usuário admin (REMOVER EM PRODUÇÃO!)
# DEVE TER SIDO REMOVIDA/COMENTADA APÓS O TESTE ANTERIOR!
# @app.route('/criar_admin')
# def criar_admin():
#     username = "admin"
#     password = "admin_password" # Mude para uma senha forte!
#     hashed_password = generate_password_hash(password)
#     if users_collection.find_one({"username": username}):
#         flash(f'Usuário "{username}" já existe.', 'info')
#         return redirect(url_for('login'))
#     user_data = {
#         "username": username,
#         "password": hashed_password,
#         "role": "admin"
#     }
#     users_collection.insert_one(user_data)
#     flash(f'Usuário admin "{username}" criado com sucesso! Senha: {password}', 'success')
#     return redirect(url_for('login'))

# --- NOVAS ROTAS DE GERENCIAMENTO (APENAS PARA ADMIN) ---

@app.route('/admin_panel')
@admin_required # Apenas admins podem acessar
def admin_panel():
    return render_template('admin_panel.html')

# Gerenciamento de Setores
@app.route('/admin/setores', methods=['GET', 'POST'])
@admin_required
def gerenciar_setores():
    if request.method == 'POST':
        nome_setor = request.form['nome_setor'].strip()
        if nome_setor:
            # Verifica se o setor já existe para evitar duplicidade
            if setores_collection.find_one({"nome": nome_setor}):
                flash(f'Setor "{nome_setor}" já existe.', 'error')
            else:
                setores_collection.insert_one({"nome": nome_setor})
                flash(f'Setor "{nome_setor}" adicionado com sucesso!', 'success')
        else:
            flash('O nome do setor não pode ser vazio.', 'error')
        return redirect(url_for('gerenciar_setores'))
    
    setores = list(setores_collection.find({}).sort("nome", 1))
    return render_template('gerenciar_setores.html', setores=setores)

# Gerenciamento de Equipamentos
@app.route('/admin/equipamentos', methods=['GET', 'POST'])
@admin_required
def gerenciar_equipamentos():
    # Buscar setores para preencher o select de setor
    setores_disponiveis = list(setores_collection.find({}).sort("nome", 1))

    if request.method == 'POST':
        nome_equipamento = request.form['nome_equipamento'].strip()
        setor_id = request.form['setor_id'] # ID do setor selecionado

        if nome_equipamento and setor_id:
            # Pega o nome do setor pelo ID para armazenar junto ao equipamento
            setor_obj = setores_collection.find_one({"_id": ObjectId(setor_id)})
            if not setor_obj:
                flash('Setor selecionado inválido.', 'error')
                return redirect(url_for('gerenciar_equipamentos'))

            # Verifica se o equipamento já existe para evitar duplicidade
            if equipamentos_collection.find_one({"nome": nome_equipamento}):
                flash(f'Equipamento "{nome_equipamento}" já existe.', 'error')
            else:
                equipamentos_collection.insert_one({
                    "nome": nome_equipamento,
                    "setor_id": ObjectId(setor_id),
                    "setor_nome": setor_obj['nome'] # Armazena o nome também para facilitar consultas
                })
                flash(f'Equipamento "{nome_equipamento}" adicionado com sucesso!', 'success')
        else:
            flash('Nome do equipamento e setor são obrigatórios.', 'error')
        return redirect(url_for('gerenciar_equipamentos'))
    
    equipamentos = list(equipamentos_collection.find({}).sort("nome", 1))
    return render_template('gerenciar_equipamentos.html', equipamentos=equipamentos, setores=setores_disponiveis)


# Garante que o aplicativo só rode se este arquivo for executado diretamente
if __name__ == '__main__':
    app.run(debug=True)