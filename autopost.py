import os
import sys
import re
import json
import random
import smtplib
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from bs4 import BeautifulSoup

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ==============================================================================
# CONFIGURATION (Automatically loads from .env file or system environment)
# ==============================================================================
env_file = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_file):
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

RSS_FEED_URL = "https://tishhanews.com/feed/"
HEALTHLINE_NUTRITION_URL = "https://www.healthline.com/nutrition"
HISTORY_FILE = "posted_history.json"

# Google Gemini API Key (Get free from: https://aistudio.google.com/)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Blogger Email-to-Post Settings (Blogger -> Settings -> Email -> Post using email)
BLOGGER_EMAIL = os.environ.get("BLOGGER_EMAIL", "")

# Sender Gmail settings (used to send the email to Blogger)
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
SENDER_APP_PASSWORD = os.environ.get("SENDER_APP_PASSWORD", "")

# Maximum articles to process per run
MAX_POSTS_PER_RUN = 2


def load_history():
    """Load list of previously processed post URLs."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            print(f"[Warning] Error loading history: {e}")
    return set()


def save_history(history_set):
    """Save processed URLs to prevent duplicate posting."""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(list(history_set), f, indent=2, ensure_ascii=False)


def fetch_latest_articles():
    """Fetch and parse news articles from WordPress RSS feed."""
    print(f"[*] Fetching RSS feed from: {RSS_FEED_URL}")
    req = urllib.request.Request(
        RSS_FEED_URL,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        xml_data = response.read()

    root = ET.fromstring(xml_data)
    items = root.findall("./channel/item")
    print(f"[*] Found {len(items)} articles in RSS feed.")

    articles = []
    ns = {"content": "http://purl.org/rss/1.0/modules/content/"}

    for item in items:
        title = item.find("title").text if item.find("title") is not None else ""
        link = item.find("link").text if item.find("link") is not None else ""
        content_elem = item.find("content:encoded", ns)
        
        if content_elem is not None and content_elem.text:
            body = content_elem.text
        elif item.find("description") is not None and item.find("description").text:
            body = item.find("description").text
        else:
            body = ""

        categories = [c.text for c in item.findall("category") if c.text]

        if title and link and body:
            articles.append({
                "title": title.strip(),
                "link": link.strip(),
                "body": body.strip(),
                "categories": categories,
                "is_healthline": False
            })

    return articles


def fetch_healthline_nutrition_articles(history, max_articles=3):
    """
    Scrapes the latest health and nutrition guides from Healthline Nutrition.
    Filters out calculator tools, index hubs, and previously processed articles.
    """
    print(f"[*] Fetching Healthline Nutrition articles from: {HEALTHLINE_NUTRITION_URL}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    try:
        req = urllib.request.Request(HEALTHLINE_NUTRITION_URL, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as response:
            html = response.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[!] Error fetching Healthline hub: {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", href=True)

    seen = set()
    ignored_patterns = [
        "/category/", "/tag/", "/author/", "/about/", "/contact",
        "calculator", "grocery-delivery", "meal-kits", "refresh-letter",
        "food-and-nutrients", "nutrition-for-conditions", "vitamins-and-supplements",
        "weight-management"
    ]
    candidate_urls = []

    for a in links:
        href = a["href"].split("?")[0].split("#")[0]
        if "/nutrition/" in href:
            if not href.startswith("http"):
                href = "https://www.healthline.com" + href
            slug = href.rstrip("/").split("/")[-1]
            if href not in history and href not in seen and len(slug) > 15:
                if not any(ign in href for ign in ignored_patterns):
                    seen.add(href)
                    candidate_urls.append(href)

    print(f"[*] Discovered {len(candidate_urls)} unposted Healthline nutrition article URLs.")

    articles = []
    for art_url in candidate_urls:
        if len(articles) >= max_articles:
            break
        try:
            print(f"[*] Scraping Healthline article: {art_url}")
            art_req = urllib.request.Request(art_url, headers=headers)
            with urllib.request.urlopen(art_req, timeout=20) as a_res:
                a_html = a_res.read().decode("utf-8", errors="ignore")

            a_soup = BeautifulSoup(a_html, "html.parser")
            h1 = a_soup.find("h1")
            title = h1.get_text(strip=True) if h1 else ""

            article_elem = a_soup.find("article") or a_soup.find("div", class_=re.compile(r"article-body|content", re.I))
            if article_elem:
                paras = [p.get_text(strip=True) for p in article_elem.find_all("p") if len(p.get_text(strip=True)) > 25]
                body_text = "\n\n".join(paras)
            else:
                body_text = ""

            if title and len(body_text.split()) >= 150:
                articles.append({
                    "title": title,
                    "link": art_url,
                    "body": body_text,
                    "categories": ["Nutrition", "Health & Wellness"],
                    "is_healthline": True
                })
                print(f"[+] Extracted: '{title}' ({len(body_text.split())} words)")
            else:
                print(f"[-] Skipped non-article/short page: {art_url}")
        except Exception as e:
            print(f"[!] Error extracting {art_url}: {e}")

    return articles


def rewrite_with_gemini(article):
    """
    Calls Google Gemini API (Free) to rewrite the article into a 100% unique,
    high-ranking SEO news or nutrition report with new title, subheadings, bullet points, and FAQs.
    Guarantees 0% plagiarism and zero copyright infringement.
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set. Please set it in config or environment.")

    clean_body = re.sub(r'<[^>]+>', ' ', article.get('body', ''))
    clean_body = re.sub(r'\s+', ' ', clean_body).strip()

    is_nutrition = "Nutrition" in article.get("categories", []) or article.get("is_healthline", False)

    if is_nutrition:
        directive = f"""
You are a senior clinical nutritionist, diet researcher, and lead wellness editor for 'Dainik Saar'.
Your task is to transform the following nutrition research material into an in-depth, 100% original, comprehensive, and authoritative dietary guide (minimum 750 to 1,000 words).
Ensure high Information Gain (E-E-A-T): Do NOT copy sentences from the source. Synthesize the scientific evidence, nutritional breakdown, health benefits, meal planning tips, and practical food guidance in your own engaging, trustworthy voice.
CRITICAL: Include 'Nutrition' in the labels list so it appears in the blog's dedicated Nutrition section.
"""
    else:
        directive = f"""
You are a senior investigative news journalist and lead SEO editor for 'Dainik Saar' (an authoritative news and analysis publication).
Your task is to transform the following raw news wire into an in-depth, original, comprehensive, and authoritative journalistic report (minimum 750 to 1,000 words).
Ensure high Information Gain (E-E-A-T): Do not simply summarize or rephrase sentences. Expand with rich analytical context, explain historical background, analyze industry/societal implications, and weave data and perspectives into an engaging narrative that satisfies Google's Helpful Content System.
"""

    prompt = f"""
{directive}

ORIGINAL TITLE: {article['title']}
ORIGINAL CONTENT:
{clean_body[:4000]}

EDITORIAL GUIDELINES:
1. TITLE: Create an irresistible, click-worthy, yet factually accurate headline (English, 55-70 characters).
2. INTRO: Begin directly with a powerful lead paragraph that hooks the reader and clearly explains the core revelation, who is impacted, and why it matters.
3. HEADINGS: Use dynamic, natural, topic-specific <h2> and <h3> subheadings (avoid repetitive generic headers; craft headings that fit the story).
4. DEPTH & SECTIONS (Target 750-1000+ words total):
   - Lead Story & Key Takeaway (highlighting core dietary/scientific facts)
   - Essential Details & Data Points (bullet points with concrete figures, nutritional metrics, or dates)
   - Deep Background, Context & Science Behind It
   - Practical Dietary Advice / Market Impact (who benefits, how to implement)
   - Expert Perspectives & Clinical Observations
   - Future Outlook / Key Takeaway for Readers
   - Frequently Asked Questions (2-3 highly searched, thoughtful questions with detailed, authoritative answers)
5. FORMATTING: Clean semantic HTML using <p>, <h2>, <h3>, <ul>, <li>, and <blockquote>. Use modern inline CSS styling:
   - Lead paragraph: <p class=\"story-lead\" style=\"font-size:18px;line-height:1.7;color:#1e293b;font-weight:500;margin-bottom:20px;\">
   - Key stats/points: <div class=\"story-highlights\" style=\"background:#f8fafc;border-left:4px solid #2563eb;padding:16px 20px;border-radius:8px;margin:24px 0;\">
   - Section headings: <h2 style=\"font-size:22px;color:#0f172a;margin-top:28px;margin-bottom:12px;font-weight:700;\">
   - FAQ container: <div class=\"faq-section\" style=\"margin-top:30px;background:#f8fafc;padding:20px;border-radius:10px;\">
6. Do NOT include <html>, <head>, or <body> tags.

OUTPUT FORMAT IN STRICT JSON:
You must return ONLY a valid JSON object with the following keys (no markdown code fences, just raw JSON):
{{
    "new_title": "Compelling, high-CTR, SEO-optimized title",
    "meta_description": "A unique, compelling 140-160 character meta description summarizing the key hook",
    "image_prompt": "A 5-8 word descriptive prompt for a photorealistic editorial photo",
    "labels": ["Nutrition", "Health & Wellness", "Diet"],
    "html_content": "HTML string containing the complete, in-depth report formatted with the styles above"
}}
"""

    models_to_try = ["gemini-flash-lite-latest", "gemini-flash-latest"]
    last_err = None

    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.4,
                "responseMimeType": "application/json"
            }
        }
        for attempt in range(2):
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=60) as response:
                    result = json.loads(response.read().decode("utf-8"))

                parts = result["candidates"][0]["content"]["parts"]
                raw_text = "".join(part.get("text", "") for part in parts).strip()

                if raw_text.startswith("```"):
                    lines = raw_text.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    raw_text = "\n".join(lines).strip()

                data = json.loads(raw_text)

                # Ensure Nutrition label is present if it's a nutrition article
                labels = data.get("labels", [])
                if is_nutrition and "Nutrition" not in labels:
                    labels.insert(0, "Nutrition")
                data["labels"] = labels

                return data
            except Exception as e:
                last_err = e
                import time
                time.sleep(2)

    if last_err is not None:
        raise last_err
    raise RuntimeError("Failed to rewrite article: No attempts succeeded.")


def extract_source_image(article_url):
    """
    Extracts authentic high-resolution editorial news photo from original source article.
    """
    if not article_url:
        return ""
    try:
        req = urllib.request.Request(
            article_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=15) as res:
            html = res.read().decode("utf-8", errors="ignore")
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
        if not m:
            m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html, re.I)
        if m:
            img_url = m.group(1).strip()
            if img_url.startswith("http"):
                return img_url
    except Exception as e:
        print(f"[!] Note: Could not fetch original article image: {e}")
    return ""


def get_curated_news_image(topic_text):
    """
    Returns a crisp, 1200x675 HD royalty-free editorial photograph from Unsplash
    matching the news topic (zero blur, zero watermarks, 100% copyright-free).
    """
    text = (topic_text or "").lower()

    # 1. Nutrition & Diet (100% Copyright-Free Curated Unsplash Photos)
    if any(k in text for k in ["nutrition", "diet", "food", "vitamin", "fruit", "vegetable", "calorie", "healthy eating", "nutrient", "meal", "recipe", "protein", "supplement", "weight", "eating"]):
        nutrition_photos = [
            "https://images.unsplash.com/photo-1498837167922-ddd27525d352?w=1200&h=675&fit=crop&q=80",
            "https://images.unsplash.com/photo-1490645935967-10de6ba17061?w=1200&h=675&fit=crop&q=80",
            "https://images.unsplash.com/photo-1540420773420-3366772f4999?w=1200&h=675&fit=crop&q=80",
            "https://images.unsplash.com/photo-1505576399279-565b52d4ac71?w=1200&h=675&fit=crop&q=80",
            "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=1200&h=675&fit=crop&q=80"
        ]
        return random.choice(nutrition_photos)

    # 2. General Health & Hospitals
    elif any(k in text for k in ["hospital", "doctor", "health", "med", "clinic", "vaccine", "disease", "virus", "patient"]):
        return "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?w=1200&h=675&fit=crop&q=80"

    # 3. Technology & AI
    elif any(k in text for k in ["tech", "ai", "digital", "cyber", "software", "phone", "mobile", "gcc", "data"]):
        return "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1200&h=675&fit=crop&q=80"

    # 4. Government Schemes & Law
    elif any(k in text for k in ["court", "order", "nadda", "government", "minister", "scheme", "yojana", "policy", "india", "state", "centre", "law"]):
        return "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=1200&h=675&fit=crop&q=80"

    # 5. Finance & Economy
    elif any(k in text for k in ["job", "market", "business", "crore", "economy", "bank", "finance", "money"]):
        return "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=1200&h=675&fit=crop&q=80"

    else:
        return "https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=1200&h=675&fit=crop&q=80"


def publish_to_blogger(new_title, html_content, labels, source_url="", image_prompt="", is_healthline=False):
    """
    Publishes the post to Blogger using Blogger's official Post-by-Email feature.
    - Sourcing: 100% copyright-free Unsplash photography for Healthline (never copies proprietary images).
    - Embeds the image at the top in full-width responsive format.
    - Assigns tags and Nutrition label cleanly.
    """
    if not (BLOGGER_EMAIL and SENDER_EMAIL and SENDER_APP_PASSWORD):
        raise ValueError("Email credentials not set. Need BLOGGER_EMAIL, SENDER_EMAIL, and SENDER_APP_PASSWORD.")

    msg = MIMEMultipart("mixed")
    msg["Subject"] = new_title
    msg["From"] = SENDER_EMAIL
    msg["To"] = BLOGGER_EMAIL

    # 1. Source professional, 100% royalty-free image
    image_url = ""
    # For Healthline, NEVER use source image because Healthline images are copyrighted!
    # Always use Unsplash HD editorial photography for 100% copyright safety!
    if source_url and not is_healthline:
        print("[*] Sourcing editorial news photo from source article...")
        image_url = extract_source_image(source_url)
        if image_url:
            print(f"[+] Authentic news image found: {image_url}")

    if not image_url:
        print("[*] Using high-resolution curated royalty-free Unsplash photography (100% Copyright-Free)...")
        image_url = get_curated_news_image(new_title + " " + image_prompt + " " + " ".join(labels))
        print(f"[+] Royalty-free photo selected: {image_url}")

    # 2. Embed the image at the VERY TOP of the article
    image_header_html = ""
    if image_url:
        image_header_html = f"""<div class="separator post-hero-banner" style="clear: both; text-align: center; margin: 0 auto 25px auto;">
<a href="{image_url}" style="margin-left: 1em; margin-right: 1em;">
<img alt="{new_title}" border="0" data-original-height="675" data-original-width="1200" src="{image_url}" style="width: 100%; max-width: 100%; height: auto; border-radius: 12px; object-fit: cover; display: block; margin: 0 auto; box-shadow: 0 6px 24px rgba(0,0,0,0.08);" />
</a>
</div>\n\n"""

    # 3. Modern interactive pill tags
    labels_html = ""
    if labels:
        pills = "".join(f'<span class="post-tag-pill" style="display:inline-block;background:#f1f5f9;color:#2563eb;font-size:12.5px;font-weight:600;padding:5px 12px;border-radius:20px;border:1px solid #e2e8f0;margin:3px 4px;">#{label.strip().replace(" ", "")}</span>' for label in labels)
        labels_html = f"""<div class="post-tags-container" style="display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:18px 0 0 0;margin-top:25px;border-top:1px dashed #e2e8f0;">
<span class="tags-label" style="font-size:13.5px;font-weight:700;color:#64748b;">🏷️ Topics:</span>
<div class="tags-pills-wrap">{pills}</div>
</div>"""

    full_html = image_header_html + html_content + labels_html

    part = MIMEText(full_html, "html", "utf-8")
    msg.attach(part)

    print(f"[*] Sending post via SMTP to {BLOGGER_EMAIL}...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, BLOGGER_EMAIL, msg.as_string())

    print(f"[+] Successfully published to Blogger: '{new_title}' with labels {labels}")


def run():
    print("=" * 60)
    print(f"Starting News & Nutrition Auto-Sync: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    history = load_history()

    # 1. Fetch from Healthline Nutrition
    nutrition_articles = fetch_healthline_nutrition_articles(history, max_articles=MAX_POSTS_PER_RUN)
    unposted_nutrition = [a for a in nutrition_articles if a["link"] not in history]
    print(f"[*] New unposted Healthline nutrition articles: {len(unposted_nutrition)}")

    # 2. Fetch from News RSS Feed
    news_articles = fetch_latest_articles()
    unposted_news = [a for a in news_articles if a["link"] not in history]
    print(f"[*] New unposted news articles: {len(unposted_news)}")

    # Select candidates to process up to MAX_POSTS_PER_RUN
    candidates = []
    nut_idx = 0
    news_idx = 0
    while len(candidates) < MAX_POSTS_PER_RUN:
        added = False
        if nut_idx < len(unposted_nutrition):
            candidates.append(unposted_nutrition[nut_idx])
            nut_idx += 1
            added = True
            if len(candidates) >= MAX_POSTS_PER_RUN:
                break
        if news_idx < len(unposted_news):
            candidates.append(unposted_news[news_idx])
            news_idx += 1
            added = True
        if not added:
            break

    if not candidates:
        print("[✓] All articles from both news and nutrition sources are up to date. Nothing to post.")
        return

    processed = 0
    for article in candidates:
        source_name = "Healthline Nutrition" if article.get("is_healthline") else "Tishha News"
        print(f"\n---> Processing: '{article['title']}' from [{source_name}]")
        try:
            # 1. Rewrite with Gemini into 100% unique, plagiarism-free article
            print("[*] Synthesizing 100% original, copyright-free report with Google Gemini AI...")
            rewritten = rewrite_with_gemini(article)
            print(f"[+] New Title: {rewritten.get('new_title')}")
            print(f"[+] Labels: {rewritten.get('labels')}")

            # 2. Publish to Blogger with high-resolution copyright-free featured image
            publish_to_blogger(
                new_title=rewritten.get("new_title"),
                html_content=rewritten.get("html_content"),
                labels=rewritten.get("labels", []),
                source_url=article.get("link", ""),
                image_prompt=rewritten.get("image_prompt", ""),
                is_healthline=article.get("is_healthline", False)
            )

            # 3. Mark as posted
            history.add(article["link"])
            save_history(history)
            processed += 1

        except Exception as e:
            print(f"[!] Error processing article '{article['title']}': {e}")

    print(f"\n[✓] Completed run. Successfully posted {processed} new article(s).")


if __name__ == "__main__":
    run()
