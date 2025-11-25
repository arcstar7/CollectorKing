# CollectorKing

A small desktop app for managing a local **Yu-Gi-Oh! TCG** collection, backed by **SQLite** and powered by the **YGOPRODeck API**.  

Import your collection from CSV, automatically resolve card names/rarities/prices, cache images, and view totals in a **PySide6 (Qt)** UI.

---

## ✨ Features

- 📥 **CSV import of collection**
  - Accepts a CSV of printed set codes (e.g. `SOI-EN001`) plus optional rarity & quantity.
  - Flexible header handling (e.g. `set_code`, `code`, `printcode`, `cardsetcode`, `cardcode`, etc.).
  - Optional rarity column with shorthand handling (e.g. `QCSE`, `Collectors Rare`).

- 🔍 **Automatic card metadata lookup**
  - Uses `cardsetsinfo.php` from YGOPRODeck to fetch:
    - Card name
    - Set name
    - Default rarity
    - Default price (set price)
  - Downloads card images via `cardinfo.php` and caches them under `images/`.

- 🎚️ **Multi-rarity resolution**
  - Normalizes alias inputs like `qcse`, `platinum secret`, `collectors rare`, etc.
  - If rarity is missing/unknown, queries `cardinfo.php` to find all rarities for the set code.
  - If multiple rarities exist, shows a modal dialog so you can pick the correct one.

- 💰 **Accurate rarity-specific pricing**
  - Uses `fetch_price_for_set_code_and_rarity` to retrieve price for the exact `(set_code, rarity)` when possible.
  - Falls back to `set_price` from `cardsetsinfo` if no rarity-specific price is available.

- 💾 **SQLite collection database**
  - Stores cards in `ygo_collection.db` in a `cards` table with fields:
    - `set_code`, `name`, `set_name`, `rarity`
    - `price`, `quantity`
    - `image_paths`, `ygopro_id`
    - `last_updated`

- 🖥️ **Desktop UI (PySide6 / Qt)**
  - Tabular view of your collection with:
    - Thumbnail image
    - Name, set code, set name, rarity
    - Editable quantity
    - Unit price, line total, last updated
  - Live total collection value displayed in the toolbar.
  - Actions: **Import CSV**, **Refresh Prices**, **Export CSV**.

- 📝 **Logging**
  - Uses a dedicated `CollectorKing` logger (via a shared `logging_setup.py`).
  - Supports `COLLECTORKING_DEBUG=1` environment variable to enable debug logging.

---

## 📂 Project Structure

```text
ygo-desktop-library/
├─ main.py             # Main PySide6 app, DB, CSV, YGOPRODeck integration, UI
├─ rarity_resolver.py  # Rarity & rarity-specific price helpers
├─ logging_setup.py    # Your logging config (expected, not included)
├─ ygo_collection.db   # SQLite DB (created at runtime)
└─ images/             # Cached card images (created at runtime)
Key files:

main.py
Application entry point. Contains:

Qt UI classes

Database initialization & upsert logic

CSV import/export logic

YGOPRODeck API integration

Price refresh background worker

rarity_resolver.py
Rarity/premium helper module with:

fetch_rarities_by_set_code(set_code)

fetch_price_for_set_code_and_rarity(set_code, rarity)

logging_setup.py
logging mainly for troubleshooting

⚙️ Requirements
Python 3.10+ (3.8+ may work, but 3.10+ recommended)

Python packages:

PySide6

requests

Install dependencies:

bash
'''pip install PySide6 requests'''

(Optional) Create a virtual environment:

bash

```
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
```


🚀 Getting Started

```
git clone https://github/com/arcstar7/CollectorKing
```

## Ensure the folder has at least:

```
main.py
rarity_resolver.py
logging_setup.py
```


## Install dependencies

bash

```
pip install PySide6 requests
```

## Run the app

python main.py


## On first run, the app will:

# 1. Create ygo_collection.db and the cards table (if they don’t exist).

# 2. Create the images/ directory for image caching.


# 📊 CSV Import Format

## The Import CSV button expects a file with at least a set code column.
## The app is flexible with header names and will normalize them.

### Supported header names
### Matching is case-insensitive and ignores spaces, underscores, and hyphens.

Set Code, Rarity, Quantity

Example CSV
csv
Copy code
set_code,rarity,quantity
SOI-EN001,Ultimate Rare,1
MFC-105,QCSE,2
LOB-001,,3
Behavior:

SOI-EN001
Uses the provided rarity "Ultimate Rare" as-is.

MFC-105
Rarity alias "QCSE" is normalized to "Quarter Century Secret Rare".

LOB-001
Rarity is blank:

App calls fetch_rarities_by_set_code("LOB-001").

If multiple rarities exist, it shows a popup to let you choose.

If only one rarity exists, that one is auto-selected.

🔑 No API key required
(As currently implemented), but you should:

PLEASE Respect YGOPRODeck rate limits.

Cache results whenever possible.

🧩 Next Steps / Ideas
Add card search & filtering in the UI.

Support multiple collections / profiles.

Add automatic backup/export on exit.

Track purchase price vs current price for profit/loss views.
