# coding=utf-8
import csv
import io
import os
import sqlite3
import sys
import threading
import time
import uuid
import logging
from datetime import datetime
from urllib.parse import quote

import requests
from PySide6 import QtCore, QtGui, QtWidgets

# Logging (expects logging_setup.py as shared earlier)
from logging_setup import setup_logging

# Multi-rarity helpers
from rarity_resolver import (
    fetch_rarities_by_set_code,
    fetch_price_for_set_code_and_rarity,
)

APP_NAME = "YGO Desktop Library"
DB_FILE = "ygo_collection.db"
IMG_DIR = os.path.join("images")
os.makedirs(IMG_DIR, exist_ok=True)

# Initialize logging as early as possible
logger = setup_logging()  # honors COLLECTORKING_DEBUG=1 for DEBUG level
log = logging.getLogger("CollectorKing").getChild("main")

# ---------- Small logger adapter for per-run context ----------
class Ctx(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        extra = {**self.extra, **kwargs.pop("extra", {})}
        return msg, {"extra": extra, **kwargs}

# -------------------------------------------------------------------
# Optional: allow shorthand/variant rarity inputs from CSV (QCSE, etc.)
# -------------------------------------------------------------------
RARITY_ALIASES = {
    "qcse": "Quarter Century Secret Rare",
    "quarter century secret rare": "Quarter Century Secret Rare",
    "platinum secret": "Platinum Secret Rare",
    "psr": "Platinum Secret Rare",
    "collectors rare": "Collector's Rare",      # no apostrophe
    "collector’s rare": "Collector's Rare",     # curly apostrophe
    "prismatic secret": "Prismatic Secret Rare",
    # add more as you like...
}

def normalize_rarity_text(s: str | None) -> str:
    t = (s or "").strip()
    if not t:
        return ""
    key = t.lower().replace("’", "'")
    return RARITY_ALIASES.get(key, t)

# ---------------------------
# Database helpers (sqlite3)
# ---------------------------

def db_connect():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def db_init():
    log.debug("Initializing database", extra={"db": DB_FILE})
    conn = db_connect()
    conn.execute(
        """
      CREATE TABLE IF NOT EXISTS cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        set_code TEXT UNIQUE,
        name TEXT,
        set_name TEXT,
        rarity TEXT,
        price REAL,
        quantity INTEGER,
        image_paths TEXT,
        ygopro_id INTEGER,
        last_updated TEXT
      )
    """
    )
    conn.commit()
    conn.close()


def db_upsert(card):
    conn = db_connect()
    try:
        conn.execute(
            """
          INSERT INTO cards (set_code, name, set_name, rarity, price, quantity, image_paths, ygopro_id, last_updated)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
          ON CONFLICT(set_code) DO UPDATE SET
            name=excluded.name,
            set_name=excluded.set_name,
            rarity=excluded.rarity,
            price=excluded.price,
            quantity=excluded.quantity,
            image_paths=excluded.image_paths,
            ygopro_id=excluded.ygopro_id,
            last_updated=excluded.last_updated
        """,
            (
                card["set_code"],
                card["name"],
                card["set_name"],
                card["rarity"],
                card["price"],
                card["quantity"],
                card["image_paths"],
                card["ygopro_id"],
                card["last_updated"],
            ),
        )
        conn.commit()
    except Exception:
        log.error("DB upsert failed", extra={"set_code": card.get("set_code")}, exc_info=True)
        raise
    finally:
        conn.close()


def db_all():
    conn = db_connect()
    try:
        rows = conn.execute("SELECT * FROM cards ORDER BY name ASC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def db_set_quantity(set_code, qty):
    conn = db_connect()
    try:
        conn.execute(
            "UPDATE cards SET quantity=?, last_updated=? WHERE set_code=?",
            (qty, datetime.utcnow().isoformat(timespec="seconds"), set_code),
        )
        conn.commit()
        log.debug("Quantity updated", extra={"set_code": set_code, "qty": qty})
    except Exception:
        log.error("Failed to update quantity", extra={"set_code": set_code, "qty": qty}, exc_info=True)
        raise
    finally:
        conn.close()


def db_update_price(set_code, price, rarity=None):
    conn = db_connect()
    try:
        if rarity is None:
            conn.execute(
                "UPDATE cards SET price=?, last_updated=? WHERE set_code=?",
                (price, datetime.utcnow().isoformat(timespec="seconds"), set_code),
            )
        else:
            conn.execute(
                "UPDATE cards SET price=?, rarity=?, last_updated=? WHERE set_code=?",
                (price, rarity, datetime.utcnow().isoformat(timespec="seconds"), set_code),
            )
        conn.commit()
        log.debug("Price updated", extra={"set_code": set_code, "price": price, "rarity": rarity})
    except Exception:
        log.error("Failed to update price", extra={"set_code": set_code}, exc_info=True)
        raise
    finally:
        conn.close()

# ---------------------------
# API helpers (YGOPRODeck v7)
# ---------------------------
YGOPRO_BASE = "https://db.ygoprodeck.com/api/v7"


def api_get_set_info(set_code: str):
    """Card Set Info by printed set code (id, name, set_name, set_code, set_rarity, set_price)."""
    url = f"{YGOPRO_BASE}/cardsetsinfo.php?setcode={quote(set_code)}"
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, dict) and data.get("set_code"):
            return data
        raise ValueError(f"No data for set_code {set_code}")
    except Exception:
        log.error("api_get_set_info failed", extra={"set_code": set_code, "url": url}, exc_info=True)
        raise


def api_get_images_by_id(ygopro_id: int):
    """ Card Info by id to obtain image URLs. """
    url = f"{YGOPRO_BASE}/cardinfo.php?id={ygopro_id}"
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        if "data" not in data or not data["data"]:
            return []
        imgs = data["data"][0].get("card_images", [])
        out = []
        for im in imgs:
            if "image_url" in im:
                out.append(im["image_url"])
            elif "image_url_small" in im:
                out.append(im["image_url_small"])
        return out
    except Exception:
        log.error("api_get_images_by_id failed", extra={"ygopro_id": ygopro_id, "url": url}, exc_info=True)
        raise


def download_image(url: str, filename_hint: str) -> str:
    ext = os.path.splitext(url.split("?")[0])[1]
    if not ext or len(ext) > 5:
        ext = ".jpg"
    fname = f"{filename_hint}{ext}"
    path = os.path.join(IMG_DIR, fname)
    if os.path.exists(path):
        return path
    try:
        with requests.get(url, stream=True, timeout=30) as resp:
            resp.raise_for_status()
            with open(path, "wb") as f:
                for chunk in resp.iter_content(8192):
                    if chunk:
                        f.write(chunk)
        return path
    except Exception:
        log.warning("Image download failed", extra={"url": url, "hint": filename_hint}, exc_info=True)
        raise


def upsert_card_from_set_code(set_code: str, rarity_override: str | None, quantity: int):
    """
    Inserts/updates a card row based on printed set_code.
    If rarity_override is provided, it will be saved.
    If provided, we also try to fetch the price for that exact rarity (if available).
    """
    info = api_get_set_info(set_code)
    ygopro_id = int(info.get("id"))
    name = info.get("name")
    set_name = info.get("set_name")

    # Price logic
    rarity = (rarity_override.strip() if rarity_override else info.get("set_rarity"))
    price = None

    if rarity_override:
        # Try to pull an exact price for the chosen rarity
        price = fetch_price_for_set_code_and_rarity(set_code, rarity_override)

    if price is None:
        # Fallback to default set price from cardsetsinfo
        price = float(info.get("set_price") or 0.0)
    else:
        price = float(price or 0.0)

    # images
    urls = api_get_images_by_id(ygopro_id)
    local_paths = []
    for idx, url in enumerate(urls[:3]):
        hint = f"{set_code.replace('/', '_')}_{idx}"
        try:
            p = download_image(url, hint)
            local_paths.append(p.replace("\\", "/"))
        except Exception:
            # already logged in download_image
            pass

    db_upsert(
        {
            "set_code": set_code,
            "name": name,
            "set_name": set_name,
            "rarity": rarity or "",
            "price": price,
            "quantity": int(quantity or 1),
            "image_paths": ",".join(local_paths),
            "ygopro_id": ygopro_id,
            "last_updated": datetime.utcnow().isoformat(timespec="seconds"),
        }
    )

# ---------------------------
# Qt Model / UI
# ---------------------------
HEADERS = ["Image", "Name", "Set Code", "Set", "Rarity", "Quantity", "Unit Price", "Line Total", "Last Updated"]


def _is_missing_rarity(r: str | None) -> bool:
    r0 = (r or "").strip().lower()
    return r0 in ("", "unknown", "n/a", "na", "none", "null")


class CardTableModel(QtCore.QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self.rows = []

    def load(self):
        self.beginResetModel()
        self.rows = db_all()
        self.endResetModel()

    def rowCount(self, parent=None):
        return len(self.rows)

    def columnCount(self, parent=None):
        return len(HEADERS)

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
            return HEADERS[section]
        return None

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.ItemIsEnabled
        flags = super().flags(index)
        # Quantity editable
        if index.column() == 5:
            flags |= QtCore.Qt.ItemIsEditable
        return flags

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        r = self.rows[index.row()]
        col = index.column()

        if role == QtCore.Qt.DecorationRole and col == 0:
            # show first image as thumbnail
            img_paths = (r.get("image_paths") or "").split(",")
            p = img_paths[0].strip() if img_paths and img_paths[0].strip() else ""
            if p and os.path.exists(p):
                pix = QtGui.QPixmap(p)
                if not pix.isNull():
                    return pix.scaled(90, 130, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            return None

        if role == QtCore.Qt.DisplayRole:
            if col == 0:
                return ""  # image column
            if col == 1:
                return r.get("name") or ""
            if col == 2:
                return r.get("set_code") or ""
            if col == 3:
                return r.get("set_name") or ""
            if col == 4:
                return r.get("rarity") or ""
            if col == 5:
                return str(r.get("quantity") or 1)
            if col == 6:
                return f"${(r.get('price') or 0.0):.2f}"
            if col == 7:
                qty = r.get("quantity") or 1
                price = r.get("price") or 0.0
                return f"${(qty*price):.2f}"
            if col == 8:
                return r.get("last_updated") or ""
        return None

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        if not index.isValid() or index.column() != 5 or role != QtCore.Qt.EditRole:
            return False
        r = self.rows[index.row()]
        set_code = r["set_code"]
        try:
            qty = int(str(value).strip())
            if qty < 0:
                qty = 0
        except Exception:
            qty = r.get("quantity") or 1
        try:
            db_set_quantity(set_code, qty)
            # refresh local
            self.rows[index.row()]["quantity"] = qty
            self.dataChanged.emit(index, index)
            # also update line total cell
            lt_idx = self.index(index.row(), 7)
            self.dataChanged.emit(lt_idx, lt_idx)
            return True
        except Exception:
            log.error("Failed to set quantity from UI", extra={"set_code": set_code, "qty": qty}, exc_info=True)
            return False


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1100, 720)

        # Top bar
        toolbar = QtWidgets.QToolBar()
        self.addToolBar(toolbar)

        import_action = QtGui.QAction("Import CSV", self)
        import_action.triggered.connect(self.import_csv)
        toolbar.addAction(import_action)

        refresh_action = QtGui.QAction("Refresh Prices", self)
        refresh_action.triggered.connect(self.refresh_prices)
        toolbar.addAction(refresh_action)

        export_action = QtGui.QAction("Export CSV", self)
        export_action.triggered.connect(self.export_csv)
        toolbar.addAction(export_action)

        # Total label
        self.total_lbl = QtWidgets.QLabel("Total: $0.00")
        self.total_lbl.setStyleSheet("font-weight:600; margin-left:12px;")
        toolbar.addWidget(self.total_lbl)

        # Table
        self.model = CardTableModel()
        self.table = QtWidgets.QTableView()
        self.table.setModel(self.model)
        self.table.verticalHeader().setDefaultSectionSize(134)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.DoubleClicked | QtWidgets.QAbstractItemView.SelectedClicked
        )
        self.table.setColumnWidth(0, 110)
        self.table.setColumnWidth(1, 260)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 200)
        self.table.setColumnWidth(4, 120)
        self.table.setColumnWidth(5, 90)
        self.table.setColumnWidth(6, 100)
        self.table.setColumnWidth(7, 110)
        self.table.horizontalHeader().setStretchLastSection(True)

        self.setCentralWidget(self.table)

        # Status
        self.status = self.statusBar()

        # Load
        self.reload_table()

        # Recompute total when model changes
        self.model.dataChanged.connect(lambda *_: self.update_total())
        self.model.modelReset.connect(lambda: self.update_total())

    def reload_table(self):
        self.model.load()
        self.update_total()

    def update_total(self):
        rows = self.model.rows
        total = sum((r.get("price") or 0.0) * (r.get("quantity") or 1) for r in rows)
        self.total_lbl.setText(f"Total: ${total:.2f}")

    # --------------------------
    # Rarity chooser (Qt modal)
    # --------------------------
    def _choose_rarity_modal(self, set_code: str, candidates: list[str]) -> str:
        """
        Shows a blocking modal dropdown to choose a rarity.
        Returns a valid choice. Defaults to the first item if user cancels.
        """
        item, ok = QtWidgets.QInputDialog.getItem(
            self,
            f"Select rarity for {set_code}",
            f"Multiple rarities found for {set_code}. Please choose:",
            candidates,
            0,
            False,
        )
        return item if ok and item else candidates[0]

    # --------------------------
    # Actions
    # --------------------------
    def import_csv(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select CSV", "", "CSV Files (*.csv)")
        if not path:
            return

        run_id = str(uuid.uuid4())[:8]
        ctx = Ctx(log, {"run_id": run_id, "import_file": path})
        ctx.info("Starting CSV import")

        # --- Read file robustly & sniff dialect ---
        try:
            with open(path, "rb") as fb:
                raw = fb.read()
        except Exception:
            ctx.error("Failed to read file", exc_info=True)
            QtWidgets.QMessageBox.critical(self, "Import", "Could not read the file.")
            return

        # Strip possible UTF-8 BOM
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
        try:
            text = raw.decode("utf-8", errors="ignore")
        except Exception:
            ctx.error("Failed to decode file as UTF-8", exc_info=True)
            QtWidgets.QMessageBox.critical(self, "Import", "Could not decode the file as UTF-8.")
            return

        # Try to sniff delimiter; fall back to comma
        try:
            first_line = text.splitlines()[0] if text else ""
            sniff = csv.Sniffer().sniff(first_line, delimiters=[",", ";", "\t", "|"])
            dialect = sniff
            ctx.debug("Delimiter sniffed", extra={"delimiter": dialect.delimiter})
        except Exception:
            class _D:
                delimiter = ","
            dialect = _D()
            ctx.debug("Using default delimiter", extra={"delimiter": ","})

        reader = csv.DictReader(io.StringIO(text), delimiter=dialect.delimiter)

        # --- Normalize headers (more variants accepted) ---
        def norm_key(k: str) -> str:
            return (k or "").strip().lower().replace(" ", "").replace("-", "").replace("_", "")

        header_map = {k: norm_key(k) for k in (reader.fieldnames or [])}
        ctx.debug("Headers detected", extra={"headers": ",".join(reader.fieldnames or [])})

        def get_set_code(row: dict) -> str:
            # Accept many variants
            for k, nk in header_map.items():
                if nk in ("setcode", "code", "printcode", "cardsetcode", "cardcode"):
                    v = (row.get(k) or "").strip()
                    if v:
                        return v
            return ""

        def get_rarity(row: dict) -> str:
            for k, nk in header_map.items():
                if nk in ("rarity", "setrarity", "printrarity"):
                    return (row.get(k) or "").strip()
            return ""

        def get_qty(row: dict) -> int:
            for k, nk in header_map.items():
                if nk in ("quantity", "qty", "count", "amount"):
                    v = (row.get(k) or "").strip()
                    if v.isdigit():
                        return int(v)
                    try:
                        return int(float(v))
                    except Exception:
                        pass
            return 1

        rows = list(reader)
        if not rows:
            ctx.warning("CSV appears empty or unreadable")
            QtWidgets.QMessageBox.warning(self, "Import", "CSV appears empty or unreadable.")
            return

        # UI progress
        progress = QtWidgets.QProgressDialog("Importing…", "Cancel", 0, len(rows), self)
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.setMinimumDuration(0)

        ok, err = 0, 0
        error_msgs = []  # keep first 20
        for i, row in enumerate(rows, 1):
            progress.setValue(i - 1)
            if progress.wasCanceled():
                ctx.info("User canceled import", extra={"processed": i - 1})
                break

            set_code = get_set_code(row)
            if not set_code:
                err += 1
                if len(error_msgs) < 20:
                    cols = ", ".join(reader.fieldnames or [])
                    error_msgs.append(f"Row {i}: missing set code (columns found: {cols})")
                ctx.warning("Missing set_code in row", extra={"row": i})
                continue

            rarity = get_rarity(row) or None
            # Optional: allow shorthand (QCSE, Collectors Rare, etc.)
            rarity = normalize_rarity_text(rarity)

            qty = get_qty(row)

            try:
                # Resolve rarity if missing/unknown
                if _is_missing_rarity(rarity):
                    candidates = fetch_rarities_by_set_code(set_code)
                    if len(candidates) > 1:
                        rarity = self._choose_rarity_modal(set_code, candidates)
                    elif len(candidates) == 1:
                        rarity = candidates[0]
                    # else: keep None and fall back to API default

                upsert_card_from_set_code(set_code, rarity, qty)
                ok += 1
                if ok % 25 == 0:
                    ctx.info("Progress", extra={"ok": ok, "err": err, "row": i})
                QtWidgets.QApplication.processEvents()
                time.sleep(0.01)
            except Exception as e:
                err += 1
                if len(error_msgs) < 20:
                    error_msgs.append(f"Row {i} ({set_code}): {e}")
                ctx.error("Row failed", extra={"row": i, "set_code": set_code}, exc_info=True)

        progress.setValue(len(rows))
        self.reload_table()

        # Visible summary
        detail = ""
        if error_msgs:
            detail = "\n\nIssues (first 20):\n- " + "\n- ".join(error_msgs)
        QtWidgets.QMessageBox.information(
            self,
            "Import complete",
            f"Imported: {ok}\nFailed: {err}{detail}",
        )
        ctx.info("IMPORT_SUMMARY", extra={"ok": ok, "err": err, "total": len(rows)})
        self.status.showMessage(f"Import complete: {ok} ok, {err} failed.", 5000)

    def refresh_prices(self):
        rows = db_all()
        if not rows:
            return

        def worker():
            upd, fail = 0, 0
            worker_log = log.getChild("refresh")
            for r in rows:
                try:
                    info = api_get_set_info(r["set_code"])
                    # If user already set a rarity, respect it and try to update with the exact rarity price
                    existing_rarity = (r.get("rarity") or "").strip()
                    if existing_rarity:
                        price = fetch_price_for_set_code_and_rarity(r["set_code"], existing_rarity)
                        if price is None:
                            price = float(info.get("set_price") or 0.0)
                        db_update_price(r["set_code"], float(price or 0.0), None)
                    else:
                        # Keep API-provided rarity only when DB rarity is blank
                        price = float(info.get("set_price") or 0.0)
                        rarity = info.get("set_rarity")
                        db_update_price(r["set_code"], price, rarity)
                    upd += 1
                    if upd % 50 == 0:
                        worker_log.info("Refresh progress", extra={"updated": upd, "failed": fail})
                    time.sleep(0.02)
                except Exception:
                    worker_log.error("Refresh failed", extra={"set_code": r.get('set_code')}, exc_info=True)
                    fail += 1
            QtCore.QMetaObject.invokeMethod(
                self,
                "_refresh_done",
                QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(int, upd),
                QtCore.Q_ARG(int, fail),
            )

        threading.Thread(target=worker, daemon=True).start()
        self.status.showMessage("Refreshing prices")

    @QtCore.Slot(int, int)
    def _refresh_done(self, upd, fail):
        self.reload_table
        self.reload_table()
        log.info("Prices refreshed", extra={"updated": upd, "failed": fail})
        self.status.showMessage(f"Prices refreshed: {upd} updated, {fail} failed.", 5000)

    def export_csv(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export CSV", "ygo_library_export.csv", "CSV Files (*.csv)")
        if not path:
            return
        rows = db_all()
        try:
            with open(path, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(
                    [
                        "set_code",
                        "name",
                        "set_name",
                        "rarity",
                        "quantity",
                        "unit_price",
                        "line_total",
                        "image_paths",
                        "last_updated",
                    ]
                )
                for r in rows:
                    qty = r.get("quantity") or 1
                    price = r.get("price") or 0.0
                    w.writerow(
                        [
                            r.get("set_code") or "",
                            r.get("name") or "",
                            r.get("set_name") or "",
                            r.get("rarity") or "",
                            qty,
                            f"{price:.2f}",
                            f"{(qty*price):.2f}",
                            r.get("image_paths") or "",
                            r.get("last_updated") or "",
                        ]
                    )
            log.info("Export complete", extra={"path": path, "rows": len(rows)})
            QtWidgets.QMessageBox.information(self, "Export", "Export complete.")
        except Exception:
            log.error("Export failed", extra={"path": path}, exc_info=True)
            QtWidgets.QMessageBox.critical(self, "Export", "Failed to write CSV.")


def main():
    log.info("Application started")
    try:
        db_init()
        app = QtWidgets.QApplication(sys.argv)
        win = MainWindow()
        win.show()
        sys.exit(app.exec())
    except Exception:
        log.critical("Fatal error in main()", exc_info=True)
        raise


if __name__ == "__main__":
    main()
