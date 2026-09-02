# Python 自动化运维平台

一个用 Python 写的轻量运维工具，解决一个痛点：**同时给多台 Linux 服务器执行命令、分发文件、定时跑任务**。不用挨个 SSH 登录，在网页上全搞定。

参考 [OpsManage](https://github.com/welliamcao/OpsManage) 和 [Spug](https://github.com/openspug/spug) 设计，用最简架构实现核心功能。

## 技术栈

Flask + Paramiko + APScheduler + MySQL + Bootstrap 5

## 架构

```
浏览器
  ↓
Flask（接收请求，ThreadPoolExecutor 并发 SSH）
  ├── 命令执行 → SSH 到多台主机，结果写日志
  ├── 文件分发 → SFTP 上传到多台主机
  └── 定时任务 → APScheduler 后台线程，到点自动触发
  ↓
MySQL（4 张表：用户 / 主机 / 日志 / 任务）
```

## 项目结构

```
├── app.py              # 入口：路由注册、DB 建表、调度器启动
├── config.py           # 配置：MySQL 连接、命令黑名单、超时
├── models.py           # 4 张表定义
├── ssh_utils.py        # SSH 连接、命令执行、文件上传
├── routes/
│   ├── auth.py         # 登录/登出
│   ├── host.py         # 主机增删查、连通性测试
│   ├── exec.py         # 命令执行（立即/定时）+ 日志查询
│   ├── file.py         # 文件分发
│   └── task.py         # 定时任务调度引擎（APScheduler）
├── templates/          # 页面模板
└── uploads/            # 上传文件临时目录
```

## 快速开始

**1. 建数据库**

```sql
CREATE DATABASE ops_platform CHARACTER SET utf8mb4;
```

**2. 装依赖**

```bash
pip install -r requirements.txt
```

**3. 改配置**（`config.py` 中两处）

```python
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:你的密码@你的IP/ops_platform'
SECRET_KEY = '改成一个随机字符串'
```

**4. 启动**

```bash
python app.py
```

浏览器打开 `http://127.0.0.1:5000`，账号 `admin / admin123`


## 功能一览

| 功能 | 说明 |
|------|------|
| 登录认证 | Session + 装饰器，未登录自动跳转 |
| 主机管理 | 增删查、分组筛选、SSH 连通性测试 |
| 命令执行 | 选主机输命令，可立即执行或存为定时任务 |
| 执行日志 | 分页展示，按主机名/命令搜索 |
| 文件分发 | SFTP 批量上传到多台主机 |
| 定时任务 | Cron 表达式定时执行，支持启停/删除 |
| 命令黑名单 | 拦截 `rm -rf /`、`shutdown` 等危险命令 |

