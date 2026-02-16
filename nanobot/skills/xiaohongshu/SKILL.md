---
name: xiaohongshu
description: "小红书自动化：登录、搜索笔记、获取笔记详情、发布笔记。当用户提到小红书、红书、XHS时必须使用此skill。"
metadata: {"nanobot":{"emoji":"📕","always":true,"requires":{"python":["playwright"]},"install":[{"id":"pip","kind":"pip","packages":["playwright"],"label":"Install Playwright (pip)"}]}}
---

# 小红书 Skill

> **重要**：当用户提到"小红书"、"红书"、"XHS"、"笔记搜索"等关键词时，必须使用本 skill。
> **禁止**修改 `browser/skill.py` 来实现小红书功能。所有小红书相关代码都在 `nanobot/skills/xiaohongshu/skill.py` 中。

## 使用方法

所有函数都在 `nanobot/skills/xiaohongshu/skill.py` 中，通过 exec 工具调用 Python 代码执行。

### 1. 登录（所有操作前必须先登录）

```python
# 通过 exec 工具执行：
python3 -c "
import asyncio
from nanobot.skills.xiaohongshu.skill import login
result = asyncio.run(login())
print(result)
"
```

登录流程：
1. headless 浏览器打开小红书登录页
2. 截图二维码保存到 `~/.nanobot/xhs_qr.png`
3. **你必须立即用 MEDIA 标记把二维码发给用户**：`MEDIA:~/.nanobot/xhs_qr.png`
4. 函数内部轮询等待扫码成功（最多 120 秒）
5. 扫码成功后 cookie 自动保存到 `~/.nanobot/xhs_cookies.json`

### 2. 搜索笔记（需要先登录）

```python
python3 -c "
import asyncio
from nanobot.skills.xiaohongshu.skill import search
result = asyncio.run(search('关键词', limit=10))
print(result)
"
```

### 3. 获取笔记详情

```python
python3 -c "
import asyncio
from nanobot.skills.xiaohongshu.skill import get_note
result = asyncio.run(get_note('https://www.xiaohongshu.com/explore/xxxxx'))
print(result)
"
```

### 4. 发布图文笔记（需要登录）

```python
python3 -c "
import asyncio
from nanobot.skills.xiaohongshu.skill import publish
result = asyncio.run(publish('标题', '正文内容', ['/path/to/image.png'], draft=False))
print(result)
"
```

## 注意事项

- Cookie 保存在 `~/.nanobot/xhs_cookies.json`，过期需重新登录
- 搜索需要登录，未登录会返回错误提示
- 标题最多 20 字符，超出自动截断
- 发布笔记时浏览器以非 headless 模式打开（需要桌面环境）
