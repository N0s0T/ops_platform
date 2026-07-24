from flask import Blueprint, render_template, redirect, url_for, request, session, flash
from functools import wraps
from models import db, User

auth_bp = Blueprint('auth', __name__)

# ====== 手写登录认证（替代 Flask-Login）======
def login_required(f):
    """登录保护装饰器：检查 session 中是否有 user_id"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

#@auth_bp.route('/')
#def index():
 
 #   if 'user_id' in session:
    #    return redirect(url_for('host.list_hosts'))
   # return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面和登录处理"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            return redirect(url_for('host.list_hosts'))
        flash('用户名或密码错误')
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    session.pop('user_id', None)
    return redirect(url_for('auth.login'))
"""
用户认证模块
- 手写 session 实现登录/登出
- login_required 装饰器用于路由保护
"""