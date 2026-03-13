"""
Azure Storage Migration Query Monitor
--------------------------------------
Monitors Reddit, Stack Overflow, and community RSS feeds for questions
about storage migrations to Azure. Detects relevant posts, generates
AI-powered suggested responses via GitHub Models (GPT-4o), and publishes
an RSS feed that Power Automate consumes to post notifications to Teams.

Fully free: RSS feeds + GitHub Actions + GitHub Pages + Power Automate.
"""

import feedparser
import json
import os
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ============================================================
# CONFIGURATION
# ============================================================

RSS_FEEDS = [
    # Reddit - Azure subreddit: ALL new posts (is_relevant() filters)
    "https://www.reddit.com/r/azure/new/.rss",
    # Reddit - Azure subreddit search: broad OR query for migration tools
    "https://www.reddit.com/r/azure/search.rss?q=storage+migration+OR+data+box+OR+azcopy+OR+azure+migrate+OR+file+sync+OR+storage+mover&restrict_sr=1&sort=new&t=week",
    # Reddit - sysadmin: broad OR (catches any Azure migration/storage topic)
    "https://www.reddit.com/r/sysadmin/search.rss?q=azure+storage+OR+azure+migration+OR+azure+migrate+OR+data+box+OR+azcopy+OR+on-prem+to+azure&restrict_sr=1&sort=new&t=week",
    # Reddit - cloud computing: broad OR
    "https://www.reddit.com/r/cloudcomputing/search.rss?q=azure+storage+OR+azure+migration+OR+data+box+OR+azcopy+OR+migrate+to+azure&restrict_sr=1&sort=new&t=week",
    # Reddit - dataengineering: broad OR
    "https://www.reddit.com/r/dataengineering/search.rss?q=azure+storage+OR+azure+migration+OR+data+box+OR+azcopy+OR+data+lake+migration&restrict_sr=1&sort=new&t=week",
    # Stack Overflow - azure-storage tag
    "https://stackoverflow.com/feeds/tag?tagnames=azure-storage&sort=newest",
    # Stack Overflow - azure-migrate tag
    "https://stackoverflow.com/feeds/tag?tagnames=azure-migrate&sort=newest",
    # Stack Overflow - azcopy tag
    "https://stackoverflow.com/feeds/tag?tagnames=azcopy&sort=newest",
    # Server Fault - azure tag (sysadmins doing migrations)
    "https://serverfault.com/feeds/tag/azure",
]

# Microsoft Q&A — searched via Learn Search API with QnA category filter
# Each query is searched separately; results go through is_relevant() like RSS posts
MSQA_SEARCH_QUERIES = [
    "azure storage migration",
    "azure data box",
    "azcopy",
    "azure migrate",
    "azure file sync",
    "azure storage mover",
    "migrate to azure storage",
    "data box 120",
    "data box 525",
    "azure blob migration",
    "on-premises to azure storage",
]

# --- Keyword filters ---

# Tier 1: High-confidence phrases — match alone, no other context needed
HIGH_CONFIDENCE_PHRASES = [
    # Azure storage migration tools — all name variants
    "azcopy", "az copy", "azcopy10",
    "storage mover", "azure storage mover", "storagemover",
    "azure file sync", "file sync agent",
    "data box", "databox", "azure data box", "azure databox",
    "data box heavy", "data box disk", "data box gateway",
    "data box 120", "data box 525",
    "azure migrate", "azure site recovery", "asr migration",
    # Strong migration phrases
    "on-prem to azure", "on-premises to azure", "on prem to azure",
    "on-prem to cloud", "on-premises to cloud", "on prem to cloud",
    "migrate to azure", "migration to azure", "moving to azure",
    "move to azure", "transfer to azure", "copy to azure",
    "aws to azure", "s3 to azure", "gcp to azure",
    "offline migration", "online migration", "lift and shift",
    "storage migration", "data migration to azure",
    "migrate storage", "migrate file server",
    "migrate blob", "migrate file share",
    "agentless discovery", "agentless migration",
]

# Tier 2: Broader keywords — need ANY TWO of these three categories
CATEGORY_A_MIGRATION = [
    "migrate", "migration", "move data", "transfer data",
    "copy data", "data movement", "data transfer",
    "cutover", "replicate", "sync data", "move files",
    "moving data", "moving files", "transferring",
    "importing data", "exporting data",
]

CATEGORY_B_STORAGE = [
    "storage", "blob", "file share", "file server", "azure files",
    "data lake", "adls", "s3 bucket", "object storage", "block storage",
    "managed disk", "nas ", " san ", "smb", "nfs", "cifs",
    "backup", "archive", "netapp", "file system",
    "terabyte", " tb ", "petabyte", " pb ",
    "bucket", "container storage",
]

CATEGORY_C_INFRA = [
    # Source/destination infra (NOT just "azure" — too generic)
    "on-prem", "on-premises", "on premises",
    "aws", " s3 ", "gcp", "google cloud",
    "vmware", "hyper-v", "local storage",
    "datacenter", "data center", "physical server",
    "colocation", "netapp",
    "azure storage", "azure blob", "azure files",
    "azure data lake", "blob storage",
]

# Posts matching these are excluded (common false positives)
EXCLUDE_KEYWORDS = [
    "subscription migration", "migrate subscription",
    "devops migration", "tfs migration", "migrate pipeline",
    "migrate work item", "code migration", "sdk migration",
    "api migration", "migrate project", "project migration",
    "framework migration", ".net migration", "dotnet migration",
    "identity migration", "user migration", "auth migration",
    "jit migration", "jit provisioning",
    "mobility service agent",
]

# --- GitHub Models API (GPT-4o, free tier: 150 req/day) ---
# Uses your GitHub PAT — no special scope needed
# Leave empty to use template-based responses (no API needed)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# Output RSS feed — Power Automate reads this to post to Teams
FEED_DIR = Path("docs")
FEED_FILE = FEED_DIR / "feed.xml"
MAX_FEED_ITEMS = 50  # Keep last 50 items in the feed

# State file
STATE_FILE = Path("seen_posts.json")
MAX_STATE_ENTRIES = 5000

# Only notify about posts created within this many days
MAX_POST_AGE_DAYS = int(os.getenv("MAX_POST_AGE_DAYS", "7"))

USER_AGENT = "AzureMigrationMonitor/1.0 (GitHub Actions; +https://github.com)"


# ============================================================
# STATE MANAGEMENT
# ============================================================

def load_seen_posts():
    """Load set of previously seen post IDs."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except (json.JSONDecodeError, TypeError):
            return set()
    return set()


def save_seen_posts(seen):
    """Save seen post IDs, keeping only the most recent entries."""
    seen_list = list(seen)[-MAX_STATE_ENTRIES:]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(seen_list, f)


# ============================================================
# RSS FEED FETCHING
# ============================================================

def fetch_feed(url, retries=2):
    """Fetch and parse an RSS feed with retry for rate limiting."""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=20) as resp:
                content = resp.read()

            feed = feedparser.parse(content)
            posts = []
            for entry in feed.entries:
                body = entry.get("summary", "")
                if not body and entry.get("content"):
                    body = entry["content"][0].get("value", "")

                # Strip HTML tags
                body = re.sub(r"<[^>]+>", " ", body)
                body = re.sub(r"\s+", " ", body).strip()

                post = {
                    "id": entry.get("id", entry.get("link", "")),
                    "title": entry.get("title", "").strip(),
                    "body": body,
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "source": _extract_source(url),
                }
                posts.append(post)
            return posts

        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                wait = 10 * (attempt + 1)
                print(f"  Rate limited (429) on {url}, retrying in {wait}s...")
                time.sleep(wait)
                continue
            print(f"  Error fetching {url}: {e}")
            return []
        except Exception as e:
            print(f"  Error fetching {url}: {e}")
            return []


def _extract_source(url):
    """Get a human-readable source name from the feed URL."""
    if "reddit.com" in url:
        match = re.search(r"/r/(\w+)", url)
        return f"Reddit r/{match.group(1)}" if match else "Reddit"
    if "stackoverflow.com" in url:
        return "Stack Overflow"
    if "serverfault.com" in url:
        return "Server Fault"
    if "learn.microsoft.com" in url:
        return "Microsoft Q&A"
    return url.split("/")[2]


def fetch_msqa(queries, seen):
    """Fetch questions from Microsoft Q&A via Learn Search API.

    Uses the same Learn Search API we already use for doc lookup,
    but with category filter set to 'QnA' instead of 'Documentation'.
    Returns list of post dicts compatible with the rest of the pipeline.
    """
    posts = []
    seen_urls = set()
    for query in queries:
        try:
            encoded = urllib.parse.quote(query)
            url = (
                f"https://learn.microsoft.com/api/search?search={encoded}"
                "&locale=en-us&%24filter=(category+eq+%27QnA%27)&%24top=10"
            )
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            for item in data.get("results", []):
                item_url = item.get("url", "")
                if not item_url or item_url in seen_urls:
                    continue
                seen_urls.add(item_url)

                # Use URL as unique ID
                post_id = f"msqa:{item_url}"
                if post_id in seen:
                    continue

                title = item.get("title", "").strip()
                # Remove " - Microsoft Q&A" suffix if present
                title = re.sub(r"\s*-\s*Microsoft Q&A\s*$", "", title)
                description = item.get("description", "")
                # Strip HTML from description
                description = re.sub(r"<[^>]+>", " ", description)
                description = re.sub(r"\s+", " ", description).strip()

                post = {
                    "id": post_id,
                    "title": title,
                    "body": description,
                    "link": item_url,
                    "published": item.get("lastUpdatedDate", ""),
                    "source": "Microsoft Q&A",
                }
                posts.append(post)

        except Exception as e:
            print(f"  MS Q&A search error for '{query}': {e}")
        time.sleep(1)  # Be polite to the API

    print(f"  Microsoft Q&A: {len(posts)} unique questions from {len(queries)} queries")
    return posts


def _parse_date(date_str):
    """Parse various RSS date formats into a datetime."""
    if not date_str:
        return None
    # feedparser provides parsed time tuples we can use as fallback
    for fmt in [
        "%Y-%m-%dT%H:%M:%S%z",       # ISO 8601 with tz
        "%Y-%m-%dT%H:%M:%SZ",        # ISO 8601 UTC
        "%Y-%m-%dT%H:%M:%S.%f%z",    # ISO 8601 with microseconds
        "%a, %d %b %Y %H:%M:%S %z",  # RFC 2822
        "%a, %d %b %Y %H:%M:%S %Z",  # RFC 2822 with tz name
    ]:
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def is_recent(post):
    """Check if a post was published within MAX_POST_AGE_DAYS."""
    pub_date = _parse_date(post.get("published", ""))
    if pub_date is None:
        # If we can't parse the date, include it (fail open)
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_POST_AGE_DAYS)
    return pub_date >= cutoff


# ============================================================
# KEYWORD FILTERING
# ============================================================

def is_relevant(post):
    """Check if a post is about Azure storage migration."""
    text = f" {post['title']} {post['body']} ".lower()
    title = f" {post['title']} ".lower()

    # Exclude common false positives first
    if any(kw in text for kw in EXCLUDE_KEYWORDS):
        return False

    # Tier 1: High-confidence phrases — match alone
    if any(phrase in text for phrase in HIGH_CONFIDENCE_PHRASES):
        return True

    # Tier 2: MIGRATION + (STORAGE or INFRA), but at least one keyword
    # must appear in the TITLE (prevents matching random words in long posts)
    has_migration = any(kw in text for kw in CATEGORY_A_MIGRATION)
    has_storage = any(kw in text for kw in CATEGORY_B_STORAGE)
    has_infra = any(kw in text for kw in CATEGORY_C_INFRA)

    if has_migration and (has_storage or has_infra):
        all_tier2 = CATEGORY_A_MIGRATION + CATEGORY_B_STORAGE + CATEGORY_C_INFRA
        if any(kw in title for kw in all_tier2):
            return True

    return False


# ============================================================
# RESPONSE GENERATION
# ============================================================

def generate_response(post):
    """Generate a suggested response, using GitHub Models + MS Learn if available."""
    if GITHUB_TOKEN:
        ai_response = _generate_llm_response(post)
        if ai_response:
            return ai_response
    return _generate_template_response(post)


def _search_learn_docs(query):
    """Search Microsoft Learn docs and return top results."""
    try:
        encoded_query = urllib.parse.quote(query)
        url = (
            f"https://learn.microsoft.com/api/search?search={encoded_query}"
            "&locale=en-us&$filter=(category%20eq%20%27Documentation%27)&$top=5"
        )
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        docs = []
        for r in data.get("results", []):
            docs.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "description": r.get("description", ""),
            })
        return docs
    except Exception as e:
        print(f"  MS Learn API error: {e}")
        return []


def _generate_llm_response(post):
    """Call GitHub Models (GPT-4o-mini) with MS Learn context for a response."""
    try:
        # Step 1: Build search query from post keywords
        search_terms = f"Azure storage migration {post['title'][:100]}"
        learn_docs = _search_learn_docs(search_terms)

        # Step 2: Format Learn docs as context
        docs_context = ""
        if learn_docs:
            docs_context = "Relevant Microsoft Learn documentation:\n"
            for i, doc in enumerate(learn_docs, 1):
                docs_context += (
                    f"{i}. {doc['title']}\n"
                    f"   URL: {doc['url']}\n"
                    f"   Summary: {doc['description'][:200]}\n\n"
                )

        # Step 3: Call GitHub Models API (OpenAI-compatible)
        url = "https://models.inference.ai.azure.com/chat/completions"
        system_prompt = (
            "You are a Microsoft Azure storage migration expert replying "
            "on a community forum. Use the provided Microsoft Learn documentation "
            "to give accurate, helpful answers. Always include relevant documentation "
            "links from the context provided. Keep answers professional and under 300 words."
        )
        user_prompt = (
            f"{docs_context}\n"
            f"A user posted this question on a forum:\n\n"
            f"Title: {post['title']}\n"
            f"Body: {post['body'][:2000]}\n\n"
            "Draft a helpful response referencing the Microsoft Learn docs above. "
            "Include specific steps and link to the relevant docs."
        )

        payload = json.dumps({
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 800,
        }).encode("utf-8")

        req = urllib.request.Request(
            url, data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "User-Agent": USER_AGENT,
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]

    except Exception as e:
        print(f"  GitHub Models API error: {e}. Falling back to template.")
        return None


def _generate_template_response(post):
    """Rule-based response when no LLM API is configured."""
    text = f" {post['title']} {post['body']} ".lower()
    lines = ["Here are Azure tools that can help with your migration:\n"]

    if any(w in text for w in ["large", "terabyte", "tb", "petabyte", "pb", "offline", "data box", "ship"]):
        lines.append(
            "**Azure Data Box** - For large offline migrations (tens of TBs+). "
            "Microsoft ships a physical device to your site.\n"
            "Docs: https://learn.microsoft.com/azure/databox/"
        )

    if any(w in text for w in ["file server", "file share", "smb", "cifs", "nas", "file sync"]):
        lines.append(
            "**Azure File Sync** - Sync on-prem file servers with Azure Files, "
            "with cloud tiering to free local space.\n"
            "Docs: https://learn.microsoft.com/azure/storage/file-sync/"
        )

    if any(w in text for w in ["blob", "s3", "object", "azcopy", "container", "bucket"]):
        lines.append(
            "**AzCopy** - Fast CLI tool for copying data to/from Azure Blob Storage. "
            "Supports direct S3-to-Azure copy.\n"
            "Docs: https://learn.microsoft.com/azure/storage/common/storage-use-azcopy-v10"
        )

    if any(w in text for w in ["storage mover", "managed", "agent-based"]):
        lines.append(
            "**Azure Storage Mover** - Fully managed migration service with "
            "agent-based orchestration.\n"
            "Docs: https://learn.microsoft.com/azure/storage-mover/"
        )

    if any(w in text for w in ["vm", "server", "vmware", "hyper-v", "virtual machine"]):
        lines.append(
            "**Azure Migrate** - Discover, assess, and migrate servers and VMs.\n"
            "Docs: https://learn.microsoft.com/azure/migrate/"
        )

    # Always include AzCopy if not already mentioned
    if not any("AzCopy" in l for l in lines):
        lines.append(
            "**AzCopy** - Versatile CLI tool for Azure Storage data movement.\n"
            "Docs: https://learn.microsoft.com/azure/storage/common/storage-use-azcopy-v10"
        )

    lines.append(
        "\nFull migration guide: "
        "https://learn.microsoft.com/azure/storage/common/storage-migration-overview"
    )

    return "\n\n".join(lines)








# ============================================================
# OUTPUT RSS FEED (for Power Automate → Teams)
# ============================================================

def _xml_escape(text):
    """Escape text for safe XML embedding."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;"))


def load_existing_feed_items():
    """Load existing items from feed.xml to preserve history."""
    if not FEED_FILE.exists():
        return []
    try:
        content = FEED_FILE.read_text(encoding="utf-8")
        items = []
        for match in re.finditer(r"<item>(.*?)</item>", content, re.DOTALL):
            items.append(match.group(0))
        return items
    except Exception:
        return []


def write_feed(processed_posts):
    """Write processed matches to docs/feed.xml as RSS 2.0."""
    FEED_DIR.mkdir(exist_ok=True)

    # Build new <item> entries
    new_items = []
    for post, response in processed_posts:
        raw_date = post.get("published", "")
        # Always convert to RFC 2822 format (required by RSS spec)
        parsed = _parse_date(raw_date) if raw_date else None
        if parsed is None:
            parsed = datetime.now(timezone.utc)
        pub_date = parsed.strftime("%a, %d %b %Y %H:%M:%S %z")
        description = (
            f"Source: {_xml_escape(post['source'])}\n\n"
            f"Question:\n{_xml_escape(post['title'])}\n\n"
            f"{_xml_escape(post['body'][:500])}\n\n"
            f"---\n\n"
            f"Suggested Response:\n{_xml_escape(response[:1500])}"
        )
        item = (
            f"    <item>\n"
            f"      <title>{_xml_escape(post['source'])}: {_xml_escape(post['title'][:150])}</title>\n"
            f"      <link>{_xml_escape(post['link'])}</link>\n"
            f"      <guid isPermaLink=\"false\">{_xml_escape(post['id'])}</guid>\n"
            f"      <pubDate>{_xml_escape(pub_date)}</pubDate>\n"
            f"      <description>{description}</description>\n"
            f"    </item>"
        )
        new_items.append(item)

    # Merge with existing items (new first), cap at MAX_FEED_ITEMS
    existing_items = load_existing_feed_items()
    all_items = new_items + existing_items

    # Deduplicate by guid
    seen_guids = set()
    unique_items = []
    for item in all_items:
        guid_match = re.search(r"<guid[^>]*>(.*?)</guid>", item)
        guid = guid_match.group(1) if guid_match else item
        if guid not in seen_guids:
            seen_guids.add(guid)
            unique_items.append(item)
    all_items = unique_items[:MAX_FEED_ITEMS]

    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")
    feed_url = "https://lakshj-ms.github.io/azure-migration-monitor/feed.xml"
    feed_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        '  <channel>\n'
        '    <title>Azure Migration Monitor</title>\n'
        f'    <link>https://github.com/LakshJ-MS/azure-migration-monitor</link>\n'
        '    <description>Azure storage migration queries from Reddit, Stack Overflow, and community forums with suggested responses.</description>\n'
        f'    <atom:link href="{feed_url}" rel="self" type="application/rss+xml"/>\n'
        f'    <lastBuildDate>{now}</lastBuildDate>\n'
        f'{chr(10).join(all_items)}\n'
        '  </channel>\n'
        '</rss>'
    )

    FEED_FILE.write_text(feed_xml, encoding="utf-8")
    print(f"Feed updated: {len(new_items)} new + {len(all_items) - len(new_items)} existing = {len(all_items)} total items")


# ============================================================
# MAIN
# ============================================================

def main():
    print(f"=== Azure Migration Monitor — {datetime.now(timezone.utc).isoformat()} ===\n")

    seen = load_seen_posts()
    initial_seen_count = len(seen)
    new_relevant = []

    # --- Phase 1: RSS feeds (Reddit, Stack Overflow, Server Fault) ---
    for feed_url in RSS_FEEDS:
        print(f"Fetching: {feed_url}")
        posts = fetch_feed(feed_url)
        print(f"  Got {len(posts)} posts")

        for post in posts:
            if post["id"] in seen:
                continue
            seen.add(post["id"])

            if not is_recent(post):
                continue

            if is_relevant(post):
                print(f"  MATCH: {post['title'][:80]}  ({post['published'][:10]})")
                new_relevant.append(post)

        # Small delay between feeds to avoid rate limiting
        if "reddit.com" in feed_url:
            time.sleep(3)

    # --- Phase 2: Microsoft Q&A (via Learn Search API) ---
    print(f"\nFetching: Microsoft Q&A ({len(MSQA_SEARCH_QUERIES)} queries)")
    msqa_posts = fetch_msqa(MSQA_SEARCH_QUERIES, seen)
    for post in msqa_posts:
        seen.add(post["id"])
        if not is_recent(post):
            continue
        if is_relevant(post):
            print(f"  MATCH: {post['title'][:80]}  ({post['published'][:10]})")
            new_relevant.append(post)

    print(f"\nNew posts scanned: {len(seen) - initial_seen_count}")
    print(f"Relevant matches:  {len(new_relevant)}\n")

    processed = []
    for post in new_relevant:
        print(f"Processing: {post['title'][:80]}")
        response = generate_response(post)
        processed.append((post, response))
        print()

    # Always write feed (merges new + existing items)
    write_feed(processed)

    save_seen_posts(seen)
    print("Done.")


if __name__ == "__main__":
    main()
