import html
import json
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}


def clean_text(value):
    if value is None:
        return ""

    value = html.unescape(str(value))
    value = value.replace("\\n", "\n")
    value = value.replace("\\r", "")
    value = value.replace("\\t", " ")
    value = value.replace('\\"', '"')
    value = value.replace("\\/", "/")

    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n[ \t]+", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)

    return value.strip()


def normalize_url(url, source_url=None):
    if not url:
        return ""

    url = html.unescape(str(url))
    url = url.replace("\\/", "/")
    url = url.replace("\\u002F", "/")
    url = url.replace("\\u0026", "&")

    if url.startswith("//"):
        return "https:" + url

    if url.startswith("/"):
        return urljoin(source_url or "https://metruyenchu.co", url)

    if not url.startswith(("http://", "https://")):
        return urljoin(source_url or "https://metruyenchu.co/", url)

    return url


def fetch_html_requests(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


class MTCBrowserSession:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None

    def start(self):
        if self.browser is not None:
            return

        self.playwright = sync_playwright().start()

        try:
            self.browser = self.playwright.chromium.launch(
                channel="chrome",
                headless=True,
            )
        except Exception:
            self.browser = self.playwright.chromium.launch(
                headless=True,
            )

        self.context = self.browser.new_context(
            user_agent=HEADERS["User-Agent"],
            locale="vi-VN",
            viewport={
                "width": 1440,
                "height": 1000,
            },
        )

    def new_page(self):
        if self.context is None:
            self.start()
        return self.context.new_page()

    def close(self):
        try:
            if self.context is not None:
                self.context.close()
        except Exception:
            pass

        try:
            if self.browser is not None:
                self.browser.close()
        except Exception:
            pass

        try:
            if self.playwright is not None:
                self.playwright.stop()
        except Exception:
            pass

        self.context = None
        self.browser = None
        self.playwright = None


def _chapter_link_count(page):
    try:
        return page.locator(
            "a[href*='chuong'], "
            "[data-chapter], "
            "[data-chapter-url], "
            "[data-href*='chuong'], "
            "[data-url*='chuong']"
        ).count()
    except Exception:
        return 0


def _chapter_text_count(page):
    try:
        return page.locator("text=/Chương\\s+\\d+/i").count()
    except Exception:
        return 0


def _find_show_all_controls(page):
    """Return clickable elements/ancestors whose visible text is exactly 'Xem tất cả'."""
    try:
        return page.locator(
            "a:has-text('Xem tất cả'), "
            "button:has-text('Xem tất cả'), "
            "[role='button']:has-text('Xem tất cả')"
        )
    except Exception:
        return None


def click_show_all(page):
    """Force MTC to expand/load the complete chapter list before parsing HTML."""
    before_links = _chapter_link_count(page)
    before_text = _chapter_text_count(page)

    # First, inspect the actual clickable element. If MTC exposes a real href,
    # opening that href is more reliable than simulating a click in headless mode.
    try:
        info = page.evaluate(
            """
            () => {
                const norm = s => (s || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                const all = Array.from(document.querySelectorAll('a,button,[role="button"]'));
                const el = all.find(x => norm(x.innerText || x.textContent) === 'xem tất cả');
                if (!el) return null;
                return {
                    tag: el.tagName,
                    href: el.href || '',
                    text: (el.innerText || el.textContent || '').trim()
                };
            }
            """
        )
    except Exception:
        info = None

    # If it is a real link, navigate to it directly.
    if info and info.get("href"):
        href = normalize_url(info["href"], page.url)
        if href and href != page.url:
            try:
                page.goto(href, wait_until="domcontentloaded", timeout=60000)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except PlaywrightTimeoutError:
                    pass
                page.wait_for_timeout(1500)
            except Exception:
                pass

    # Main path: click the actual <a>/<button>, not an arbitrary child <span>.
    controls = _find_show_all_controls(page)
    if controls is not None:
        try:
            count = controls.count()
        except Exception:
            count = 0

        for i in range(count):
            control = controls.nth(i)
            try:
                if not control.is_visible():
                    continue
                control.scroll_into_view_if_needed(timeout=5000)
                page.wait_for_timeout(300)
                control.click(force=True, timeout=10000)
                page.wait_for_timeout(1000)
                break
            except Exception:
                continue

    # Fallback: find the text node and click its nearest clickable ancestor.
    try:
        clicked = page.evaluate(
            """
            () => {
                const norm = s => (s || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                const nodes = Array.from(document.querySelectorAll('*'));
                const textNode = nodes.find(el => norm(el.innerText || el.textContent) === 'xem tất cả');
                if (!textNode) return false;

                let target = textNode;
                for (let i = 0; i < 5 && target; i++, target = target.parentElement) {
                    const tag = (target.tagName || '').toLowerCase();
                    if (tag === 'a' || tag === 'button' || target.getAttribute('role') === 'button') {
                        target.scrollIntoView({block: 'center'});
                        target.click();
                        return true;
                    }
                }

                textNode.scrollIntoView({block: 'center'});
                textNode.click();
                return true;
            }
            """
        )
        if clicked:
            page.wait_for_timeout(1500)
    except Exception:
        pass

    # Some MTC versions insert the complete list asynchronously. Wait for the
    # DOM to grow instead of immediately taking page.content().
    for _ in range(30):
        current_links = _chapter_link_count(page)
        current_text = _chapter_text_count(page)

        if current_links > before_links or current_text > before_text:
            # Keep waiting briefly because the list can be appended in batches.
            page.wait_for_timeout(500)
            continue

        page.wait_for_timeout(500)

    # One final scroll can trigger lazy rendering inside a scrollable chapter box.
    try:
        page.evaluate(
            """
            () => {
                window.scrollTo(0, document.body.scrollHeight);
                for (const el of document.querySelectorAll('*')) {
                    const cs = getComputedStyle(el);
                    if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll') &&
                        el.scrollHeight > el.clientHeight) {
                        el.scrollTop = el.scrollHeight;
                    }
                }
            }
            """
        )
    except Exception:
        pass

    page.wait_for_timeout(2000)

    return {
        "before_links": before_links,
        "after_links": _chapter_link_count(page),
        "before_text": before_text,
        "after_text": _chapter_text_count(page),
    }

def fetch_rendered_html(url, browser_session=None):
    own_session = browser_session is None
    session = browser_session or MTCBrowserSession()

    try:
        if own_session:
            session.start()

        page = session.new_page()

        try:
            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            try:
                page.wait_for_load_state(
                    "networkidle",
                    timeout=20000,
                )
            except PlaywrightTimeoutError:
                pass

            page.wait_for_timeout(1500)
            click_show_all(page)

            try:
                page.wait_for_load_state(
                    "networkidle",
                    timeout=10000,
                )
            except PlaywrightTimeoutError:
                pass

            page.wait_for_timeout(1000)
            return page.content()
        finally:
            page.close()
    finally:
        if own_session:
            session.close()


def fetch_html(url, browser_session=None):
    # Prefer the browser-rendered DOM. The raw HTTP response from MTC only
    # contains the newest few chapters before the JS chapter list is opened.
    # The previous 10,000-character check could silently throw away a valid
    # rendered page and fall back to that incomplete HTTP response.
    try:
        rendered = fetch_rendered_html(
            url,
            browser_session=browser_session,
        )

        if rendered and len(rendered) > 2000:
            return rendered
    except Exception:
        pass

    return fetch_html_requests(url)


def extract_chapter_number(value):
    if value is None:
        return None

    text = clean_text(value)

    patterns = [
        r"(?:chương|chuong)\s*0*(\d+)",
        r"/chuong[-/](\d+)",
        r"\b(\d+)\b",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass

    return None


def chapter_from_href(href, text="", source_url=""):
    href = normalize_url(href, source_url)

    if not href:
        return None

    parsed = urlparse(href)
    path = parsed.path.rstrip("/")

    match = re.search(
        r"/chuong[-/](\d+)(?:[-/].*)?$",
        path,
        re.IGNORECASE,
    )

    if not match:
        match = re.search(
            r"(?:^|/)chuong[-/](\d+)(?:[-/].*)?",
            path,
            re.IGNORECASE,
        )

    number = None

    if match:
        number = int(match.group(1))

    if number is None:
        number = extract_chapter_number(text)

    if number is None:
        return None

    name = clean_text(text)

    if not name:
        name = f"Chương {number}"

    if not re.search(r"(?:chương|chuong)", name, re.IGNORECASE):
        name = f"Chương {number}: {name}"

    return {
        "number": number,
        "name": name,
        "url": href,
        "slug": path.split("/")[-1],
        "slug_id": path.split("/")[-1],
    }


def extract_chapters_from_links(page_html, source_url):
    soup = BeautifulSoup(page_html, "html.parser")

    chapters = {}

    for link in soup.find_all("a"):
        href = (
            link.get("href")
            or link.get("data-href")
            or link.get("data-url")
            or ""
        )

        text = link.get_text(
            " ",
            strip=True,
        )

        item = chapter_from_href(
            href,
            text,
            source_url,
        )

        if item is None:
            continue

        number = item["number"]

        if number not in chapters:
            chapters[number] = item

    return chapters


def extract_chapters_from_data_attributes(page_html, source_url):
    soup = BeautifulSoup(page_html, "html.parser")

    chapters = {}

    attributes = [
        "data-href",
        "data-url",
        "data-link",
        "data-slug",
        "data-chapter",
        "data-chapter-url",
    ]

    for element in soup.find_all(True):
        values = []

        for attribute in attributes:
            value = element.get(attribute)

            if value:
                values.append(value)

        for value in values:
            value = str(value)

            if "chuong" not in value.lower():
                continue

            item = chapter_from_href(
                value,
                element.get_text(
                    " ",
                    strip=True,
                ),
                source_url,
            )

            if item is None:
                continue

            chapters[item["number"]] = item

    return chapters


def decode_embedded_text(value):
    if not isinstance(value, str):
        return value

    result = value

    for _ in range(8):
        previous = result

        result = html.unescape(result)
        result = result.replace("\\/", "/")
        result = result.replace("\\u002F", "/")
        result = result.replace("\\u0026", "&")
        result = result.replace('\\"', '"')
        result = result.replace("\\'", "'")

        try:
            decoded = json.loads(result)

            if isinstance(decoded, str):
                result = decoded
        except Exception:
            pass

        if result == previous:
            break

    return result


def extract_chapters_from_embedded_data(page_html, source_url):
    chapters = {}

    decoded = decode_embedded_text(page_html)

    patterns = [
        re.compile(
            r'"slugId"\s*:\s*"([^"]+)"'
            r'.{0,2500}?'
            r'"number"\s*:\s*(\d+)'
            r'.{0,2500}?'
            r'"name"\s*:\s*"([^"]+)"',
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r'"number"\s*:\s*(\d+)'
            r'.{0,2500}?'
            r'"slugId"\s*:\s*"([^"]+)"'
            r'.{0,2500}?'
            r'"name"\s*:\s*"([^"]+)"',
            re.IGNORECASE | re.DOTALL,
        ),
    ]

    for pattern in patterns:
        for match in pattern.finditer(decoded):
            groups = match.groups()

            if len(groups) != 3:
                continue

            first, second, third = groups

            if first.isdigit():
                number = int(first)
                slug = second
                name = third
            else:
                slug = first
                number = int(second)
                name = third

            if number < 1:
                continue

            if number > 1000000:
                continue

            slug = clean_text(slug)
            name = clean_text(name)

            if not slug:
                continue

            if not name:
                name = f"Chương {number}"

            if not re.search(
                r"(?:chương|chuong)",
                name,
                re.IGNORECASE,
            ):
                name = f"Chương {number}: {name}"

            chapter_url = normalize_url(
                f"/truyen/{urlparse(source_url).path.strip('/').split('/')[-1]}/{slug}",
                source_url,
            )

            chapters[number] = {
                "number": number,
                "name": name,
                "url": chapter_url,
                "slug": slug,
                "slug_id": slug,
            }

    return chapters


def extract_chapters_from_number_slug_pairs(page_html, source_url):
    chapters = {}

    decoded = decode_embedded_text(page_html)

    number_matches = list(
        re.finditer(
            r'(?:"|\\")number(?:"|\\")\s*:\s*(\d+)',
            decoded,
            re.IGNORECASE,
        )
    )

    for number_match in number_matches:
        number = int(number_match.group(1))

        if number < 1 or number > 1000000:
            continue

        start = max(
            0,
            number_match.start() - 3000,
        )

        end = min(
            len(decoded),
            number_match.end() + 3000,
        )

        area = decoded[start:end]

        slug_matches = re.findall(
            r'(?:"|\\")slugId(?:"|\\")\s*:\s*(?:"|\\")([^"\\]+)',
            area,
            re.IGNORECASE,
        )

        if not slug_matches:
            continue

        slug = slug_matches[-1].strip()

        if not slug:
            continue

        name_matches = re.findall(
            r'(?:"|\\")name(?:"|\\")\s*:\s*(?:"|\\")([^"\\]+)',
            area,
            re.IGNORECASE,
        )

        name = name_matches[-1].strip() if name_matches else f"Chương {number}"

        if not re.search(
            r"(?:chương|chuong)",
            name,
            re.IGNORECASE,
        ):
            name = f"Chương {number}: {name}"

        path_parts = urlparse(source_url).path.strip("/").split("/")

        if len(path_parts) >= 2:
            novel_slug = path_parts[-1]
        else:
            novel_slug = ""

        chapter_url = normalize_url(
            f"/truyen/{novel_slug}/{slug}",
            source_url,
        )

        chapters[number] = {
            "number": number,
            "name": clean_text(name),
            "url": chapter_url,
            "slug": slug,
            "slug_id": slug,
        }

    return chapters


def extract_json_chapters(page_html, source_url):
    chapters = {}

    for extractor in (
        extract_chapters_from_embedded_data,
        extract_chapters_from_number_slug_pairs,
    ):
        try:
            found = extractor(
                page_html,
                source_url,
            )

            for number, item in found.items():
                chapters[number] = item
        except Exception:
            continue

    return chapters


def fetch_mtc_chapters(source_url, browser_session=None):
    page_html = fetch_html(source_url, browser_session=browser_session)

    chapters = {}

    link_chapters = extract_chapters_from_links(
        page_html,
        source_url,
    )

    chapters.update(link_chapters)

    data_attribute_chapters = extract_chapters_from_data_attributes(
        page_html,
        source_url,
    )

    chapters.update(data_attribute_chapters)

    embedded_chapters = extract_json_chapters(
        page_html,
        source_url,
    )

    for number, item in embedded_chapters.items():
        if number not in chapters:
            chapters[number] = item
        else:
            current = chapters[number]

            if not current.get("slug") and item.get("slug"):
                current["slug"] = item["slug"]

            if not current.get("url") and item.get("url"):
                current["url"] = item["url"]

            if (
                current.get("name", "").startswith("Chương ")
                and item.get("name")
            ):
                current["name"] = item["name"]

    result = []

    for number in sorted(chapters):
        item = chapters[number]

        item["number"] = int(number)
        item["name"] = clean_text(
            item.get("name") or f"Chương {number}"
        )
        item["url"] = normalize_url(
            item.get("url"),
            source_url,
        )

        result.append(item)

    return result


def extract_title(soup):
    selectors = [
        "h1",
        "[class*='title']",
        "meta[property='og:title']",
        "meta[name='title']",
    ]

    for selector in selectors:
        element = soup.select_one(selector)

        if not element:
            continue

        if element.name == "meta":
            value = element.get("content")
        else:
            value = element.get_text(
                " ",
                strip=True,
            )

        value = clean_text(value)

        if value:
            return value

    return ""


def extract_author(soup):
    selectors = [
        "[class*='author']",
        "meta[name='author']",
        "meta[property='book:author']",
    ]

    for selector in selectors:
        element = soup.select_one(selector)

        if not element:
            continue

        if element.name == "meta":
            value = element.get("content")
        else:
            value = element.get_text(
                " ",
                strip=True,
            )

        value = clean_text(value)

        if value:
            return value

    return ""


def extract_description(soup):
    selectors = [
        "meta[name='description']",
        "meta[property='og:description']",
        "[class*='description']",
        "[class*='intro']",
    ]

    for selector in selectors:
        element = soup.select_one(selector)

        if not element:
            continue

        if element.name == "meta":
            value = element.get("content")
        else:
            value = element.get_text(
                "\n",
                strip=True,
            )

        value = clean_text(value)

        if value:
            return value

    return ""


def extract_cover(soup, source_url):
    selectors = [
        "meta[property='og:image']",
        "meta[name='twitter:image']",
        "img",
    ]

    for selector in selectors:
        element = soup.select_one(selector)

        if not element:
            continue

        if element.name == "meta":
            value = element.get("content")
        else:
            value = (
                element.get("src")
                or element.get("data-src")
                or element.get("data-lazy-src")
            )

        value = normalize_url(
            value,
            source_url,
        )

        if value:
            return value

    return ""


def extract_categories(soup):
    categories = []

    for element in soup.select(
        "a[href*='/the-loai/'], "
        "a[href*='/the-loai'], "
        "[class*='category'] a, "
        "[class*='tag'] a"
    ):
        name = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if not name:
            continue

        if name not in categories:
            categories.append(name)

    return categories


def fetch_mtc_novel(source_url, browser_session=None):
    page_html = fetch_html(source_url, browser_session=browser_session)

    soup = BeautifulSoup(
        page_html,
        "html.parser",
    )

    title = extract_title(soup)
    author = extract_author(soup)
    description = extract_description(soup)
    cover = extract_cover(
        soup,
        source_url,
    )
    categories = extract_categories(soup)

    return {
        "title": title,
        "author": author,
        "description": description,
        "cover": cover,
        "categories": categories,
        "source_url": source_url,
    }


def extract_chapter_content_from_html(page_html):
    soup = BeautifulSoup(
        page_html,
        "html.parser",
    )

    selectors = [
        "article",
        "[class*='chapter-content']",
        "[class*='chapter-content'] div",
        "[class*='content-text']",
        "[class*='reading-content']",
        "[class*='chapter']",
        "main",
    ]

    candidates = []

    for selector in selectors:
        for element in soup.select(selector):
            text = element.get_text(
                "\n",
                strip=True,
            )

            if len(text) >= 100:
                candidates.append(
                    (
                        len(text),
                        element,
                    )
                )

    if not candidates:
        return ""

    candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    element = candidates[0][1]

    for unwanted in element.select(
        "script, style, nav, button, header, footer"
    ):
        unwanted.decompose()

    text = element.get_text(
        "\n",
        strip=True,
    )

    lines = []

    for line in text.splitlines():
        line = clean_text(line)

        if not line:
            continue

        lines.append(line)

    return "\n\n".join(lines).strip()


def fetch_mtc_chapter(chapter_url, browser_session=None):
    if not chapter_url:
        return {
            "title": "",
            "content": "",
        }

    try:
        page_html = fetch_html_requests(chapter_url)

        content = extract_chapter_content_from_html(page_html)

        if len(content) >= 100:
            soup = BeautifulSoup(page_html, "html.parser")
            title = extract_title(soup)
            return {
                "title": title,
                "content": content,
            }
    except Exception:
        pass

    try:
        page_html = fetch_rendered_html(
            chapter_url,
            browser_session=browser_session,
        )

        content = extract_chapter_content_from_html(page_html)
        soup = BeautifulSoup(page_html, "html.parser")
        title = extract_title(soup)

        return {
            "title": title,
            "content": content,
        }
    except Exception:
        return {
            "title": "",
            "content": "",
        }

