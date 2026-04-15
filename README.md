# WhereIsIt

WhereIsIt 是一个自托管的家庭物品管理系统，支持房屋/房间定位、分类标签、图片上传、用户权限管理，以及 GUI 可调用的数据库与图片备份恢复 API。

## 技术栈

- 后端：FastAPI + SQLAlchemy
- 数据库：PostgreSQL 16
- 前端：Jinja2 + 原生 JavaScript
- 部署：Docker Compose

## 当前可用能力（20260416 代码）

- 物品、位置、分类、标签、用户管理
- 登录鉴权（Cookie + Bearer Token）
- 健康检查：`GET /api/health`
- GUI 备份恢复 API（在线）：
  - 任务查询与取消：`/api/tasks*`
  - 数据库备份恢复：`/api/backup/database*`、`/api/restore/database*`
  - 图片备份恢复：`/api/backup/uploads*`、`/api/restore/uploads*`
  - 管理端数据导入导出：`/api/admin/data/*`

## 认证与返回格式

- 登录接口：`POST /api/auth/login`
- 登录返回是 envelope：
  - `code`
  - `message`
  - `data.access_token`
  - `data.token_type`
- 健康检查接口是：`GET /api/health`，返回 `{ "status": "ok" }`

## GUI 备份恢复说明

- GUI 文档见 [GUI备份恢复API.md](/E:/code/WhereIsIt/docs/GUI备份恢复API.md)。
- 任务状态（task/manifest/upload 索引）当前是进程内存态：
  - 服务重启后会清空任务状态
  - 不影响已落盘的备份文件本身
- 数据库备份恢复调用 `pg_dump/pg_restore/psql`，并在执行前校验工具主版本与目标数据库主版本一致。

## 目录

```text
app/
  routers/            API 路由
  services/           业务服务（含 GUI 任务状态）
  static/             静态资源
  templates/          页面模板
docs/
  GUI备份恢复API.md
  GUI接口测试报告与CSharp示例.md
Dockerfile
docker-compose.avahi.yml
docker-compose.avahi.self-build.yml
```

