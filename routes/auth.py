"""用户认证：登录/登出 + login_required 装饰器"""
from flask import Blueprint, render_template, redirect, url_for, request, session, flash
from functools import wraps
from models import db, User

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    """登录保护装饰器：检查 session 中是否有 user_id"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            return redirect('/')
        flash('用户名或密码错误')
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    session.pop('user_id', None)
    return redirect(url_for('auth.login'))
