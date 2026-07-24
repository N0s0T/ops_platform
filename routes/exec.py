from flask import Blueprint, render_template, request, jsonify, session, redirect
from routes.auth import login_required
from models import db, Host, ExecLog
from ssh_utils import batch_execute
from datetime import datetime
import json

exec_bp = Blueprint('exec', __name__)

@exec_bp.route('/exec')
@login_required
def exec_page():
    """批量执行页面"""
    hosts = Host.query.order_by(Host.created_at.desc()).all()
    return render_template('exec.html', hosts=hosts)

@exec_bp.route('/exec/run', methods=['POST'])
@login_required
def run_command():
    """执行命令并记录日志"""
    data = request.get_json()
    command = data.get('command', '').strip()
    host_ids = data.get('host_ids', [])

    if not command:
        return jsonify({'code': 400, 'msg': '命令不能为空'})
    if not host_ids:
        return jsonify({'code': 400, 'msg': '请选择主机'})

    hosts = Host.query.filter(Host.id.in_(host_ids)).all()
    results = batch_execute(hosts, command)

    # 记录执行日志到数据库
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

    return jsonify({'code': 200, 'data': results})

@exec_bp.route('/exec/logs')
def logs():
    """执行日志列表，支持分页和按主机名/命令搜索"""
    if 'user_id' not in session:
        return redirect('/login')

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
"""
批量执行模块
- 批量在多台主机上执行 Shell 命令
- 使用 Paramiko + ThreadPoolExecutor 并发执行
- 执行日志记录到数据库
- 日志列表支持分页和搜索
"""