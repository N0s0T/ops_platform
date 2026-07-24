"""
SSH 工具模块
- SSHManager: 单台主机 SSH 连接管理类
- batch_execute: 多主机并发执行命令（ThreadPoolExecutor）
- upload_file: SFTP 文件上传
- check_command_safety: 命令安全检查（黑名单过滤）
"""
import paramiko
from config import Config

class SSHManager:
    """SSH 连接管理器（上下文管理器，自动关闭连接）"""
    
    def __init__(self, host, port, username, password=None, pkey=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.pkey = pkey
        self.client = None

    def connect(self):
        """建立 SSH 连接"""
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            pkey=self.pkey,
            timeout=Config.SSH_TIMEOUT
        )

    def execute(self, command):
        """执行单条命令，返回 (output, error, exit_code)"""
        if not self.client:
            self.connect()
        stdin, stdout, stderr = self.client.exec_command(command)
        output = stdout.read().decode('utf-8', errors='replace').strip()
        error = stderr.read().decode('utf-8', errors='replace').strip()
        exit_code = stdout.channel.recv_exit_status()
        return output, error, exit_code
    
    def upload_file(self, local_path, remote_path):
        """SFTP 上传文件到远程服务器"""
        if not self.client:
            self.connect()
        sftp = self.client.open_sftp()
        try:
            import os
            filename = os.path.basename(local_path)
            # 如果 remote_path 是目录（以 / 结尾），拼上文件名
            if remote_path.endswith('/'):
                remote_path = remote_path + filename
            sftp.put(local_path, remote_path)
            return True
        finally:
            sftp.close()

    def test_connection(self):
        """测试 SSH 连通性"""
        try:
            self.connect()
            self.execute('echo ok')
            return True, 'online'
        except Exception as e:
            return False, str(e)
        finally:
            self.close()

    def close(self):
        """关闭连接"""
        if self.client:
            self.client.close()
            self.client = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

def check_command_safety(command):
    """检查命令是否在黑名单中"""
    for blocked in Config.COMMAND_BLACKLIST:
        if blocked in command:
            return False, f'禁止执行危险命令: {blocked}'
    return True, None

from concurrent.futures import ThreadPoolExecutor, as_completed
import json

def batch_execute(hosts, command):
    """并发在多台主机上执行命令，返回结果列表"""
    is_safe, reason = check_command_safety(command)
    if not is_safe:
        return [{'success': False, 'host_name': '', 'error': reason}]

    results = []
    
    def run_on_host(host):
        try:
            with SSHManager(host.hostname, host.port, host.username, host.password) as ssh:
                output, error, exit_code = ssh.execute(command)
                return {
                    'success': exit_code == 0,
                    'host_id': host.id,
                    'host_name': host.name,
                    'hostname': host.hostname,
                    'output': output,
                    'error': error,
                    'exit_code': exit_code
                }
        except Exception as e:
            return {
                'success': False,
                'host_id': host.id,
                'host_name': host.name,
                'hostname': host.hostname,
                'output': '',
                'error': str(e),
                'exit_code': -1
            }

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(run_on_host, host): host for host in hosts}
        for future in as_completed(futures):
            results.append(future.result())

    return results