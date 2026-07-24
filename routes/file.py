import os
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from werkzeug.utils import secure_filename
from routes.auth import login_required
from models import db, Host
from ssh_utils import SSHManager
from concurrent.futures import ThreadPoolExecutor, as_completed

file_bp = Blueprint('file', __name__)

@file_bp.route('/files')
@login_required
def file_page():
    hosts = Host.query.order_by(Host.created_at.desc()).all()
    return render_template('files.html', hosts=hosts)

@file_bp.route('/files/upload', methods=['POST'])
@login_required
def distribute_file():
    file = request.files.get('file')
    remote_path = request.form.get('remote_path', '/tmp/').rstrip('/')
    host_ids = request.form.getlist('host_ids')

    if not file:
        return jsonify({'code': 400, 'msg': '请选择文件'})
    if not host_ids:
        return jsonify({'code': 400, 'msg': '请选择主机'})

    filename = secure_filename(file.filename)
    local_path = os.path.join(os.path.dirname(__file__), '..', 'uploads', filename)
    file.save(local_path)

    hosts = Host.query.filter(Host.id.in_(host_ids)).all()
    results = []

    def upload_to_host(host):
        try:
            with SSHManager(host.hostname, host.port, host.username, host.password) as ssh:
                target = remote_path + '/' + filename
                ssh.upload_file(local_path, target)
                return {
                    'success': True,
                    'host_name': host.name,
                    'hostname': host.hostname,
                    'path': target
                }
        except Exception as e:
            return {
                'success': False,
                'host_name': host.name,
                'hostname': host.hostname,
                'error': str(e)
            }

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(upload_to_host, host): host for host in hosts}
        for future in as_completed(futures):
            results.append(future.result())

        # 清理本地临时文件（Windows 上可能被占用，加 try-except 容错）
    try:
        if os.path.exists(local_path):
            os.remove(local_path)
    except PermissionError:
        pass  # 文件被占用时跳过清理，不影响功能

    return jsonify({'code': 200, 'data': results})

"""
文件分发模块
- 上传文件到服务器临时目录
- 通过 SFTP 分发到目标主机
- 支持多主机同时分发
"""