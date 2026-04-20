# GUI 备份恢复 API（当前实现）

更新时间：2026-04-21  
适用范围：当前仓库 `app/routers/gui_backup.py` 与 `app/services/db_executor.py`

## 1. 基础信息

- Base URL：`http://<host>:3000`
- 健康检查：`GET /api/health`
- 认证方式：先登录，再携带 `Authorization: Bearer <token>`
- 登录接口：`POST /api/auth/login`
- GUI 备份恢复接口均要求管理员权限（`require_admin`）

登录成功示例：

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

## 2. 通用返回格式（Envelope）

`/api/*` JSON 接口统一返回：

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

说明：

- 业务成功时通常 `code=0`
- `FileResponse`（下载接口）不走 JSON envelope
- 业务失败时，`message` 为错误说明，`data` 可能包含错误详情对象

## 3. 任务接口

### 3.1 查询任务列表

- `GET /api/tasks`

响应示例：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "taskId": "task_20260421120101_abcd1234",
        "taskType": "db_backup",
        "status": "running",
        "stage": "db_backup",
        "createdAt": "2026-04-21T12:01:01Z",
        "startedAt": "2026-04-21T12:01:02Z",
        "finishedAt": null,
        "createdBy": "admin",
        "message": "exporting database",
        "progress": { "percent": 10.0 },
        "errorCode": null,
        "errorMessage": null,
        "metadata": {},
        "cancelRequested": false
      }
    ]
  }
}
```

### 3.2 查询单任务

- `GET /api/tasks/{taskId}`

### 3.3 取消任务

- `POST /api/tasks/{taskId}/cancel`

说明：

- 常见 `taskType`：`db_backup`、`db_restore`、`uploads_restore`
- 任务状态保存在进程内存，服务重启后会清空

## 4. 数据库备份/恢复（GUI）

### 4.1 备份前置检查（推荐先调）

- `POST /api/backup/database/preflight`

请求示例：

```json
{
  "dbName": ""
}
```

响应 `data` 字段：

- `serverVersion`：数据库版本文本，如 `16.8`
- `serverVersionNum`：版本号整数，如 `160008`
- `resolvedMajor`：主版本，如 `16`
- `selectedStrategy`：`docker_exec|docker_run_tools|local|null`
- `selectedToolsImage`：选中的工具镜像（可能为空）
- `warnings`：警告列表（如 `UNTESTED_MAJOR_VERSION`）
- `canProceed`：是否可继续
- `blockingReason`：不可继续时原因

### 4.2 创建数据库备份任务

- `POST /api/backup/database`

请求示例：

```json
{
  "format": "custom",
  "dbName": ""
}
```

参数说明：

- `format`：`custom|plain|sql`（`sql` 按 plain 处理）
- `dbName`：可空，空则使用默认库

行为说明：

- 接口内部会先做 preflight
- preflight 不通过时返回 400，错误码为 `PG_BACKUP_PREFLIGHT_FAILED`

成功响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "taskId": "task_xxx",
    "status": "queued"
  }
}
```

### 4.3 下载备份文件

- `GET /api/backup/database/{taskId}/download`
- 返回二进制文件流（`application/octet-stream`）

### 4.4 查询备份文件元数据

- `GET /api/backup/database/{taskId}/metadata`

响应示例：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "taskId": "task_xxx",
    "fileName": "whereisit-db-backup-20260421-120101.dump",
    "size": 123456,
    "sha256": "....",
    "metadata": {}
  }
}
```

### 4.5 上传待恢复数据库文件

- `POST /api/restore/database/upload`
- `multipart/form-data`，字段：`file`

成功响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "uploadFileId": "upload_xxx",
    "fileName": "backup.dump",
    "size": 123456,
    "sha256": "...."
  }
}
```

### 4.6 恢复前置检查（推荐先调）

- `POST /api/restore/database/preflight`

请求示例：

```json
{
  "targetDbName": ""
}
```

返回字段与备份 preflight 一致。

### 4.7 创建数据库恢复任务

- `POST /api/restore/database`

请求示例：

```json
{
  "uploadFileId": "upload_xxx",
  "targetDbName": "",
  "restoreMode": "drop_and_restore",
  "confirmText": "CONFIRM RESTORE"
}
```

参数说明：

- `uploadFileId`：必填
- `targetDbName`：可空，空则默认库
- `restoreMode`：当前实现主要使用 `drop_and_restore`
- `confirmText`：当 `restoreMode=drop_and_restore` 时必须为 `CONFIRM RESTORE`

行为说明：

- `.sql` 走 `psql`
- 其他（如 `.dump`）走 `pg_restore`
- 接口内部会先做 preflight
- preflight 不通过时返回 400，错误码为 `PG_RESTORE_PREFLIGHT_FAILED`

### 4.8 数据库工具版本策略（当前实现）

GUI 备份/恢复接口中，即使 `PG_EXEC_MODE=auto`，也只按顺序选择：

1. `docker_exec`：在 PostgreSQL 容器内执行工具
2. `docker_run_tools`：按主版本拉工具镜像执行

说明：

- GUI 链路已禁用 `local` 回退；前两种策略都不可用时会直接失败并返回 preflight 阻断原因
- GUI 客户端不需要自带 `pg_dump/pg_restore/psql`

### 4.9 常见数据库错误码

- `PG_SERVER_VERSION_DETECT_FAILED`
- `PG_BACKUP_PREFLIGHT_FAILED`
- `PG_RESTORE_PREFLIGHT_FAILED`
- `PG_TOOLS_IMAGE_NOT_FOUND`
- `PG_DUMP_FAILED`
- `PG_RESTORE_FAILED`

## 5. 上传目录（图片）备份/恢复（GUI）

### 5.1 创建上传清单

- `POST /api/backup/uploads/create-manifest`

请求示例：

```json
{
  "scope": "images",
  "incremental": false,
  "modifiedAfter": null
}
```

说明：

- `modifiedAfter` 支持 `null` 或 ISO 时间
- 返回包含 `manifestId`、`fileCount`、`totalBytes`、`files[]`

### 5.2 获取清单

- `GET /api/backup/uploads/manifest/{manifestId}`

### 5.3 下载单文件

- `GET /api/backup/uploads/file/{fileId}`

### 5.4 创建上传恢复任务

- `POST /api/restore/uploads/create-task`

请求示例：

```json
{
  "scope": "images",
  "overwriteMode": "skip_if_exists",
  "fileCount": 10,
  "totalBytes": 123456
}
```

`overwriteMode` 可选：

- `skip_if_exists`
- `overwrite_if_exists`
- `overwrite_if_newer`（当前接口无远端 modifiedAt，行为接近 overwrite）

### 5.5 上传恢复文件

- `POST /api/restore/uploads/{taskId}/upload-file`
- `multipart/form-data` 字段：
- `relativePath`（必填）
- `sha256`（可空）
- `size`（可为 0）
- `file`（必填）

返回 `data.status`：

- `completed`
- `skipped`
- `failed`（校验失败）

### 5.6 完成上传恢复任务

- `POST /api/restore/uploads/{taskId}/complete`

成功后返回 `summary`（`completed/skipped/failed/uploadedBytes`）。

## 6. 建议调用顺序（GUI）

数据库备份：

1. `POST /api/backup/database/preflight`
2. `POST /api/backup/database`
3. 轮询 `GET /api/tasks/{taskId}`
4. 成功后 `GET /api/backup/database/{taskId}/download`

数据库恢复：

1. `POST /api/restore/database/upload`
2. `POST /api/restore/database/preflight`
3. `POST /api/restore/database`
4. 轮询 `GET /api/tasks/{taskId}`

上传目录恢复：

1. `POST /api/restore/uploads/create-task`
2. 多次调用 `POST /api/restore/uploads/{taskId}/upload-file`
3. `POST /api/restore/uploads/{taskId}/complete`
