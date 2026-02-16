"""
Browser Skill - 使用 Playwright 控制浏览器
"""
import asyncio
import os
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright


async def screenshot(url: str, path: Optional[str] = None, agree: bool = True) -> str:
    """
    截取网页截图
    
    Args:
        url: 目标网页 URL
        path: 保存路径，默认 ~/Downloads/screenshot.png
        agree: 是否勾选用户协议，默认 True
    
    Returns:
        截图保存的路径
    """
    if path is None:
        path = os.path.expanduser("~/Downloads/screenshot.png")
    
    # 确保目录存在
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1280, 'height': 800})
        await page.goto(url, timeout=60000)
        await page.wait_for_timeout(3000)
        
        # 尝试勾选用户协议复选框（Element UI 组件）
        if agree:
            try:
                checkboxes = await page.query_selector_all('.el-checkbox')
                if checkboxes:
                    await checkboxes[0].click()
                    print("已勾选用户协议")
            except Exception as e:
                print(f"尝试勾选用户协议时出错: {e}")
        
        await page.screenshot(path=path)
        await browser.close()
    
    return path


async def browse(url: str) -> str:
    """
    浏览网页并返回内容摘要
    
    Args:
        url: 目标网页 URL
    
    Returns:
        网页标题和内容摘要
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url)
        
        title = await page.title()
        
        # 获取主要内容
        content = await page.evaluate("""
            () => {
                const body = document.body;
                return body ? body.innerText.substring(0, 2000) : '';
            }
        """)
        
        await browser.close()
    
    return f"标题: {title}\n\n内容:\n{content[:1000]}..."


# 同步封装，供 agent 调用
def screenshot_sync(url: str, path: Optional[str] = None) -> str:
    """同步版本的截图函数"""
    return asyncio.run(screenshot(url, path))


def browse_sync(url: str) -> str:
    """同步版本的浏览函数"""
    return asyncio.run(browse(url))


if __name__ == "__main__":
    # 测试
    import sys
    if len(sys.argv) > 1:
        url = sys.argv[1]
        print(f"访问: {url}")
        print(browse_sync(url))
    else:
        print("用法: python skill.py <url>")
