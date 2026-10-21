#!/usr/bin/env python3
"""
AyumiLove Champion Scraper & Autonomous Gist Sync for RSL Mercy Tracker
Scrapes the latest Mythical, Void Legendary, and Non-Void Legendary champions
directly from AyumiLove and writes them to latest_champions.json.
When GIST_TOKEN environment variable is provided, automatically compares with
the live Gist and PATCHes updates autonomously.
Uses standard Python library (zero pip dependencies).
"""

import urllib.request
import re
import json
import os
import sys
from datetime import datetime, timezone

URL = "https://ayumilove.net/raid-shadow-legends-list-of-champions-by-affinity/"
GIST_ID = "3bb0b4ad73aa438eaef76573171ee164"
GIST_FILE = "champions.json"
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "latest_champions.json")

def normalize_name(name):
    """Normalize champion name for case-insensitive, punctuation-safe comparison."""
    return re.sub(r"[^a-z0-9]", "", name.lower())

def fetch_current_gist():
    """Fetch current champions.json from the live GitHub Gist."""
    url = f"https://api.github.com/gists/{GIST_ID}"
    print(f"Fetching current Gist ({GIST_ID}) ...")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "RSL-Mercy-Tracker-Scraper",
            "Accept": "application/vnd.github+json"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["files"][GIST_FILE]["content"]
            return json.loads(content)
    except Exception as e:
        print(f"⚠️ Warning: Could not fetch live Gist: {e}")
        return None

def patch_gist(token, payload):
    """PATCH the updated champions.json to the GitHub Gist."""
    url = f"https://api.github.com/gists/{GIST_ID}"
    next_ver = payload.get("version", 1)
    body = json.dumps({
        "description": f"RSL Champion Roster Update v{next_ver} (Autopilot)",
        "files": {
            GIST_FILE: {
                "content": json.dumps(payload, indent=2, ensure_ascii=False)
            }
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        method="PATCH",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "RSL-Mercy-Tracker-Scraper"
        }
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status in (200, 201)

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

    scraped_counts = {
        "mythical": len(mythicals),
        "void": len(void_legendaries),
        "nonVoid": len(non_void_legendaries),
        "total": len(mythicals) + len(void_legendaries) + len(non_void_legendaries)
    }

    print(f"✅ Successfully scraped {scraped_counts['total']} champions from AyumiLove:")
    print(f"   • Mythicals: {scraped_counts['mythical']}")
    print(f"   • Void Legendaries: {scraped_counts['void']}")
    print(f"   • Non-Void Legendaries: {scraped_counts['nonVoid']}")

    # Check against live Gist
    current_gist = fetch_current_gist()
    recently_added = []
    has_changes = False
    gist_version = current_gist.get("version", 1) if current_gist else 1

    if current_gist:
        gist_map = {}
        for name in current_gist.get("mythicalChampions", []):
            gist_map[normalize_name(name)] = {"name": name, "rarity": "mythical"}
        for name in current_gist.get("voidLegendaries", []):
            gist_map[normalize_name(name)] = {"name": name, "rarity": "void"}
        for name in current_gist.get("nonVoidLegendaries", []):
            gist_map[normalize_name(name)] = {"name": name, "rarity": "nonvoid"}

        def check_delta(candidates, target_rarity):
            nonlocal has_changes
            for name in candidates:
                norm = normalize_name(name)
                if norm not in gist_map:
                    recently_added.append({"name": name, "rarity": target_rarity})
                    has_changes = True
                elif gist_map[norm]["rarity"] != target_rarity:
                    recently_added.append({
                        "name": gist_map[norm]["name"],
                        "rarity": target_rarity,
                        "isMove": True,
                        "oldRarity": gist_map[norm]["rarity"]
                    })
                    has_changes = True

        check_delta(mythicals, "mythical")
        check_delta(void_legendaries, "void")
        check_delta(non_void_legendaries, "nonvoid")

    now_iso = datetime.now(timezone.utc).isoformat()
    gist_token = os.environ.get("GIST_TOKEN", "").strip()

    if has_changes:
        print(f"⚡ Autopilot Delta Detected: {len(recently_added)} update(s):")
        for item in recently_added:
            tag = "MOVE" if item.get("isMove") else "NEW"
            print(f"   • [{tag}] {item['name']} ({item['rarity']})")

        if gist_token and current_gist:
            next_version = gist_version + 1
            # Build merged sets preserving existing names
            staged_norm_map = {normalize_name(item["name"]): item for item in recently_added}
            
            merged_mythicals = [n for n in current_gist.get("mythicalChampions", []) if normalize_name(n) not in staged_norm_map]
            merged_voids = [n for n in current_gist.get("voidLegendaries", []) if normalize_name(n) not in staged_norm_map]
            merged_non_voids = [n for n in current_gist.get("nonVoidLegendaries", []) if normalize_name(n) not in staged_norm_map]

            for item in recently_added:
                if item["rarity"] == "mythical":
                    merged_mythicals.append(item["name"])
                elif item["rarity"] == "void":
                    merged_voids.append(item["name"])
                else:
                    merged_non_voids.append(item["name"])

            new_payload = {
                "version": next_version,
                "lastAutopilotRun": now_iso,
                "recentlyAdded": recently_added,
                "mythicalChampions": sorted(list(set(merged_mythicals)), key=lambda s: s.lower()),
                "voidLegendaries": sorted(list(set(merged_voids)), key=lambda s: s.lower()),
                "nonVoidLegendaries": sorted(list(set(merged_non_voids)), key=lambda s: s.lower())
            }

            try:
                patch_gist(gist_token, new_payload)
                print(f"🚀 Autopilot: Successfully PATCHed Gist to version v{next_version}!")
                gist_version = next_version
            except Exception as e:
                print(f"❌ Autopilot: Failed to PATCH Gist: {e}")
        else:
            if not gist_token:
                print("ℹ️ GIST_TOKEN not set; skipping auto-PATCH (staged in local file for manual review).")
    else:
        print(f"🎉 Gist (v{gist_version}) is 100% in sync with AyumiLove! No new champions.")

    # Save snapshot locally for web app / offline usage
    local_result = {
        "lastScraped": now_iso,
        "lastAutopilotRun": now_iso,
        "source": URL,
        "gistVersion": gist_version,
        "counts": scraped_counts,
        "recentlyAdded": recently_added if has_changes else (current_gist.get("recentlyAdded", []) if current_gist else []),
        "mythicalChampions": sorted(list(mythicals), key=lambda s: s.lower()),
        "voidLegendaries": sorted(list(void_legendaries), key=lambda s: s.lower()),
        "nonVoidLegendaries": sorted(list(non_void_legendaries), key=lambda s: s.lower())
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(local_result, f, indent=2, ensure_ascii=False)

    print(f"Saved local snapshot to: {OUTPUT_FILE}")
    return local_result

if __name__ == "__main__":
    scrape_ayumilove()
