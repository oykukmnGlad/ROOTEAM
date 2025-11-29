from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'gizli-anahtar-buraya'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bitki_takip.db'
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- VERİTABANI MODELLERİ ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True) # Unique ID
    username = db.Column(db.String(150), unique=True, nullable=False) # Kullanıcı Adı
    password = db.Column(db.String(150), nullable=False) # Şifre
    plants = db.relationship('Plant', backref='owner', lazy=True)
    posts = db.relationship('ForumPost', backref='author', lazy=True)

class Plant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False) # Kullanıcının bitkiye verdiği isim
    species = db.Column(db.String(100), nullable=False) # Bitkinin türü (Forum için)
    logs = db.relationship('CareLog', backref='plant', lazy=True)

class CareLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plant_id = db.Column(db.Integer, db.ForeignKey('plant.id'), nullable=False)
    action_type = db.Column(db.String(50), nullable=False) # 'Su' veya 'Gübre'
    date = db.Column(db.DateTime, default=datetime.utcnow)
    note = db.Column(db.String(200))

class ForumPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plant_species = db.Column(db.String(100), nullable=False) # Konu başlığı (Bitki Türü)
    content = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROTALAR (ROUTES) ---

# 1. Ana Sayfa ve Dashboard
@app.route('/')
@login_required
def dashboard():
    # Kullanıcının kendi bitkilerini listele
    user_plants = Plant.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', name=current_user.username, plants=user_plants)

# 2. Giriş ve Kayıt
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        # Basitlik için şifre hashleme yapılmadı, gerçek projede hashlenmeli!
        if user and user.password == password:
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Giriş başarısız. ID veya şifre yanlış.')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        # Unique ID kontrolü (Username üzerinden)
        if User.query.filter_by(username=username).first():
            flash('Bu ID zaten alınmış.')
        else:
            new_user = User(username=username, password=password)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# 3. Bitki Ekleme ve Bakım Loglama
@app.route('/add_plant', methods=['POST'])
@login_required
def add_plant():
    name = request.form.get('name')
    species = request.form.get('species') # Örn: Monstera
    new_plant = Plant(user_id=current_user.id, name=name, species=species)
    db.session.add(new_plant)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/log_care/<int:plant_id>', methods=['POST'])
@login_required
def log_care(plant_id):
    plant = Plant.query.get_or_404(plant_id)
    if plant.user_id == current_user.id:
        action = request.form.get('action') # 'su' veya 'gubre'
        new_log = CareLog(plant_id=plant.id, action_type=action)
        db.session.add(new_log)
        db.session.commit()
    return redirect(url_for('dashboard'))

# 4. Forum (Bitki Odaklı)
@app.route('/forum', methods=['GET', 'POST'])
@login_required
def forum():
    filter_species = request.args.get('species') # URL'den gelen filtre (?species=Orkide)
    
    if request.method == 'POST':
        # Yeni yorum ekleme
        species_input = request.form.get('plant_species')
        content = request.form.get('content')
        new_post = ForumPost(user_id=current_user.id, plant_species=species_input, content=content)
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for('forum', species=species_input))

    # Filtreleme Mantığı:
    if filter_species:
        # Sadece seçilen bitki türüne ait postları getir
        posts = ForumPost.query.filter_by(plant_species=filter_species).order_by(ForumPost.date.desc()).all()
    else:
        # Hepsi
        posts = ForumPost.query.order_by(ForumPost.date.desc()).all()

    # Forumdaki mevcut tüm bitki kategorilerini bul (Tekrarsız)
    categories = db.session.query(ForumPost.plant_species).distinct().all()
    
    return render_template('forum.html', posts=posts, categories=categories, active_filter=filter_species)

# Uygulamayı başlatma ve veritabanını oluşturma
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)