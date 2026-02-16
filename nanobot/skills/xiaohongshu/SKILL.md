---
name: xiaohongshu
description: "小红书创作者平台自动化：登录、发布图文笔记、保存草稿。基于 Playwright 浏览器自动化。"
metadata: {"nanobot":{"emoji":"📕","requires":{"python":["playwright"]},"install":[{"id":"pip","kind":"pip","packages":["playwright"],"label":"Install Playwright (pip)"}]}}
---

# 小红书创作者平台 Skill

使用 Playwright 自动化操作小红书创作者平台，支持登录、发布图文笔记。

## 依赖

```bash
pip install playwright
playwright install chromium
```

## 使用方式

所有操作通过 `exec` 工具执行 Python 代码，调用 `nanobot/skills/xiaohongshu/skill.py` 中的函数。

### 1. 登录（首次使用需要扫码）

```python
from nanobot.skills.xiaohongshu.skill import login_sync
result = login_sync()
print(result)
```

登录后 cookie 会保存到 `~/.nanobot/xhs_cookies.json`，后续操作自动复用。

### 2. 发布图文笔记

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

### 3. 保存为草稿

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

- 标题不能超过 20 个字符，超出会自动截断
- 首次登录需要手动扫码，之后 cookie 自动保存复用
- 如果 cookie 过期，会提示重新登录
- 发布时浏览器会以非 headless 模式打开（需要桌面环境）
- 图片支持 jpg/png/webp 格式
