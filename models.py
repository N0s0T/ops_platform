"""
数据库模型定义（ORM）
- User: 用户表
- Host: 主机表（含分组、状态）
- ExecLog: 执行日志表
- Task: 定时任务表
"""
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Host(db.Model):
    __tablename__ = 'hosts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    hostname = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer, default=22)
    username = db.Column(db.String(80), default='root')
    password = db.Column(db.String(255), nullable=False)
    group_name = db.Column(db.String(50), default='default')
    status = db.Column(db.String(20), default='unknown')
    created_at = db.Column(db.DateTime, default=db.func.now())

class ExecLog(db.Model):
    __tablename__ = 'exec_logs'
    id = db.Column(db.Integer, primary_key=True)
    command = db.Column(db.Text, nullable=False)
    host_id = db.Column(db.Integer, db.ForeignKey('hosts.id'))
    host_name = db.Column(db.String(100))
    output = db.Column(db.Text, default='')
    error = db.Column(db.Text, default='')
    exit_code = db.Column(db.Integer, default=-1)
    status = db.Column(db.String(20), default='running')
    created_at = db.Column(db.DateTime, default=db.func.now())

class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    cron_expr = db.Column(db.String(100), nullable=False)
    command = db.Column(db.Text, nullable=False)
    host_ids = db.Column(db.Text, default='[]')  # JSON 格式存储
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=db.func.now())