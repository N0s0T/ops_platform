"""
配置文件

- 数据库连接配置（MySQL）

- Flask 密钥

- 命令黑名单（危险命令拦截）

- SSH 连接超时设置
"""

import os

class Config:
    # MySQL 连接（虚拟机 IP）
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:Ops%402024!@192.168.40.128/ops_platform'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Flask 密钥（用于 session 签名）
    SECRET_KEY = 'change-this-to-a-random-string'

    # 上传文件临时目录
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')

    # 命令黑名单（危险命令拦截）
    COMMAND_BLACKLIST = ['rm -rf /', 'shutdown', 'reboot', 'mkfs', 'dd if=']

    # SSH 超时时间（秒）
    SSH_TIMEOUT = 30