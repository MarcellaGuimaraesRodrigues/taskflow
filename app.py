import os
import re
from flask import Flask, render_template, request, redirect, flash, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "troque_essa_chave_no_env")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///banco.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "index"
login_manager.login_message = "Faça login para acessar essa página."
login_manager.login_message_category = "erro"


class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    senha = db.Column(db.String(255), nullable=False)


class Tarefa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    categoria = db.Column(db.String(100), nullable=False)
    prioridade = db.Column(db.String(50), nullable=False, default="Média")
    status = db.Column(db.String(50), nullable=False, default="hoje")
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))


def senha_forte(senha):
    """
    Regras:
    - mínimo 8 caracteres
    - pelo menos 1 letra maiúscula
    - pelo menos 1 número
    """
    if len(senha) < 8:
        return False, "A senha precisa ter pelo menos 8 caracteres."

    if not re.search(r"[A-Z]", senha):
        return False, "A senha precisa ter pelo menos 1 letra maiúscula."

    if not re.search(r"\d", senha):
        return False, "A senha precisa ter pelo menos 1 número."

    return True, ""


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect("/dashboard")
    return render_template("index.html")


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if current_user.is_authenticated:
        return redirect("/dashboard")

    if request.method == "POST":
        nome = request.form["nome"].strip()
        email = request.form["email"].strip().lower()
        senha = request.form["senha"].strip()
        confirmar_senha = request.form["confirmar_senha"].strip()

        if len(nome) < 2:
            flash("O nome precisa ter pelo menos 2 caracteres.", "erro")
            return render_template("cadastro.html")

        usuario_existente = Usuario.query.filter_by(email=email).first()
        if usuario_existente:
            flash("Esse e-mail já está cadastrado.", "erro")
            return render_template("cadastro.html")

        forte, mensagem = senha_forte(senha)
        if not forte:
            flash(mensagem, "erro")
            return render_template("cadastro.html")

        if senha != confirmar_senha:
            flash("As senhas não coincidem.", "erro")
            return render_template("cadastro.html")

        senha_hash = generate_password_hash(senha)

        novo_usuario = Usuario(
            nome=nome,
            email=email,
            senha=senha_hash
        )

        db.session.add(novo_usuario)
        db.session.commit()

        flash("Conta criada com sucesso. Faça login.", "sucesso")
        return redirect("/")

    return render_template("cadastro.html")


@app.route("/login", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect("/dashboard")

    email = request.form["email"].strip().lower()
    senha = request.form["senha"].strip()

    usuario = Usuario.query.filter_by(email=email).first()

    if usuario and check_password_hash(usuario.senha, senha):
        login_user(usuario)
        flash("Login realizado com sucesso.", "sucesso")
        return redirect("/dashboard")

    flash("E-mail ou senha inválidos.", "erro")
    return redirect("/")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Você saiu da conta.", "sucesso")
    return redirect("/")


@app.route("/dashboard")
@login_required
def dashboard():
    total = Tarefa.query.filter_by(usuario_id=current_user.id).count()
    hoje = Tarefa.query.filter_by(usuario_id=current_user.id, status="hoje").count()
    semana = Tarefa.query.filter_by(usuario_id=current_user.id, status="semana").count()
    depois = Tarefa.query.filter_by(usuario_id=current_user.id, status="depois").count()
    concluido = Tarefa.query.filter_by(usuario_id=current_user.id, status="concluido").count()

    categorias = (
        db.session.query(Tarefa.categoria)
        .filter_by(usuario_id=current_user.id)
        .distinct()
        .all()
    )
    categorias = [c[0] for c in categorias]

    return render_template(
        "dashboard.html",
        total=total,
        hoje=hoje,
        semana=semana,
        depois=depois,
        concluido=concluido,
        categorias=categorias,
        nome=current_user.nome
    )


@app.route("/board")
@login_required
def board():
    filtro_categoria = request.args.get("categoria", "").strip()

    query = Tarefa.query.filter_by(usuario_id=current_user.id)

    if filtro_categoria:
        query = query.filter_by(categoria=filtro_categoria)

    tarefas = query.order_by(Tarefa.id.desc()).all()

    col_hoje = [t for t in tarefas if t.status == "hoje"]
    col_semana = [t for t in tarefas if t.status == "semana"]
    col_depois = [t for t in tarefas if t.status == "depois"]
    col_concluido = [t for t in tarefas if t.status == "concluido"]

    categorias = (
        db.session.query(Tarefa.categoria)
        .filter_by(usuario_id=current_user.id)
        .distinct()
        .all()
    )
    categorias = [c[0] for c in categorias]

    return render_template(
        "board.html",
        nome=current_user.nome,
        categorias=categorias,
        categoria_ativa=filtro_categoria,
        col_hoje=col_hoje,
        col_semana=col_semana,
        col_depois=col_depois,
        col_concluido=col_concluido
    )


@app.route("/add", methods=["POST"])
@login_required
def add():
    titulo = request.form["titulo"].strip()
    descricao = request.form["descricao"].strip()
    categoria = request.form["categoria"].strip()
    prioridade = request.form["prioridade"].strip()
    status = request.form["status"].strip()

    if not titulo or not categoria:
        flash("Título e categoria são obrigatórios.", "erro")
        return redirect("/board")

    nova_tarefa = Tarefa(
        titulo=titulo,
        descricao=descricao,
        categoria=categoria,
        prioridade=prioridade,
        status=status,
        usuario_id=current_user.id
    )

    db.session.add(nova_tarefa)
    db.session.commit()

    flash("Tarefa adicionada com sucesso.", "sucesso")
    return redirect("/board")


@app.route("/move/<int:id>/<novo_status>")
@login_required
def move(id, novo_status):
    tarefa = Tarefa.query.get_or_404(id)

    if tarefa.usuario_id != current_user.id:
        flash("Você não pode alterar essa tarefa.", "erro")
        return redirect("/board")

    if novo_status in ["hoje", "semana", "depois", "concluido"]:
        tarefa.status = novo_status
        db.session.commit()
        flash("Tarefa atualizada.", "sucesso")

    return redirect("/board")


@app.route("/delete/<int:id>")
@login_required
def delete(id):
    tarefa = Tarefa.query.get_or_404(id)

    if tarefa.usuario_id != current_user.id:
        flash("Você não pode excluir essa tarefa.", "erro")
        return redirect("/board")

    db.session.delete(tarefa)
    db.session.commit()
    flash("Tarefa excluída com sucesso.", "sucesso")
    return redirect("/board")


@app.route("/perfil", methods=["GET", "POST"])
@login_required
def perfil():
    if request.method == "POST":
        nome = request.form["nome"].strip()
        email = request.form["email"].strip().lower()

        if len(nome) < 2:
            flash("O nome precisa ter pelo menos 2 caracteres.", "erro")
            return redirect("/perfil")

        usuario_existente = Usuario.query.filter(Usuario.email == email, Usuario.id != current_user.id).first()
        if usuario_existente:
            flash("Esse e-mail já está em uso.", "erro")
            return redirect("/perfil")

        current_user.nome = nome
        current_user.email = email
        db.session.commit()

        flash("Perfil atualizado com sucesso.", "sucesso")
        return redirect("/perfil")

    return render_template("perfil.html")


@app.route("/redefinir_senha", methods=["GET", "POST"])
@login_required
def redefinir_senha():
    if request.method == "POST":
        senha_atual = request.form["senha_atual"].strip()
        nova_senha = request.form["nova_senha"].strip()
        confirmar_nova_senha = request.form["confirmar_nova_senha"].strip()

        if not check_password_hash(current_user.senha, senha_atual):
            flash("A senha atual está incorreta.", "erro")
            return redirect("/redefinir_senha")

        forte, mensagem = senha_forte(nova_senha)
        if not forte:
            flash(mensagem, "erro")
            return redirect("/redefinir_senha")

        if nova_senha != confirmar_nova_senha:
            flash("As novas senhas não coincidem.", "erro")
            return redirect("/redefinir_senha")

        current_user.senha = generate_password_hash(nova_senha)
        db.session.commit()

        flash("Senha redefinida com sucesso.", "sucesso")
        return redirect("/perfil")

    return render_template("redefinir_senha.html")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True)