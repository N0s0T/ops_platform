"""
Flask 应用入口
- 初始化 Flask、SQLAlchemy
- 注册所有 Blueprint（auth/host/exec/file/task）
- 启动 APScheduler 定时任务调度器
- 统一 404/500 错误处理
"""
from flask import Flask, render_template, session, redirect
from models import db, User, Host, ExecLog, Task
from config import Config
from datetime import datetime
import os

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    from routes.auth import auth_bp
    from routes.host import host_bp
    from routes.exec import exec_bp
    from routes.file import file_bp
    from routes.task import task_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(host_bp)
    app.register_blueprint(exec_bp)
    app.register_blueprint(file_bp)
    app.register_blueprint(task_bp)

    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print('默认管理员已创建: admin / admin123')

    from routes.task import init_scheduler
    init_scheduler(app)

    # 根路由 — 仪表盘
    @app.route('/')
    def index():
        if 'user_id' not in session:
            return redirect('/login')
        
        host_count = Host.query.count()
        online_count = Host.query.filter_by(status='online').count()
        task_count = Task.query.filter_by(is_active=True).count()
        
        today = datetime.now().date()
        today_exec_count = ExecLog.query.filter(
            db.func.date(ExecLog.created_at) == today
        ).count()
        
        recent_logs = ExecLog.query.order_by(ExecLog.id.desc()).limit(5).all()
        
        return render_template('dashboard.html',
                               host_count=host_count,
                               online_count=online_count,
                               task_count=task_count,
                               today_exec_count=today_exec_count,
                               recent_logs=recent_logs)

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(e):
        return render_template('500.html'), 500

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)

