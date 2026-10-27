import os
import sys
import re
import json
import smtplib
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import datetime

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
HISTORY_FILE = "posted_history.json"

# Google Gemini API Key (Get free from: https://aistudio.google.com/)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Blogger Email-to-Post Settings (Blogger -> Settings -> Email -> Post using email)
# Format: yourusername.secretword@blogger.com
BLOGGER_EMAIL = os.environ.get("BLOGGER_EMAIL", "")

# Sender Gmail settings (used to send the email to Blogger)
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
SENDER_APP_PASSWORD = os.environ.get("SENDER_APP_PASSWORD", "")

# Maximum articles to process per run (recommended: 1 to 2 to maintain high quality)
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
    """Fetch and parse articles from the WordPress RSS feed."""
    print(f"[*] Fetching RSS feed from: {RSS_FEED_URL}")
    req = urllib.request.Request(
        RSS_FEED_URL,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        xml_data = response.read()

    root = ET.fromstring(xml_data)
    items = root.findall("./channel/item")
    print(f"[*] Found {len(items)} articles in feed.")

    articles = []
    ns = {"content": "http://purl.org/rss/1.0/modules/content/"}

    for item in items:
        title = item.find("title").text if item.find("title") is not None else ""
        link = item.find("link").text if item.find("link") is not None else ""
        content_elem = item.find("content:encoded", ns)
        
        # If content:encoded not available, fallback to description
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
                "categories": categories
            })

    return articles


def rewrite_with_gemini(article):
    """
    Calls Google Gemini API (Free) to rewrite the article into a 100% unique,
    high-ranking SEO news report with new title, subheadings, bullet points, and FAQs.
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set. Please set it in config or environment.")

    import re
    # Strip HTML tags and clean up whitespace from original article
    clean_body = re.sub(r'<[^>]+>', ' ', article.get('body', ''))
    clean_body = re.sub(r'\s+', ' ', clean_body).strip()

    prompt = f"""
You are a senior investigative news journalist and lead SEO editor for 'Dainik Saar' (an authoritative news and analysis publication).
Your task is to transform the following raw news wire into an in-depth, original, comprehensive, and authoritative journalistic report (minimum 750 to 1,000 words).
Ensure high Information Gain (E-E-A-T): Do not simply summarize or rephrase sentences. Expand with rich analytical context, explain historical background, analyze industry/societal implications, and weave data and perspectives into an engaging narrative that satisfies Google's Helpful Content System.

ORIGINAL TITLE: {article['title']}
ORIGINAL CONTENT:
{clean_body[:4000]}

EDITORIAL GUIDELINES:
1. TITLE: Create an irresistible, click-worthy, yet factually accurate news headline (English, 55-70 characters).
2. INTRO: Begin directly with a powerful lead paragraph that hooks the reader and clearly explains the core revelation, who is impacted, and why it matters today.
3. HEADINGS: Use dynamic, natural, topic-specific <h2> and <h3> subheadings (do NOT use repetitive or generic headers like 'Key Highlights' or 'In-Depth Analysis' for every post; craft headings that fit the story).
4. DEPTH & SECTIONS (Target 750-1000+ words total):
   - Lead Story & Key Takeaway (highlighting the core facts)
   - Essential Details & Data Points (bullet points with concrete figures, percentages, dates, and names)
   - Deep Background, Context & Previous Developments (how did we get here?)
   - Policy, Market, or Societal Implications (who benefits, what changes?)
   - Official Statements & Expert Perspectives (synthesized quotes and viewpoints)
   - Future Roadmap & What to Watch Next
   - Frequently Asked Questions (2-3 highly searched, thoughtful questions with detailed, authoritative answers)
5. FORMATTING: Clean semantic HTML using <p>, <h2>, <h3>, <ul>, <li>, and <blockquote>. Use modern CSS classes:
   - Lead paragraph: <p class=\"story-lead\" style=\"font-size:18px;line-height:1.7;color:#1e293b;font-weight:500;margin-bottom:20px;\">
   - Key stats/points: <div class=\"story-highlights\" style=\"background:#f8fafc;border-left:4px solid #2563eb;padding:16px 20px;border-radius:8px;margin:24px 0;\">
   - Section headings: <h2 style=\"font-size:22px;color:#0f172a;margin-top:28px;margin-bottom:12px;font-weight:700;\">
   - FAQ container: <div class=\"faq-section\" style=\"margin-top:30px;background:#f8fafc;padding:20px;border-radius:10px;\">
6. Do NOT include <html>, <head>, or <body> tags.

OUTPUT FORMAT IN STRICT JSON:
You must return ONLY a valid JSON object with the following keys (no markdown code fences, just raw JSON):
{{
    "new_title": "Compelling, high-CTR, SEO-optimized title",
    "meta_description": "A unique, compelling 140-160 character meta description summarizing the key news hook",
    "image_prompt": "A 5-8 word descriptive prompt for a photorealistic editorial news photo",
    "labels": ["Category1", "Tag2", "Tag3"],
    "html_content": "HTML string containing the complete, in-depth news report formatted with the styles above"
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

                return json.loads(raw_text)
            except Exception as e:
                last_err = e
                import time
                time.sleep(2)

    if last_err is not None:
        raise last_err
    raise RuntimeError("Failed to rewrite article: No attempts succeeded.")


def extract_source_image(article_url):
    """
    Extracts authentic high-resolution editorial news photo from the original source article.
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
    matching the news topic (zero blur, zero watermarks, 100% professional).
    """
    text = (topic_text or "").lower()
    if any(k in text for k in ["hospital", "doctor", "health", "med", "clinic", "vaccine", "disease", "virus", "patient"]):
        return "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?w=1200&h=675&fit=crop&q=80"
    elif any(k in text for k in ["tech", "ai", "digital", "cyber", "software", "phone", "mobile", "gcc", "data"]):
        return "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1200&h=675&fit=crop&q=80"
    elif any(k in text for k in ["court", "order", "nadda", "government", "minister", "scheme", "yojana", "policy", "india", "state", "centre", "law"]):
        return "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=1200&h=675&fit=crop&q=80"
    elif any(k in text for k in ["job", "market", "business", "crore", "economy", "bank", "finance", "money"]):
        return "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=1200&h=675&fit=crop&q=80"
    else:
        return "https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=1200&h=675&fit=crop&q=80"


def publish_to_blogger(new_title, html_content, labels, source_url="", image_prompt=""):
    """
    Publishes the post to Blogger using Blogger's official Post-by-Email feature.
    - Sources professional, high-resolution editorial photography (100% free & copyright-free).
    - Embeds the image at the VERY TOP in Blogger's native full-width separator container.
    - Blogger automatically generates the homepage thumbnail from the top image.
    """
    if not (BLOGGER_EMAIL and SENDER_EMAIL and SENDER_APP_PASSWORD):
        raise ValueError("Email credentials not set. Need BLOGGER_EMAIL, SENDER_EMAIL, and SENDER_APP_PASSWORD.")

    msg = MIMEMultipart("mixed")
    msg["Subject"] = new_title
    msg["From"] = SENDER_EMAIL
    msg["To"] = BLOGGER_EMAIL

    # 1. Source professional, high-resolution editorial news photo
    image_url = ""
    if source_url:
        print("[*] Sourcing authentic editorial news photo from source article...")
        image_url = extract_source_image(source_url)
        if image_url:
            print(f"[✓] Authentic news image found: {image_url}")

    # Fallback to high-resolution curated Unsplash editorial photography
    if not image_url:
        print("[*] Using high-resolution curated editorial news photo...")
        image_url = get_curated_news_image(new_title + " " + image_prompt + " " + " ".join(labels))
        print(f"[✓] Editorial photo selected: {image_url}")

    # 2. Embed the image at the VERY TOP of the article (Matching Blogger standard structure)
    # This ensures 100% responsive full-width display, beautiful banner styling, and automatic Blogger thumbnail extraction
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

    print(f"[✓] Successfully published to Blogger: '{new_title}'")


def run():
    print("=" * 60)
    print(f"Starting News Auto-Sync: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    history = load_history()
    articles = fetch_latest_articles()

    # Find unposted articles
    new_articles = [a for a in articles if a["link"] not in history]
    print(f"[*] New unposted articles found: {len(new_articles)}")

    if not new_articles:
        print("[✓] All articles are up to date. Nothing to post.")
        return

    processed = 0
    for article in reversed(new_articles[:MAX_POSTS_PER_RUN]):
        print(f"\n---> Processing: {article['title']}")
        try:
            # 1. Rewrite with Gemini
            print("[*] Rewriting with Google Gemini AI...")
            rewritten = rewrite_with_gemini(article)
            print(f"[✓] New Title: {rewritten.get('new_title')}")

            # 2. Publish to Blogger with high-resolution editorial featured image
            publish_to_blogger(
                new_title=rewritten.get("new_title"),
                html_content=rewritten.get("html_content"),
                labels=rewritten.get("labels", []),
                source_url=article.get("link", ""),
                image_prompt=rewritten.get("image_prompt", "")
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
