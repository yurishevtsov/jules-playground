from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_oauthlib.client import OAuth
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_very_secret_key'  # Replace with a real secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Google OAuth configuration
app.config['GOOGLE_CLIENT_ID'] = 'YOUR_GOOGLE_CLIENT_ID' # Placeholder
app.config['GOOGLE_CLIENT_SECRET'] = 'YOUR_GOOGLE_CLIENT_SECRET' # Placeholder

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Initialize OAuth
oauth = OAuth(app)

google = oauth.remote_app(
    'google',
    consumer_key=app.config.get('GOOGLE_CLIENT_ID'),
    consumer_secret=app.config.get('GOOGLE_CLIENT_SECRET'),
    request_token_params={
        'scope': 'email profile'
    },
    base_url='https://www.googleapis.com/oauth2/v1/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://accounts.google.com/o/oauth2/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
)

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=True)
    notes = db.relationship('Note', backref='author', lazy='dynamic')
    checklists = db.relationship('Checklist', backref='user', lazy='dynamic')

    def __repr__(self):
        return f'<User {self.email}>'

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<Note {self.title}>'

class Checklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    items = db.relationship('ChecklistItem', backref='checklist', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Checklist {self.title}>'

class ChecklistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(300), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    checklist_id = db.Column(db.Integer, db.ForeignKey('checklist.id'), nullable=False)

    def __repr__(self):
        return f'<ChecklistItem {self.text}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login')
def login():
    return google.authorize(callback=url_for('authorized', _external=True))

@app.route('/login/authorized')
def authorized():
    resp = google.authorized_response()
    if resp is None or resp.get('access_token') is None:
        flash('Access denied: reason={} error={}'.format(
            request.args.get('error_reason', 'Unknown reason'),
            request.args.get('error_description', 'Unknown error')
        ), 'danger')
        return redirect(url_for('home'))

    session['google_token'] = (resp['access_token'], '')
    user_info = google.get('userinfo')
    email = user_info.data.get('email')
    name = user_info.data.get('name', email) # Use email as name if name is not provided

    if email is None:
        flash('Login failed: Email not provided by Google.', 'danger')
        return redirect(url_for('home'))

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email, name=name)
        db.session.add(user)
        db.session.commit()
        flash('New account created successfully!', 'success')
    
    login_user(user, remember=True)
    flash(f'Welcome back, {user.name}!', 'success')
    return redirect(url_for('profile'))

@google.tokengetter
def get_google_oauth_token():
    return session.get('google_token')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('google_token', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

# Notes routes
@app.route('/notes')
@login_required
def notes():
    user_notes = Note.query.filter_by(user_id=current_user.id).order_by(Note.timestamp.desc()).all()
    return render_template('notes/list_notes.html', notes=user_notes)

@app.route('/notes/new', methods=['GET', 'POST'])
@login_required
def new_note():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        if not title or not content:
            flash('Title and content are required!', 'warning')
        else:
            note = Note(title=title, content=content, user_id=current_user.id)
            db.session.add(note)
            db.session.commit()
            flash('Note created successfully!', 'success')
            return redirect(url_for('notes'))
    return render_template('notes/create_note.html')

@app.route('/notes/<int:note_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_note(note_id):
    note = Note.query.get_or_404(note_id)
    if note.author != current_user:
        flash('You are not authorized to edit this note.', 'danger')
        return redirect(url_for('notes'))
    
    if request.method == 'POST':
        note.title = request.form.get('title')
        note.content = request.form.get('content')
        if not note.title or not note.content:
            flash('Title and content are required!', 'warning')
        else:
            db.session.commit()
            flash('Note updated successfully!', 'success')
            return redirect(url_for('notes'))
    return render_template('notes/edit_note.html', note=note)

@app.route('/notes/<int:note_id>/delete', methods=['POST'])
@login_required
def delete_note(note_id):
    note = Note.query.get_or_404(note_id)
    if note.author != current_user:
        flash('You are not authorized to delete this note.', 'danger')
        return redirect(url_for('notes'))
    
    db.session.delete(note)
    db.session.commit()
    flash('Note deleted successfully!', 'success')
    return redirect(url_for('notes'))

# Checklist Routes
@app.route('/checklists')
@login_required
def checklists():
    user_checklists = Checklist.query.filter_by(user_id=current_user.id).order_by(Checklist.id.desc()).all()
    return render_template('checklists/list_checklists.html', checklists=user_checklists)

@app.route('/checklists/new', methods=['GET', 'POST'])
@login_required
def new_checklist():
    if request.method == 'POST':
        title = request.form.get('title')
        if not title:
            flash('Title is required!', 'warning')
        else:
            checklist = Checklist(title=title, user_id=current_user.id)
            db.session.add(checklist)
            db.session.commit()
            flash('Checklist created successfully!', 'success')
            return redirect(url_for('checklists'))
    return render_template('checklists/create_checklist.html')

@app.route('/checklists/<int:checklist_id>')
@login_required
def view_checklist(checklist_id):
    checklist = Checklist.query.get_or_404(checklist_id)
    if checklist.user_id != current_user.id:
        flash('You are not authorized to view this checklist.', 'danger')
        return redirect(url_for('checklists'))
    items = ChecklistItem.query.filter_by(checklist_id=checklist.id).order_by(ChecklistItem.id.asc()).all()
    return render_template('checklists/view_checklist.html', checklist=checklist, items=items)

@app.route('/checklists/<int:checklist_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_checklist(checklist_id):
    checklist = Checklist.query.get_or_404(checklist_id)
    if checklist.user_id != current_user.id:
        flash('You are not authorized to edit this checklist.', 'danger')
        return redirect(url_for('checklists'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        if not title:
            flash('Title is required!', 'warning')
        else:
            checklist.title = title
            db.session.commit()
            flash('Checklist updated successfully!', 'success')
            return redirect(url_for('view_checklist', checklist_id=checklist.id))
    return render_template('checklists/edit_checklist.html', checklist=checklist)

@app.route('/checklists/<int:checklist_id>/delete', methods=['POST'])
@login_required
def delete_checklist(checklist_id):
    checklist = Checklist.query.get_or_404(checklist_id)
    if checklist.user_id != current_user.id:
        flash('You are not authorized to delete this checklist.', 'danger')
        return redirect(url_for('checklists'))
    
    db.session.delete(checklist)
    db.session.commit()
    flash('Checklist deleted successfully!', 'success')
    return redirect(url_for('checklists'))

@app.route('/checklists/<int:checklist_id>/items/add', methods=['POST'])
@login_required
def add_checklist_item(checklist_id):
    checklist = Checklist.query.get_or_404(checklist_id)
    if checklist.user_id != current_user.id:
        flash('You are not authorized to add items to this checklist.', 'danger')
        return redirect(url_for('checklists'))
    
    text = request.form.get('text')
    if not text:
        flash('Item text is required!', 'warning')
    else:
        item = ChecklistItem(text=text, checklist_id=checklist.id)
        db.session.add(item)
        db.session.commit()
        flash('Item added successfully!', 'success')
    return redirect(url_for('view_checklist', checklist_id=checklist.id))

@app.route('/items/<int:item_id>/toggle', methods=['POST'])
@login_required
def toggle_checklist_item(item_id):
    item = ChecklistItem.query.get_or_404(item_id)
    if item.checklist.user_id != current_user.id:
        flash('You are not authorized to modify this item.', 'danger')
        return redirect(url_for('checklists'))
        
    item.completed = not item.completed
    db.session.commit()
    flash('Item status updated!', 'success')
    return redirect(url_for('view_checklist', checklist_id=item.checklist_id))

@app.route('/items/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_checklist_item(item_id):
    item = ChecklistItem.query.get_or_404(item_id)
    if item.checklist.user_id != current_user.id:
        flash('You are not authorized to delete this item.', 'danger')
        return redirect(url_for('checklists'))
        
    db.session.delete(item)
    db.session.commit()
    flash('Item deleted successfully!', 'success')
    return redirect(url_for('view_checklist', checklist_id=item.checklist_id))

# Function to create database tables
def create_tables():
    with app.app_context():
        db.create_all()

if __name__ == '__main__':
    create_tables() # Create tables when the app starts
    app.run(debug=True)
