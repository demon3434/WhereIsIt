# WhereIsIt

WhereIsIt 是一个自托管的家庭物品管理系统，支持房屋/房间定位、分类标签、图片上传、用户权限管理，以及 GUI 可调用的数据库与图片备份恢复 API。

## 技术栈

- 后端：FastAPI + SQLAlchemy
- 数据库：PostgreSQL 16
- 前端：Jinja2 + 原生 JavaScript
- 部署：Docker Compose

## 当前能力（2026-04-16）

- 物品、位置、分类、标签、用户管理
- 登录鉴权（Cookie + Bearer Token）
- 健康检查：`GET /api/health`
- GUI 备份恢复 API：
  - 任务查询与取消：`/api/tasks*`
  - 数据库备份恢复：`/api/backup/database*`、`/api/restore/database*`
  - 图片备份恢复：`/api/backup/uploads*`、`/api/restore/uploads*`
  - 管理端数据导入导出：`/api/admin/data/*`

## API 返回格式

- 所有 `/api/*` 的 JSON 接口统一返回 envelope：
  - `code`
  - `message`
  - `data`
- 健康检查示例：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "status": "ok"
  }
}
```

## 文档索引

- [API-Envelope接口文档.md](/E:/code/WhereIsIt/docs/API-Envelope接口文档.md)
- [GUI备份恢复API.md](/E:/code/WhereIsIt/docs/GUI备份恢复API.md)
- [内网服务发现技术规范.md](/E:/code/WhereIsIt/docs/内网服务发现技术规范.md)
- [数据字典.md](/E:/code/WhereIsIt/docs/数据字典.md)

## 目录

```text
app/
  routers/            API 路由
  services/           业务服务（含 GUI 任务状态）
  static/             静态资源
  templates/          页面模板
docs/
  API-Envelope接口文档.md
  GUI备份恢复API.md
  内网服务发现技术规范.md
  数据字典.md
Dockerfile
docker-compose.avahi.yml
docker-compose.avahi.self-build.yml
```
