---
name: xiaohongshu
description: "小红书自动化：搜索笔记、获取笔记详情、登录、发布笔记。所有操作需要先登录。"
metadata: {"nanobot":{"emoji":"📕","requires":{"python":["playwright"]},"install":[{"id":"pip","kind":"pip","packages":["playwright"],"label":"Install Playwright (pip)"}]}}
---

# 小红书 Skill

使用 Playwright 自动化操作小红书。搜索、获取笔记、发布都需要先登录。

## 依赖

```bash
pip install playwright
playwright install chromium
```

## 重要：所有操作前必须先登录

小红书搜索和查看笔记都需要登录。登录流程：
1. 调用 `login_sync()` → headless 浏览器打开登录页，截图保存到 `~/.nanobot/xhs_qr.png`
2. 用 MEDIA 标记把二维码截图发给用户
3. 函数内部会轮询等待扫码成功（最多 120 秒）
4. 扫码成功后 cookie 自动保存，后续操作复用

### 登录示例

```python
from nanobot.skills.xiaohongshu.skill import login_sync
result = login_sync(timeout=120)
print(result)
# 登录成功前，二维码截图在 ~/.nanobot/xhs_qr.png
# 用 MEDIA 标记发送: MEDIA:~/.nanobot/xhs_qr.png
```

**agent 使用流程：**
1. 执行 `login_sync()` 开始登录
2. 立即用 `MEDIA:~/.nanobot/xhs_qr.png` 把二维码发给用户
3. 等待函数返回（用户扫码后自动完成）

### 搜索笔记

```python
from nanobot.skills.xiaohongshu.skill import search_sync
results = search_sync("Python 学习", limit=10)
print(results)
```

### 获取笔记详情

```python
from nanobot.skills.xiaohongshu.skill import get_note_sync
note = get_note_sync("https://www.xiaohongshu.com/explore/xxxxx")
print(note)
```

### 发布图文笔记

```python
from nanobot.skills.xiaohongshu.skill import publish_sync
result = publish_sync(
    title="今日分享",
    content="笔记正文内容",
    images=["/path/to/image.png"],
    draft=False  # True=草稿
)
print(result)
```

## 注意事项

- 所有操作都需要先登录（搜索也需要）
- 登录使用 headless 模式，二维码通过截图发送
- Cookie 保存在 `~/.nanobot/xhs_cookies.json`，过期需重新登录
- 标题最多 20 字符，超出自动截断
- 发布笔记时浏览器以非 headless 模式打开
