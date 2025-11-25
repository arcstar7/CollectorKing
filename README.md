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
Expected to provide a setup_logging() function and configure the CollectorKing logger.

⚙️ Requirements
Python 3.10+ (3.8+ may work, but 3.10+ recommended)

Python packages:

PySide6

requests

Install dependencies:

bash
Copy code
pip install PySide6 requests
(Optional) Create a virtual environment:

bash
Copy code
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
🚀 Getting Started
Clone / copy the project

bash
Copy code
git clone <your-repo-url> ygo-desktop-library
cd ygo-desktop-library
Ensure the folder has at least:

text
Copy code
main.py
rarity_resolver.py
logging_setup.py   # you create this file
Install dependencies

bash
Copy code
pip install PySide6 requests
Run the app

bash
Copy code
python main.py
On first run, the app will:

Create ygo_collection.db and the cards table (if they don’t exist).

Create the images/ directory for image caching.

📊 CSV Import Format
The Import CSV button expects a file with at least a set code column.
The app is flexible with header names and will normalize them.

Supported header names
Matching is case-insensitive and ignores spaces, underscores, and hyphens.

Set Code (required)
Any of:

set_code

setcode

code

printcode

cardsetcode

cardcode

Rarity (optional)
Any of:

rarity

setrarity

printrarity

Quantity (optional, defaults to 1)
Any of:

quantity

qty

count

amount

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

🧠 Rarity & Pricing Logic
During Import
For each row in the CSV:

Normalize rarity

Uses an internal RARITY_ALIASES map to normalize known aliases:

e.g. "qcse" → "Quarter Century Secret Rare"

e.g. "collectors rare" / "cr" → "Collector's Rare"

Resolve missing rarity

If no rarity is provided (or it’s unknown):

Calls fetch_rarities_by_set_code(set_code) from rarity_resolver.py.

If multiple rarities are returned:

User gets a modal dialog to select the correct rarity.

If one rarity is returned:

Uses that rarity automatically.

Upsert into database

Calls something like upsert_card_from_set_code(set_code, rarity, quantity) which:

Fetches card info from YGOPRODeck (cardsetsinfo.php).

Gets:

Card name

Set name

Default rarity

Default set price

If a rarity is provided:

Attempts rarity-specific pricing via fetch_price_for_set_code_and_rarity.

Falls back to set_price when rarity-specific pricing isn’t available.

Downloads up to 3 images:

Saves their paths in image_paths as a comma-separated list.

Inserts or updates the row in the cards table.

Updates last_updated with the current timestamp.

Refresh Prices
When you click Refresh Prices:

A background worker iterates over all cards in the database.

For each card:

If a rarity is set:

Tries to pull rarity-specific pricing via fetch_price_for_set_code_and_rarity.

If no rarity:

Uses the API-provided default set_rarity and set_price.

Updates price (and possibly rarity) in the DB.

Refreshes the UI and total collection value when complete.

🖱️ UI Usage
Main Table
For each card, the main table shows:

Thumbnail image (first path in image_paths)

Card name

Set code

Set name

Rarity

Unit price

Quantity

Line total (price × quantity)

Last updated

Actions
Import CSV

Prompts for a CSV file.

Auto-detects delimiter.

Maps headers to expected fields.

Resolves set codes/rarities via the API.

Shows a summary of successes/errors at the end.

Refresh Prices

Runs a background price refresh for all cards in the DB.

Updates table values and the grand total when done.

Export CSV

Exports the current collection to a CSV with columns like:

set_code

name

set_name

rarity

quantity

unit_price

line_total

image_paths

last_updated

Editing Quantities
Double-click the Quantity cell for a card.

Enter the new quantity and confirm.

The app:

Updates the database record.

Recalculates line total.

Recalculates the grand total.

🧾 Logging
The app expects a logging_setup.py with a function:

python
Copy code
def setup_logging():
    ...
A simple example:

python
Copy code
import logging
import os

def setup_logging():
    level = logging.DEBUG if os.getenv("COLLECTORKING_DEBUG") == "1" else logging.INFO
    logger = logging.getLogger("CollectorKing")
    logger.setLevel(level)

    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setLevel(level)
        formatter = logging.Formatter(
            "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"
        )
        ch.setFormatter(formatter)
        logger.addHandler(ch)
main.py then does something like:

python
Copy code
from logging_setup import setup_logging

setup_logging()
logger = logging.getLogger("CollectorKing.main")
📌 Notes & Limitations
🌐 Internet required
All metadata, images, and prices are retrieved from the YGOPRODeck API.

🔑 No API key required
(As currently implemented), but you should:

Respect YGOPRODeck rate limits.

Cache results whenever possible.

🗄️ Database schema
The schema is simple and opinionated.
If you change it, make sure to update:

DB initialization logic

Upsert/update code

Any queries that assume the old structure.

🧩 Next Steps / Ideas
Add card search & filtering in the UI.

Support multiple collections / profiles.

Add automatic backup/export on exit.

Track purchase price vs current price for profit/loss views.
