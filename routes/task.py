from flask import Blueprint, request, jsonify, session, render_template, redirect
from models import db, Task, Host, ExecLog
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from ssh_utils import batch_execute, check_command_safety
import datetime
import json
import logging

task_bp = Blueprint('task', __name__, url_prefix='/tasks')

scheduler = BackgroundScheduler()
scheduler.start()

_app = None

def _run_task(task_id):
    """定时任务执行函数（APScheduler 后台线程调用）"""
    with _app.app_context():
        task = Task.query.get(task_id)
        if not task or not task.is_active:
            logging.warning(f"[Task] Task {task_id} not found or inactive, skip.")
            return

        host_ids = json.loads(task.host_ids) if task.host_ids else []
        if not host_ids:
            logging.warning(f"[Task] Task {task_id} has no hosts, skip.")
            return

        hosts = Host.query.filter(Host.id.in_(host_ids)).all()
        if not hosts:
            logging.warning(f"[Task] Task {task.id} hosts not found, skip.")
            return

        if not check_command_safety(task.command):
            task.last_result = 'blacklist_blocked'
            task.last_run_at = datetime.datetime.now()
            db.session.commit()
            logging.warning(f"[Task] Task {task.id} blocked by blacklist.")
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
                created_at=datetime.datetime.now()
            )
            db.session.add(log)
            if r.get('success'):
                success_count += 1
            else:
                fail_count += 1

        db.session.commit()
        task.last_run_at = datetime.datetime.now()
        if fail_count == 0:
            task.last_result = 'success'
        elif success_count == 0:
            task.last_result = 'failed'
        else:
            task.last_result = 'partial (' + str(success_count) + '/' + str(len(results)) + ')'
        db.session.commit()
        logging.info(f"[Task] Task {task.id} finished: {task.last_result}")

def _add_scheduler_job(task):
    """添加/更新调度器 Job"""
    try:
        job_id = 'task_' + str(task.id)
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass

        parts = task.cron_expr.split()
        if len(parts) != 5:
            logging.error(f"[Task] Invalid cron: {task.cron_expr}")
            return False

        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4]
        )
        scheduler.add_job(
            func=_run_task,
            trigger=trigger,
            id=job_id,
            args=[task.id],
            replace_existing=True,
            max_instances=1
        )
        return True
    except Exception as e:
        logging.error(f"[Task] Failed to add job for task {task.id}: {e}")
        return False

def init_scheduler(app):
    """Flask 启动时初始化调度器，加载所有激活任务"""
    global _app
    _app = app
    with app.app_context():
        tasks = Task.query.filter_by(is_active=True).all()
        for task in tasks:
            _add_scheduler_job(task)
        logging.info(f"[Task] Loaded {len(tasks)} active scheduled tasks.")

@task_bp.route('/')
def index():
    """定时任务管理页面"""
    if 'user_id' not in session:
        return redirect('/login')
    tasks = Task.query.order_by(Task.id.desc()).all()
    hosts = Host.query.all()
    return render_template('tasks.html', tasks=tasks, hosts=hosts)

@task_bp.route('/add', methods=['POST'])
def add_task():
    """添加新定时任务"""
    if 'user_id' not in session:
        return jsonify({'error': '未登录'}), 401

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
def toggle_task(task_id):
    """暂停/启动定时任务"""
    if 'user_id' not in session:
        return jsonify({'error': '未登录'}), 401

    task = Task.query.get_or_404(task_id)
    task.is_active = not task.is_active
    db.session.commit()

    if task.is_active:
        _add_scheduler_job(task)
    else:
        try:
            scheduler.remove_job('task_' + str(task.id))
        except Exception:
            pass

    return jsonify({'success': True, 'is_active': task.is_active})

@task_bp.route('/delete/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    """删除定时任务"""
    if 'user_id' not in session:
        return jsonify({'error': '未登录'}), 401

    task = Task.query.get_or_404(task_id)
    try:
        scheduler.remove_job('task_' + str(task.id))
    except Exception:
        pass

    db.session.delete(task)
    db.session.commit()
    return jsonify({'success': True})

"""
定时任务模块
- APScheduler BackgroundScheduler 后台调度
- Cron 表达式解析（支持标准 5 段格式）
- 任务的增删改查、暂停/启动
- 后台线程通过全局 app 引用获取 Flask 上下文
"""