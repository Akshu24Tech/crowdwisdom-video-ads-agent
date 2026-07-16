"""
Ads Manager Agent

1. Searches Meta Ad Library (via Apify actor) for ads matching a product/niche.
2. Filters to ads active in the last 30 days.
3. Ranks candidates using "days running" as a free proxy for ad performance
   (Meta Ad Library doesn't expose spend/CTR publicly - an ad that's still
   running after N days is a reasonable signal advertisers keep paying for it).
4. Extracts pain point / marketing concept / emotional hook per ad via LLM.

Swap APIFY_ACTOR_ID for whichever Meta Ad Library scraper actor you pick from
the Apify store (search "Meta Ad Library Scraper" - several free/cheap options
exist, e.g. apify/facebook-ads-scraper).
"""

import os
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

from apify_client import ApifyClient
from openai import OpenAI  # OpenRouter is OpenAI-compatible
from dotenv import load_dotenv
load_dotenv()

APIFY_TOKEN = os.getenv("APIFY_TOKEN")
APIFY_ACTOR_ID = os.getenv("APIFY_META_ADS_ACTOR", "automly/facebook-ad-library-scraper")
# OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
# OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "x-ai/grok-4.1-fast:free")
# DATA_DIR = Path(__file__).parent.parent / "data"

#llm_client = OpenAI(
#    base_url="https://openrouter.ai/api/v1",
#    api_key=OPENROUTER_API_KEY,
#)
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY")
LLM_MODEL = os.environ.get("LLM_MODEL", "meta/llama-3.3-70b-instruct")

DATA_DIR = Path(__file__).parent.parent / "data"

llm_client = OpenAI(
    base_url=LLM_BASE_URL,
    api_key=LLM_API_KEY,
)

def scrape_meta_ads(search_terms: list[str], country: str = "US", max_items: int = 40) -> list[dict]:
    """Runs the Apify Meta Ad Library actor and returns raw ad records."""
    client = ApifyClient(APIFY_TOKEN)
    run_input = {
        "searchTerms": search_terms,
        "countryCode": country,
        "activeStatus": "active",
        "maxItems": max_items,
    }
    run = client.actor(APIFY_ACTOR_ID).call(run_input=run_input)
    try:
        dataset_id = run.default_dataset_id
    except AttributeError:
        dataset_id = run["defaultDatasetId"]
    items = list(client.dataset(dataset_id).iterate_items())
    return items

def filter_last_30_days(ads: list[dict]) -> list[dict]:
    cutoff = datetime.utcnow() - timedelta(days=30)
    out = []
    for ad in ads:
        start_str = ad.get("ad_delivery_start_time") or ad.get("startDate")
        if not start_str:
            continue
        try:
            start = datetime.fromisoformat(start_str.replace("Z", ""))
        except ValueError:
            continue
        if start >= cutoff:
            out.append(ad)
    return out


def rank_ads(ads: list[dict], top_n: int = 10) -> list[dict]:
    """Proxy ranking: longer-running ads within the 30-day window = stronger signal."""

    def days_running(ad):
        start_str = ad.get("ad_delivery_start_time") or ad.get("startDate")
        try:
            start = datetime.fromisoformat(start_str.replace("Z", ""))
            return (datetime.utcnow() - start).days
        except Exception:
            return 0

    ranked = sorted(ads, key=days_running, reverse=True)
    return ranked[:top_n]


def extract_pain_and_concept(ad: dict) -> dict:
    """Uses the LLM to extract pain point, marketing concept, and hook style from ad copy."""
    ad_text = ad.get("ad_creative_body") or ad.get("body") or ad.get("text") or ""
    prompt = f"""You are a direct-response marketing analyst. Given this ad copy,
extract three things as JSON only (no preamble, no markdown fences):

{{
  "pain_point": "the specific fear/frustration/problem this ad targets",
  "marketing_concept": "the core angle or big idea the ad is built on",
  "hook_style": "how the first line grabs attention (e.g. shock stat, question, bold claim)"
}}

Ad copy:
\"\"\"{ad_text}\"\"\"
"""
    resp = llm_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    raw = resp.choices[0].message.content.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"pain_point": None, "marketing_concept": None, "hook_style": None, "_raw": raw}


def run(search_terms: list[str], top_n: int = 10) -> dict:
    """Full Ads Manager pipeline. Returns the saved result dict."""
    raw_ads = scrape_meta_ads(search_terms)
    recent = filter_last_30_days(raw_ads)
    top_ads = rank_ads(recent, top_n=top_n)

    enriched = []
    for i, ad in enumerate(top_ads, 1):
        print(f"[ads_manager] Analyzing ad {i}/{len(top_ads)}...")
        analysis = extract_pain_and_concept(ad)
        enriched.append({
            "ad_id": ad.get("id") or ad.get("adArchiveID"),
            "page_name": ad.get("page_name") or ad.get("pageName"),
            "ad_text": ad.get("ad_creative_body") or ad.get("body"),
            "start_date": ad.get("ad_delivery_start_time") or ad.get("startDate"),
            "analysis": analysis,
        })
        time.sleep(0.5)  # be polite to the LLM API rate limits

    result = {
        "search_terms": search_terms,
        "generated_at": datetime.utcnow().isoformat(),
        "total_scraped": len(raw_ads),
        "total_recent": len(recent),
        "top_ads": enriched,
    }

    out_path = DATA_DIR / "scraped_ads.json"
    out_path.write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    result = run(search_terms=["trading signals", "stock alerts", "day trading community"])
    print(f"Saved {len(result['top_ads'])} analyzed ads to data/scraped_ads.json")
