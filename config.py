"""配置文件：MySQL、Flask密钥、命令黑名单、SSH超时"""
import os

class Config:
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:Ops%402024!@192.168.40.128/ops_platform'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SECRET_KEY = 'change-this-to-a-random-string'

    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')

    COMMAND_BLACKLIST = ['rm -rf /', 'shutdown', 'reboot', 'mkfs', 'dd if=']

    SSH_TIMEOUT = 30
