# WhereIsIt API Envelope 接口文档

## 1. 统一返回结构

所有 `application/json` 类型的 `/api/*` 接口统一返回：

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

- `code`
  - `0` 表示成功
  - 非 `0` 表示失败，通常为 HTTP 状态码（如 `400/401/403/404/422/500`）
- `message`
  - 成功通常为 `ok`
  - 失败为可读错误描述
- `data`
  - 成功时为业务数据对象/数组/标量
  - 失败时通常为 `null`，校验错误时为校验详情数组

## 2. 错误返回示例

```json
{
  "code": 404,
  "message": "Not Found",
  "data": null
}
```

422 参数校验失败示例：

```json
{
  "code": 422,
  "message": "Validation Error",
  "data": [
    {
      "loc": ["body", "username"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

## 3. 接口清单（全部按 Envelope 返回）

### 3.1 健康检查

- `GET /api/health`
  - `data`：`{"status":"ok"}`

### 3.2 认证与当前用户

- `POST /api/auth/login`
  - `data`：`{"access_token":"...","token_type":"bearer"}`
- `POST /api/auth/logout`
  - `data`：`{"message":"..."}`（兼容历史 message 输出）
- `GET /api/auth/me`
  - `data`：`UserOut`
- `GET /api/me`
  - `data`：`UserOut`
- `PUT /api/me`
  - `data`：`{"message":"..."}`

### 3.3 管理员用户管理

- `GET /api/admin/users`
  - `data`：`UserOut[]`
- `POST /api/admin/users`
  - `data`：`UserOut`
- `PUT /api/admin/users/{user_id}`
  - `data`：`{"message":"..."}`
- `POST /api/admin/users/{user_id}/enable`
  - `data`：`{"message":"..."}`
- `POST /api/admin/users/{user_id}/disable`
  - `data`：`{"message":"..."}`
- `POST /api/admin/users/{user_id}/reset-password`
  - `data`：`{"message":"..."}`
- `DELETE /api/admin/users/{user_id}`
  - `data`：`{"message":"..."}`

### 3.4 房屋 / 房间 / 分类 / 标签

- `GET /api/houses` -> `data: HouseOut[]`
- `POST /api/houses` -> `data: HouseOut`
- `PUT /api/houses/{house_id}` -> `data: {"message":"..."}`
- `POST /api/houses/{house_id}/enable` -> `data: {"message":"..."}`
- `POST /api/houses/{house_id}/disable` -> `data: {"message":"..."}`
- `DELETE /api/houses/{house_id}` -> `data: {"message":"..."}`

- `GET /api/rooms` -> `data: LocationOut[]`
- `POST /api/rooms` -> `data: LocationOut`
- `PUT /api/rooms/{room_id}` -> `data: {"message":"..."}`
- `POST /api/rooms/{room_id}/enable` -> `data: {"message":"..."}`
- `POST /api/rooms/{room_id}/disable` -> `data: {"message":"..."}`
- `DELETE /api/rooms/{room_id}` -> `data: {"message":"..."}`

- `GET /api/categories` -> `data: CategoryOut[]`
- `POST /api/categories` -> `data: CategoryOut`
- `PUT /api/categories/{category_id}` -> `data: {"message":"..."}`
- `POST /api/categories/{category_id}/enable` -> `data: {"message":"..."}`
- `POST /api/categories/{category_id}/disable` -> `data: {"message":"..."}`
- `DELETE /api/categories/{category_id}` -> `data: {"message":"..."}`

- `GET /api/tags` -> `data: TagOut[]`
- `POST /api/tags` -> `data: TagOut`
- `PUT /api/tags/{tag_id}` -> `data: {"message":"..."}`
- `POST /api/tags/{tag_id}/enable` -> `data: {"message":"..."}`
- `POST /api/tags/{tag_id}/disable` -> `data: {"message":"..."}`
- `DELETE /api/tags/{tag_id}` -> `data: {"message":"..."}`

### 3.5 物品

- `GET /api/items`
  - `data`：`PaginatedItemsOut`
- `POST /api/items`
  - `data`：`ItemOut`
- `PUT /api/items/{item_id}`
  - `data`：`ItemOut`
- `DELETE /api/items/{item_id}`
  - `data`：`{"message":"..."}`
- `DELETE /api/items/{item_id}/images/{image_id}`
  - `data`：`{"message":"..."}`

### 3.6 管理员数据管理（JSON 接口）

- `POST /api/admin/data/import/db` -> `data: {"message":"..."}`
- `POST /api/admin/data/import/db-json` -> `data: {"message":"..."}`
- `GET /api/admin/data/export/images/manifest` -> `data: {"count": number, "files": [...] }`
- `POST /api/admin/data/import/images` -> `data: {"message":"...", "total":..., "saved":..., "skipped":..., "renamed":..., "target_dir":"..."}`

### 3.7 GUI 备份恢复（任务接口）

- `GET /api/tasks` -> `data: {"items":[...]}`
- `GET /api/tasks/{task_id}` -> `data: Task`
- `POST /api/tasks/{task_id}/cancel` -> `data: {"taskId":"...","status":"..."}`

- `POST /api/backup/database` -> `data: {"taskId":"...","status":"queued"}`
- `GET /api/backup/database/{task_id}/metadata` -> `data: {"taskId":"...","fileName":"...","size":...,"sha256":"...","metadata":{}}`
- `POST /api/restore/database/upload` -> `data: {"uploadFileId":"...","fileName":"...","size":...,"sha256":"..."}`
- `POST /api/restore/database` -> `data: {"taskId":"...","status":"queued"}`

- `POST /api/backup/uploads/create-manifest` -> `data: Manifest`
- `GET /api/backup/uploads/manifest/{manifest_id}` -> `data: Manifest`
- `POST /api/restore/uploads/create-task` -> `data: {"taskId":"...","status":"running"}`
- `POST /api/restore/uploads/{task_id}/upload-file` -> `data: {"relativePath":"...","status":"completed|skipped|failed"}`
- `POST /api/restore/uploads/{task_id}/complete` -> `data: {"taskId":"...","summary":{...}}`

## 4. 文件流接口（非 JSON，不走 Envelope）

以下接口返回二进制文件流（`application/octet-stream` 或附件下载），为保证下载能力，不使用 JSON envelope：

- `GET /api/admin/data/export/db`
- `GET /api/admin/data/export/db-json`（附件 JSON 文件下载）
- `GET /api/admin/data/export/images/download`
- `GET /api/backup/database/{task_id}/download`
- `GET /api/backup/uploads/file/{file_id}`
