# 部署 GitHub Actions 踩坑指南

本文记录本项目通过 GitHub Actions 自动部署到云服务器 `/www/wwwroot/weview-repo` 过程中已经实际遇到的问题、原因和解决方法。

适用场景：

```text
本地修改代码
提交并推送到 GitHub main 分支
GitHub Actions 自动构建前端、上传产物、更新服务器代码、重启后端服务
```

核心文件：

```text
.github/workflows/deploy.yml
部署_git_action.md
```

服务器部署目录：

```text
/www/wwwroot/weview-repo
```

## 1. authorized_keys 里为什么已经有一个公钥

现象：

```text
~/.ssh/authorized_keys 里已经有一行 root@VM-0-16-opencloudos
后来又新增了一行 weview-github-actions-deploy
```

原因：

```text
上面那行通常是服务器创建时、宝塔面板、云厂商控制台或你之前登录时已有的 SSH 公钥。
下面那行是本次专门给 GitHub Actions 部署用的新公钥。
```

解决：

```text
不要随便删除原来的公钥。
只要新生成的私钥能登录服务器，就说明新公钥配置成功。
```

本地验证命令：

```powershell
ssh -i "$env:USERPROFILE\.ssh\weview_github_actions" root@124.223.94.16
```

## 2. GitHub Secret 里的私钥要粘贴哪部分

结论：

```text
私钥完整内容在：
C:\Users\33019\.ssh\weview_github_actions
```

GitHub Secret `SERVER_SSH_KEY` 要粘贴完整内容，包括开头和结尾：

```text
-----BEGIN OPENSSH PRIVATE KEY-----
中间很多行
-----END OPENSSH PRIVATE KEY-----
```

不要粘贴 `.pub` 文件内容。

`.pub` 是公钥，放服务器 `authorized_keys`；没有 `.pub` 后缀的是私钥，放 GitHub Secrets。

## 3. 提交 workflow 会不会影响 GitHub 上已有项目

结论：

```text
不会删除已有代码。
它只是新增或修改 .github/workflows/deploy.yml。
```

真正影响服务器的是：

```text
push 到 main 分支后 GitHub Actions 会开始部署。
```

因此第一次上线前，要确认服务器 `.env`、`.venv`、systemd、Nginx 都已准备好。

## 4. pnpm install 报 ERR_PNPM_TARBALL_URL_MISMATCH

现象：

```text
Install frontend dependencies
ERR_PNPM_TARBALL_URL_MISMATCH
tarball URL ... registry.npmmirror.com ...
does not match ... registry.npmjs.org ...
```

原因：

```text
frontend/pnpm-lock.yaml 里记录的是 npmmirror 的包地址。
GitHub Actions 使用的是 npmjs 官方源。
pnpm 的供应链校验发现 lockfile 里的 tarball 域名和当前 registry 不一致，于是拒绝安装。
```

解决方法：

```text
统一 registry。
本项目当前选择统一为 https://registry.npmjs.org
```

workflow 中应有：

```yaml
- name: Configure pnpm registry
  working-directory: frontend
  run: pnpm config set registry https://registry.npmjs.org
```

并且 `frontend/pnpm-lock.yaml` 里的 tarball 地址应统一为：

```text
https://registry.npmjs.org/
```

本地验证：

```powershell
cd E:\WeView\work4\frontend
corepack.cmd pnpm install --frozen-lockfile --registry=https://registry.npmjs.org
corepack.cmd pnpm build
```

## 5. GitHub Actions 新触发的那一次在哪里看

入口：

```text
GitHub 仓库页面
Actions
点击最新 workflow run
左侧点 deploy
展开失败步骤
```

如果页面右上角有：

```text
Latest #2
```

说明你当前可能正在看第 1 次失败记录，但已有第 2 次新运行。点 `Latest #2` 可以跳到最新一次。

## 6. SCP 报 dial tcp xxx:22: i/o timeout

现象：

```text
appleboy/scp-action
drone-scp error: error copy file to dest
dial tcp xxx:22: i/o timeout
```

原因：

```text
GitHub Actions 云端 runner 连不上服务器 22 端口。
这不是本地电脑能不能 SSH 的问题，也不是本地是否开启科学上网的问题。
```

为什么和本地科学上网无关：

```text
你的电脑只是打开 GitHub 网页看日志。
真正执行 scp 的是 GitHub Actions 云端机器。
```

优先检查：

```text
1. GitHub Secret SERVER_HOST 是否只填公网 IP，例如 124.223.94.16
2. 腾讯云安全组是否放行 TCP 22 入站
3. 宝塔安全、防火墙、系统 firewalld 是否放行 22
4. 如果服务器 SSH 改过端口，workflow 也必须配置对应端口
```

腾讯云安全组临时验证配置：

```text
协议：TCP
端口：22
来源：0.0.0.0/0
策略：允许
```

如果本地能连、GitHub 还是经常 timeout，可以考虑长期方案：

```text
在云服务器安装 GitHub self-hosted runner。
```

这样服务器主动连接 GitHub，不需要 GitHub 反向 SSH 到服务器。

## 7. Python requires-python 版本不匹配

现象：

```text
ERROR: Package 'weview-work4-backend' requires a different Python:
3.11.6 not in '<3.14,>=3.12'
```

原因：

```text
backend/pyproject.toml 里声明了 requires-python = ">=3.12,<3.14"。
服务器 /www/wwwroot/weview-repo/.venv 使用的是 Python 3.11.6。
pip 会严格检查这个声明，所以拒绝安装后端包。
```

推荐解决：

```text
服务器安装 Python 3.12 或 3.13，并重新创建 .venv。
```

本次实际采用的解决：

```text
用户明确决定允许 Python 3.11.6 运行。
因此把 backend/pyproject.toml 放宽为：
requires-python = ">=3.11,<3.14"
```

workflow 中的服务器 Python 预检查也同步放宽为：

```text
>=3.11,<3.14
```

注意：

```text
这是为了快速适配现有服务器环境。
如果后续使用 Python 3.12 或 3.13，仍然更贴近原始技术栈建议。
```

## 8. deploy.yml 报 Invalid workflow file line 105

现象：

```text
Invalid workflow file
You have an error in your yaml syntax on line 105
```

原因：

```text
workflow 的 script: | 里写了 Python heredoc。
heredoc 里的 import sys 没有缩进进 YAML 多行字符串，导致 YAML 语法无效。
```

错误形态类似：

```yaml
"$APP_DIR/.venv/bin/python" - <<'PY'
import sys
PY
```

解决：

```text
不要在 workflow 里嵌套容易错缩进的 heredoc。
改成一行 Python 命令。
```

当前 workflow 使用：

```bash
"$APP_DIR/.venv/bin/python" -c 'import sys; print("Python runtime:", sys.version); raise SystemExit(0 if (3, 11) <= sys.version_info[:2] < (3, 14) else "Python runtime must be >=3.11 and <3.14.")'
```

## 9. 后端重启后 health check 失败，日志显示 Permission denied: '.env'

现象：

```text
curl: (7) Failed to connect to 127.0.0.1 port 8000
journalctl -u weview-api 里看到：
PermissionError: [Errno 13] Permission denied: '.env'
```

原因：

```text
systemd 服务 weview-api 使用 www 用户运行。
但 /www/wwwroot/weview-repo/.env 是 root:root 且权限 600。
www 用户无法读取 .env，后端启动失败，所以 8000 端口没有监听。
```

检查命令：

```bash
systemctl status weview-api --no-pager -l
journalctl -u weview-api -n 160 --no-pager
ls -l /www/wwwroot/weview-repo/.env /www/wwwroot/weview-repo/backend/.env
cat /etc/systemd/system/weview-api.service
```

本次服务器修复命令：

```bash
chown www:www /www/wwwroot/weview-repo/.env
chmod 600 /www/wwwroot/weview-repo/.env
ln -sf /www/wwwroot/weview-repo/.env /www/wwwroot/weview-repo/backend/.env
systemctl restart weview-api
curl -f http://127.0.0.1:8000/health
```

workflow 已加入自动保护：

```bash
SERVICE_USER="$(systemctl show -p User --value weview-api 2>/dev/null || true)"
if [ -n "$SERVICE_USER" ] && [ "$SERVICE_USER" != "root" ] && [ "$(id -u)" -eq 0 ]; then
  chown "$SERVICE_USER:$SERVICE_USER" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
fi
```

## 10. 宝塔 `.user.ini` 导致前端 dist 删除失败

现象：

```text
[4/8] Replace backend and frontend artifacts
rm: cannot remove '/www/wwwroot/weview-repo/frontend/dist/.user.ini': Operation not permitted
```

原因：

```text
宝塔可能会在站点目录下生成 .user.ini，并给它加不可删除保护。
即使当前使用 root 部署，rm -rf frontend/dist 也可能删不掉这个文件。
```

解决：

```text
部署时不要整体删除 frontend/dist。
只清空 dist 里的普通文件，并保留 .user.ini，然后再复制新的前端构建产物。
```

当前 workflow 使用：

```bash
mkdir -p "$APP_DIR/frontend/dist"
find "$APP_DIR/frontend/dist" -mindepth 1 ! -name '.user.ini' -exec rm -rf {} +
cp -a "$TMP_DIR/frontend/." "$APP_DIR/frontend/"
```

如果你明确不需要宝塔的 `.user.ini`，也可以在服务器手动去掉不可删除属性后删除：

```bash
chattr -i /www/wwwroot/weview-repo/frontend/dist/.user.ini
rm -f /www/wwwroot/weview-repo/frontend/dist/.user.ini
```

但当前项目没有必要这样做，保留它更稳。

## 11. 健康检查 curl 太快，服务其实稍后已经启动成功

现象：

```text
[7/8] Restart backend
[8/8] Health check
curl: (7) Failed to connect to 127.0.0.1 port 8000
```

但稍后手动检查：

```bash
systemctl is-active weview-api
curl -fsS http://127.0.0.1:8000/health
```

返回：

```text
active
{"status":"ok","service":"weview-work4-api"}
```

原因：

```text
systemctl restart 返回时，只代表 systemd 已经发起启动。
FastAPI/Uvicorn 可能还需要 1 秒左右完成应用启动并监听 8000。
workflow 立刻 curl，容易抢跑失败。
```

解决：

```text
把单次 curl 改成最多等待 30 秒的重试循环。
如果 30 秒仍失败，再输出 systemctl 和 journalctl 日志。
```

当前 workflow 使用：

```bash
for i in {1..30}; do
  if curl -fsS http://127.0.0.1:8000/health; then
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "Health check failed after 30 seconds"
    sudo systemctl status weview-api --no-pager -l || true
    sudo journalctl -u weview-api -n 80 --no-pager || true
    exit 1
  fi
  sleep 1
done
```

## 12. Codex 为什么能直接操作服务器

原因：

```text
本机已有 SSH 私钥：
C:\Users\33019\.ssh\weview_github_actions
```

并且这个私钥对应的公钥已经写入服务器 root 用户的：

```text
/root/.ssh/authorized_keys
```

所以可以从本机执行：

```powershell
ssh -i "$env:USERPROFILE\.ssh\weview_github_actions" root@124.223.94.16 "systemctl status weview-api"
```

这不是绕过服务器，而是使用你已经配置好的 SSH 权限。

安全建议：

```text
当前 root 私钥权限很高。
后续正式交给小白维护时，推荐改成 deploy 用户：
只允许写 /www/wwwroot/weview-repo
只允许重启 / 查看 weview-api
不要长期让 GitHub Actions 使用 root。
```

## 13. 常用排查命令

本地检查 Git 状态：

```powershell
cd E:\WeView\work4
git status --short
```

服务器检查后端服务：

```bash
systemctl status weview-api --no-pager -l
journalctl -u weview-api -n 120 --no-pager
curl -fsS http://127.0.0.1:8000/health
ss -lntp | grep ':8000'
```

服务器检查部署目录：

```bash
ls -la /www/wwwroot/weview-repo
ls -la /www/wwwroot/weview-repo/backend
ls -la /www/wwwroot/weview-repo/frontend
```

服务器检查 `.env`：

```bash
ls -l /www/wwwroot/weview-repo/.env /www/wwwroot/weview-repo/backend/.env
```

不要输出 `.env` 内容到聊天窗口，因为里面可能有数据库密码、JWT 密钥和 DashScope API Key。

## 14. 当前建议提交的文件

如果你已经按前面的修复修改了 workflow 和文档，提交时一般包括：

```powershell
git add .github/workflows/deploy.yml 部署_git_action.md 部署_github_actions_踩坑指南.md
git commit -m "Document GitHub Actions deployment pitfalls"
git push origin main
```

如果本地还有这些文件的未提交修复，也一并确认：

```text
backend/pyproject.toml
frontend/pnpm-lock.yaml
```

最终目标是：

```text
GitHub Actions 显示绿色
服务器 systemctl is-active weview-api 返回 active
服务器 curl http://127.0.0.1:8000/health 返回 ok
```
