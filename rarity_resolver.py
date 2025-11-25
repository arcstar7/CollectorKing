# coding=utf-8
# rarity_resolver.py
from __future__ import annotations

import requests
from urllib.parse import quote

YGOPRO_BASE = "https://db.ygoprodeck.com/api/v7"

def fetch_rarities_by_set_code(set_code: str) -> list[str]:
    """
    Returns a sorted list of distinct rarities that exist for the given printed set code
    (e.g., 'SOI-EN001') by querying YGOPRODeck cardinfo for that setcode.

    If the API is unavailable or nothing matches, returns [].
    """
    if not set_code:
        return []

    url = f"{YGOPRO_BASE}/cardinfo.php?setcode={quote(set_code)}"
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        return []

    rarities = set()
    for card in payload.get("data", []):
        for cs in card.get("card_sets", []) or []:
            # Match the exact printed code
            if str(cs.get("set_code", "")).strip().upper() == set_code.strip().upper():
                r = (cs.get("set_rarity") or "").strip()
                if r:
                    rarities.add(r)

    # Basic ranking so defaults are sensible; tweak to your taste.
    rank = {
        "Common": 100,
        "Rare": 90,
        "Super Rare": 80,
        "Ultra Rare": 70,
        "Ultimate Rare": 60,
        "Secret Rare": 50,
        "Prismatic Secret Rare": 40,
        "Collector's Rare": 30,
        "Starlight Rare": 20,
        "Ghost Rare": 10,
    }
    return sorted(rarities, key=lambda r: rank.get(r, 999))


def fetch_price_for_set_code_and_rarity(set_code: str, rarity: str) -> float | None:
    """
    Attempts to find the price for the specific (set_code, rarity) combo by scanning
    YGOPRODeck cardinfo. Returns float or None if not found.
    """
    if not set_code or not rarity:
        return None

    url = f"{YGOPRO_BASE}/cardinfo.php?setcode={quote(set_code)}"
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        return None

    rarity_norm = rarity.strip().lower()
    for card in payload.get("data", []):
        for cs in card.get("card_sets", []) or []:
            if str(cs.get("set_code", "")).strip().upper() == set_code.strip().upper():
                r = (cs.get("set_rarity") or "").strip()
                if r and r.strip().lower() == rarity_norm:
                    try:
                        return float(cs.get("set_price") or 0.0)
                    except Exception:
                        return None
    return None
