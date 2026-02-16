# Browser

## Description

使用 Playwright 控制浏览器，执行自动化任务和截图。

## Structure

- `skill.py` - 技能实现（使用 Playwright）

## Requirements

```bash
# 安装 Playwright
pip install playwright

# 安装浏览器
playwright install chromium
```

## Functions

### screenshot

截取指定网页的截图。

**参数：**
- `url` (str): 目标网页 URL
- `path` (str, optional): 保存截图的路径，默认 `~/Downloads/screenshot.png`

**示例：**
```python
screenshot("https://jms.jtexpress.com.cn/login", "~/Downloads/login.png")
```

### browse

浏览网页并返回页面内容。

**参数：**
- `url` (str): 目标网页 URL

**示例：**
```python
browse("https://example.com")
```
