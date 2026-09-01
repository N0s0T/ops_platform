"""批量执行 + 定时任务：并发 SSH 执行命令、定时任务管理、执行日志"""
from flask import Blueprint, render_template, request, jsonify
from routes.auth import login_required
from models import db, Host, ExecLog, Task
from ssh_utils import check_command_safety, batch_execute
from datetime import datetime

exec_bp = Blueprint('exec', __name__)

@exec_bp.route('/exec')
@login_required
def exec_page():
    hosts = Host.query.order_by(Host.created_at.desc()).all()
    tasks = Task.query.order_by(Task.id.desc()).all()
    return render_template('exec.html', hosts=hosts, tasks=tasks)

@exec_bp.route('/exec/run', methods=['POST'])
@login_required
def run_command():
    data = request.get_json()
    command = data.get('command', '').strip()
    host_ids = data.get('host_ids', [])

    if not command:
        return jsonify({'code': 400, 'msg': '命令不能为空'})
    if not host_ids:
        return jsonify({'code': 400, 'msg': '请选择主机'})

    is_safe, reason = check_command_safety(command)
    if not is_safe:
        return jsonify({'code': 400, 'msg': reason})

    hosts = Host.query.filter(Host.id.in_(host_ids)).all()
    results = batch_execute(hosts, command)

    for r in results:
        log = ExecLog(
            command=command,
            host_id=r.get('host_id'),
            host_name=r.get('host_name', ''),
            output=r.get('output', ''),
            error=r.get('error', ''),
            exit_code=r.get('exit_code', -1),
            status='success' if r.get('success') else 'failed',
            created_at=datetime.now()
        )
        db.session.add(log)
    db.session.commit()

    return jsonify({'code': 200, 'results': results})

@exec_bp.route('/exec/logs')
@login_required
def logs():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    host_name = request.args.get('host_name', '').strip()
    command = request.args.get('command', '').strip()

    query = ExecLog.query
    if host_name:
        query = query.filter(ExecLog.host_name.like('%' + host_name + '%'))
    if command:
        query = query.filter(ExecLog.command.like('%' + command + '%'))

    query = query.order_by(ExecLog.id.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('logs.html', logs=pagination.items, pagination=pagination,
                           host_name=host_name, command=command)
