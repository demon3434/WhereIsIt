# WhereIsIt API Envelope 接口文档

## 1. 统一返回结构

所有 `/api/*` 的 `application/json` 接口统一返回：

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

字段说明：
- `code`
  - `0` 表示成功
  - 非 `0` 通常为 HTTP 状态码，例如 `400/401/403/404/422/500`
- `message`
  - 成功通常为 `ok`
  - 失败时为可读错误描述
- `data`
  - 成功时为业务数据对象、数组或标量
  - 失败时通常为 `null`
  - 参数校验失败时通常为校验详情数组

## 2. 错误返回示例

404 示例：

```json
{
  "code": 404,
  "message": "Not Found",
  "data": null
}
```

422 示例：

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

## 3. 适用范围

按 Envelope 返回的接口包括：
- 认证与当前用户：`/api/auth/*`、`/api/me`
- 房屋、房间、分类、标签、物品、用户管理：`/api/houses`、`/api/rooms`、`/api/categories`、`/api/tags`、`/api/items`、`/api/admin/users`
- 健康检查：`GET /api/health`
- 管理端数据管理：`/api/admin/data/*`
- GUI 备份恢复任务接口：`/api/tasks*`、`/api/backup/*`、`/api/restore/*`
- 语音搜索最终识别接口：`POST /api/voice-search/finalize`、`POST /api/voice-search/final`

## 4. 不走 Envelope 的接口

以下接口不返回 JSON Envelope：

### 4.1 文件下载接口

这些接口返回文件流或附件下载：
- `GET /api/admin/data/export/db`
- `GET /api/admin/data/export/db-json`
- `GET /api/admin/data/export/images/download`
- `GET /api/backup/database/{task_id}/download`
- `GET /api/backup/uploads/file/{file_id}`

### 4.2 WebSocket 接口

这些接口返回 WebSocket 消息帧，不走 HTTP Envelope：
- `WS /api/voice-search/stream`

当前语音流式消息类型包括：
- `session`
- `partial`
- `finalizing`
- `limit_reached`
- `error`

## 5. 典型接口示例

### 5.1 健康检查

- `GET /api/health`

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "status": "ok"
  }
}
```

### 5.2 登录

- `POST /api/auth/login`

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

### 5.3 物品列表

- `GET /api/items`

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [],
    "total": 0,
    "page": 1,
    "page_size": 20,
    "total_pages": 0
  }
}
```

### 5.4 语音搜索最终识别

- `POST /api/voice-search/finalize`

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "session_id": "vs_xxx",
    "first_stage_text": "罗技鼠标",
    "final_text": "罗技鼠标",
    "normalized_query": "罗技 鼠标",
    "keywords": ["罗技", "鼠标"],
    "items": [],
    "timing": {
      "offline_asr_ms": 320,
      "search_ms": 18
    },
    "debug": {
      "asr_mode": "funasr",
      "audio_format": "pcm_s16le",
      "audio_duration_ms": 1800
    }
  }
}
```
