"""
小红书创作者平台 Skill - 基于 Playwright 浏览器自动化
"""
import asyncio
import json
import os
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright

# Cookie 存储路径
COOKIE_PATH = Path.home() / ".nanobot" / "xhs_cookies.json"
CREATOR_URL = "https://creator.xiaohongshu.com"
LOGIN_URL = f"{CREATOR_URL}/login"
MAX_TITLE_LEN = 20


async def login() -> str:
    """登录小红书创作者平台（扫码登录），保存 cookie。"""
    COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(LOGIN_URL)
            print("请扫描二维码登录，等待最多 5 分钟...")

            # 等待登录成功（出现"发布笔记"按钮或跳转到首页）
            try:
                await page.get_by_text("发布笔记", exact=True).or_(
                    page.locator(".publish-btn")
                ).first.wait_for(state="visible", timeout=300_000)
            except Exception:
                await page.wait_for_url("**/creator/home**", timeout=30_000)

            # 保存 cookie
            state = await context.storage_state()
            COOKIE_PATH.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            return f"登录成功，cookie 已保存到 {COOKIE_PATH}"
        finally:
            await browser.close()


async def publish(
    title: str,
    content: str,
    images: list[str],
    draft: bool = False,
) -> str:
    """发布图文笔记或保存草稿。

    Args:
        title: 笔记标题（最多 20 字符，超出自动截断）
        content: 笔记正文
        images: 图片文件路径列表
        draft: True=保存草稿, False=直接发布
    """
    if not COOKIE_PATH.exists():
        return "未登录，请先调用 login() 扫码登录。"

    # 校验图片
    for img in images:
        if not Path(img).is_file():
            return f"图片不存在: {img}"

    # 标题截断
    if len(title) > MAX_TITLE_LEN:
        title = title[:MAX_TITLE_LEN]
        print(f"标题已截断为 {MAX_TITLE_LEN} 字符: {title}")

    state = json.loads(COOKIE_PATH.read_text(encoding="utf-8"))

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state=state)
        page = await context.new_page()

        try:
            await page.goto(f"{CREATOR_URL}/creator/home")
            await page.wait_for_timeout(2000)

            # 点击"发布笔记"
            publish_btn = page.get_by_text("发布笔记", exact=True).or_(
                page.locator(".publish-btn")
            )
            await publish_btn.first.click()
            await page.wait_for_timeout(2000)

            # 点击"上传图文"
            upload_btn = page.get_by_text("上传图文").first
            await upload_btn.wait_for(state="visible")
            await upload_btn.click()
            await page.wait_for_timeout(3000)

            # 上传图片
            file_input = page.locator('input[type="file"]').first
            await file_input.wait_for(state="attached", timeout=10_000)
            await file_input.set_input_files(images)
            await page.wait_for_timeout(3000)

            # 填写标题
            title_input = page.locator('#title-input, [placeholder*="标题"]').first
            await title_input.wait_for(state="visible", timeout=10_000)
            await title_input.click()
            await title_input.fill(title)

            # 填写正文
            content_input = page.locator('#post-content, .ql-editor, [contenteditable="true"]').first
            await content_input.wait_for(state="visible", timeout=10_000)
            await content_input.click()
            await content_input.fill(content)
            await page.wait_for_timeout(2000)

            if draft:
                # 保存草稿
                save_btn = (
                    page.get_by_text("暂存离开", exact=True)
                    .or_(page.get_by_text("保存草稿"))
                    .or_(page.get_by_text("存草稿"))
                )
                await save_btn.first.click()
                await page.wait_for_timeout(3000)
                return "草稿已保存。"
            else:
                # 直接发布
                pub_btn = page.get_by_text("发布", exact=True).or_(
                    page.locator('button:has-text("发布")')
                )
                await pub_btn.first.click()
                await page.wait_for_timeout(5000)
                return "笔记已发布。"

        except Exception as e:
            return f"操作失败: {e}"
        finally:
            await browser.close()


# 同步封装
def login_sync() -> str:
    return asyncio.run(login())


def publish_sync(
    title: str,
    content: str,
    images: list[str],
    draft: bool = False,
) -> str:
    return asyncio.run(publish(title, content, images, draft))


if __name__ == "__main__":
    print(login_sync())
