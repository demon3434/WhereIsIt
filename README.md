# WhereIsIt

![logo](logo.jpeg)
一个自托管的家庭/仓库物品管理系统，支持房屋-房间定位、分类、标签、图片上传与多用户权限控制。

## 1. 技术栈

- 后端：FastAPI + SQLAlchemy
- 数据库：PostgreSQL 16
- 前端：单页应用（`app/templates/index.html` + `app/static/js/app.js`）
- 部署：Docker Compose

## 2. 功能概览

- 物品管理：新增、编辑、筛选、图片上传
- 位置管理：房屋管理 + 房间管理
- 分类管理、标签管理
- 用户管理（管理员）
- 图片压缩策略（Android/Web 统一）：
  - 新增、编辑物品时，Web 端上传前先压缩并统一转 JPEG（透明图铺白底）
  - 先限制长边 `<=1600`，初始质量 `0.82`，单图目标 `<=900KB`
  - 超限时先降质量（每次 `-0.08`，最低 `0.56`），再降分辨率（长边 `*0.85`，不低于 `720`）
- 基于角色的页面访问控制：
  - `admin`：可访问 `/items /locations /categories /tags /users /profile`
  - `user`：仅可访问 `/items`

## 3. 目录结构

```text
.
├─ app/
│  ├─ routers/          # API 路由
│  ├─ services/         # 业务服务（存储、mDNS）
│  ├─ static/           # 静态资源（CSS/JS/图片）
│  └─ templates/        # 页面模板
├─ docs/
│  └─ 数据字典.md
├─ docker-compose.yml
├─ docker-compose(self-build).yml
├─ Dockerfile
└─ .env
```

## 4. 部署（新手必读）

本项目提供两种部署方式，请先选一种：

1. 使用已发布镜像部署（推荐，最快）
2. 用本地代码构建镜像后部署（用于你要改代码的场景）

### 4.1 前置条件

- 已安装 Docker Engine 与 Docker Compose（`docker compose version` 可用）
- 服务器可联网拉取镜像
- 你有一个工作目录（例如 `/opt/docker/whereisit`）

### 4.2 准备环境变量 `.env`

在部署目录创建或编辑 `.env`（仓库内已有示例，可直接复制后改值）：

```env
APP_NAME=WhereIsIt
APP_ENV=production
SECRET_KEY=please-change-this-secret
ACCESS_TOKEN_EXPIRE_MINUTES=10080
CORS_ORIGINS=*
POSTGRES_DB=whereisit
POSTGRES_USER=whereisit
POSTGRES_PASSWORD=whereisit
UPLOAD_DIR=/data/uploads
MAX_UPLOAD_MB=10
MAX_IMAGES_PER_ITEM=9
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=123456
DEFAULT_ADMIN_NICKNAME=管理员
SYNC_DEFAULT_ADMIN_PASSWORD=true
WEB_PORT=3000
```

### 4.3 方式 A：使用 DockerHub 镜像部署（推荐）

`docker-compose.yml` 默认使用镜像：`demon3434/where_is_it:latest`。

适合人群：
- 不改代码，只想快速部署
- 想和 DockerHub 最新镜像保持一致

操作步骤：

1. 进入部署目录（目录中应有 `docker-compose.yml` 和 `.env`）
2. 拉取并启动容器

```bash
docker compose pull
docker compose up -d
docker compose ps
```

3. 打开健康检查确认服务正常

```bash
# 在宿主机上运行
curl http://127.0.0.1:${WEB_PORT}/api/health
```

如果返回 `{"status":"ok"}`，说明部署成功。

### 4.4 方式 B：用本地代码构建镜像部署

`docker-compose(self-build).yml` 是“根据当前目录代码构建并运行”的 Compose 文件，不依赖 DockerHub 的应用镜像。

适合人群：
- 你改了代码，想直接在本机/服务器用当前代码运行
- 你不想依赖外网拉取应用镜像

操作步骤：

```bash
docker compose -f 'docker-compose(self-build).yml' up -d --build
docker compose -f 'docker-compose(self-build).yml' ps
```

### 4.5 两个 Compose 文件的区别（重要）

- `docker-compose.yml`
  - 使用远程镜像 `demon3434/where_is_it:latest`
  - 启动快，适合生产部署和新手

- `docker-compose(self-build).yml`
  - 使用本地代码 `build` 镜像
  - 适合开发、测试、改代码后验证

建议：
- 生产环境优先用 `docker-compose.yml`
- 开发调试优先用 `docker-compose(self-build).yml`

### 4.6 直接用 `docker run` 运行镜像（可选）

如果你不想用 Compose，也可以直接运行：

1. 用 `.env` 传参：

```bash
docker run -d --name whereisit-app --env-file .env -p 3000:3000 demon3434/where_is_it:latest
```

2. 或在命令行覆盖单个参数（优先级高于 `--env-file`）：

```bash
# 以修改 ACCESS_TOKEN_EXPIRE_MINUTES 参数为例
docker run -d --name whereisit-app --env-file .env -e ACCESS_TOKEN_EXPIRE_MINUTES=525600 -p 3000:3000 demon3434/where_is_it:latest
```

## 5. 关键可配置参数说明

- `SECRET_KEY`：JWT 签名密钥，生产环境必须替换
- `ACCESS_TOKEN_EXPIRE_MINUTES`：登录令牌有效期（分钟）
- `CORS_ORIGINS`：允许的跨域来源，多个用逗号分隔
- `POSTGRES_*`：数据库库名/用户名/密码
- `UPLOAD_DIR`：上传文件挂载目录（容器内）
- `MAX_UPLOAD_MB`：单图最大体积（MB）
- `MAX_IMAGES_PER_ITEM`：单物品最大图片数
- `DEFAULT_ADMIN_*`：默认管理员初始化信息
- `SYNC_DEFAULT_ADMIN_PASSWORD`：
  - `true`：每次启动都把默认管理员密码重置为 `.env` 中配置值
  - `false`：仅在首次创建时使用该密码
- `WEB_PORT`：主机端口映射到容器 `3000`

## 6. docker-compose 说明

默认包含两个服务：

1. `db`（PostgreSQL）
2. `app`（FastAPI）

默认卷映射：

- `./data/db` -> PostgreSQL 数据目录
- `./data/uploads` -> 上传图片目录

端口映射：

- `${WEB_PORT}:3000`

## 7. 数据库结构说明

详见：

- `docs/数据字典.md`

## 8. 生产环境建议

- 修改 `SECRET_KEY`、数据库密码、默认管理员密码
- 将 `CORS_ORIGINS` 限制为可信域名
- 通过反向代理（Nginx/Caddy）提供 HTTPS
- 定期备份 `data/db` 与 `data/uploads`
