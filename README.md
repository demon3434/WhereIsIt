# WhereIsIt

WhereIsIt 是一个自托管的家庭物品管理系统，支持房屋/房间定位、分类标签、图片上传、用户权限、数据库与图片备份恢复，以及面向 Android 客户端的语音搜索。

## 技术栈

- 后端：FastAPI、SQLAlchemy、Pydantic Settings
- 数据库：PostgreSQL 16
- 前端：Jinja2、原生 JavaScript
- 语音搜索：WebSocket、sherpa-onnx、FunASR 兼容回退链路
- 部署：Docker Compose

## 文档索引

- [API-Envelope接口文档.md](docs/API-Envelope接口文档.md)
- [GUI备份恢复API.md](docs/GUI备份恢复API.md)
- [内网服务发现技术规范.md](docs/内网服务发现技术规范.md)
- [数据字典.md](docs/数据字典.md)
- [语音清洗词维护说明.md](docs/语音搜索/语音清洗词维护说明.md)

## 目录

```text
app/
  routers/            API 路由
  services/           业务服务
  static/             静态资源
  templates/          页面模板
docs/
  语音搜索/
Dockerfile
docker-compose.avahi.yml
docker-compose.avahi.self-build.yml
```

## 部署方法

服务器当前部署信息：

- 主机：`192.168.7.186`
- 用户：`docker`
- 部署目录：`/opt/docker/whereisit`
- 编排文件：`docker-compose.avahi.self-build.yml`

部署前，`.env` 中至少要手工确认并修改这些键值：

- `SECRET_KEY`
  生产环境必须改成高强度随机字符串，不能继续使用默认值。
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
  这 3 项决定 PostgreSQL 的库名、账号和密码，首次部署前应按目标环境修改。
- `DEFAULT_ADMIN_USERNAME`
- `DEFAULT_ADMIN_PASSWORD`
  默认管理员账号和密码，首次部署前建议改掉默认值。
- `CORS_ORIGINS`
  如果要给 Android、局域网网页或反向代理域名访问，这里要改成实际允许的来源；公网环境不要长期使用 `*`。
- `WEB_PORT`
  宿主机对外暴露端口，和实际部署端口保持一致。
- `SERVICE_ADVERTISE_HOST`
  服务对外通告地址，局域网部署时一般改成服务器 IP。

如果语音搜索要启用，还要确认这些路径配置：

- `VOICE_MODEL_DOWNLOAD_ROOT`
- `VOICE_SHERPA_MODEL_DIR`
- `VOICE_CLEANING_LEXICON_DIR`

这几项通常保持容器内路径即可，但要确保它们在 `docker-compose` 中有正确的宿主机卷挂载。

常用部署命令：

```bash
cd /opt/docker/whereisit
docker compose -f docker-compose.avahi.self-build.yml up -d --build
```

如果不想自行构建镜像，也可以直接使用 Docker Hub 镜像：

```bash
docker pull demon3434/where_is_it:2.0
docker tag demon3434/where_is_it:2.0 whereisit-app:latest
cd /opt/docker/whereisit
docker compose -f docker-compose.avahi.yml up -d
```
