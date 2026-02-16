---
name: xiaohongshu
description: "小红书自动化（基于 xhs-mcp）：登录、搜索笔记、获取详情、点赞收藏评论、发布内容。当用户提到小红书、红书、XHS时使用此skill。"
metadata: {"nanobot":{"emoji":"📕","always":true}}
---

# 小红书 Skill（xhs-mcp）

本 skill 通过 MCP 协议连接 `@sillyl12324/xhs-mcp` 服务器实现小红书自动化。

> 所有工具名称以 `mcp_xhs_` 为前缀（nanobot 自动添加）。

## 使用流程

### 1. 添加账号（首次使用需登录）

```
mcp_xhs_xhs_add_account({ "name": "我的账号" })
```

系统返回二维码 URL，用小红书 App 扫码登录。

### 2. 查看已有账号

```
mcp_xhs_xhs_list_accounts()
```

### 3. 搜索笔记

```
mcp_xhs_xhs_search({ "keyword": "美食推荐" })
```

返回结果包含 `noteId` 和 `xsecToken`，后续操作需要用到。

### 4. 获取笔记详情

```
mcp_xhs_xhs_get_note({ "noteId": "xxx", "xsecToken": "yyy" })
```

### 5. 互动操作

- 点赞：`mcp_xhs_xhs_like_feed({ "noteId": "xxx", "xsecToken": "yyy" })`
- 收藏：`mcp_xhs_xhs_favorite_feed({ "noteId": "xxx", "xsecToken": "yyy" })`
- 评论：`mcp_xhs_xhs_post_comment({ "noteId": "xxx", "xsecToken": "yyy", "content": "写得真好！" })`

### 6. 发布图文笔记

```
mcp_xhs_xhs_publish_content({
  "title": "今日分享",
  "content": "笔记正文...",
  "images": ["/path/to/image.jpg"]
})
```

## 数据目录

所有数据存储在 `~/.xhs-mcp/`：
- `data.db` — SQLite 数据库（账号、cookie 等）
- `downloads/` — 下载的图片和视频
- `logs/` — 日志文件
