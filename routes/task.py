"""定时任务管理：APScheduler 后台调度 + 增删改查"""
from flask import Blueprint, request, jsonify, render_template
from routes.auth import login_required
from models import db, Task, Host, ExecLog
from ssh_utils import check_command_safety, batch_execute
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import json
import logging

task_bp = Blueprint('task', __name__, url_prefix='/tasks')
scheduler = BackgroundScheduler(daemon=True)
_app = None


def init_scheduler(app):
    """Flask 启动时调用，加载所有活跃的定时任务到调度器"""
    global _app
    _app = app
    with app.app_context():
        tasks = Task.query.filter_by(is_active=True).all()
        for task in tasks:
            _add_scheduler_job(task)
    scheduler.start()


def _add_scheduler_job(task):
    """将 Task 对象注册到 APScheduler"""
    parts = task.cron_expr.split()
    if len(parts) != 5:
        return
    scheduler.add_job(
        _run_task, 'cron',
        minute=parts[0], hour=parts[1], day=parts[2], month=parts[3], day_of_week=parts[4],
        args=[task.id], id=f'task_{task.id}', replace_existing=True
    )


def _run_task(task_id):
    """APScheduler 定时触发的执行函数（在后台线程中运行）"""
    if not _app:
        return
    with _app.app_context():
        task = Task.query.get(task_id)
        if not task or not task.is_active:
            return

        host_ids = json.loads(task.host_ids) if task.host_ids else []
        if not host_ids:
            return

        is_safe, reason = check_command_safety(task.command)
        if not is_safe:
            task.last_result = 'blacklist_blocked'
            task.last_run_at = datetime.now()
            db.session.commit()
            return

        hosts = Host.query.filter(Host.id.in_(host_ids)).all()
        if not hosts:
            return

        results = batch_execute(hosts, task.command)

        success_count = 0
        fail_count = 0
        for r in results:
            log = ExecLog(
                command=task.command,
                host_id=r.get('host_id'),
                host_name=r.get('host_name', ''),
                output=r.get('output', '')[:4000],
                error=r.get('error', ''),
                exit_code=r.get('exit_code', -1),
                status='success' if r.get('success') else 'failed',
                created_at=datetime.now()
            )
            db.session.add(log)
            if r.get('success'):
                success_count += 1
            else:
                fail_count += 1

        db.session.commit()

        task.last_run_at = datetime.now()
        if fail_count == 0:
            task.last_result = 'success'
        elif success_count == 0:
            task.last_result = 'failed'
        else:
            task.last_result = f'partial ({success_count}/{len(results)})'
        db.session.commit()
        logging.info(f"[Task] Task {task.id} finished: {task.last_result}")


@task_bp.route('/')
@login_required
def index():
    tasks = Task.query.order_by(Task.id.desc()).all()
    hosts = Host.query.all()
    return render_template('tasks.html', tasks=tasks, hosts=hosts)

@task_bp.route('/add', methods=['POST'])
@login_required
def add_task():
    data = request.get_json()
    name = data.get('name', '').strip()
    cron_expr = data.get('cron_expr', '').strip()
    command = data.get('command', '').strip()
    host_ids = data.get('host_ids', [])

    if not name or not cron_expr or not command:
        return jsonify({'error': '名称、Cron 表达式和命令不能为空'}), 400

    if len(cron_expr.split()) != 5:
        return jsonify({'error': 'Cron 表达式格式错误，应为 5 段（分 时 日 月 周）'}), 400

    try:
        task = Task(
            name=name,
            cron_expr=cron_expr,
            command=command,
            host_ids=json.dumps(host_ids),
            is_active=True
        )
        db.session.add(task)
        db.session.commit()
        _add_scheduler_job(task)
        return jsonify({'success': True, 'id': task.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@task_bp.route('/toggle/<int:task_id>', methods=['POST'])
@login_required
def toggle_task(task_id):
    task = Task.query.get_or_404(task_id)
    task.is_active = not task.is_active
    db.session.commit()

    if task.is_active:
        _add_scheduler_job(task)
    else:
        try:
            scheduler.remove_job(f'task_{task.id}')
        except Exception:
            pass

    return jsonify({'success': True, 'is_active': task.is_active})

@task_bp.route('/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    try:
        scheduler.remove_job(f'task_{task.id}')
    except Exception:
        pass
    db.session.delete(task)
    db.session.commit()
    return jsonify({'success': True})
