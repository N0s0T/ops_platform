# Python 自动化运维平台

一个基于 Flask + Paramiko + MySQL 的轻量级自动化运维平台，实现主机管理、批量命令执行、文件分发、定时任务四大核心功能。参考 [OpsManage](https://github.com/welliamcao/OpsManage) 和 [Spug](https://github.com/openspug/spug) 的设计思路，做了大幅简化——4 张表替代 40+ 张表，单机运行替代分布式部署。

## 技术栈

| 类别 | 技术 | 用途 |
|------|------|------|
| Web 框架 | Flask | 路由、模板渲染、Session |
| ORM | Flask-SQLAlchemy | 数据库操作 |
| SSH | Paramiko | 远程命令执行、SFTP 文件传输 |
| 并发 | ThreadPoolExecutor | 多主机并发执行 |
| 定时任务 | APScheduler | Cron 调度 |
| 数据库 | MySQL 5.7+ | 数据持久化 |
| 前端 | Bootstrap 5 + Jinja2 | 页面渲染 |
| 认证 | 手写 Session | 登录保护（不依赖 Flask-Login）|

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                     浏览器 (Chrome)                    │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ │
│  │ 登录 │ │ 主机 │ │ 执行 │ │ 日志 │ │ 分发 │ │ 定时 │ │
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ │
└─────┼────────┼────────┼────────┼────────┼────────┼──────┘
      │        │        │        │        │        │
      ▼        ▼        ▼        ▼        ▼        ▼
┌─────────────────────────────────────────────────────────┐
│              Flask 应用 (app.py)                       │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│  │ auth_bp │ │ host_bp │ │ exec_bp │ │ file_bp │        │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘        │
│  ┌─────────┐                                       │
│  │ task_bp │  ◄── APScheduler (后台线程)           │
│  └────┬────┘                                       │
└───────┼───────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────┐
│    MySQL 数据库        │
│  users / hosts /       │
│  exec_logs / tasks     │
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│  目标 Linux 服务器     │
│  (SSH:22 / SFTP)      │
└───────────────────────┘
```

## 核心流程

### 批量命令执行流程

```mermaid
flowchart TD
    A[用户选择主机 + 输入命令] --> B{命令安全检查}
    B -- 命中黑名单 --> C[拒绝执行, 返回错误]
    B -- 通过检查 --> D[ThreadPoolExecutor 并发执行]
    D --> E1[线程1: SSH连接主机A → 执行命令]
    D --> E2[线程2: SSH连接主机B → 执行命令]
    D --> E3[线程N: SSH连接主机N → 执行命令]
    E1 --> F[汇总所有结果]
    E2 --> F
    E3 --> F
    F --> G[写入 exec_logs 表]
    G --> H[返回结果给前端展示]
```

### 定时任务调度流程

```mermaid
flowchart TD
    A[Flask 启动] --> B[init_scheduler 加载所有激活任务]
    B --> C[APScheduler 解析 Cron 表达式]
    C --> D[注册到 BackgroundScheduler]
    D --> E{到达触发时间?}
    E -- 否 --> E
    E -- 是 --> F[后台线程执行 _run_task]
    F --> G[获取 Flask app 上下文]
    G --> H[查询任务和目标主机]
    H --> I{命令安全检查}
    I -- 不通过 --> J[标记 blacklist_blocked]
    I -- 通过 --> K[batch_execute 并发执行]
    K --> L[写入 exec_logs 表]
    L --> M[更新任务 last_run_at / last_result]
    J --> M
    M --> E
```

### 文件分发流程

```mermaid
flowchart TD
    A[用户选择文件 + 目标主机] --> B[上传文件到服务器 uploads 目录]
    B --> C[ThreadPoolExecutor 并发分发]
    C --> D1[线程1: SFTP 连接主机A → 上传文件]
    C --> D2[线程2: SFTP 连接主机B → 上传文件]
    C --> D3[线程N: SFTP 连接主机N → 上传文件]
    D1 --> E[汇总分发结果]
    D2 --> E
    D3 --> E
    E --> F[删除本地临时文件]
    F --> G[返回结果给前端]
```

## 功能模块

### 1. 登录认证
- 手写 Session 实现登录/登出，不依赖 Flask-Login
- `login_required` 装饰器保护所有业务路由
- 密码使用 werkzeug 的 `generate_password_hash` / `check_password` 存储

### 2. 首页仪表盘
- 统计卡片：主机总数、在线主机、今日执行次数、激活的定时任务数
- 最近 5 条执行日志速览

### 3. 主机管理
- 主机增删查，支持分组（如 web服务器、数据库）
- 按分组标签筛选主机
- SSH 连通性一键测试，自动更新在线/离线状态

### 4. 批量执行
- 选择多台主机 + 输入 Shell 命令
- ThreadPoolExecutor 并发 SSH 执行
- 命令黑名单拦截（`rm -rf /`、`shutdown`、`reboot` 等危险命令）
- 执行结果实时展示（输出、退出码、成功/失败）

### 5. 执行日志
- 所有执行记录统一存储（手动执行 + 定时任务自动执行）
- 分页展示（每页 20 条）
- 按主机名 / 命令关键词搜索

### 6. 文件分发
- 上传文件到服务器，通过 SFTP 并发分发到多台目标主机
- 支持自定义远程路径

### 7. 定时任务
- Cron 表达式可视化输入（5 个独立输入框 + 快捷模板下拉）
- 任务启停控制（暂停/启动）
- 后台调度器在 Flask 应用上下文外运行（通过全局 app 引用解决）
- 执行结果自动写入日志，和手动执行统一管理

### 8. 错误处理
- 404 / 500 统一友好错误页面

## 数据库设计

```mermaid
erDiagram
    users ||--o{ exec_logs : ""
    users {
        int id PK
        string username
        string password_hash
    }

    hosts ||--o{ exec_logs : "host_id"
    hosts ||--o{ tasks : "host_ids (JSON)"
    hosts {
        int id PK
        string name
        string hostname
        int port
        string username
        string password
        string group_name
        string status
        datetime created_at
    }

    exec_logs {
        int id PK
        string command
        int host_id
        string host_name
        string output
        string error
        int exit_code
        string status
        datetime created_at
    }

    tasks {
        int id PK
        string name
        string cron_expr
        string command
        string host_ids
        boolean is_active
        string last_result
        datetime last_run_at
        datetime created_at
    }
```

共 **4 张表**，相比 OpsManage 的 40+ 张表做了极简化，保留核心功能。

## 项目结构

```
ops_platform/
├── app.py                # Flask 主程序入口，初始化数据库/蓝图/调度器
├── config.py             # 配置文件（数据库连接、密钥、黑名单、超时）
├── models.py             # 数据库模型（User/Host/ExecLog/Task）
├── ssh_utils.py          # SSH 工具（SSHManager/batch_execute/upload_file）
├── requirements.txt      # Python 依赖
├── .gitignore
│
├── routes/               # 路由模块（Blueprint）
│   ├── __init__.py
│   ├── auth.py           # 登录/登出 + login_required 装饰器
│   ├── host.py           # 主机管理（增删查/分组筛选/SSH测试）
│   ├── exec.py           # 批量执行 + 执行日志（分页/搜索）
│   ├── file.py           # 文件分发（SFTP 上传）
│   └── task.py           # 定时任务（APScheduler/Cron/启停/删除）
│
├── templates/            # Jinja2 模板
│   ├── base.html         # 基础模板（导航栏）
│   ├── login.html        # 登录页
│   ├── dashboard.html    # 仪表盘
│   ├── hosts.html        # 主机管理
│   ├── exec.html         # 批量执行
│   ├── logs.html         # 执行日志（分页/搜索）
│   ├── files.html        # 文件分发
│   ├── tasks.html        # 定时任务
│   ├── 404.html          # 404 错误页
│   └── 500.html          # 500 错误页
│
├── static/               # 静态资源
│   └── 404.png           # 404 页面图片
│
└── uploads/              # 文件上传临时目录
```

## 快速开始

### 环境要求

- Python 3.10+
- MySQL 5.7+
- 至少 1 台可 SSH 连接的 Linux 服务器

### 安装步骤

**1. 创建 MySQL 数据库**

```sql
CREATE DATABASE ops_platform CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
```

**2. 克隆项目**

```bash
git clone https://github.com/N0s0T/ops_platform.git
cd ops_platform
```

**3. 安装依赖**

```bash
pip install -r requirements.txt
```

**4. 修改配置**

编辑 `config.py`，修改数据库连接信息：

```python
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:your_password@localhost/ops_platform'
SECRET_KEY = 'your-secret-key-change-this'
```

**5. 启动**

```bash
python app.py
```

访问 `http://127.0.0.1:5000`，默认账号：`admin` / `admin123`

## 技术要点

### Flask 后台线程与 App Context

APScheduler 的 BackgroundScheduler 在独立线程中执行任务，而 Flask 的 `current_app` 代理需要请求上下文才能工作。解决方案：

```python
# 模块全局变量保存 Flask app 实例
_app = None

def init_scheduler(app):
    global _app
    _app = app  # 启动时保存

def _run_task(task_id):
    with _app.app_context():  # 后台线程中手动创建上下文
        task = Task.query.get(task_id)
        # ... 执行任务
```

### 命令安全黑名单

```python
COMMAND_BLACKLIST = ['rm -rf /', 'shutdown', 'reboot', 'mkfs', 'dd if=']

def check_command_safety(command):
    for dangerous in COMMAND_BLACKLIST:
        if dangerous in command:
            return False
    return True
```

### 并发执行

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def batch_execute(hosts, command):
    results = []
    with ThreadPoolExecutor(max_workers=len(hosts)) as executor:
        futures = {executor.submit(execute_on_host, host, command): host for host in hosts}
        for future in as_completed(futures):
            results.append(future.result())
    return results
```

## 与 OpsManage / Spug 的对比

| 对比项 | OpsManage / Spug | 本项目 |
|--------|-------------------|--------|
| 数据库表 | 40+ 张 | 4 张 |
| 消息队列 | RabbitMQ + Redis | 不需要 |
| 前端 | Vue.js 前后端分离 | Jinja2 模板渲染 |
| 部署 | Docker + Nginx | `python app.py` 直接运行 |
| 代码量 | 几万行 | 几百行 |
| 定位 | 生产级运维平台 | 教学演示级，展示核心原理 |

## 已知限制

本项目定位为教学演示和中小规模场景，目前存在以下已知短板：

| 限制项 | 说明 |
|---|---|
| 主机规模 | 建议 **100 台以内**。ThreadPoolExecutor 单机并发，主机过多时线程数和 SSH 连接数会线性增长，导致性能下降 |
| 调度可靠性 | APScheduler 为进程内调度，**应用重启后调度器需重新加载**，任务状态不持久化到独立消息队列 |
| 部署方式 | 单进程 Flask 开发服务器运行，**不适合生产环境高并发请求**，需配合 Gunicorn + Nginx 使用 |
| 权限控制 | 仅支持单用户登录，**无 RBAC 角色权限管理**，无法区分管理员/普通操作员 |
| 高可用 | 单机单点运行，**无集群部署能力**，服务器宕机则服务中断 |
| 监控告警 | 无主机资源监控（CPU/内存/磁盘）、无告警通知机制（邮件/钉钉/企微） |
| 操作审计 | 仅记录命令执行结果，**无操作行为审计日志**（谁、何时、做了什么操作） |
| 前端架构 | Jinja2 服务端渲染，页面交互依赖整页刷新，**不适合复杂前端场景** |
| 文件大小 | 文件分发通过内存加载后 SFTP 传输，**大文件（>500MB）可能占用过多内存** |

## 后续优化方向

- SSH 密钥认证替代密码
- Gunicorn 多进程部署
- Celery + Redis 分布式任务队列替代 APScheduler
- 主机数量多时的搜索和分页
- RBAC 角色权限管理
