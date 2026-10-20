#!/usr/bin/env python3
"""
AyumiLove Champion Scraper for RSL Mercy Tracker
Scrapes the latest Mythical, Void Legendary, and Non-Void Legendary champions
directly from AyumiLove and writes them to latest_champions.json.
Uses standard Python library (zero pip dependencies).
"""

import urllib.request
import re
import json
import os
from datetime import datetime, timezone

URL = "https://ayumilove.net/raid-shadow-legends-list-of-champions-by-affinity/"
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "latest_champions.json")

def scrape_ayumilove():
    print(f"Fetching {URL} ...")
    req = urllib.request.Request(
        URL,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    )
    
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8")

    pattern = re.compile(r"<h4>([^<]+)</h4>\s*<ul>([\s\S]*?)</ul>", re.IGNORECASE)
    sections = pattern.findall(html)

    mythicals = set()
    void_legendaries = set()
    non_void_legendaries = set()

    for header, list_html in sections:
        h = header.lower()
        # Extract champion names inside <a> tags before parentheses
        champions = re.findall(r"<li><a[^>]*>([^<(]+?)(?:\s*\([A-Za-z0-9\-]+\))?</a></li>", list_html)
        cleaned = [c.strip() for c in champions if c.strip()]

        if "mythical" in h:
            mythicals.update(cleaned)
        elif "void legendary" in h:
            void_legendaries.update(cleaned)
        elif "legendary" in h and any(aff in h for aff in ["force", "spirit", "magic"]):
            non_void_legendaries.update(cleaned)

    result = {
        "lastScraped": datetime.now(timezone.utc).isoformat(),
        "source": URL,
        "counts": {
            "mythical": len(mythicals),
            "void": len(void_legendaries),
            "nonVoid": len(non_void_legendaries),
            "total": len(mythicals) + len(void_legendaries) + len(non_void_legendaries)
        },
        "mythicalChampions": sorted(list(mythicals), key=lambda s: s.lower()),
        "voidLegendaries": sorted(list(void_legendaries), key=lambda s: s.lower()),
        "nonVoidLegendaries": sorted(list(non_void_legendaries), key=lambda s: s.lower())
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"✅ Successfully scraped {result['counts']['total']} champions:")
    print(f"   • Mythicals: {result['counts']['mythical']}")
    print(f"   • Void Legendaries: {result['counts']['void']}")
    print(f"   • Non-Void Legendaries: {result['counts']['nonVoid']}")
    print(f"Saved to: {OUTPUT_FILE}")
    return result

if __name__ == "__main__":
    scrape_ayumilove()
