# WhereIsIt

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
├─ Dockerfile
└─ .env
```

## 4. 快速部署

### 4.1 前置条件

- 已安装 Docker / Docker Compose
- Linux 服务器或支持 Docker 的环境

### 4.2 配置环境变量

编辑 `.env`（仓库已提供示例，按需调整）：

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
WEB_PORT=4000
```

### 4.3 启动

```bash
docker compose up -d --build
docker compose ps
```

访问：`http://<服务器IP>:<WEB_PORT>`（默认 `4000`）

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

`docker-compose.yml` 中包含两个服务：

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
