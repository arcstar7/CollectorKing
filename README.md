# CollectorKing
Yugioh TCG Collector Application Portfolio
A small desktop app for managing a local Yu-Gi-Oh! TCG collection, backed by SQLite and powered by the YGOPRODeck API. Import your collection from CSV, automatically resolve card names/rarities/prices, cache images, and view totals in a PySide6 (Qt) UI. 

main

Features

CSV import of collection

Accepts a CSV of printed set codes (e.g. SOI-EN001) plus optional rarity & quantity.

Robust header handling (accepts set_code, code, printcode, cardsetcode, cardcode, etc.).

Optional rarity column with shorthand handling (e.g. QCSE, Collectors Rare). 

main

Automatic card metadata lookup

Uses cardsetsinfo.php from YGOPRODeck to fetch name, set name, default rarity, and price for each set code.

Downloads card images via cardinfo.php and caches them under images/. 

main

Multi-rarity resolution

Normalizes alias inputs like qcse, platinum secret, collectors rare, etc.

If rarity is missing/unknown, queries cardinfo.php to find all rarities for the set code.

If multiple rarities exist, shows a modal dialog so you can pick the correct one.

Accurate rarity-specific pricing

Uses fetch_price_for_set_code_and_rarity to retrieve price for the exact (set_code, rarity) from YGOPRODeck when possible. 

rarity_resolver

Falls back to set_price from cardsetsinfo if a rarity-specific price isn’t available. 

main

SQLite collection database

Stores cards in ygo_collection.db in a cards table with fields: set_code, name, set_name, rarity, price, quantity, image_paths, ygopro_id, last_updated. 

main

Desktop UI (PySide6 / Qt)

Tabular view of your collection with:

Thumbnail image

Name, set code, set name, rarity

Editable quantity

Unit price, line total, last updated

Live total value displayed in the toolbar.

Actions: Import CSV, Refresh Prices, Export CSV. 

main

Logging

Uses a dedicated CollectorKing logger and expects a shared logging_setup.py.

Honors a COLLECTORKING_DEBUG=1 environment variable to flip logging to DEBUG. 

main

Project Structure

main.py — main application entry point, Qt UI, database layer, CSV import/export, YGOPRODeck integration, and price refresh logic. 

main

rarity_resolver.py — helpers for resolving rarities & prices via YGOPRODeck (fetch_rarities_by_set_code, fetch_price_for_set_code_and_rarity). 

rarity_resolver

ygo_collection.db — SQLite database created on first run (if not present). 

main

images/ — local cache of downloaded card images (created automatically).

logging_setup.py — shared logging configuration module (expected, not included here). 

main

Requirements

Python 3.10+ (3.8+ should work, but tested with modern Python)

Dependencies:

PySide6

requests

Standard library modules (sqlite3, csv, logging, etc.) are already included. 

main

Install with:

pip install PySide6 requests

Setup & Running

Clone / copy the project files into a directory, e.g.:

ygo-desktop-library/
  main.py
  rarity_resolver.py
  logging_setup.py   # you provide this


Create a virtual environment (optional but recommended):

python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate


Install dependencies:

pip install PySide6 requests


Run the app:

python main.py


On first run, this will:

Create ygo_collection.db and the cards table (if missing).

Create the images/ directory for image caching.

CSV Import Format

The Import CSV button expects a file with at least a set code column. The app is flexible with header names and will normalize them. 

main

Supported header names

All matching is case-insensitive and ignores spaces/underscores/hyphens.

Set code (required) — any of:

set_code, setcode, code, printcode, cardsetcode, cardcode 

main

Rarity (optional) — any of:

rarity, setrarity, printrarity 

main

Quantity (optional, defaults to 1) — any of:

quantity, qty, count, amount 

main

Example CSV
set_code,rarity,quantity
SOI-EN001,Ultimate Rare,1
MFC-105,QCSE,2
LOB-001,,3


Behavior:

SOI-EN001 → uses provided rarity "Ultimate Rare" as-is.

MFC-105 → rarity alias "QCSE" will be normalized to "Quarter Century Secret Rare". 

main

LOB-001 → rarity is blank; the app will call fetch_rarities_by_set_code to discover rarities and may prompt you to choose if multiple exist.

Rarity & Pricing Logic

During import for each row:

Normalize rarity text with alias map (RARITY_ALIASES).

If rarity is missing/unknown, call fetch_rarities_by_set_code(set_code).

If multiple rarities: show a modal rarity picker.

If one rarity: use that.

Call upsert_card_from_set_code(set_code, rarity, quantity):

Fetch name, set name, default rarity, and set price via cardsetsinfo.php.

If rarity is provided, try fetch_price_for_set_code_and_rarity first.

Fallback to set_price from cardsetsinfo if rarity-specific price isn’t found.

Download up to 3 images and store comma-separated paths in image_paths.

Insert/update the row in cards with last_updated timestamp.

Refresh Prices:

For each card in the DB:

If a rarity is already set, try to pull the exact rarity price.

If no rarity, use API-provided set_rarity and set_price.

Update price (and sometimes rarity) and refresh the UI once done.

UI Usage

Import CSV
Load or update your collection. The app will:

Read the file (auto-sniff delimiter).

Map headers to expected fields.

Resolve each row via YGOPRODeck.

Show a summary of successes/failures at the end. 

main

Refresh Prices
Runs a background thread to refresh prices for all cards, updating the UI when complete. 

main

Export CSV
Exports the current collection to a CSV with:

set_code, name, set_name, rarity, quantity, unit_price, line_total, image_paths, last_updated. 

main

Editing quantities

Double-click the Quantity column for a card to edit.

Changes are written directly to the database and the line total / grand total are recalculated. 

main

Logging

The app expects a logging_setup.py that exposes setup_logging() and configures a CollectorKing logger. A typical minimalist implementation might:

Set up console/file handlers.

Use COLLECTORKING_DEBUG env var to switch level to DEBUG.

main.py calls setup_logging() as early as possible and then uses a nested logger (CollectorKing.main) plus a LoggerAdapter for per-run context during imports.

Notes & Limitations

Internet required: all metadata, images, and prices come from the YGOPRODeck public API.

No API key is required as written, but you should respect YGOPRODeck’s rate limits and usage policies.

Schema: the DB schema is simple and opinionated; if you extend it, keep db_init() and db_upsert() in sync.
