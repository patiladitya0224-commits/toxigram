"""
ToxiGram - Social Media Toxic Neutralizer
Flask Backend Application
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from nlp_engine import neutralize_text, analyze_sentiment_trend, extract_keywords, compute_toxicity_score
import os
import json

# ── App Config ───────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config['SECRET_KEY'] = 'toxigram-nlp-secret-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///toxigram.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

os.makedirs('static/uploads', exist_ok=True)
os.makedirs('static/css', exist_ok=True)
os.makedirs('static/js', exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ── Database Models ──────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    bio = db.Column(db.String(200), default='')
    avatar = db.Column(db.String(200), default='default.png')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    posts = db.relationship('Post', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    caption = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(200), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    comments = db.relationship('Comment', backref='post', lazy=True, cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='post', lazy=True, cascade='all, delete-orphan')

    @property
    def like_count(self):
        return len(self.likes)

    @property
    def comment_count(self):
        return len(self.comments)


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_text = db.Column(db.Text, nullable=False)
    neutralized_text = db.Column(db.Text, nullable=False)
    toxicity_score = db.Column(db.Float, default=0.0)
    toxicity_label = db.Column(db.String(50), default='Clean')
    was_modified = db.Column(db.Boolean, default=False)
    replacements = db.Column(db.Text, default='[]')  # JSON list
    sentiment = db.Column(db.String(30), default='Neutral')
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_replacements(self):
        try:
            return json.loads(self.replacements)
        except:
            return []


class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ToxicityLog(db.Model):
    """Stores all toxicity events for analytics."""
    id = db.Column(db.Integer, primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    toxicity_score = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    posts = Post.query.order_by(Post.created_at.desc()).all()
    posts_data = []
    for post in posts:
        comments_text = [c.neutralized_text for c in post.comments]
        sentiment_trend = analyze_sentiment_trend(comments_text)
        liked = Like.query.filter_by(user_id=current_user.id, post_id=post.id).first() is not None
        posts_data.append({
            'post': post,
            'liked': liked,
            'sentiment_trend': sentiment_trend
        })
    return render_template('index.html', posts_data=posts_data)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password', 'error')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            flash('Username already taken', 'error')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return redirect(url_for('register'))
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('index'))
    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/create_post', methods=['GET', 'POST'])
@login_required
def create_post():
    if request.method == 'POST':
        caption = request.form.get('caption', '')
        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_name = f"{current_user.id}_{datetime.utcnow().timestamp()}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
                image_filename = unique_name

        post = Post(caption=caption, image=image_filename, user_id=current_user.id)
        db.session.add(post)
        db.session.commit()
        flash('Post created!', 'success')
        return redirect(url_for('index'))
    return render_template('create_post.html')


@app.route('/post/<int:post_id>')
@login_required
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    liked = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first() is not None
    comments_text = [c.neutralized_text for c in post.comments]
    sentiment_trend = analyze_sentiment_trend(comments_text)
    return render_template('post_detail.html', post=post, liked=liked, sentiment_trend=sentiment_trend)


@app.route('/comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment(post_id):
    post = Post.query.get_or_404(post_id)
    text = request.form.get('comment', '').strip()
    if not text:
        return redirect(url_for('index'))

    # ── NLP Processing ──
    result = neutralize_text(text)

    comment = Comment(
        original_text=result['original'],
        neutralized_text=result['neutralized'],
        toxicity_score=result['toxicity_score'],
        toxicity_label=result['toxicity_label']['label'],
        was_modified=result['was_modified'],
        replacements=json.dumps(result['replacements_made']),
        sentiment=result['sentiment'],
        post_id=post_id,
        user_id=current_user.id
    )
    db.session.add(comment)
    db.session.commit()

    # Log toxicity event if toxic
    if result['toxicity_score'] > 0.2:
        log = ToxicityLog(
            comment_id=comment.id,
            user_id=current_user.id,
            toxicity_score=result['toxicity_score']
        )
        db.session.add(log)
        db.session.commit()

    return redirect(url_for('index'))


@app.route('/like/<int:post_id>', methods=['POST'])
@login_required
def toggle_like(post_id):
    post = Post.query.get_or_404(post_id)
    existing = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(like)
        liked = True
    db.session.commit()
    return jsonify({'liked': liked, 'count': post.like_count})


@app.route('/profile/<username>')
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.created_at.desc()).all()

    # Toxicity stats for this user
    user_comments = Comment.query.filter_by(user_id=user.id).all()
    avg_toxicity = 0
    if user_comments:
        avg_toxicity = round(sum(c.toxicity_score for c in user_comments) / len(user_comments) * 100)
    modified_count = sum(1 for c in user_comments if c.was_modified)

    return render_template('profile.html',
        profile_user=user,
        posts=posts,
        avg_toxicity=avg_toxicity,
        modified_count=modified_count,
        total_comments=len(user_comments)
    )


@app.route('/api/analyze', methods=['POST'])
@login_required
def api_analyze():
    """Live toxicity analysis as user types (AJAX endpoint)."""
    data = request.get_json()
    text = data.get('text', '')
    if not text:
        return jsonify({'toxicity_percent': 0, 'label': 'Clean ✅', 'color': '#22c55e'})
    score = compute_toxicity_score(text)
    from nlp_engine import get_toxicity_label
    label_info = get_toxicity_label(score)
    return jsonify({
        'toxicity_percent': int(score * 100),
        'label': label_info['label'],
        'color': label_info['color'],
        'level': label_info['level']
    })


@app.route('/analytics')
@login_required
def analytics():
    """Global platform toxicity analytics."""
    total_comments = Comment.query.count()
    toxic_comments = Comment.query.filter(Comment.toxicity_score > 0.4).count()
    neutralized = Comment.query.filter_by(was_modified=True).count()
    avg_score = db.session.query(db.func.avg(Comment.toxicity_score)).scalar() or 0

    # Recent toxic logs
    recent_logs = ToxicityLog.query.order_by(ToxicityLog.created_at.desc()).limit(10).all()

    return render_template('analytics.html',
        total_comments=total_comments,
        toxic_comments=toxic_comments,
        neutralized=neutralized,
        avg_score=round(float(avg_score) * 100, 1),
        recent_logs=recent_logs
    )


@app.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id:
        flash('Not authorized', 'error')
        return redirect(url_for('index'))
    db.session.delete(post)
    db.session.commit()
    flash('Post deleted', 'success')
    return redirect(url_for('index'))


# ── Init DB & Run ────────────────────────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ Database initialized!")
        print("🚀 ToxiGram running at http://127.0.0.1:5000")
    app.run(debug=True)
