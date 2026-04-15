# GUI 备份恢复 API（已下线）

更新时间：2026-04-16

## 当前状态

当前代码版本已移除 GUI 备份恢复能力，不再提供以下接口族：

- `/api/tasks*`
- `/api/backup/*`
- `/api/restore/*`
- `/api/admin/data/*`

对接方若继续调用上述接口，服务端将返回 `404 Not Found`。

## 代码层面的变更

以下实现已从仓库删除：

- `app/routers/gui_backup.py`
- `app/services/gui_backup.py`
- `app/routers/data_management.py`
- `app/templates/partials/_tab_data.html`
- `app/static/js/app-page-data.js`

`app/main.py` 也已移除对应 `include_router(...)` 注册。

## 仍可用的基础接口（用于连通性/登录）

- `GET /api/health`：健康检查，返回 `{ "status": "ok" }`
- `POST /api/auth/login`：登录，返回 envelope（`code/message/data`）
- `POST /api/auth/logout`：登出
- `GET /api/me`：获取当前用户信息

## 备份建议（当前版本）

由于 GUI 备份恢复接口已下线，建议使用运维层方案：

1. PostgreSQL：使用 `pg_dump/pg_restore` 进行数据库备份恢复。
2. 上传文件：直接备份 `data/uploads` 挂载目录。
