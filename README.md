# WhereIsIt

![logo](logo.jpeg)
一个自托管的家庭/仓库物品管理系统，支持房屋-房间定位、分类、标签、图片上传与多用户权限控制。

## 1. 技术栈

- 后端：FastAPI + SQLAlchemy
- 数据库：PostgreSQL 16
- 前端：单页应用（`app/templates/index.html` + `app/static/js/app-*.js` 模块脚本）
- 部署：Docker Compose

## 2. 功能概览

- 物品管理：新增、编辑、筛选、图片上传
- 位置管理：房屋管理 + 房间管理
- 分类管理、标签管理
- 用户管理（管理员）
- 不包含“数据管理”页面与 GUI 备份恢复 API（已下线）
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
│  └─ templates/        # 页面模板（index + partials 拆分）
├─ docs/
│  ├─ 数据字典.md
│  ├─ 内网服务发现技术规范.md
│  ├─ GUI备份恢复API.md
│  └─ GUI接口测试报告与CSharp示例.md
├─ docker-compose.avahi.yml
├─ docker-compose.avahi.self-build.yml
├─ Dockerfile
├─ scripts/
│  └─ setup_avahi_whereisit.sh
└─ .env
```

## 4. 部署（新手必读）

当前统一采用“Docker bridge 网络 + Avahi 反射 mDNS”的部署方式。  
你可以二选一：

1. 使用 DockerHub 已发布镜像（最快）
2. 使用本地代码自行 build 镜像（适合改代码）

### 4.1 前置条件

- Debian/Ubuntu Linux 服务器（推荐）
- 已安装 Docker Engine 与 Docker Compose（`docker compose version` 可用）
- 服务器可访问局域网（手机和服务器在同一网段）
- 你有部署目录（例如 `/opt/docker/whereisit`）

### 4.2 进入部署目录

```bash
cd /opt/docker/whereisit
```

目录中应包含：
- `.env`
- `docker-compose.avahi.yml`
- `docker-compose.avahi.self-build.yml`
- `scripts/setup_avahi_whereisit.sh`

### 4.3 准备 `.env`（至少确认以下参数）

```env
WEB_PORT=3000
POSTGRES_DB=whereisit
POSTGRES_USER=whereisit
POSTGRES_PASSWORD=whereisit
SERVICE_DISCOVERY_ENABLED=true
SERVICE_DISCOVERY_TYPE=_whereisit._tcp.local.
SERVICE_DISCOVERY_NAME=WhereIsIt
SERVICE_ADVERTISE_HOST=192.168.1.50
```

说明：
- `SERVICE_ADVERTISE_HOST` 必须填写服务器局域网 IP（手机可访问）
- 不要填 `127.0.0.1`，也不要填 `172.x.x.x` 这类 Docker 内网地址

### 4.4 首次执行 Avahi 自动配置（只需一次）

给脚本执行权限并运行：

```bash
chmod +x scripts/setup_avahi_whereisit.sh
sudo bash scripts/setup_avahi_whereisit.sh
```

脚本会自动：
- 安装 `avahi-daemon`
- 创建/校验 Docker 网络 `whereisit_mdns`（桥接网卡 `br-whereisit`）
- 写入 Avahi 反射配置并重启服务

### 4.5 方式 A：DockerHub 镜像部署（推荐）

```bash
docker compose -f docker-compose.avahi.yml pull
docker compose -f docker-compose.avahi.yml up -d
docker compose -f docker-compose.avahi.yml ps
```

### 4.6 方式 B：本地代码 build 镜像部署

```bash
docker compose -f docker-compose.avahi.self-build.yml up -d --build
docker compose -f docker-compose.avahi.self-build.yml ps
```

### 4.7 部署后验证

1. 检查后端健康：
```bash
curl http://127.0.0.1:${WEB_PORT}/api/health
```

2. 检查 mDNS 是否被发现：
```bash
avahi-browse -atr | grep -i whereisit
```

出现类似以下内容即说明发现链路正常：
```text
+ br-whereisit IPv4 WhereIsIt _whereisit._tcp local
= br-whereisit IPv4 WhereIsIt _whereisit._tcp local
  hostname = [whereisit.local]
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

默认卷映射（当前 compose 文件）：

- `/opt/docker/whereisit/data/db` -> PostgreSQL 数据目录
- `/opt/docker/whereisit/data/uploads` -> 上传图片目录

端口映射：

- `${WEB_PORT}:3000`

## 7. 数据库结构说明

详见：

- `docs/数据字典.md`

## 8. API 兼容说明

- 当前版本已移除 GUI 备份恢复相关接口：
  - `/api/tasks*`
  - `/api/backup/*`
  - `/api/restore/*`
  - `/api/admin/data/*`
- 当前保留的核心接口以业务 CRUD 与认证为主（如 `/api/auth/*`、`/api/me`、`/api/items` 等）。

## 9. 生产环境建议

- 修改 `SECRET_KEY`、数据库密码、默认管理员密码
- 将 `CORS_ORIGINS` 限制为可信域名
- 通过反向代理（Nginx/Caddy）提供 HTTPS
- 定期备份 `data/db` 与 `data/uploads`
