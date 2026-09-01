"""主机管理：增删查、SSH连通性测试、分组筛选"""
from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from routes.auth import login_required
from models import db, Host
from ssh_utils import SSHManager

host_bp = Blueprint('host', __name__)

@host_bp.route('/hosts')
@login_required
def list_hosts():
    group = request.args.get('group', '').strip()

    if group:
        hosts = Host.query.filter_by(group_name=group).order_by(Host.created_at.desc()).all()
    else:
        hosts = Host.query.order_by(Host.created_at.desc()).all()

    groups = db.session.query(Host.group_name).distinct().all()
    groups = [g[0] for g in groups if g[0]]

    return render_template('hosts.html', hosts=hosts, groups=groups, current_group=group)

@host_bp.route('/hosts/add', methods=['POST'])
@login_required
def add_host():
    name = request.form.get('name')
    hostname = request.form.get('hostname')
    port = int(request.form.get('port', 22))
    username = request.form.get('username', 'root')
    password = request.form.get('password', '')
    group_name = request.form.get('group_name', 'default')

    host = Host(
        name=name, hostname=hostname, port=port,
        username=username, password=password,
        group_name=group_name
    )
    db.session.add(host)
    db.session.commit()
    return redirect(url_for('host.list_hosts'))

@host_bp.route('/hosts/delete/<int:host_id>')
@login_required
def delete_host(host_id):
    host = Host.query.get_or_404(host_id)
    db.session.delete(host)
    db.session.commit()
    return redirect(url_for('host.list_hosts'))

@host_bp.route('/hosts/test/<int:host_id>')
@login_required
def test_host(host_id):
    host = Host.query.get_or_404(host_id)
    ssh = SSHManager(host.hostname, host.port, host.username, host.password)
    success, msg = ssh.test_connection()

    host.status = 'online' if success else 'offline'
    db.session.commit()

    return jsonify({'success': success, 'message': msg, 'status': host.status})
