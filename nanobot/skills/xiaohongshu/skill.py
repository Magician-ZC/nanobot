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


async def search(keyword: str, limit: int = 10) -> str:
    """搜索小红书笔记。

    Args:
        keyword: 搜索关键词
        limit: 返回结果数量，默认 10

    Returns:
        JSON 格式的搜索结果列表
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        # 如果有 cookie 就用，提高搜索成功率
        if COOKIE_PATH.exists():
            state = json.loads(COOKIE_PATH.read_text(encoding="utf-8"))
            context = await browser.new_context(storage_state=state)

        page = await context.new_page()

        try:
            search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_search_result_notes"
            await page.goto(search_url, timeout=30_000)
            await page.wait_for_timeout(3000)

            # 等待笔记卡片加载
            await page.wait_for_selector(".note-item, .search-result-item, section", timeout=15_000)
            await page.wait_for_timeout(2000)

            # 提取笔记信息
            results = await page.evaluate(f"""
                () => {{
                    const items = document.querySelectorAll(
                        '.note-item, section.note-item, [data-v-a264b01a], a.cover'
                    );
                    const results = [];
                    const seen = new Set();
                    for (const item of items) {{
                        if (results.length >= {limit}) break;
                        const link = item.closest('a') || item.querySelector('a');
                        const href = link ? link.href : '';
                        if (!href || seen.has(href)) continue;
                        seen.add(href);

                        // 尝试多种选择器获取标题和作者
                        const titleEl = item.querySelector('.title, .note-title, .desc, span');
                        const authorEl = item.querySelector('.author, .name, .nickname');
                        const likeEl = item.querySelector('.like-count, .count, .like');

                        results.push({{
                            title: titleEl ? titleEl.innerText.trim() : '',
                            author: authorEl ? authorEl.innerText.trim() : '',
                            likes: likeEl ? likeEl.innerText.trim() : '',
                            url: href,
                        }});
                    }}
                    return results;
                }}
            """)

            if not results:
                # 备用方案：直接获取所有链接
                results = await page.evaluate(f"""
                    () => {{
                        const links = document.querySelectorAll('a[href*="/explore/"], a[href*="/discovery/item/"]');
                        const results = [];
                        const seen = new Set();
                        for (const a of links) {{
                            if (results.length >= {limit}) break;
                            const href = a.href;
                            if (seen.has(href)) continue;
                            seen.add(href);
                            results.push({{
                                title: a.innerText.trim().substring(0, 100) || '无标题',
                                url: href,
                            }});
                        }}
                        return results;
                    }}
                """)

            return json.dumps(results, ensure_ascii=False, indent=2)

        except Exception as e:
            return f"搜索失败: {e}"
        finally:
            await browser.close()


async def get_note(url: str) -> str:
    """获取单篇小红书笔记的详细内容。

    Args:
        url: 笔记 URL

    Returns:
        笔记标题、作者、正文、点赞数等信息
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        if COOKIE_PATH.exists():
            state = json.loads(COOKIE_PATH.read_text(encoding="utf-8"))
            context = await browser.new_context(storage_state=state)

        page = await context.new_page()

        try:
            await page.goto(url, timeout=30_000)
            await page.wait_for_timeout(3000)

            note = await page.evaluate("""
                () => {
                    const title = document.querySelector('#detail-title, .title, h1');
                    const content = document.querySelector('#detail-desc, .desc, .content, .note-text');
                    const author = document.querySelector('.author .name, .username, .user-name');
                    const likes = document.querySelector('.like-count, .like .count, [data-type="like"]');
                    const comments = document.querySelector('.comment-count, [data-type="comment"]');
                    const collects = document.querySelector('.collect-count, [data-type="collect"]');
                    const date = document.querySelector('.date, .publish-date, time');

                    return {
                        title: title ? title.innerText.trim() : '',
                        content: content ? content.innerText.trim() : '',
                        author: author ? author.innerText.trim() : '',
                        likes: likes ? likes.innerText.trim() : '',
                        comments: comments ? comments.innerText.trim() : '',
                        collects: collects ? collects.innerText.trim() : '',
                        date: date ? date.innerText.trim() : '',
                    };
                }
            """)

            return json.dumps(note, ensure_ascii=False, indent=2)

        except Exception as e:
            return f"获取笔记失败: {e}"
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


def search_sync(keyword: str, limit: int = 10) -> str:
    return asyncio.run(search(keyword, limit))


def get_note_sync(url: str) -> str:
    return asyncio.run(get_note(url))


if __name__ == "__main__":
    print(login_sync())
