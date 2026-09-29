"""SQLite storage for Buxoro Eksport Monitor.

All writes go through transactions; the schema is created on first run.
"""
from __future__ import annotations
import sqlite3, json, os, re, shutil, datetime as dt
from pathlib import Path

BASE = Path(os.environ.get("EXPORT_APP_DATA", Path(__file__).resolve().parent.parent / "data"))
DB_PATH = BASE / "export.db"
BACKUP_DIR = BASE / "backups"

SCHEMA = """
PRAGMA journal_mode=DELETE;   -- single-file DB: safe for Google Drive sync (no -wal/-shm side files)
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS districts (
  code TEXT PRIMARY KEY,          -- 1706401
  name_uz TEXT NOT NULL,          -- Бухоро шаҳри
  name_short TEXT,                -- Бухоро ш  (номманом "Ҳудуди")
  name_ru TEXT,                   -- город Бухара
  order_no INTEGER
);

CREATE TABLE IF NOT EXISTS companies (
  inn TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  district_code TEXT REFERENCES districts(code),
  hudud TEXT,          -- номманом D  (Бухоро ш)
  tarmoq TEXT,         -- номманом S  (Электротехника саноати)
  rus_district TEXT,   -- номманом W  (город Бухара)
  uyushma TEXT,        -- номманом X  (02_Узэлтех)
  district_full TEXT,  -- номманом Z  (Бухоро шаҳри)
  kind TEXT NOT NULL DEFAULT 'sanoat',  -- sanoat | meva   (номманом AA)
  product TEXT,        -- номманом AB
  extras TEXT,         -- JSON: other номманом columns (T,U,V,Y,AC,AD,AE)
  source TEXT,         -- nomma-nom | baza | gtd
  confirmed INTEGER NOT NULL DEFAULT 1,
  excluded INTEGER NOT NULL DEFAULT 0,   -- memo row: listed in номманом but not counted in totals
  created_at TEXT DEFAULT (datetime('now','localtime')),
  updated_at TEXT
);

-- Monthly opening balances (history that was not loaded GTD-by-GTD)
CREATE TABLE IF NOT EXISTS opening_balances (
  inn TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'sanoat',   -- sanoat | meva (a company may have both)
  year INTEGER NOT NULL,
  month INTEGER NOT NULL,
  amount REAL NOT NULL,          -- ming USD
  through_date TEXT,             -- for the current month: data valid through this day
  source TEXT,
  PRIMARY KEY (inn, kind, year, month)
);

CREATE TABLE IF NOT EXISTS uploads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  filename TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  report_dates TEXT NOT NULL,    -- JSON list of report dates found in file
  loaded_at TEXT DEFAULT (datetime('now','localtime')),
  rows_total INTEGER, rows_bukhara INTEGER, rows_karantin INTEGER, rows_dup INTEGER,
  sum_sanoat REAL, sum_meva REAL,
  new_inns TEXT,                 -- JSON list
  status TEXT NOT NULL,          -- pending | saved | rejected | voided
  note TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_uploads_sha ON uploads(sha256) WHERE status='saved';

CREATE TABLE IF NOT EXISTS gtd_rows (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  upload_id INTEGER NOT NULL REFERENCES uploads(id),
  report_date TEXT NOT NULL,     -- «Дата выгрузки» (YYYY-MM-DD)
  dedup_key TEXT NOT NULL UNIQUE,-- post/date/no + item no
  kind TEXT NOT NULL,            -- sanoat | meva
  inn TEXT NOT NULL,
  exporter TEXT,
  district_code TEXT,            -- sanoat: company district; meva: grown district
  regime TEXT, tnved TEXT, product TEXT, country TEXT,
  qty REAL, netto REAL, stat_usd REAL, invoice_usd REAL,
  gtd_no TEXT, item_no TEXT,
  grown_region TEXT, grown_district TEXT,
  raw TEXT NOT NULL,             -- JSON of the full source row (all columns)
  voided INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_gtd_date ON gtd_rows(report_date);
CREATE INDEX IF NOT EXISTS ix_gtd_inn ON gtd_rows(inn);

CREATE TABLE IF NOT EXISTS prognoz (
  district_code TEXT NOT NULL REFERENCES districts(code),
  year INTEGER NOT NULL,
  kind TEXT NOT NULL,            -- all | sanoat | meva
  year_plan REAL,                -- yillik prognoz
  m9_plan REAL,                  -- 9 oylik prognoz
  period_plan REAL,              -- yil boshidan joriy oy oxirigacha prognoz
  cur_month_plan REAL,           -- joriy oy prognozi
  prev_year_base REAL,           -- o'tgan yil (masalan 2025 yil 1 oktyabr holatida) amalda
  prev_year_base_days INTEGER,   -- o'sha baza necha kunlik (273)
  months TEXT,                   -- JSON {"1": .., "12": ..} oylik reja (ixtiyoriy)
  PRIMARY KEY (district_code, year, kind)
);

CREATE TABLE IF NOT EXISTS karantin_opening (
  district_code TEXT NOT NULL REFERENCES districts(code),
  year INTEGER NOT NULL,
  ytd REAL NOT NULL DEFAULT 0,        -- meva-sabzavot YTD from the karantin svod sheet
  month INTEGER, month_amt REAL NOT NULL DEFAULT 0,
  through_date TEXT,
  PRIMARY KEY (district_code, year)
);

CREATE TABLE IF NOT EXISTS tnved_map (    -- HS code -> номманом tarmoq / uyushma (learned from existing companies)
  code TEXT PRIMARY KEY,                  -- 4-digit or 2-digit
  tarmoq TEXT, uyushma TEXT, votes REAL
);

CREATE TABLE IF NOT EXISTS template_inns (   -- companies listed in the Excel template's номманом (Sozlamalar -> 2)
  inn TEXT NOT NULL, category TEXT NOT NULL,   -- sanoat | meva (номманом AA)
  row INTEGER, district TEXT, yellow INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (inn, category)
);

-- ------------------------------------------------------------ customs base: company -> declaration -> item (the INN tree)
-- Every row of the monthly/yearly customs base («SQL Hokimyat baza») lands here, all years and both regimes (ЭК / ИМ).
-- companies (inn) <- declarations (decl_id) <- items (cmdt_id). Dictionaries: hs_codes, countries, unions, posts.
CREATE TABLE IF NOT EXISTS declarations (
  decl_id TEXT PRIMARY KEY,          -- customs DECL_ID
  inn TEXT NOT NULL,                 -- -> companies.inn
  regime TEXT NOT NULL,              -- ЭК | ИМ
  proc_code TEXT,                    -- Коди: 10 export, 11, 12, 61 … (ЭК) / 40 … (ИМ)
  year INTEGER NOT NULL, month INTEGER NOT NULL,
  rdate TEXT NOT NULL,               -- Расмийлаштирилган сана (YYYY-MM-DD) — the date every total is counted by
  gdate TEXT,                        -- дата (GTD date)
  gtd_no TEXT, post TEXT,            -- номер ГТД, Пост
  key TEXT NOT NULL,                 -- POST/gdate/NUMBER — the same key the daily GTD files use
  deal_code TEXT,                    -- 24-гр (nature of transaction)
  transport TEXT,                    -- G25: 20 rail, 30 road, 40 air …
  pnd TEXT,
  trade_country TEXT,                -- торгушая страна (code)
  country TEXT,                      -- страна отправления/назначения (name, as in the base)
  rate_usd REAL, rate_cur REAL,
  source TEXT NOT NULL DEFAULT 'baza'
);
CREATE INDEX IF NOT EXISTS ix_decl_inn ON declarations(inn, year);
CREATE INDEX IF NOT EXISTS ix_decl_key ON declarations(key);
CREATE TABLE IF NOT EXISTS items (
  cmdt_id TEXT PRIMARY KEY,          -- customs CMDT_ID
  decl_id TEXT NOT NULL REFERENCES declarations(decl_id) ON DELETE CASCADE,
  inn TEXT NOT NULL, regime TEXT NOT NULL, year INTEGER NOT NULL, month INTEGER NOT NULL, rdate TEXT NOT NULL,   -- copied from the declaration for fast sums
  gtd TEXT NOT NULL,                 -- declaration key (POST/gdate/NUMBER)
  key TEXT NOT NULL,                 -- gtd#item_no — dedup key against daily GTD rows
  item_no TEXT,
  hs10 TEXT, hs4 TEXT,               -- Код ТН ВЭД and its 4-digit head
  tovar1 TEXT, tovar2 TEXT,          -- classifier A: tarmoq -> sub-tarmoq
  sprav1 TEXT, sprav2 TEXT,          -- classifier B: product group -> product name
  unit TEXT, qty REAL, net_kg REAL, netto REAL,   -- netto = tonnes
  value REAL NOT NULL,               -- стат. стоимость, ming USD
  invoice REAL,                      -- Фактурная стоимость
  origin TEXT,                       -- страна происхождения (code)
  need_flag TEXT,                    -- Нужд
  kind TEXT NOT NULL                 -- sanoat | meva | bnpz  (ЭК); im (ИМ)
);
CREATE INDEX IF NOT EXISTS ix_items_inn ON items(inn, year, regime);
CREATE INDEX IF NOT EXISTS ix_items_date ON items(rdate);
CREATE INDEX IF NOT EXISTS ix_items_key ON items(key);
CREATE INDEX IF NOT EXISTS ix_items_hs ON items(hs4);
-- decl_id index: without it every DELETE on declarations (ON DELETE CASCADE) scans the whole items table —
-- a 2024–2025 base reload took 10+ minutes (25.09.2026); with it the same reload is seconds
CREATE INDEX IF NOT EXISTS ix_items_decl ON items(decl_id);
CREATE INDEX IF NOT EXISTS ix_items_ym ON items(year, month);
CREATE INDEX IF NOT EXISTS ix_decl_ym ON declarations(year, month);
CREATE TABLE IF NOT EXISTS hs_codes (         -- HS-10 dictionary: both classifiers hang on the code (1 code = 1 group)
  hs10 TEXT PRIMARY KEY, tovar1 TEXT, tovar2 TEXT, sprav1 TEXT, sprav2 TEXT, unit TEXT, name TEXT
);
CREATE TABLE IF NOT EXISTS countries (name TEXT PRIMARY KEY, chegara INTEGER, evrazes INTEGER, sng INTEGER);
CREATE TABLE IF NOT EXISTS unions (code TEXT PRIMARY KEY, name TEXT);
CREATE TABLE IF NOT EXISTS posts (code TEXT PRIMARY KEY, name TEXT);
CREATE TABLE IF NOT EXISTS company_plans (    -- ministry plan per company («Корхона номма-ном … РЕЖАГА»)
  inn TEXT NOT NULL, year INTEGER NOT NULL, annual REAL, months TEXT, name TEXT, district TEXT, tarmoq TEXT, source TEXT, loaded_at TEXT,
  PRIMARY KEY (inn, year)
);
CREATE TABLE IF NOT EXISTS company_contacts (
  inn TEXT PRIMARY KEY, director TEXT, phone TEXT, address TEXT, legal_form TEXT, email TEXT, note TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS company_persons (  -- other contact persons of a company (accountant, export manager, founder …)
  id INTEGER PRIMARY KEY AUTOINCREMENT, inn TEXT NOT NULL, name TEXT NOT NULL, role TEXT, phones TEXT, note TEXT,
  position REAL NOT NULL DEFAULT 0, created_at TEXT DEFAULT (datetime('now','localtime')), updated_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_company_persons ON company_persons(inn);
CREATE TABLE IF NOT EXISTS issues (           -- problems / tasks / appeals / notes; inn may be empty for general tasks
  id INTEGER PRIMARY KEY AUTOINCREMENT, inn TEXT, kind TEXT NOT NULL DEFAULT 'muammo', title TEXT NOT NULL, text TEXT,
  responsible TEXT, due_date TEXT, status TEXT NOT NULL DEFAULT 'open', resolution TEXT,
  created_at TEXT DEFAULT (datetime('now','localtime')), updated_at TEXT, closed_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_issues_inn ON issues(inn);
-- kanban board for issues: unlimited columns, multi-labels (organisations involved), attachments
CREATE TABLE IF NOT EXISTS issue_columns (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, color TEXT, position REAL NOT NULL DEFAULT 0,
  is_done INTEGER NOT NULL DEFAULT 0,      -- cards moved here count as «ҳал қилинган»
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS issue_labels (   -- badges: which organisations the problem concerns (божхона, солиқ, банк …)
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, color TEXT, position REAL NOT NULL DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS issue_label_links (
  issue_id INTEGER NOT NULL, label_id INTEGER NOT NULL, PRIMARY KEY (issue_id, label_id)
);
CREATE TABLE IF NOT EXISTS issue_files (    -- attachments of a card (documents, photos); files in data\\issue_files\\<issue_id>\\
  id INTEGER PRIMARY KEY AUTOINCREMENT, issue_id INTEGER NOT NULL, filename TEXT NOT NULL, stored TEXT NOT NULL, size INTEGER,
  mime TEXT, uploaded_at TEXT DEFAULT (datetime('now','localtime')), deleted INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_issue_files ON issue_files(issue_id);
CREATE TABLE IF NOT EXISTS issue_checks (    -- card checklist (қадамлар): steps to solve the problem, progress x/y on the card
  id INTEGER PRIMARY KEY AUTOINCREMENT, issue_id INTEGER NOT NULL, text TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0,
  position REAL NOT NULL DEFAULT 0, created_at TEXT DEFAULT (datetime('now','localtime')), done_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_issue_checks ON issue_checks(issue_id);
CREATE TABLE IF NOT EXISTS issue_comments (  -- card timeline: user notes (kind='note', editable) and automatic history (kind='log')
  id INTEGER PRIMARY KEY AUTOINCREMENT, issue_id INTEGER NOT NULL, kind TEXT NOT NULL DEFAULT 'note', text TEXT NOT NULL,
  at TEXT DEFAULT (datetime('now','localtime')), edited_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_issue_comments ON issue_comments(issue_id);
CREATE TABLE IF NOT EXISTS company_docs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, inn TEXT NOT NULL, filename TEXT NOT NULL, stored TEXT NOT NULL, size INTEGER,
  note TEXT, doc_date TEXT, uploaded_at TEXT DEFAULT (datetime('now','localtime')), deleted INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS company_events (   -- profile timeline
  id INTEGER PRIMARY KEY AUTOINCREMENT, inn TEXT NOT NULL, at TEXT DEFAULT (datetime('now','localtime')), kind TEXT, text TEXT
);
CREATE INDEX IF NOT EXISTS ix_events_inn ON company_events(inn);

CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT DEFAULT (datetime('now','localtime')),
  action TEXT NOT NULL, details TEXT
);
"""

def connect(path: Path | None = None) -> sqlite3.Connection:
    p = Path(path) if path else DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p), timeout=30)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    _migrate(con)
    return con

def _migrate(con):
    cols = {r[1] for r in con.execute("PRAGMA table_info(companies)")}
    if "is_new" not in cols: con.execute("ALTER TABLE companies ADD COLUMN is_new INTEGER NOT NULL DEFAULT 0")   # new exporter (yellow in номманом)
    if "new_date" not in cols: con.execute("ALTER TABLE companies ADD COLUMN new_date TEXT")                      # day it was found in a GTD file
    if "parts" not in {r[1] for r in con.execute("PRAGMA table_info(company_plans)")}:
        con.execute("ALTER TABLE company_plans ADD COLUMN parts TEXT")   # plan lines of one company in several branches
    ucols = {r[1] for r in con.execute("PRAGMA table_info(uploads)")}
    if "archive" not in ucols: con.execute("ALTER TABLE uploads ADD COLUMN archive TEXT")   # original GTD file kept under its day
    con.execute("UPDATE gtd_rows SET dedup_key=dedup_key || '#void' || upload_id WHERE voided=1 AND dedup_key NOT LIKE '%#void%'")
    if "in_base" not in cols:
        # in_base: INN is in the customs base registry (Bukhara). bukhara: user decision for others (1 yes / 0 no / NULL unknown)
        con.execute("ALTER TABLE companies ADD COLUMN in_base INTEGER NOT NULL DEFAULT 0")
        con.execute("ALTER TABLE companies ADD COLUMN bukhara INTEGER")
        last_reset = con.execute("SELECT coalesce(max(id), 0) FROM audit_log WHERE action='reset_all'").fetchone()[0]
        first_base = con.execute("SELECT min(at) FROM audit_log WHERE action='import_customs_base' AND id>?", (last_reset,)).fetchone()[0]
        con.execute("UPDATE companies SET in_base=1 WHERE source='baza'")
        if first_base:   # rows created by the base import keep their created_at even after номманом updated them
            con.execute("UPDATE companies SET in_base=1 WHERE source='nomma-nom' AND created_at<=?", (first_base,))
    if "bukhara_from" not in cols:
        # Bukhara period: exports are counted as Bukhara only for dates bukhara_from..bukhara_to (either side open).
        # A company that moved into the region counts from bukhara_from; one that left counts up to bukhara_to.
        con.execute("ALTER TABLE companies ADD COLUMN bukhara_from TEXT")
        con.execute("ALTER TABLE companies ADD COLUMN bukhara_to TEXT")
    ccols = {r[1] for r in con.execute("PRAGMA table_info(company_contacts)")}
    if "phones" not in ccols:
        # several phones per company: JSON list in `phones`, first one stays in `phone` (registry list, Excel)
        con.execute("ALTER TABLE company_contacts ADD COLUMN phones TEXT")
        for r in con.execute("SELECT inn, phone FROM company_contacts WHERE phone IS NOT NULL AND phone<>''").fetchall():
            ph = [x.strip() for x in re.split(r"[,;/]| ва |\n", r["phone"]) if x.strip()]
            con.execute("UPDATE company_contacts SET phones=? WHERE inn=?", (json.dumps(ph, ensure_ascii=False), r["inn"]))
    if "union_code" not in cols:
        # customs-base attributes of a company: full name, union (тармоқ номи), тармок flag (YES member / NO regional / JSH individual / PU)
        con.execute("ALTER TABLE companies ADD COLUMN full_name TEXT")
        con.execute("ALTER TABLE companies ADD COLUMN union_code TEXT")
        con.execute("ALTER TABLE companies ADD COLUMN union_name TEXT")
        con.execute("ALTER TABLE companies ADD COLUMN base_kind TEXT")
    if "opening_source" not in cols:
        # «Йил боши манбаси» per company (Jafar, 19.09.2026): 'customs' — the monthly customs base is the truth (Excel is
        # rewritten to it); 'template' — the user's номманом Jan..base-month values are imported into opening_balances
        con.execute("ALTER TABLE companies ADD COLUMN opening_source TEXT NOT NULL DEFAULT 'customs'")
    _migrate_items(con)
    from . import plans, periods, catalog; plans.ensure(con); periods.ensure(con); catalog.ensure(con)
    plans.seed_once(con)
    _repair_null_names(con)
    _migrate_board(con)
    con.commit()

def _migrate_items(con):
    """base_rows / base_import / base_keys / inn_hs4 -> declarations + items (one time). The legacy detail lacks the
    customs ids and most columns, so the rows are carried over with synthetic ids and a flag; the next base upload
    (Sozlamalar -> 1) replaces them with the full rows. Nothing is lost: every sum the site shows comes out equal."""
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "base_rows" not in tables and "base_keys" not in tables and "inn_hs4" not in tables and "base_import" not in tables: return
    legacy_year = get_setting(con, "year")
    if "base_rows" in tables and not con.execute("SELECT 1 FROM items LIMIT 1").fetchone():
        con.commit()
        try: backup("before_items")          # one-way change of the live file: keep the pre-migration copy
        except Exception: pass
        ref = reference(); exclude = set(ref.get("exclude_inns", {}))
        keys = {}
        if "base_keys" in tables:
            for r in con.execute("SELECT key, inn FROM base_keys"):
                keys.setdefault(r[0].split("#")[0], []).append(r[0])
        n = 0
        for r in con.execute("SELECT rowid, inn, rdate, gtd, hs, tovar1, tovar2, country, netto, value FROM base_rows"):
            rdate = r["rdate"]; y, m = int(rdate[:4]), int(rdate[5:7]); gtd = r["gtd"] or f"?/{rdate}/{r['inn']}"
            parts = gtd.split("/")
            decl_id = "legacy:" + gtd
            con.execute("""INSERT OR IGNORE INTO declarations(decl_id,inn,regime,year,month,rdate,gdate,gtd_no,post,key,country,source)
                           VALUES(?,?,'ЭК',?,?,?,?,?,?,?,?,'legacy')""",
                        (decl_id, r["inn"], y, m, rdate, parts[1] if len(parts) > 1 else None, parts[2] if len(parts) > 2 else None, parts[0], gtd, r["country"]))
            t = str(r["tovar1"] or "").lower(); hs = str(r["hs"] or "")
            kind = "bnpz" if r["inn"] in exclude else ("meva" if ("мева" in t if t else hs[:2] in ("07", "08")) else "sanoat")
            klist = keys.get(gtd) or []
            key = klist.pop(0) if klist else f"{gtd}#legacy{r['rowid']}"
            con.execute("""INSERT INTO items(cmdt_id,decl_id,inn,regime,year,month,rdate,gtd,key,hs10,hs4,tovar1,tovar2,netto,net_kg,value,kind)
                           VALUES(?,?,?,'ЭК',?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (f"legacy:{r['rowid']}", decl_id, r["inn"], y, m, rdate, gtd, key, hs or None, hs[:4] or None, r["tovar1"], r["tovar2"],
                         r["netto"], (r["netto"] or 0) * 1000 if r["netto"] is not None else None, r["value"] or 0, kind)); n += 1
        if "base_import" in tables:
            for r in con.execute("SELECT inn, year, month, value FROM base_import"):
                decl_id = f"legacy-im:{r['inn']}:{r['year']}-{r['month']:02d}"; rdate = f"{r['year']}-{r['month']:02d}-01"
                con.execute("INSERT OR IGNORE INTO declarations(decl_id,inn,regime,year,month,rdate,key,source) VALUES(?,?,'ИМ',?,?,?,?,'legacy')",
                            (decl_id, r["inn"], r["year"], r["month"], rdate, decl_id))
                con.execute("INSERT INTO items(cmdt_id,decl_id,inn,regime,year,month,rdate,gtd,key,value,kind) VALUES(?,?,?,'ИМ',?,?,?,?,?,?,'im')",
                            (decl_id + "#1", decl_id, r["inn"], r["year"], r["month"], rdate, decl_id, decl_id + "#1", r["value"] or 0))
        set_setting(con, "items_legacy", "1")
        log(con, "migrate_items", rows=n, year=legacy_year)
    for t in ("base_rows", "base_import", "base_keys", "inn_hs4"):
        con.execute(f"DROP TABLE IF EXISTS {t}")

def items_legacy(con) -> bool:
    """True while the item detail comes from the old base_rows conversion (no customs ids, posts, transport …)."""
    return get_setting(con, "items_legacy") == "1"

def inn_hs4(con, inn: str | None = None, year: int | None = None) -> list:
    """[(inn, hs4, amount)] — sanoat export structure per company from the customs base (was the inn_hs4 table)."""
    w, a = ["regime='ЭК'", "kind='sanoat'", "hs4 IS NOT NULL"], []
    if inn: w.append("inn=?"); a.append(inn)
    if year: w.append("year=?"); a.append(int(year))
    return [tuple(r) for r in con.execute(f"SELECT inn, hs4, sum(value) FROM items WHERE {' AND '.join(w)} GROUP BY inn, hs4", a)]

DEFAULT_COLUMNS = (("Янги", "#0F6E63", 0), ("Жараёнда", "#B7912A", 0), ("Кутилмоқда", "#B7791F", 0), ("Ҳал қилинган", "#2E8B57", 1))

def _migrate_board(con):
    """Issues get a kanban column + position; default columns are created once, existing cards are placed by status."""
    icols = {r[1] for r in con.execute("PRAGMA table_info(issues)")}
    if "column_id" not in icols: con.execute("ALTER TABLE issues ADD COLUMN column_id INTEGER")
    if "position" not in icols: con.execute("ALTER TABLE issues ADD COLUMN position REAL")
    if not con.execute("SELECT 1 FROM issue_columns LIMIT 1").fetchone():
        for i, (name, color, done) in enumerate(DEFAULT_COLUMNS, 1):
            con.execute("INSERT INTO issue_columns(name, color, position, is_done) VALUES(?,?,?,?)", (name, color, i * 10, done))
    if con.execute("SELECT 1 FROM issues WHERE column_id IS NULL OR column_id NOT IN (SELECT id FROM issue_columns) LIMIT 1").fetchone():
        first = con.execute("SELECT id FROM issue_columns WHERE is_done=0 ORDER BY position, id LIMIT 1").fetchone()
        done = con.execute("SELECT id FROM issue_columns WHERE is_done=1 ORDER BY position, id LIMIT 1").fetchone()
        first = first[0] if first else con.execute("SELECT id FROM issue_columns ORDER BY position, id LIMIT 1").fetchone()[0]
        done = done[0] if done else first
        con.execute("UPDATE issues SET column_id=CASE WHEN status='closed' THEN ? ELSE ? END WHERE column_id IS NULL OR column_id NOT IN (SELECT id FROM issue_columns)", (done, first))
    con.execute("UPDATE issues SET position=id*10 WHERE position IS NULL")
    # 26.09.2026: priority (устуворлик), basis document (асос: баён / топшириқ / хат / мурожаат), the moment a card entered its column
    if "priority" not in icols: con.execute("ALTER TABLE issues ADD COLUMN priority TEXT NOT NULL DEFAULT 'normal'")
    for c in ("basis_kind", "basis_no", "basis_date", "column_at"):
        if c not in icols: con.execute(f"ALTER TABLE issues ADD COLUMN {c} TEXT")
    con.execute("UPDATE issues SET column_at=coalesce(closed_at, updated_at, created_at) WHERE column_at IS NULL")
    # older cards get the first line of their timeline once (new cards write it on creation)
    con.execute("""INSERT INTO issue_comments(issue_id, kind, text, at) SELECT id, 'log', 'Карта яратилди', coalesce(created_at, datetime('now','localtime'))
                   FROM issues WHERE id NOT IN (SELECT issue_id FROM issue_comments)""")

def _repair_null_names(con):
    """One-time repair: the customs base has «(null)» in «Ташкилот киска номи» for individuals (Ж/ш, 14-digit PINFL);
    older imports stored that text as the company name. Names come from templates/base_names.json (built from the
    8-month base «Ташкилот номи» column) or, failing that, from the exporter name in saved GTD rows."""
    bad = [r[0] for r in con.execute("SELECT inn FROM companies WHERE name IS NULL OR trim(name)='' OR name='(null)'")]
    if not bad: return
    names = {}
    p = Path(__file__).resolve().parent / "templates" / "base_names.json"
    if p.exists():
        try: names = json.loads(p.read_text(encoding="utf-8"))
        except Exception: names = {}
    fixed = 0
    for inn in bad:
        name = (names.get(inn) or "").strip()
        if not name:
            r = con.execute("SELECT exporter FROM gtd_rows WHERE inn=? AND exporter IS NOT NULL AND trim(exporter)<>'' AND exporter<>'(null)' ORDER BY report_date DESC LIMIT 1", (inn,)).fetchone()
            name = (r[0] or "").strip() if r else ""
        if name:
            con.execute("UPDATE companies SET name=? WHERE inn=?", (name, inn)); fixed += 1
    if fixed: log(con, "repair_null_names", fixed=fixed, left=len(bad) - fixed)
    con.commit()

def reference() -> dict:
    return json.loads((Path(__file__).resolve().parent / "templates" / "reference.json").read_text(encoding="utf-8"))

def backup(reason: str, path: Path | None = None) -> Path | None:
    src = Path(path) if path else DB_PATH
    if not src.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dst = BACKUP_DIR / f"export_{stamp}_{reason}.db"
    con = sqlite3.connect(str(src)); bck = sqlite3.connect(str(dst))
    with bck: con.backup(bck)
    bck.close(); con.close()
    # keep last 60 backups
    files = sorted(BACKUP_DIR.glob("export_*.db"))
    for f in files[:-60]:
        f.unlink(missing_ok=True)
    return dst

def backup_if_stale(reason: str, minutes: int = 15):
    """Small edits (company fields) run often: one backup per quarter hour is enough."""
    if BACKUP_DIR.exists():
        last = max((f.stat().st_mtime for f in BACKUP_DIR.glob("export_*.db")), default=0)
        if dt.datetime.now().timestamp() - last < minutes * 60: return None
    return backup(reason)

MANUAL_TABLES = ("company_contacts", "company_persons", "issues", "issue_columns", "issue_labels", "issue_label_links", "issue_files", "issue_checks", "issue_comments", "company_docs", "company_events",
                 "catalog_companies", "catalog_products", "catalog_media", "catalog_inquiries")   # Каталог ҳам қўлда киритилган маълумот

def reset_all(con, keep_manual: bool = False) -> None:
    """Erase loaded data; keep only the 13 district codes. keep_manual: company contacts, issues, documents and history stay (keyed by INN)."""
    import datetime as _dt
    kept = {}
    with con:
        for t in ("gtd_rows", "uploads", "opening_balances", "karantin_opening", "prognoz", "companies", "tnved_map", "template_inns", "items", "declarations", "hs_codes", "countries", "unions", "posts", "company_plans", "plan_values", "plan_versions", *(() if keep_manual else MANUAL_TABLES), "settings", "audit_log"):
            con.execute(f"DELETE FROM {t}")
        for k, v in kept.items():
            if v is not None: set_setting(con, k, v)
        con.execute("DELETE FROM districts WHERE length(code)<>7")
        if not con.execute("SELECT count(*) FROM districts").fetchone()[0]:
            ref = json.loads((Path(__file__).resolve().parent / "templates" / "reference.json").read_text(encoding="utf-8"))
            for code, d in ref["districts"].items():
                con.execute("INSERT INTO districts(code,name_uz,order_no) VALUES(?,?,?)", (code, d["name_uz"], d["order_no"]))
        set_setting(con, "reset_at", _dt.datetime.now().isoformat(timespec="seconds"))
        log(con, "reset_all", keep_manual=keep_manual)
    con.execute("VACUUM")

def integrity_ok(con: sqlite3.Connection) -> bool:
    return con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

def log(con, action, **details):
    con.execute("INSERT INTO audit_log(action, details) VALUES (?,?)", (action, json.dumps(details, ensure_ascii=False)))

def event(con, inn, kind, text):
    if inn: con.execute("INSERT INTO company_events(inn, kind, text) VALUES(?,?,?)", (inn, kind, text))

def get_setting(con, key, default=None):
    r = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r[0] if r else default

def set_setting(con, key, value):
    con.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
