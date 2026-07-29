# WeView GitHub Actions 自动部署操作手册

本文档用于把 WeView 项目改造成以下维护方式：

```text
代码提交到 GitHub main 分支
  -> GitHub Actions 自动构建前端
  -> GitHub Actions 打包前端 dist 和后端源码
  -> GitHub Actions 通过 SSH 上传到服务器
  -> 服务器解压到 /www/wwwroot/weview-repo
  -> 服务器安装后端依赖、执行 Alembic 迁移、重启 FastAPI
  -> 自动检查 /health
```

适用目标：

- 后续维护人员不需要登录服务器手工部署。
- 云服务器不需要从 GitHub 执行 `git pull`，避免国内服务器访问 GitHub 慢。
- 前端和后端都通过 GitHub Actions 自动上线。
- 服务器只保留运行环境、数据库、Milvus、`.env` 和 `.venv`。

本文统一使用服务器目录：

```bash
/www/wwwroot/weview-repo
```

## 一、最终维护方式

后续维护人员只需要执行：

```bash
git add .
git commit -m "修改说明"
git push origin main
```

或者在 GitHub 网页端直接修改文件，并提交到 `main` 分支。

然后 GitHub Actions 会自动完成：

```text
1. 拉取 main 分支代码
2. 安装前端依赖
3. 构建 frontend/dist
4. 打包 backend 和 frontend/dist
5. 上传到服务器 /tmp/weview-release.tgz
6. 解压覆盖 /www/wwwroot/weview-repo
7. pip install -e backend
8. alembic upgrade head
9. systemctl restart weview-api
10. curl /health
```

成功标准：

```text
GitHub Actions 显示绿色 = 自动上线成功
GitHub Actions 显示红色 = 自动上线失败，查看日志或截图询问维护人员
```

## 二、为什么采用这种方式

### 1. 不让服务器直接访问 GitHub

云服务器访问 GitHub 很慢时，如果用：

```bash
git pull origin main
```

容易卡住、超时或失败。

本方案改成：

```text
GitHub Actions 在 GitHub 自己的环境中拉代码和构建
GitHub Actions 主动把部署包推送到服务器
```

服务器只需要接收一个压缩包，速度和稳定性通常更好。

### 2. 前端和后端都自动部署

前端自动部署：

```text
pnpm build -> frontend/dist -> 上传服务器
```

后端自动部署：

```text
上传 backend 源码 -> pip install -e backend -> alembic upgrade head -> restart FastAPI
```

所以不是只有前端自动化，后端也会自动上线。

### 3. 生产密钥不进入 GitHub

以下内容只保存在服务器：

```text
/www/wwwroot/weview-repo/.env
/www/wwwroot/weview-repo/.venv
MySQL 数据
Milvus 数据
DashScope API Key
JWT_SECRET_KEY
```

GitHub Actions 只上传代码和前端构建产物，不上传 `.env`。

## 三、服务器一次性准备

以下命令在云服务器执行。

### 1. 创建部署目录

```bash
mkdir -p /www/wwwroot/weview-repo
mkdir -p /www/wwwroot/weview-repo/backend
mkdir -p /www/wwwroot/weview-repo/frontend
```

为什么：

- `/www/wwwroot/weview-repo` 是最终运行目录。
- 后续 GitHub Actions 会把后端和前端文件放到这里。

### 2. 准备生产环境变量 `.env`

如果旧目录已经有 `.env`：

```bash
cp /www/wwwroot/weview/.env /www/wwwroot/weview-repo/.env
chmod 600 /www/wwwroot/weview-repo/.env
```

如果旧目录没有 `.env`，新建：

```bash
vim /www/wwwroot/weview-repo/.env
```

示例内容：

```dotenv
DATABASE_URL=mysql+pymysql://weview_mvp:<数据库密码>@127.0.0.1:3306/weview_mvp
MILVUS_HOST=127.0.0.1
MILVUS_PORT=19530
MILVUS_COLLECTION_NAME=weview_content_chunks

USE_FAKE_EXTERNAL_CLIENTS=false
JWT_SECRET_KEY=<至少32位随机字符串>

DASHSCOPE_API_KEY=<真实DashScope Key>
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_CHAT_MODEL=qwen-plus
DASHSCOPE_STRUCTURE_MODEL=qwen-plus
DASHSCOPE_QUIZ_MODEL=qwen-plus
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v4
DASHSCOPE_OCR_MODEL=qwen-vl-ocr-2025-11-20
DASHSCOPE_VISION_MODEL=qwen3.6-plus

DASHSCOPE_HTTP_TIMEOUT_SECONDS=15
DASHSCOPE_IMPORT_TIMEOUT_SECONDS=120
DASHSCOPE_OCR_TIMEOUT_SECONDS=60
DASHSCOPE_QUIZ_TIMEOUT_SECONDS=90

RAG_SIMILARITY_THRESHOLD=0.7
RAG_TOP_K=5
```

为什么：

- `.env` 保存生产数据库、Milvus、DashScope、JWT 配置。
- `.env` 不能提交到 GitHub。
- `chmod 600` 用于降低密钥泄露风险。

### 3. 创建 Python 虚拟环境

```bash
cd /www/wwwroot/weview-repo
python3.13 -m venv .venv
.venv/bin/pip install --upgrade pip
```

如果服务器访问 PyPI 慢，可设置国内源：

```bash
/www/wwwroot/weview-repo/.venv/bin/pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

为什么：

- 后端依赖安装在 `.venv`，不污染系统 Python。
- 后续自动部署会复用这个虚拟环境。
- 国内源可以减少安装依赖失败概率。

### 4. 准备 backend 下的 `.env` 软链接

```bash
cd /www/wwwroot/weview-repo/backend
ln -sf /www/wwwroot/weview-repo/.env .env
```

为什么：

- 后端配置默认读取当前工作目录下的 `.env`。
- 如果服务工作目录是 `/www/wwwroot/weview-repo/backend`，这里必须能找到 `.env`。
- 软链接可以保证只维护一份真实配置。

## 四、配置后端 systemd 服务

推荐用 systemd 管理 FastAPI 服务。

创建或编辑服务文件：

```bash
vim /etc/systemd/system/weview-api.service
```

如果使用 `www` 用户运行，内容如下：

```ini
[Unit]
Description=WeView FastAPI
After=network.target

[Service]
User=www
WorkingDirectory=/www/wwwroot/weview-repo/backend
EnvironmentFile=/www/wwwroot/weview-repo/.env
ExecStart=/www/wwwroot/weview-repo/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

如果后续采用 `deploy` 用户部署和运行服务，则把：

```ini
User=www
```

改成：

```ini
User=deploy
```

重载 systemd：

```bash
systemctl daemon-reload
systemctl enable weview-api
```

说明：

- 第一次配置时，如果代码还没有上传，服务启动失败是正常的。
- 等 GitHub Actions 第一次部署成功后，再启动或重启即可。

## 五、Nginx / 宝塔说明

如果你已经在宝塔里配置好了站点，可以跳过本节。

前端站点根目录应指向：

```text
/www/wwwroot/weview-repo/frontend/dist
```

核心 Nginx 配置：

```nginx
client_max_body_size 25m;

location / {
    try_files $uri $uri/ /index.html;
}

location = /health {
    proxy_pass http://127.0.0.1:8000/health;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    proxy_connect_timeout 30s;
    proxy_send_timeout 180s;
    proxy_read_timeout 180s;
}
```

保存后测试并重载：

```bash
nginx -t
systemctl reload nginx
```

为什么：

- `/` 服务 Vue 静态前端。
- `try_files $uri $uri/ /index.html;` 支持 Vue Router history 模式。
- `/api/` 转发到 FastAPI。
- `/health` 用于自动健康检查。

## 六、配置 SSH 部署权限

这里有两个方案。

如果要快速跑通，用方案 A。

如果要长期交给小白维护，推荐方案 B。

## 方案 A：使用 root 部署，最快

### 1. 确认 root 可以 SSH 登录

本地 Windows PowerShell 执行：

```powershell
ssh root@你的服务器公网IP
```

能登录即可。

### 2. 生成 GitHub Actions 专用 SSH Key

本地 Windows PowerShell 执行：

```powershell
ssh-keygen -t ed25519 -C "weview-github-actions-deploy" -f "$env:USERPROFILE\.ssh\weview_github_actions"
```

一路回车即可。

生成结果：

```text
C:\Users\你的用户名\.ssh\weview_github_actions
C:\Users\你的用户名\.ssh\weview_github_actions.pub
```

含义：

```text
weview_github_actions      私钥，填到 GitHub Secrets
weview_github_actions.pub  公钥，放到服务器 authorized_keys
```

### 3. 把公钥放到服务器 root

本地查看公钥：

```powershell
type "$env:USERPROFILE\.ssh\weview_github_actions.pub"
```

复制整行内容。

服务器执行：

```bash
mkdir -p /root/.ssh
vim /root/.ssh/authorized_keys
```

把公钥粘进去，保存。

修正权限：

```bash
chmod 700 /root/.ssh
chmod 600 /root/.ssh/authorized_keys
```

### 4. 测试私钥登录

本地 Windows PowerShell 执行：

```powershell
ssh -i "$env:USERPROFILE\.ssh\weview_github_actions" root@你的服务器公网IP
```

能登录就成功。

## 方案 B：使用 deploy 用户，更推荐

### 1. 创建 deploy 用户

服务器执行：

```bash
useradd -m -s /bin/bash deploy
```

如果提示用户已存在，可以继续下一步。

### 2. 给 deploy 用户部署目录权限

```bash
chown -R deploy:deploy /www/wwwroot/weview-repo
```

为什么：

- GitHub Actions 用 deploy 登录后，需要写入 `/www/wwwroot/weview-repo`。
- 目录归 deploy 所有，最不容易遇到权限问题。

### 3. 建议 systemd 服务也使用 deploy 用户

编辑：

```bash
vim /etc/systemd/system/weview-api.service
```

把：

```ini
User=www
```

改成：

```ini
User=deploy
```

确认服务文件类似：

```ini
[Unit]
Description=WeView FastAPI
After=network.target

[Service]
User=deploy
WorkingDirectory=/www/wwwroot/weview-repo/backend
EnvironmentFile=/www/wwwroot/weview-repo/.env
ExecStart=/www/wwwroot/weview-repo/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

重载：

```bash
systemctl daemon-reload
```

为什么：

- 部署用户和服务运行用户一致，权限问题最少。
- 如果 deploy 上传文件、www 运行服务，容易出现文件读写权限不一致。

### 4. 允许 deploy 免密重启服务

查看 `systemctl` 路径：

```bash
which systemctl
```

通常输出：

```text
/bin/systemctl
```

编辑 sudoers：

```bash
visudo
```

如果 `which systemctl` 是 `/bin/systemctl`，添加：

```text
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart weview-api
deploy ALL=(ALL) NOPASSWD: /bin/systemctl status weview-api
```

如果输出是 `/usr/bin/systemctl`，添加：

```text
deploy ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart weview-api
deploy ALL=(ALL) NOPASSWD: /usr/bin/systemctl status weview-api
```

为什么：

- deploy 不是 root，默认不能重启系统服务。
- 这里只授权它重启和查看 `weview-api`，比开放完整 root 权限更安全。

### 5. 生成部署 SSH Key

本地 Windows PowerShell 执行：

```powershell
ssh-keygen -t ed25519 -C "weview-github-actions-deploy" -f "$env:USERPROFILE\.ssh\weview_github_actions"
```

如果文件已存在并且不想覆盖，可换一个名字：

```powershell
ssh-keygen -t ed25519 -C "weview-github-actions-deploy" -f "$env:USERPROFILE\.ssh\weview_github_actions_deploy"
```

### 6. 把公钥放到服务器 deploy

本地查看公钥：

```powershell
type "$env:USERPROFILE\.ssh\weview_github_actions.pub"
```

如果用了另一个文件名：

```powershell
type "$env:USERPROFILE\.ssh\weview_github_actions_deploy.pub"
```

复制整行。

服务器执行：

```bash
mkdir -p /home/deploy/.ssh
vim /home/deploy/.ssh/authorized_keys
```

把公钥粘进去，保存。

修正权限：

```bash
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys
```

### 7. 本地测试 deploy 登录

如果私钥叫 `weview_github_actions`：

```powershell
ssh -i "$env:USERPROFILE\.ssh\weview_github_actions" deploy@你的服务器公网IP
```

如果私钥叫 `weview_github_actions_deploy`：

```powershell
ssh -i "$env:USERPROFILE\.ssh\weview_github_actions_deploy" deploy@你的服务器公网IP
```

能登录就成功。

### 8. 测试 deploy 能重启服务

用 deploy 登录服务器后执行：

```bash
sudo systemctl status weview-api
sudo systemctl restart weview-api
```

如果不要求输入密码，说明 sudoers 配置成功。

## 七、GitHub 配置 Secrets

进入 GitHub 仓库页面：

```text
Settings
  -> Secrets and variables
  -> Actions
  -> Repository secrets
  -> New repository secret
```

新增以下 3 个 Secret。

### 1. SERVER_HOST

Name：

```text
SERVER_HOST
```

Secret：

```text
你的服务器公网IP
```

例如：

```text
1.2.3.4
```

不要加 `http://` 或 `https://`。

### 2. SERVER_USER

如果使用 root：

```text
root
```

如果使用 deploy：

```text
deploy
```

### 3. SERVER_SSH_KEY

Name：

```text
SERVER_SSH_KEY
```

Secret 填私钥完整内容。

本地 Windows PowerShell 查看私钥：

```powershell
type "$env:USERPROFILE\.ssh\weview_github_actions"
```

如果换了名字：

```powershell
type "$env:USERPROFILE\.ssh\weview_github_actions_deploy"
```

复制完整内容，形如：

```text
-----BEGIN OPENSSH PRIVATE KEY-----
中间很多行
-----END OPENSSH PRIVATE KEY-----
```

注意：

- 填的是私钥，不是 `.pub` 公钥。
- 必须包含第一行和最后一行。
- 不要额外加空格。

为什么：

- GitHub Actions 运行时会用这些 Secrets 登录服务器。
- Secrets 不会显示在代码仓库中。

## 八、添加 GitHub Actions 工作流

在本地项目创建目录：

```bat
cd /d E:\WeView\work4
mkdir .github
mkdir .github\workflows
```

如果目录已存在，忽略报错即可。

创建文件：

```text
E:\WeView\work4\.github\workflows\deploy.yml
```

写入以下内容：

```yaml
name: Deploy WeView

on:
  push:
    branches:
      - main

concurrency:
  group: weview-production-deploy
  cancel-in-progress: true

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout source
        uses: actions/checkout@v4

      - name: Setup pnpm
        uses: pnpm/action-setup@v4
        with:
          version: 11.7.0

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: 24
          cache: pnpm
          cache-dependency-path: frontend/pnpm-lock.yaml

      - name: Configure pnpm registry
        working-directory: frontend
        run: pnpm config set registry https://registry.npmjs.org

      - name: Install frontend dependencies
        working-directory: frontend
        run: pnpm install --frozen-lockfile

      - name: Build frontend
        working-directory: frontend
        run: VITE_API_BASE_URL=/api pnpm build

      - name: Package release
        run: |
          mkdir -p release/backend release/frontend

          cp -r backend/app release/backend/app
          cp -r backend/alembic release/backend/alembic
          cp backend/alembic.ini release/backend/alembic.ini
          cp backend/pyproject.toml release/backend/pyproject.toml

          cp -r frontend/dist release/frontend/dist

          tar -czf weview-release.tgz -C release .

      - name: Upload release package
        uses: appleboy/scp-action@v0.1.7
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SERVER_SSH_KEY }}
          source: weview-release.tgz
          target: /tmp

      - name: Deploy on server
        uses: appleboy/ssh-action@v1.2.0
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SERVER_SSH_KEY }}
          script: |
            set -euo pipefail

            APP_DIR="/www/wwwroot/weview-repo"
            TMP_DIR="/tmp/weview-release"

            echo "[1/8] Prepare directories"
            rm -rf "$TMP_DIR"
            mkdir -p "$TMP_DIR"
            mkdir -p "$APP_DIR/backend"
            mkdir -p "$APP_DIR/frontend"

            echo "[2/8] Extract release package"
            tar -xzf /tmp/weview-release.tgz -C "$TMP_DIR"

            echo "[3/8] Check server-only files"
            test -f "$APP_DIR/.env"
            test -d "$APP_DIR/.venv"

            echo "[4/8] Replace backend and frontend artifacts"
            rm -rf "$APP_DIR/backend/app"
            rm -rf "$APP_DIR/backend/alembic"
            rm -rf "$APP_DIR/frontend/dist"

            cp -a "$TMP_DIR/backend/." "$APP_DIR/backend/"
            cp -a "$TMP_DIR/frontend/." "$APP_DIR/frontend/"

            echo "[5/8] Ensure backend .env symlink"
            ln -sf "$APP_DIR/.env" "$APP_DIR/backend/.env"

            echo "[6/8] Install backend dependencies and migrate database"
            cd "$APP_DIR/backend"
            "$APP_DIR/.venv/bin/pip" install -e "$APP_DIR/backend"
            "$APP_DIR/.venv/bin/python" -m alembic upgrade head

            echo "[7/8] Restart backend"
            sudo systemctl restart weview-api

            echo "[8/8] Health check"
            curl -f http://127.0.0.1:8000/health

            echo "Deploy complete"
```

## 九、为什么工作流这样写

### 1. 只在 main 分支触发

```yaml
on:
  push:
    branches:
      - main
```

含义：

```text
只有 main 分支有新提交，才自动上线。
```

### 2. 避免多个部署互相冲突

```yaml
concurrency:
  group: weview-production-deploy
  cancel-in-progress: true
```

如果连续提交两次，旧部署会取消，只部署最新一次。

### 3. 前端在 GitHub Actions 构建

```yaml
pnpm install --frozen-lockfile
VITE_API_BASE_URL=/api pnpm build
```

这样服务器不用安装前端依赖或运行构建，减少服务器压力。

GitHub Actions 当前使用 npm 官方 registry：

```text
https://registry.npmjs.org
```

因此 workflow 在安装前端依赖前显式执行：

```yaml
      - name: Configure pnpm registry
        working-directory: frontend
        run: pnpm config set registry https://registry.npmjs.org
```

如果本地 lockfile 是用 `https://registry.npmmirror.com` 等镜像源生成的，而 GitHub Actions 使用 `https://registry.npmjs.org`，pnpm 11 会进行供应链校验并报错：

```text
ERR_PNPM_TARBALL_URL_MISMATCH
Lockfile failed supply-chain policy check
```

这个错误不是 SSH 配置问题，也不是服务器问题；它发生在 GitHub runner 安装前端依赖阶段。根因是 lockfile 记录的 tarball 域名与当前 registry 不一致。

本项目处理方式：

```text
frontend/pnpm-lock.yaml 统一提交 registry.npmjs.org tarball
GitHub Actions 也显式设置 registry.npmjs.org
```

### 4. 只上传运行必需文件

上传内容：

```text
backend/app
backend/alembic
backend/alembic.ini
backend/pyproject.toml
frontend/dist
```

不上传：

```text
.env
.venv
node_modules
测试缓存
本地部署包
文档临时文件
```

这样更安全、更快。

### 5. 服务器不访问 GitHub

服务器只接收：

```text
/tmp/weview-release.tgz
```

因此不会被 GitHub 慢连接卡住。

### 6. 自动执行数据库迁移

```bash
"$APP_DIR/.venv/bin/python" -m alembic upgrade head
```

以后如果后端新增 Alembic migration，推送 main 后数据库结构会自动更新。

### 7. 自动重启后端

```bash
sudo systemctl restart weview-api
```

后端代码更新后，FastAPI 进程必须重启才会生效。

### 8. 自动健康检查

```bash
curl -f http://127.0.0.1:8000/health
```

如果后端没有启动成功，GitHub Actions 会失败变红。

## 十、提交 workflow 到 GitHub

本地执行：

```bat
cd /d E:\WeView\work4
git status --short
git add .github/workflows/deploy.yml 部署_git_action.md
git commit -m "Add GitHub Actions deployment guide and workflow"
git push origin main
```

如果你暂时只想提交文档，不提交 workflow：

```bat
git add 部署_git_action.md
git commit -m "Add GitHub Actions deployment guide"
git push origin main
```

## 十一、观察第一次自动部署

打开 GitHub 仓库：

```text
Actions -> Deploy WeView
```

点击最新一次运行，观察每一步：

```text
Checkout source
Setup pnpm
Setup Node
Install frontend dependencies
Build frontend
Package release
Upload release package
Deploy on server
```

全部绿色代表部署成功。

## 十二、第一次部署后服务器验证

服务器执行：

```bash
curl http://127.0.0.1:8000/health
```

应返回类似：

```json
{"status":"ok"}
```

检查前端产物：

```bash
ls -la /www/wwwroot/weview-repo/frontend/dist
```

应看到：

```text
index.html
assets
```

检查后端文件：

```bash
ls -la /www/wwwroot/weview-repo/backend
```

应看到：

```text
app
alembic
alembic.ini
pyproject.toml
.env -> /www/wwwroot/weview-repo/.env
```

检查服务：

```bash
systemctl status weview-api
```

## 十三、交给小白后的日常使用

维护人员只需要：

```bash
git add .
git commit -m "修改说明"
git push origin main
```

或者 GitHub 网页端直接修改文件并提交到 `main`。

维护人员只需要看 GitHub Actions：

```text
绿色 = 上线成功
红色 = 上线失败，把日志截图给维护人员
```

## 十四、常见错误和修复

### 1. SSH 登录失败

Actions 日志可能显示：

```text
ssh: handshake failed
```

检查：

```text
SERVER_HOST 是否是纯 IP
SERVER_USER 是否正确
SERVER_SSH_KEY 是否填了私钥
服务器 22 端口是否开放
公钥是否写入 authorized_keys
```

### 2. 上传成功但部署失败：`.env` 不存在

服务器执行：

```bash
ls -la /www/wwwroot/weview-repo/.env
```

如果不存在：

```bash
cp /www/wwwroot/weview/.env /www/wwwroot/weview-repo/.env
chmod 600 /www/wwwroot/weview-repo/.env
```

### 3. `.venv` 不存在

服务器执行：

```bash
cd /www/wwwroot/weview-repo
python3.13 -m venv .venv
.venv/bin/pip install --upgrade pip
```

### 4. deploy 用户不能写目录

修复：

```bash
chown -R deploy:deploy /www/wwwroot/weview-repo
```

如果使用 root 部署，不需要这一步。

### 5. deploy 用户不能重启服务

检查：

```bash
sudo systemctl restart weview-api
```

如果要求输入密码，说明 sudoers 没配好。

执行：

```bash
which systemctl
visudo
```

按实际路径添加：

```text
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart weview-api
deploy ALL=(ALL) NOPASSWD: /bin/systemctl status weview-api
```

或：

```text
deploy ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart weview-api
deploy ALL=(ALL) NOPASSWD: /usr/bin/systemctl status weview-api
```

### 6. 后端报数据库账号错误

服务器执行：

```bash
cd /www/wwwroot/weview-repo/backend
/www/wwwroot/weview-repo/.venv/bin/python -c "from app.core.config import Settings; print(Settings().database_url)"
```

如果输出不是 `.env` 里的真实数据库配置，执行：

```bash
ln -sf /www/wwwroot/weview-repo/.env /www/wwwroot/weview-repo/backend/.env
sudo systemctl restart weview-api
```

### 7. 前端页面旧版本没更新

检查 Actions 是否成功，再检查服务器文件时间：

```bash
ls -lah /www/wwwroot/weview-repo/frontend/dist
```

如果文件已更新，可能是浏览器缓存。

浏览器强刷：

```text
Ctrl + F5
```

### 8. 刷新 `/admin` 404

Nginx 缺少：

```nginx
location / {
    try_files $uri $uri/ /index.html;
}
```

### 9. `pip install -e backend` 失败

检查服务器目录：

```bash
ls -la /www/wwwroot/weview-repo/backend
```

必须有：

```text
pyproject.toml
app
alembic
alembic.ini
```

如果缺少，说明 GitHub Actions 打包或解压步骤失败。

### 10. `pnpm install --frozen-lockfile` 报 `ERR_PNPM_TARBALL_URL_MISMATCH`

Actions 日志可能显示：

```text
Lockfile failed supply-chain policy check
[ERR_PNPM_TARBALL_URL_MISMATCH]
```

原因：

```text
frontend/pnpm-lock.yaml 中记录的 tarball 域名
与 GitHub Actions 当前使用的 registry 域名不一致
pnpm 11 供应链校验发现两者不一致，所以拒绝安装
```

修复：

1. 确认 `.github/workflows/deploy.yml` 的 `Setup Node` 后、`Install frontend dependencies` 前有：

```yaml
      - name: Configure pnpm registry
        working-directory: frontend
        run: pnpm config set registry https://registry.npmjs.org
```

2. 确认 `frontend/pnpm-lock.yaml` 中没有旧镜像 tarball：

```bat
cd /d E:\WeView\work4
rg "registry.npmmirror.com" frontend\pnpm-lock.yaml
```

如果还有输出，把 lockfile 统一更新为 npm 官方 registry。

3. 提交并推送：

```bat
git add .github/workflows/deploy.yml frontend/pnpm-lock.yaml 部署_git_action.md
git commit -m "Fix pnpm lockfile registry for deployment workflow"
git push origin main
```

### 11. Alembic 迁移失败

先看 Actions 日志中的具体错误。

常见原因：

```text
DATABASE_URL 错误
MySQL 服务未启动
数据库账号无权限
迁移文件有问题
```

服务器可手工验证：

```bash
cd /www/wwwroot/weview-repo/backend
/www/wwwroot/weview-repo/.venv/bin/python -m alembic current
/www/wwwroot/weview-repo/.venv/bin/python -m alembic upgrade head
```

## 十五、上线前最终检查清单

服务器检查：

```bash
test -f /www/wwwroot/weview-repo/.env && echo ".env ok"
test -d /www/wwwroot/weview-repo/.venv && echo ".venv ok"
test -f /etc/systemd/system/weview-api.service && echo "systemd ok"
```

Python 检查：

```bash
/www/wwwroot/weview-repo/.venv/bin/python --version
/www/wwwroot/weview-repo/.venv/bin/pip --version
```

Nginx 检查：

```bash
nginx -t
```

服务检查：

```bash
systemctl status weview-api
```

GitHub Secrets 检查：

```text
SERVER_HOST 已配置
SERVER_USER 已配置
SERVER_SSH_KEY 已配置
```

## 十六、推荐执行顺序

第一次落地建议按以下顺序：

```text
1. 确认 /www/wwwroot/weview-repo/.env 存在
2. 确认 /www/wwwroot/weview-repo/.venv 存在
3. 确认 systemd 服务文件指向 /www/wwwroot/weview-repo
4. 选择 root 或 deploy 用户
5. 配置 SSH Key
6. 本地测试 SSH Key 登录服务器
7. GitHub 添加 SERVER_HOST / SERVER_USER / SERVER_SSH_KEY
8. 新增 .github/workflows/deploy.yml
9. git push origin main
10. 到 GitHub Actions 看第一次部署结果
11. 如果红色，把失败步骤和日志复制出来继续排查
```

## 十七、给维护人员的简化说明

可以把下面这段交给后续维护人员：

```text
以后修改代码后，只需要提交到 GitHub main 分支。

GitHub 会自动部署到服务器。

部署成功：Actions 显示绿色。
部署失败：Actions 显示红色，把红色日志截图发给技术人员。

不要手动修改服务器上的 /www/wwwroot/weview-repo/backend 和 frontend/dist。
不要把 .env、数据库密码、DashScope Key 提交到 GitHub。
```
