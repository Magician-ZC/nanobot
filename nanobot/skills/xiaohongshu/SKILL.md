---
name: xiaohongshu
description: "小红书自动化：搜索笔记、获取笔记内容、登录、发布图文笔记、保存草稿。基于 Playwright 浏览器自动化。"
metadata: {"nanobot":{"emoji":"📕","requires":{"python":["playwright"]},"install":[{"id":"pip","kind":"pip","packages":["playwright"],"label":"Install Playwright (pip)"}]}}
---

# 小红书 Skill

使用 Playwright 自动化操作小红书，支持搜索笔记、获取笔记详情、登录创作者平台、发布图文笔记。

## 依赖

```bash
pip install playwright
playwright install chromium
```

## 使用方式

所有操作通过 `exec` 工具执行 Python 代码，调用 `nanobot/skills/xiaohongshu/skill.py` 中的函数。

### 1. 搜索笔记

```python
from nanobot.skills.xiaohongshu.skill import search_sync
results = search_sync("Python 学习", limit=10)
print(results)
```

返回 JSON 列表，包含标题、作者、点赞数、链接。

### 2. 获取笔记详情

```python
from nanobot.skills.xiaohongshu.skill import get_note_sync
note = get_note_sync("https://www.xiaohongshu.com/explore/xxxxx")
print(note)
```

返回笔记的标题、正文、作者、点赞/评论/收藏数等。

### 3. 登录（首次使用需要扫码）

```python
from nanobot.skills.xiaohongshu.skill import login_sync
result = login_sync()
print(result)
```

登录后 cookie 保存到 `~/.nanobot/xhs_cookies.json`，后续操作自动复用。
搜索和获取笔记不需要登录也能用，但登录后成功率更高。

### 4. 发布图文笔记

```python
from nanobot.skills.xiaohongshu.skill import publish_sync

result = publish_sync(
    title="今日分享",
    content="这是笔记正文内容，支持多行文本。",
    images=["/path/to/image1.png", "/path/to/image2.jpg"],
    draft=False  # True=保存草稿, False=直接发布
)
print(result)
```

### 5. 保存为草稿

```python
from nanobot.skills.xiaohongshu.skill import publish_sync

result = publish_sync(
    title="草稿标题",
    content="草稿内容",
    images=["/path/to/image.png"],
    draft=True
)
print(result)
```

## 注意事项

- 搜索和获取笔记无需登录，但登录后反爬成功率更高
- 标题不能超过 20 个字符，超出会自动截断
- 首次登录需要手动扫码，之后 cookie 自动保存复用
- 发布时浏览器以非 headless 模式打开（需要桌面环境）
- 图片支持 jpg/png/webp 格式
