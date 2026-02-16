---
name: xiaohongshu
description: "小红书自动化（基于 xhs-mcp）：登录、搜索笔记、获取详情、点赞收藏评论、发布内容。当用户提到小红书、红书、XHS时使用此skill。"
metadata: {"nanobot":{"emoji":"📕","always":true}}
---

# 小红书 Skill（xhs-mcp）

> **重要**：当用户提到"小红书"、"登录小红书"、"搜索小红书"等关键词时，**必须调用 mcp_xhs_ 开头的工具**，禁止自己编造回复。
> **禁止**使用 exec 工具或 browser skill 来操作小红书，必须使用 MCP 工具。

## 登录流程（最常用）

当用户说"登录小红书"时，按以下步骤操作：

1. 调用工具 `mcp_xhs_xhs_add_account`，参数 `{"name": "默认账号"}`
2. 工具会返回 sessionId 和二维码 URL（qrCodeUrl）
3. 把二维码 URL 发给用户，让用户用小红书 APP 扫码
4. 用户扫码后，调用 `mcp_xhs_xhs_check_login_session`，参数 `{"sessionId": "上一步返回的sessionId"}`
5. 如果需要短信验证，调用 `mcp_xhs_xhs_submit_verification`

## 搜索笔记

调用 `mcp_xhs_xhs_search`，参数 `{"keyword": "搜索词"}`

## 获取笔记详情

调用 `mcp_xhs_xhs_get_note`，参数 `{"noteId": "xxx", "xsecToken": "yyy"}`
（noteId 和 xsecToken 从搜索结果中获取）

## 互动

- 点赞：`mcp_xhs_xhs_like_feed`
- 收藏：`mcp_xhs_xhs_favorite_feed`
- 评论：`mcp_xhs_xhs_post_comment`

## 发布

- 图文：`mcp_xhs_xhs_publish_content`
- 视频：`mcp_xhs_xhs_publish_video`
