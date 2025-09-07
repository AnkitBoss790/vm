from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Database setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vm_manager.db'
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# ==================== MODELS ====================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(20), default="user")  # "admin" or "user"

class VM(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    os_type = db.Column(db.String(50), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# ==================== LOGIN MANAGER ====================
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== ROUTES ====================
@app.route("/")
def index():
    if current_user.is_authenticated:
        vms = VM.query.filter_by(owner_id=current_user.id).all() if current_user.role == "user" else VM.query.all()
        return render_template("dashboard.html", vms=vms)
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            login_user(user)
            return redirect(url_for("index"))
        flash("Invalid credentials!", "danger")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        role = request.form.get("role", "user")
        if User.query.filter_by(username=username).first():
            flash("Username already exists!", "danger")
        else:
            user = User(username=username, password=password, role=role)
            db.session.add(user)
            db.session.commit()
            flash("Account created successfully!", "success")
            return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/create_vm", methods=["POST"])
@login_required
def create_vm():
    vm_name = request.form["name"]
    os_type = request.form["os_type"]

    new_vm = VM(name=vm_name, os_type=os_type, owner_id=current_user.id)
    db.session.add(new_vm)
    db.session.commit()

    flash(f"VM '{vm_name}' with OS {os_type} created successfully!", "success")
    return redirect(url_for("index"))

@app.route("/delete_vm/<int:vm_id>")
@login_required
def delete_vm(vm_id):
    vm = VM.query.get_or_404(vm_id)
    if current_user.role == "admin" or vm.owner_id == current_user.id:
        db.session.delete(vm)
        db.session.commit()
        flash("VM deleted successfully!", "success")
    else:
        flash("You do not have permission to delete this VM!", "danger")
    return redirect(url_for("index"))

# ==================== INIT DATABASE ====================
with app.app_context():
    db.create_all()
    # ensure an admin user exists
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", password="admin", role="admin")
        db.session.add(admin)
        db.session.commit()

# ==================== RUN APP ====================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
