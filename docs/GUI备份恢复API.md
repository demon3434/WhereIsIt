# GUI 备份恢复 API（当前在线）

更新时间：2026-04-16  
适用版本：`demon3434/where_is_it:20260416`

## 1. 基础信息

- Base URL：`http://<host>:3000`
- 健康检查：`GET /api/health`
- 认证方式：先登录拿 token，再用 `Authorization: Bearer <token>`
- 登录接口：`POST /api/auth/login`

登录返回示例（envelope）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "access_token": "xxx",
    "token_type": "bearer"
  }
}
```

## 2. 通用返回格式

GUI 备份恢复接口统一返回 envelope：

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

## 3. 任务接口

1. `GET /api/tasks`：任务列表  
2. `GET /api/tasks/{taskId}`：任务详情  
3. `POST /api/tasks/{taskId}/cancel`：请求取消任务

说明：
- `taskType` 常见值：`db_backup`、`db_restore`、`uploads_restore`
- 任务状态存储在进程内存；服务重启后任务状态会清空

## 4. 数据库备份/恢复（GUI）

1. 创建数据库备份任务  
`POST /api/backup/database`

请求体示例：

```json
{
  "format": "custom",
  "dbName": ""
}
```

2. 下载备份文件  
`GET /api/backup/database/{taskId}/download`

3. 查询备份元数据  
`GET /api/backup/database/{taskId}/metadata`

4. 上传待恢复数据库文件  
`POST /api/restore/database/upload`（`multipart/form-data`，字段名 `file`）

5. 创建恢复任务  
`POST /api/restore/database`

请求体示例：

```json
{
  "uploadFileId": "dbupload_xxx",
  "targetDbName": "",
  "restoreMode": "drop_and_restore",
  "confirmText": "CONFIRM RESTORE"
}
```

数据库恢复说明：
- `.sql` 文件走 `psql`
- 其他（如 `.dump`）走 `pg_restore`
- 服务端会先检查 `pg_dump/pg_restore/psql` 主版本是否与目标数据库主版本一致，不一致会返回 `DB_BACKUP_FAILED` 或 `DB_RESTORE_FAILED`

## 5. 图片备份/恢复（GUI）

1. 创建图片清单  
`POST /api/backup/uploads/create-manifest`

请求体示例：

```json
{
  "scope": "images",
  "incremental": false,
  "modifiedAfter": null
}
```

说明：
- `modifiedAfter` 支持 `null`
- 清单里含 `manifestId`、`files[]`、`sha256`、`downloadUrl`

2. 获取清单  
`GET /api/backup/uploads/manifest/{manifestId}`

3. 下载单文件  
`GET /api/backup/uploads/file/{fileId}`

4. 创建图片恢复任务  
`POST /api/restore/uploads/create-task`

请求体示例：

```json
{
  "scope": "images",
  "overwriteMode": "skip_if_exists",
  "fileCount": 10,
  "totalBytes": 123456
}
```

5. 上传恢复文件  
`POST /api/restore/uploads/{taskId}/upload-file`（`multipart/form-data`）

字段：
- `relativePath`
- `sha256`（可空）
- `size`（可为 0）
- `file`

6. 完成恢复任务  
`POST /api/restore/uploads/{taskId}/complete`

## 6. 管理端数据导入导出接口

1. 数据库导出（dump）：`GET /api/admin/data/export/db`
2. 数据库导入（dump/sql）：`POST /api/admin/data/import/db`
3. 数据库导出（json）：`GET /api/admin/data/export/db-json`
4. 数据库导入（json）：`POST /api/admin/data/import/db-json`
5. 图片清单导出：`GET /api/admin/data/export/images/manifest`
6. 单图下载：`GET /api/admin/data/export/images/download?path=...`
7. 图片导入：`POST /api/admin/data/import/images`

## 7. C# 客户端调用要点

1. 先调 `/api/auth/login`，从 `data.access_token` 取 token  
2. 所有 GUI 接口都带 `Authorization: Bearer <token>`  
3. `modifiedAfter` 可传 `null`  
4. 恢复数据库时若报版本不匹配，请用与数据库同主版本的 `pg_dump` 重新导出备份文件  

