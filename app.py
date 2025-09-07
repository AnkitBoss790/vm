from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import subprocess, libvirt

# Flask Setup
app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
db = SQLAlchemy(app)

# Login System
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(150))
    role = db.Column(db.String(10), default="user")  # admin / user
    vms = db.relationship("VM", backref="owner")

class VM(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    ram = db.Column(db.Integer)
    cpu = db.Column(db.Integer)
    disk = db.Column(db.Integer)
    os_type = db.Column(db.String(20))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ================= VM FUNCTIONS ===================
def list_vms_for_user(user):
    conn = libvirt.open("qemu:///system")
    domains = conn.listAllDomains()
    vms = []
    for dom in domains:
        vm_record = VM.query.filter_by(name=dom.name()).first()
        if vm_record:
            if user.role == "admin" or vm_record.user_id == user.id:
                vms.append({"name": dom.name(),
                            "status": "running" if dom.isActive() else "stopped",
                            "owner": vm_record.owner.username})
    conn.close()
    return vms

def create_vm(name, ram, cpu, disk, os_type, owner_id):
    iso_map = {
        "ubuntu": "/var/lib/libvirt/images/ubuntu-22.04.iso",
        "debian": "/var/lib/libvirt/images/debian-12.iso"
    }
    iso_path = iso_map.get(os_type, iso_map["ubuntu"])
    disk_path = f"/var/lib/libvirt/images/{name}.qcow2"
    subprocess.run(["qemu-img", "create", "-f", "qcow2", disk_path, f"{disk}G"])

    cmd = [
        "virt-install",
        "--name", name,
        "--ram", str(ram),
        "--vcpus", str(cpu),
        "--disk", f"path={disk_path},format=qcow2",
        "--cdrom", iso_path,
        "--network", "bridge=virbr0",
        "--os-variant", "ubuntu22.04" if os_type == "ubuntu" else "debian12",
        "--graphics", "vnc,listen=0.0.0.0",
        "--noautoconsole"
    ]
    subprocess.run(cmd)

    new_vm = VM(name=name, ram=ram, cpu=cpu, disk=disk, os_type=os_type, user_id=owner_id)
    db.session.add(new_vm)
    db.session.commit()

def start_vm(name):
    conn = libvirt.open("qemu:///system")
    dom = conn.lookupByName(name)
    dom.create()
    conn.close()

def stop_vm(name):
    conn = libvirt.open("qemu:///system")
    dom = conn.lookupByName(name)
    dom.shutdown()
    conn.close()

def delete_vm(name):
    conn = libvirt.open("qemu:///system")
    dom = conn.lookupByName(name)
    dom.destroy()
    dom.undefine()
    conn.close()
    VM.query.filter_by(name=name).delete()
    db.session.commit()

# ================= ROUTES ===================
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash("Invalid login")
    return render_template("login.html")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == "POST":
        username = request.form['username']
        password = generate_password_hash(request.form['password'], method='sha256')
        role = "admin" if request.form.get("admin") == "yes" else "user"
        new_user = User(username=username, password=password, role=role)
        db.session.add(new_user)
        db.session.commit()
        flash("Registered, please login")
        return redirect(url_for('login'))
    return render_template("register.html")

@app.route('/dashboard')
@login_required
def dashboard():
    vms = list_vms_for_user(current_user)
    return render_template("dashboard.html", vms=vms, user=current_user)

@app.route('/create_vm', methods=['GET', 'POST'])
@login_required
def create_vm_route():
    if request.method == "POST":
        name = request.form['name']
        ram = int(request.form['ram'])
        cpu = int(request.form['cpu'])
        disk = int(request.form['disk'])
        os_type = request.form['os_type']

        if current_user.role == "admin" and request.form.get("user_id"):
            owner_id = int(request.form['user_id'])
        else:
            owner_id = current_user.id

        create_vm(name, ram, cpu, disk, os_type, owner_id)
        flash("VM created")
        return redirect(url_for('dashboard'))

    users = User.query.all() if current_user.role == "admin" else []
    return render_template("create_vm.html", users=users)

@app.route('/start/<name>')
@login_required
def start(name):
    start_vm(name)
    return redirect(url_for('dashboard'))

@app.route('/stop/<name>')
@login_required
def stop(name):
    stop_vm(name)
    return redirect(url_for('dashboard'))

@app.route('/delete/<name>')
@login_required
def delete(name):
    delete_vm(name)
    return redirect(url_for('dashboard'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == "__main__":
    db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=True)
