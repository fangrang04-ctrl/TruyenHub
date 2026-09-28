import html
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://truyenchu.com.vn/",
}


def clean_text(value):
    if value is None:
        return ""
    value = html.unescape(str(value))
    value = value.replace("\\n", "\n")
    value = value.replace("\\r", "")
    value = value.replace("\\t", " ")
    value = value.replace("\\/", "/")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n[ \t]+", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def normalize_url(url, source_url="https://truyenchu.com.vn/"):
    if not url:
        return ""
    url = html.unescape(str(url)).strip()
    url = url.replace("\\/", "/")
    if url.startswith("//"):
        return "https:" + url
    return urljoin(source_url, url)


def fetch_html(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=45,
        allow_redirects=True,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def extract_meta(soup, selectors):
    for selector in selectors:
        element = soup.select_one(selector)
        if not element:
            continue
        value = element.get("content") if element.name == "meta" else element.get_text(" ", strip=True)
        value = clean_text(value)
        if value:
            return value
    return ""


def extract_labeled_value(soup, labels):
    wanted = {label.lower() for label in labels}
    for element in soup.find_all(["li", "div", "p", "span", "dt", "dd"]):
        text = clean_text(element.get_text(" ", strip=True))
        if not text:
            continue
        lowered = text.lower()
        for label in wanted:
            if lowered.startswith(label):
                value = re.sub(r"^" + re.escape(label) + r"\s*[:：-]?\s*", "", text, flags=re.IGNORECASE)
                value = clean_text(value)
                if value:
                    return value
    return ""


def extract_title(soup):
    value = extract_meta(soup, ["meta[property='og:title']", "meta[name='twitter:title']", "h1"])
    if value:
        value = re.sub(r"\s*[|｜-]\s*TruyenChu.*$", "", value, flags=re.IGNORECASE)
        return clean_text(value)
    title = clean_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    return re.sub(r"\s*[|｜-]\s*TruyenChu.*$", "", title, flags=re.IGNORECASE).strip()


def extract_author(soup):
    value = extract_labeled_value(soup, ["tác giả", "tac gia", "author"])
    if value:
        return value
    for selector in ["a[href*='/tac-gia/']", "a[href*='/truyen-tac-gia/']", "[class*='author'] a", "[class*='author']"]:
        element = soup.select_one(selector)
        if element:
            value = clean_text(element.get_text(" ", strip=True))
            if value and value.lower() not in {"tác giả", "author"}:
                return value
    return ""


def extract_categories(soup):
    categories = []
    selectors = [
        "a[href*='/the-loai/']",
        "a[href*='/the-loai']",
        "a[href*='/the-loai-truyen/']",
        "[class*='category'] a",
        "[class*='genre'] a",
        "[class*='tag'] a",
    ]
    for selector in selectors:
        for element in soup.select(selector):
            name = clean_text(element.get_text(" ", strip=True))
            if name and name.lower() not in {"thể loại", "the loai"} and name not in categories:
                categories.append(name)
    if not categories:
        value = extract_labeled_value(soup, ["thể loại", "the loai", "genre"])
        if value:
            categories = [clean_text(item) for item in re.split(r"[,|]", value) if clean_text(item)]
    return categories


def extract_description(soup):
    value = extract_meta(soup, ["meta[name='description']", "meta[property='og:description']"])
    if value and len(value) > 80:
        return value
    candidates = []
    for selector in ["[class*='description']", "[class*='gioi-thieu']", "[class*='intro']", "[class*='content-intro']", "article"]:
        for element in soup.select(selector):
            text = clean_text(element.get_text("\n", strip=True))
            text = re.sub(r"^Giới thiệu truyện\s*", "", text, flags=re.IGNORECASE)
            if len(text) >= 80:
                candidates.append(text)
    if candidates:
        return max(candidates, key=len)
    return value


def extract_cover(soup, source_url):
    selectors = [
        "meta[property='og:image']",
        "meta[name='twitter:image']",
        "img[src]",
        "img[data-src]",
        "img[data-lazy-src]",
    ]
    for selector in selectors:
        element = soup.select_one(selector)
        if not element:
            continue
        value = element.get("content") or element.get("src") or element.get("data-src") or element.get("data-lazy-src")
        value = normalize_url(value, source_url)
        if value:
            return value
    return ""


def chapter_number(value):
    text = clean_text(value)
    patterns = [
        r"(?:chương|chuong)\s*0*(\d+)",
        r"(?:chapter)\s*0*(\d+)",
        r"(?:^|[/_-])0*(\d+)(?:[/_.-]|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            number = int(match.group(1))
            if 1 <= number <= 1000000:
                return number
    return None


def chapter_item(href, text, source_url):
    href = normalize_url(href, source_url)
    if not href:
        return None
    parsed = urlparse(href)
    path = parsed.path.rstrip("/")
    lower = path.lower()
    if not any(token in lower for token in ["chuong", "chapter", "/truyen/"]):
        return None
    number = chapter_number(text) or chapter_number(path)
    if number is None:
        return None
    name = clean_text(text) or f"Chương {number}"
    if len(name) > 250:
        name = f"Chương {number}"
    if not re.search(r"(?:chương|chuong|chapter)", name, re.IGNORECASE):
        name = f"Chương {number}: {name}"
    return {
        "number": number,
        "name": name,
        "url": href,
        "slug": path.split("/")[-1],
        "slug_id": path.split("/")[-1],
    }


def extract_chapters(page_html, source_url):
    soup = BeautifulSoup(page_html, "html.parser")
    chapters = {}
    for link in soup.find_all("a"):
        href = link.get("href") or link.get("data-href") or link.get("data-url") or link.get("data-link") or ""
        text = link.get_text(" ", strip=True)
        item = chapter_item(href, text, source_url)
        if item:
            chapters.setdefault(item["number"], item)
    for element in soup.find_all(True):
        for attr in ["data-href", "data-url", "data-link", "data-chapter-url", "data-chapter"]:
            value = element.get(attr)
            if not value:
                continue
            item = chapter_item(value, element.get_text(" ", strip=True), source_url)
            if item:
                chapters.setdefault(item["number"], item)
    return sorted(chapters.values(), key=lambda item: item["number"])


def fetch_truyenchu_novel(source_url):
    page_html, final_url = fetch_html(source_url)
    soup = BeautifulSoup(page_html, "html.parser")
    return {
        "title": extract_title(soup),
        "author": extract_author(soup),
        "description": extract_description(soup),
        "cover": extract_cover(soup, final_url),
        "categories": extract_categories(soup),
        "source_url": source_url,
    }


def fetch_truyenchu_chapters(source_url):
    page_html, final_url = fetch_html(source_url)
    chapters = extract_chapters(page_html, final_url)
    if not chapters:
        raise ValueError("Không tìm thấy danh sách chương trên TruyenChu.")
    return chapters


def extract_chapter_content(page_html):
    soup = BeautifulSoup(page_html, "html.parser")
    for unwanted in soup.select("script, style, nav, header, footer, aside, form, button"):
        unwanted.decompose()
    selectors = [
        "article",
        "[class*='chapter-content']",
        "[class*='chapter_content']",
        "[class*='content-chapter']",
        "[class*='reading-content']",
        "[class*='reading_content']",
        "[class*='content']",
        "main",
    ]
    candidates = []
    for selector in selectors:
        for element in soup.select(selector):
            text = clean_text(element.get_text("\n", strip=True))
            if len(text) >= 200:
                candidates.append((len(text), text))
    if not candidates:
        return ""
    text = max(candidates, key=lambda item: item[0])[1]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n\n".join(lines).strip()


def fetch_truyenchu_chapter(chapter_url, number=None):
    page_html, final_url = fetch_html(chapter_url)
    soup = BeautifulSoup(page_html, "html.parser")
    title = extract_title(soup)
    if not title and number:
        title = f"Chương {number}"
    content = extract_chapter_content(page_html)
    if len(content) < 50:
        raise ValueError(f"Không lấy được nội dung chương: {chapter_url}")
    return {
        "number": number or chapter_number(title) or chapter_number(final_url),
        "title": title or f"Chương {number or 0}",
        "content": content,
        "url": final_url,
    }
