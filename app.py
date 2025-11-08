
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key")

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///webread.db"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(80), nullable=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    delete_code = db.Column(db.String(32), nullable=True)
    likes = db.Column(db.Integer, default=0)
    comments = db.relationship("Comment", backref="post", cascade="all, delete-orphan")

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False, index=True)
    author = db.Column(db.String(80), nullable=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    delete_code = db.Column(db.String(32), nullable=True)

def ensure_db():
    with app.app_context():
        db.create_all()
        print("✅ Tables ensured: Post & Comment")
ensure_db()

def clean(s):
    return (s or "").strip()

@app.route("/", methods=["GET"])
def index():
    q = clean(request.args.get("q"))
    posts = Post.query
    if q:
        like = f"%{q}%"
        posts = posts.filter(db.or_(Post.author.ilike(like), Post.content.ilike(like)))
    posts = posts.order_by(Post.created_at.desc()).all()
    counts = dict(db.session.query(Comment.post_id, func.count(Comment.id)).group_by(Comment.post_id).all())
    return render_template("index.html", posts=posts, counts=counts, q=q or "")

@app.route("/write", methods=["GET","POST"])
def write():
    if request.method == "POST":
        author = clean(request.form.get("author"))
        content = clean(request.form.get("content"))
        delete_code = clean(request.form.get("delete_code"))
        if not content:
            flash("내용은 필수입니다.", "error")
            return redirect(url_for("write"))
        p = Post(author=author or None, content=content, delete_code=delete_code or None)
        db.session.add(p)
        db.session.commit()
        flash("작성 완료!", "success")
        return redirect(url_for("post_detail", post_id=p.id))
    return render_template("write.html")

@app.route("/post/<int:post_id>")
def post_detail(post_id):
    p = Post.query.get_or_404(post_id)
    comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at.asc()).all()
    return render_template("post.html", p=p, comments=comments)

@app.route("/post/<int:post_id>/like", methods=["POST"])
def like_post(post_id):
    p = Post.query.get_or_404(post_id)
    p.likes = (p.likes or 0) + 1
    db.session.commit()
    return redirect(url_for("post_detail", post_id=post_id))

@app.route("/post/<int:post_id>/delete", methods=["POST"])
def delete_post(post_id):
    p = Post.query.get_or_404(post_id)
    code = clean(request.form.get("delete_code"))
    admin = os.environ.get("ADMIN_TOKEN")
    admin_code = clean(request.form.get("admin_token"))
    if (p.delete_code and code and code == p.delete_code) or (admin and admin_code == admin):
        db.session.delete(p)
        db.session.commit()
        flash("게시글이 삭제되었습니다.", "success")
        return redirect(url_for("index"))
    else:
        flash("삭제 코드가 올바르지 않습니다.", "error")
        return redirect(url_for("post_detail", post_id=post_id))

@app.route("/post/<int:post_id>/comment", methods=["POST"])
def add_comment(post_id):
    _ = Post.query.get_or_404(post_id)
    author = clean(request.form.get("author"))
    content = clean(request.form.get("content"))
    delete_code = clean(request.form.get("delete_code"))
    if not content:
        flash("댓글 내용을 입력하세요.", "error")
        return redirect(url_for("post_detail", post_id=post_id))
    c = Comment(post_id=post_id, author=author or None, content=content, delete_code=delete_code or None)
    db.session.add(c)
    db.session.commit()
    return redirect(url_for("post_detail", post_id=post_id))

@app.route("/comment/<int:cid>/delete", methods=["POST"])
def delete_comment(cid):
    c = Comment.query.get_or_404(cid)
    code = clean(request.form.get("delete_code"))
    admin = os.environ.get("ADMIN_TOKEN")
    admin_code = clean(request.form.get("admin_token"))
    if (c.delete_code and code and code == c.delete_code) or (admin and admin_code == admin):
        pid = c.post_id
        db.session.delete(c)
        db.session.commit()
        flash("댓글이 삭제되었습니다.", "success")
        return redirect(url_for("post_detail", post_id=pid))
    else:
        flash("삭제 코드가 올바르지 않습니다.", "error")
        return redirect(url_for("post_detail", post_id=c.post_id))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
