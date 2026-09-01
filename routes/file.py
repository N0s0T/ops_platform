"""文件分发：SFTP 并发上传到多台主机"""
import os
from flask import Blueprint, render_template, request, jsonify
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
    upload_dir = os.path.join(os.path.dirname(__file__), '..', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    local_path = os.path.join(upload_dir, filename)
    file.save(local_path)

    hosts = Host.query.filter(Host.id.in_([int(h) for h in host_ids])).all()

    def upload_to_host(host):
        try:
            with SSHManager(host.hostname, host.port, host.username, host.password) as ssh:
                target = remote_path + '/' + filename
                ssh.upload_file(local_path, target)
                return {'success': True, 'host_name': host.name, 'hostname': host.hostname, 'path': target}
        except Exception as e:
            return {'success': False, 'host_name': host.name, 'hostname': host.hostname, 'error': str(e)}

    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(upload_to_host, host): host for host in hosts}
        for future in as_completed(futures):
            results.append(future.result())

    try:
        os.remove(local_path)
    except PermissionError:
        pass

    return jsonify({'code': 200, 'results': results})
