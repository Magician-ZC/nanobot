"""
小红书 Skill - 基于 Playwright 浏览器自动化
支持：登录（截图二维码）、搜索笔记、获取笔记详情、发布笔记
"""
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright, Browser, BrowserContext

# 路径配置
COOKIE_DIR = Path.home() / ".nanobot"
XHS_COOKIE_PATH = COOKIE_DIR / "xhs_cookies.json"
QR_SCREENSHOT_PATH = COOKIE_DIR / "xhs_qr.png"
MAX_TITLE_LEN = 20
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _ensure_dir():
    COOKIE_DIR.mkdir(parents=True, exist_ok=True)


def _save_cookies(state: dict):
    _ensure_dir()
    XHS_COOKIE_PATH.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def _load_cookies() -> dict | None:
    if XHS_COOKIE_PATH.exists():
        return json.loads(XHS_COOKIE_PATH.read_text(encoding="utf-8"))
    return None


async def _make_context(browser: Browser) -> BrowserContext:
    """创建上下文，有 cookie 就加载"""
    cookies = _load_cookies()
    if cookies:
        return await browser.new_context(storage_state=cookies, user_agent=UA)
    return await browser.new_context(user_agent=UA)


# ============================================================
# 登录：headless 截图二维码 → 发给用户扫码 → 轮询等待
# ============================================================

async def login(timeout: int = 120) -> str:
    """登录小红书（www.xiaohongshu.com）。

    流程：headless 打开登录页 → 截图二维码 → 返回截图路径（用 MEDIA 标记发送）
    → 后台轮询等待扫码成功 → 保存 cookie

    Returns:
        包含二维码截图路径的结果字符串
    """
    _ensure_dir()
    qr_path = str(QR_SCREENSHOT_PATH)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=UA)
        page = await context.new_page()

        try:
            await page.goto("https://www.xiaohongshu.com", timeout=30_000)
            await page.wait_for_timeout(2000)

            # 点击登录按钮触发二维码弹窗
            try:
                login_btn = page.get_by_text("登录", exact=True).first
                await login_btn.click()
                await page.wait_for_timeout(2000)
            except Exception:
                pass

            # 截图整个页面（包含二维码）
            await page.screenshot(path=qr_path, full_page=False)

            # 轮询等待登录成功
            poll_count = timeout // 3
            for i in range(poll_count):
                await page.wait_for_timeout(3000)

                # 检测登录成功的标志：页面上不再有登录弹窗，或出现用户头像
                logged_in = await page.evaluate("""
                    () => {
                        // 如果有用户头像或"我"的入口，说明已登录
                        const avatar = document.querySelector('.user-avatar, .side-bar .avatar, img[class*="avatar"]');
                        const me = document.querySelector('a[href*="/user/profile"]');
                        // 登录弹窗消失
                        const loginModal = document.querySelector('.login-container, .qrcode-img');
                        return (avatar || me) && !loginModal;
                    }
                """)

                if logged_in:
                    state = await context.storage_state()
                    _save_cookies(state)
                    return "登录成功！cookie 已保存。"

                # 每 30 秒重新截图（二维码可能刷新）
                if i > 0 and i % 10 == 0:
                    await page.screenshot(path=qr_path, full_page=False)

            return f"等待超时（{timeout}秒），请重试。"

        finally:
            await browser.close()


# ============================================================
# 搜索笔记（需要登录）
# ============================================================

async def search(keyword: str, limit: int = 10) -> str:
    """搜索小红书笔记（需要先登录）。

    Args:
        keyword: 搜索关键词
        limit: 返回结果数量，默认 10

    Returns:
        JSON 格式的搜索结果
    """
    if not _load_cookies():
        return json.dumps({"error": "未登录，请先调用 login() 并扫码登录"}, ensure_ascii=False)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await _make_context(browser)
        page = await context.new_page()

        try:
            url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_search_result_notes"
            await page.goto(url, timeout=30_000)
            await page.wait_for_timeout(5000)

            # 检查是否仍需登录
            need_login = await page.evaluate("""
                () => {
                    const text = document.body.innerText;
                    return text.includes('登录后查看搜索结果') || text.includes('登录后查看');
                }
            """)
            if need_login:
                return json.dumps({"error": "cookie 已过期，请重新调用 login() 登录"}, ensure_ascii=False)

            # 等待内容加载
            await page.wait_for_timeout(3000)

            results = await page.evaluate("""
                (limit) => {
                    const results = [];
                    const seen = new Set();

                    // 获取所有笔记卡片的链接
                    const links = document.querySelectorAll('a[href*="/explore/"], a[href*="/discovery/item/"], a[href*="/search_result/"]');
                    for (const a of links) {
                        if (results.length >= limit) break;
                        const href = a.href;
                        if (seen.has(href)) continue;
                        seen.add(href);

                        // 从卡片中提取信息
                        const card = a.closest('section') || a.closest('[class*="note"]') || a;
                        const spans = card.querySelectorAll('span');
                        let title = '', author = '', likes = '';

                        for (const span of spans) {
                            const text = span.innerText.trim();
                            if (!text) continue;
                            if (span.className.includes('title') || span.className.includes('desc')) {
                                title = text;
                            } else if (span.className.includes('name') || span.className.includes('author')) {
                                author = text;
                            } else if (span.className.includes('count') || span.className.includes('like')) {
                                likes = text;
                            }
                        }

                        if (!title) {
                            // 取卡片内第一段有意义的文本作为标题
                            const allText = card.innerText.trim().split('\\n').filter(t => t.length > 2);
                            title = allText[0] || '';
                        }

                        if (title) {
                            results.push({ title, author, likes, url: href });
                        }
                    }
                    return results;
                }
            """, limit)

            return json.dumps(results, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        finally:
            await browser.close()


# ============================================================
# 获取单篇笔记详情
# ============================================================

async def get_note(url: str) -> str:
    """获取单篇小红书笔记的详细内容。"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await _make_context(browser)
        page = await context.new_page()

        try:
            await page.goto(url, timeout=30_000)
            await page.wait_for_timeout(5000)

            note = await page.evaluate("""
                () => {
                    const q = (sel) => {
                        const el = document.querySelector(sel);
                        return el ? el.innerText.trim() : '';
                    };
                    return {
                        title: q('#detail-title') || q('.title') || q('h1'),
                        content: q('#detail-desc') || q('.desc') || q('.content'),
                        author: q('.author .name') || q('.username'),
                        likes: q('.like-count') || q('[data-type="like"] .count'),
                        comments: q('.comment-count') || q('[data-type="comment"] .count'),
                        collects: q('.collect-count') || q('[data-type="collect"] .count'),
                        date: q('.date') || q('time'),
                        url: window.location.href,
                    };
                }
            """)
            return json.dumps(note, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        finally:
            await browser.close()


# ============================================================
# 发布笔记（需要登录创作者平台）
# ============================================================

async def publish(title: str, content: str, images: list[str], draft: bool = False) -> str:
    """发布图文笔记或保存草稿。"""
    if not _load_cookies():
        return "未登录，请先调用 login() 扫码登录。"

    for img in images:
        if not Path(img).is_file():
            return f"图片不存在: {img}"

    if len(title) > MAX_TITLE_LEN:
        title = title[:MAX_TITLE_LEN]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await _make_context(browser)
        page = await context.new_page()

        try:
            await page.goto("https://creator.xiaohongshu.com/creator/home")
            await page.wait_for_timeout(2000)

            await page.get_by_text("发布笔记", exact=True).or_(
                page.locator(".publish-btn")
            ).first.click()
            await page.wait_for_timeout(2000)

            await page.get_by_text("上传图文").first.click()
            await page.wait_for_timeout(3000)

            file_input = page.locator('input[type="file"]').first
            await file_input.wait_for(state="attached", timeout=10_000)
            await file_input.set_input_files(images)
            await page.wait_for_timeout(3000)

            title_input = page.locator('#title-input, [placeholder*="标题"]').first
            await title_input.click()
            await title_input.fill(title)

            content_input = page.locator('#post-content, .ql-editor, [contenteditable="true"]').first
            await content_input.click()
            await content_input.fill(content)
            await page.wait_for_timeout(2000)

            if draft:
                await page.get_by_text("暂存离开", exact=True).or_(
                    page.get_by_text("保存草稿")
                ).first.click()
                await page.wait_for_timeout(3000)
                return "草稿已保存。"
            else:
                await page.get_by_text("发布", exact=True).first.click()
                await page.wait_for_timeout(5000)
                return "笔记已发布。"

        except Exception as e:
            return f"操作失败: {e}"
        finally:
            await browser.close()


# ============================================================
# 同步封装
# ============================================================

def login_sync(timeout: int = 120) -> str:
    return asyncio.run(login(timeout))

def search_sync(keyword: str, limit: int = 10) -> str:
    return asyncio.run(search(keyword, limit))

def get_note_sync(url: str) -> str:
    return asyncio.run(get_note(url))

def publish_sync(title: str, content: str, images: list[str], draft: bool = False) -> str:
    return asyncio.run(publish(title, content, images, draft))


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(search_sync(sys.argv[1]))
    else:
        print("用法: python skill.py <搜索关键词>")
