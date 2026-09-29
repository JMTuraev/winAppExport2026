"""Local web server (standard library only). Opens http://127.0.0.1:<port> in the browser."""
from __future__ import annotations
import json, re, os, sys, socket, threading, time, traceback, shutil, mimetypes, webbrowser, secrets, datetime as dt, urllib.parse, urllib.request, hashlib
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from . import db, daily, report, export, reinit, tpl, sources, companies, geo, trade, board, smart, contacts_import, products, plans, dispute, periods, tahlil, reyting, mahsulot, catalog

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
APP_DIR = ROOT.parent
CONFIG = APP_DIR / "config.json"
WRITE_LOCK = threading.Lock()
HOST = socket.gethostname()
STATE = {"readonly": False, "lock_owner": None, "token": secrets.token_hex(8), "started": dt.datetime.now().isoformat(timespec="seconds")}

def load_config():
    cfg = {"data_dir": "data", "port": 8765, "open_browser": True}
    if CONFIG.exists():
        cfg.update(json.loads(CONFIG.read_text(encoding="utf-8")))
    d = Path(cfg["data_dir"])
    if not d.is_absolute(): d = APP_DIR / d
    cfg["data_path"] = d.resolve()
    return cfg

def set_data_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    db.BASE = path; db.DB_PATH = path / "export.db"; db.BACKUP_DIR = path / "backups"
    for sub in ("incoming", "gtd_archive", "exports"): (path / sub).mkdir(exist_ok=True)
    clean_incoming()

# ------------------------------------------------------------ multi-device lock (Google Drive)
def lock_path(): return db.BASE / "export.lock"

def acquire_lock():
    lp = lock_path()
    if lp.exists():
        try:
            info = json.loads(lp.read_text(encoding="utf-8"))
            age = time.time() - info.get("heartbeat", 0)
            if info.get("host") != HOST and age < 180:
                STATE["readonly"] = True; STATE["lock_owner"] = info
                return False
        except Exception:
            pass
    write_lock()
    return True

def write_lock():
    lock_path().write_text(json.dumps({"host": HOST, "pid": os.getpid(), "heartbeat": time.time(), "token": STATE["token"],
                                       "since": dt.datetime.now().isoformat(timespec="seconds")}), encoding="utf-8")

def heartbeat():
    while True:
        time.sleep(60)
        if STATE["readonly"]: continue
        try:
            info = json.loads(lock_path().read_text(encoding="utf-8")) if lock_path().exists() else {}
            if info.get("host") and info.get("host") != HOST and time.time() - info.get("heartbeat", 0) < 180:
                STATE["readonly"] = True; STATE["lock_owner"] = info      # another computer took the folder over (Google Drive)
                print(f"DIQQAT: baza {info.get('host')} kompyuterida ochildi — faqat ko'rish rejimiga o'tildi.")
                continue
            write_lock()
        except Exception: pass

def release_lock():
    if not STATE["readonly"]:
        try: lock_path().unlink()
        except Exception: pass

# ------------------------------------------------------------ helpers
def conn(): return db.connect()

def stage_write(path: Path, data: bytes) -> None:
    """Write a staging file so it is either complete or absent. Windows: write next to it, then rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    with open(tmp, "wb") as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)

def read_retry(path: Path, tries: int = 4, wait: float = 0.4) -> bytes:
    """Read a staging file. Windows: antivirus may hold a just-written file for a moment — try again."""
    for i in range(tries):
        try: return path.read_bytes()
        except OSError:
            if i == tries - 1: raise
            time.sleep(wait)
    return b""

def clean_incoming(days: int = 2) -> None:
    """Drop staging files older than `days` (a preview that was never saved)."""
    try:
        cut = time.time() - days * 86400
        for f in (db.BASE / "incoming").glob("*"):
            if f.is_file() and (f.stat().st_mtime < cut or f.suffix == ".part"):
                try: f.unlink()
                except OSError: pass
    except Exception: pass

def log_exc(where: str = "") -> str:
    """Full traceback -> data\\xato.log; returns «fayl.py:qator» of the last line inside the app."""
    tb = traceback.format_exc()
    loc = ""
    try:
        for fr in traceback.extract_tb(sys.exc_info()[2]):
            if Path(fr.filename).parent.name == "app": loc = f"{Path(fr.filename).name}:{fr.lineno}"
    except Exception: pass
    try:
        base = db.BASE if getattr(db, "BASE", None) else APP_DIR
        with open(base / "xato.log", "a", encoding="utf-8") as f:
            f.write(f"\n===== {dt.datetime.now():%Y-%m-%d %H:%M:%S} {where}\n{tb}")
    except Exception: pass
    return loc

def err_json(self, e, where=""):
    loc = log_exc(where)
    traceback.print_exc()
    msg = str(e) or e.__class__.__name__
    if not isinstance(e, (ValueError, KeyError)) and loc: msg = f"{msg} [{loc}]"
    if isinstance(e, OSError):
        msg += " — fayl yozishda tizim xatosi. Antivirus yoki papka huquqlarini tekshiring."
    return self.send_json({"error": msg}, 400)

def jdefault(o):
    if isinstance(o, (dt.date, dt.datetime)): return o.isoformat()
    if isinstance(o, set): return sorted(o)
    return str(o)

# ------------------------------------------------------------ «Ўтган йил базаси» (Sozlamalar) — prognoz.prev_year_base
PREV_KINDS = ("all", "sanoat", "meva")

def prev_year_get(con, year: int) -> dict:
    """{label, days, year, rows:[{code, name, all, sanoat, meva}]} — region '1706' first, then the districts.
    The figures are entered by hand in Sozlamalar (not the customs 2025 base) and prorated by day-of-year in report.prev_year_amount."""
    vals = {(r["district_code"], r["kind"]): dict(r) for r in con.execute("SELECT district_code, kind, prev_year_base, prev_year_base_days FROM prognoz WHERE year=?", (year,))}
    days = next((r["prev_year_base_days"] for r in vals.values() if r["prev_year_base_days"]), None) or 273
    rows = [{"code": d["code"], "name": d["name_uz"], **{k: (vals.get((d["code"], k)) or {}).get("prev_year_base") for k in PREV_KINDS}} for d in report.districts(con)]
    if not any(r["code"] == report.REGION for r in rows):
        rows.insert(0, {"code": report.REGION, "name": "Бухоро вилояти", **{k: (vals.get((report.REGION, k)) or {}).get("prev_year_base") for k in PREV_KINDS}})
    return {"year": year, "label": db.get_setting(con, "prev_year_base_label") or "", "days": days,
            "day_offset": int(db.get_setting(con, "prev_year_day_offset", "0") or 0), "rows": rows}

def _num_or_none(v, what: str):
    if v in (None, ""): return None
    try: x = float(str(v).replace(" ", "").replace("\u00a0", "").replace(",", "."))
    except ValueError: raise ValueError(f"{what}: рақам эмас — «{v}»")
    if x != x or x < 0: raise ValueError(f"{what}: манфий бўлмасин")
    return round(x, 3)

def prev_year_save(con, body: dict) -> dict:
    """POST /api/prev_year {year, label, days, rows:[{code, sanoat, meva, all}]}. sanoat/meva are entered; all = sanoat + meva
    (a district's blank 'all' is auto-filled). Region row: the entered figures win; a blank region cell = sum of the districts."""
    year = int(body.get("year") or db.get_setting(con, "year") or dt.date.today().year)
    days = int(_num_or_none(body.get("days", 273), "Ҳолат кунлари") or 273)
    if not 1 <= days <= 366: raise ValueError("Ҳолат кунлари 1–366 оралиғида бўлсин")
    label = str(body.get("label") or "").strip()
    codes = {d["code"] for d in report.districts(con)} | {report.REGION}
    ent = {}
    for r in body.get("rows") or []:
        code = str(r.get("code") or "").strip()
        if code not in codes: raise ValueError(f"Номаълум туман коди: {code}")
        nm = r.get("name") or code
        san, mev, al = (_num_or_none(r.get(k), f"{nm} · {k}") for k in ("sanoat", "meva", "all"))
        if san is None and mev is None and al is None: continue
        if san is not None or mev is not None: al = round((san or 0) + (mev or 0), 3)     # жами = саноат + мева
        ent[code] = {"sanoat": san if san is not None else 0.0, "meva": mev if mev is not None else 0.0, "all": al}
    dist = {c: v for c, v in ent.items() if c != report.REGION}
    if dist:
        # region row: entered figures win; a blank саноат/мева = sum of the districts; жами = саноат + мева
        raw = next((r for r in body.get("rows") or [] if str(r.get("code")) == report.REGION), {})
        reg = {}
        for k in ("sanoat", "meva"):
            v = _num_or_none(raw.get(k), f"Вилоят · {k}")
            reg[k] = v if v is not None else round(sum(x[k] for x in dist.values()), 3)
        reg["all"] = round(reg["sanoat"] + reg["meva"], 3)
        ent[report.REGION] = reg
    if not ent: raise ValueError("Ҳеч қандай рақам киритилмади")
    db.backup_if_stale("before_prev_year")
    with con:
        for code, v in ent.items():
            for k in PREV_KINDS:
                con.execute("""INSERT INTO prognoz(district_code, year, kind, prev_year_base, prev_year_base_days) VALUES(?,?,?,?,?)
                               ON CONFLICT(district_code, year, kind) DO UPDATE SET prev_year_base=excluded.prev_year_base, prev_year_base_days=excluded.prev_year_base_days""",
                            (code, year, k, v[k], days))
        con.execute("UPDATE prognoz SET prev_year_base_days=? WHERE year=?", (days, year))
        if label or "label" in body: db.set_setting(con, "prev_year_base_label", label)
        db.log(con, "prev_year_update", year=year, days=days, label=label, rows={c: v for c, v in ent.items()})
    return {"ok": True, **prev_year_get(con, year)}

class Handler(BaseHTTPRequestHandler):
    server_version = "EksportMonitor/1.0"
    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (dt.datetime.now().strftime("%H:%M:%S"), fmt % args))

    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False, default=jdefault).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)

    def send_file(self, path: Path, download_name=None, extra=None, inline_name=None):
        data = path.read_bytes()
        ctype = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
                 ".woff2": "font/woff2", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".png": "image/png",
                 ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".svg": "image/svg+xml", ".pdf": "application/pdf", ".zip": "application/zip",
                 ".json": "application/json; charset=utf-8"}.get(path.suffix.lower()) \
                or mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(200); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")   # after an update the browser must not show the old page
        if download_name:
            q = urllib.parse.quote(download_name)
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{q}")
        elif inline_name:
            self.send_header("Content-Disposition", f"inline; filename*=UTF-8''{urllib.parse.quote(inline_name)}")
        for k, v in (extra or {}).items():
            self.send_header(k, urllib.parse.quote(json.dumps(v, ensure_ascii=False)))
        self.end_headers(); self.wfile.write(data)

    def body_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def require_write(self):
        if STATE["readonly"]:
            raise PermissionError(f"Baza boshqa kompyuterda ochiq ({STATE['lock_owner'].get('host')}). Faqat ko'rish rejimi.")

    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        try:
            if u.path in ("/", "/index.html"): return self.send_file(STATIC / "index.html")
            if u.path.startswith("/static/"):
                p = (STATIC / u.path[len("/static/"):]).resolve()
                if STATIC in p.parents and p.exists(): return self.send_file(p)
                return self.send_json({"error": "topilmadi"}, 404)
            if u.path == "/catalog":                     # Каталог сайти (локал олдиндан кўриш) — статик пакет билан бир хил код
                self.send_response(302); self.send_header("Location", "/catalog/" + (("?" + u.query) if u.query else "")); self.end_headers(); return
            if u.path.startswith("/catalog/"):
                rest = urllib.parse.unquote(u.path[len("/catalog/"):]) or "index.html"
                if rest in ("data.js", "data-admin.js") or rest.startswith(("media/", "docs/")):
                    con = conn()
                    try:
                        if rest.startswith(("media/", "docs/")):
                            mp = catalog.media_path(con, rest.split("/", 1)[1])
                            if not mp: return self.send_json({"error": "topilmadi"}, 404)
                            return self.send_file(mp[0], inline_name=mp[1]) if rest.startswith("docs/") else self.send_file(mp[0])
                        body = catalog.data_js(con, admin=rest == "data-admin.js")
                    finally: con.close()
                    self.send_response(200); self.send_header("Content-Type", "application/javascript; charset=utf-8")
                    self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body); return
                base = STATIC / ("fonts" if rest.startswith("fonts/") else "site")
                p = (base / (rest[len("fonts/"):] if rest.startswith("fonts/") else rest)).resolve()
                if base in p.parents and p.exists(): return self.send_file(p)
                return self.send_json({"error": "topilmadi"}, 404)
            con = conn()
            try:
                if u.path == "/api/status":
                    last = report.last_data_date(con)
                    return self.send_json({"opening_date": report.opening_date(con), "last_date": last, "db_path": str(db.DB_PATH), "data_dir": str(db.BASE),
                        "host": HOST, "readonly": STATE["readonly"], "lock_owner": STATE["lock_owner"],
                        "companies": con.execute("SELECT count(*) FROM companies").fetchone()[0],
                        "first_date": report.first_data_date(con),
                        "opening_source": db.get_setting(con, "opening_source"),
                        "template": {k: db.get_setting(con, f"template_{k}") for k in ("label", "through", "cur_month", "file", "loaded_at", "karantin_sheet")} if db.get_setting(con, "template_through") else None,
                        "new_companies": con.execute("SELECT count(*) FROM companies WHERE new_date IS NOT NULL").fetchone()[0],
                        "open_issues": con.execute("SELECT count(*) FROM issues WHERE status='open'").fetchone()[0],
                        "prognoz": con.execute("SELECT count(*) FROM prognoz").fetchone()[0],
                        "unconfirmed": con.execute("SELECT count(*) FROM companies WHERE confirmed=0").fetchone()[0],
                        "uploads": con.execute("SELECT count(*) FROM uploads WHERE status='saved'").fetchone()[0],
                        "last_upload": dict(con.execute("SELECT id, filename, loaded_at FROM uploads WHERE status='saved' ORDER BY id DESC LIMIT 1").fetchone() or {}) or None,
                        "last_backup": (sorted(db.BACKUP_DIR.glob("export_*.db"))[-1].name if db.BACKUP_DIR.exists() and list(db.BACKUP_DIR.glob("export_*.db")) else None),
                        "db_mtime": dt.datetime.fromtimestamp(db.DB_PATH.stat().st_mtime).isoformat(timespec="seconds") if db.DB_PATH.exists() else None,
                        "code_time": dt.datetime.fromtimestamp(Path(__file__).stat().st_mtime).isoformat(timespec="seconds"),
                        "started": STATE["started"], "pid": os.getpid()})
                if u.path.startswith("/api/catalog/"):
                    res = catalog.http_get(con, u.path, q)
                    if isinstance(res, tuple): return self.send_file(res[1], download_name=res[2])
                    return self.send_json(res)
                if u.path == "/api/dashboard": return self.send_json(report.dashboard(con, q.get("date"), report.plan_param(q.get("plan")), report.fset_param(q.get("fs"))))
                if u.path == "/api/selectors":   # Dashboard/Свод: режа ва «амалда» тўплами танлови (29.09.2026)
                    D = q.get("date") or report.last_data_date(con) or dt.date.today().isoformat()
                    return self.send_json({"date": D, "plans": plans.choices(con, D), "prev_year": int(D[:4]) - 1,
                                           "sets": periods.year_sets(con, int(D[:4]) - 1)})
                if u.path == "/api/geo": return self.send_json(geo.rows(con, q))
                if u.path == "/api/geo/country": return self.send_json(geo.country(con, q))
                if u.path == "/api/geo/trade_meta": return self.send_json(trade.meta(con))   # давлат Excel модали: йиллар, охирги ёпилган ой
                if u.path == "/api/companies/list": return self.send_json(companies.list_companies(con, q))
                if u.path == "/api/company": return self.send_json(companies.profile(con, q["inn"], int(q["year"]) if q.get("year") else None))
                if u.path == "/api/companies/names": return self.send_json(companies.names(con))
                if u.path == "/api/issues": return self.send_json(companies.issues_list(con, q))
                if u.path == "/api/board": return self.send_json(board.board(con))
                if u.path == "/api/issue/timeline": return self.send_json(board.timeline(con, int(q["id"])))
                if u.path == "/api/issue/company": return self.send_json(board.company_brief(con, q["inn"]))
                if u.path == "/api/issue/file":
                    p, name = board.file_path(con, int(q["id"]))
                    if q.get("inline"): return self.send_file(p, inline_name=name)
                    return self.send_file(p, download_name=name)
                if u.path == "/api/export/issues":
                    out_dir = db.BASE / "exports"; out_dir.mkdir(parents=True, exist_ok=True)
                    name = f"Муаммо ва вазифалар {dt.date.today():%d.%m.%Y}.xlsx"
                    return self.send_file(board.export_xlsx(con, out_dir / name), download_name=name)
                if u.path == "/api/company/doc":
                    p, name = companies.doc_path(con, int(q["id"])); return self.send_file(p, download_name=name)
                if u.path == "/api/products": return self.send_json(products.tree(con, q))
                if u.path == "/api/dynamics": return self.send_json(products.dynamics(con, q))
                if u.path == "/api/plans":
                    last = report.last_data_date(con) or dt.date.today().isoformat()
                    eff = plans.effective_version(con, last)
                    return self.send_json({"versions": plans.versions(con), "cards": plans.cards(con), "effective": eff, "last_date": last, "year": int(db.get_setting(con, "year") or last[:4]),
                                           "workbook_plan": bool(con.execute("SELECT 1 FROM prognoz LIMIT 1").fetchone()),
                                           "sign": {"position": db.get_setting(con, "report_sign_pos", "Бошқарма бошлиғи"), "name": db.get_setting(con, "report_sign_name", "")}})
                if u.path == "/api/plans/grid": return self.send_json(plans.grid(con, int(q["id"])))
                if u.path == "/api/periods":
                    last = report.last_data_date(con) or dt.date.today().isoformat()
                    return self.send_json({"periods": periods.list_periods(con), "year": int(db.get_setting(con, "year") or last[:4]), "last_date": last,
                                           "max_year": periods.max_year(con), "prev_source": periods.prev_info(con, last)})
                if u.path == "/api/periods/grid":
                    return self.send_json(periods.grid(con, int(q.get("year") or 0), int(q["months"]), q.get("set") or None))
                if u.path == "/api/fact_sets":   # «Амалда» тўпламлари (29.09.2026)
                    last = report.last_data_date(con) or dt.date.today().isoformat()
                    return self.send_json({"sets": periods.sets(con), "max_year": periods.max_year(con), "last_date": last,
                                           "year": int(db.get_setting(con, "year") or last[:4]), "prev_source": periods.prev_info(con, last)})
                if u.path == "/api/periods/template":
                    out_dir = db.BASE / "exports"; out_dir.mkdir(parents=True, exist_ok=True)
                    y, m = int(q.get("year") or periods.max_year(con)), int(q.get("months") or 12)
                    name = periods.file_name(y, m)
                    return self.send_file(periods.template_xlsx(con, y, m, out_dir / name, q.get("set") or None), download_name=name)
                if u.path == "/api/prev_year": return self.send_json(prev_year_get(con, int(q.get("year") or db.get_setting(con, "year") or dt.date.today().year)))
                if u.path == "/api/disputes":
                    return self.send_json({"base_month": dispute.base_month(con), "template": db.get_setting(con, "template_label"), "rows": dispute.disputes(con)})
                if u.path == "/api/plans/template":
                    out_dir = db.BASE / "exports"; out_dir.mkdir(parents=True, exist_ok=True)
                    name = f"Режа шаблони {q.get('year') or ''}.xlsx".replace("  ", " ")
                    return self.send_file(plans.template_xlsx(con, int(q["id"]) if q.get("id") else None, int(q.get("year") or db.get_setting(con, "year") or dt.date.today().year), out_dir / name), download_name=name)
                if u.path == "/api/analysis/tarmoq/meta":
                    cy = int(db.get_setting(con, "year") or dt.date.today().year)
                    years = [r[0] for r in con.execute("SELECT DISTINCT year FROM items WHERE regime='ЭК' ORDER BY year")]
                    if cy not in years: years.append(cy)
                    return self.send_json({"categories": tahlil.categories(con), "years": [y for y in years if y - 1 in years] or years, "year": cy,
                                           "default_months": tahlil.default_months(con), "last_date": report.last_data_date(con),
                                           "opening_through": db.get_setting(con, "opening_through_date") or "",
                                           "districts": [{"code": d["code"], "name": d["name_uz"]} for d in report.districts(con)]})
                if u.path == "/api/analysis/tarmoq": return self.send_json(tahlil.build(con, q))
                if u.path == "/api/export/analysis/tarmoq":
                    out_dir = db.BASE / "exports"; out_dir.mkdir(parents=True, exist_ok=True)
                    name = f"Тармоқ таҳлили {dt.datetime.now():%d.%m.%Y %H-%M}.xlsx"
                    return self.send_file(tahlil.export_xlsx(con, q, out_dir / name), download_name=name)
                if u.path == "/api/analysis/mahsulot/meta": return self.send_json(mahsulot.meta(con))
                if u.path == "/api/analysis/mahsulot/catalog": return self.send_json(mahsulot.catalog(con, q))
                if u.path == "/api/analysis/mahsulot": return self.send_json(mahsulot.build(con, q))
                if u.path == "/api/export/analysis/mahsulot":   # маҳсулотлар таҳлили — 6 варақ
                    out_dir = db.BASE / "exports"; out_dir.mkdir(parents=True, exist_ok=True)
                    name = f"Маҳсулотлар таҳлили {dt.datetime.now():%d.%m.%Y %H-%M}.xlsx"
                    return self.send_file(mahsulot.export_xlsx(con, q, out_dir / name), download_name=name)
                if u.path == "/api/analysis/reyting/meta":
                    return self.send_json(reyting.meta(con))
                if u.path == "/api/analysis/reyting":
                    return self.send_json(reyting.build(con, q))
                if u.path == "/api/export/analysis/reyting":   # экспорт қилган корхоналар рўйхати — каттадан кичикка
                    out_dir = db.BASE / "exports"; out_dir.mkdir(parents=True, exist_ok=True)
                    name = f"Экспорт қилган корхоналар {dt.datetime.now():%d.%m.%Y %H-%M}.xlsx"
                    return self.send_file(reyting.export_xlsx(con, q, out_dir / name), download_name=name)
                if u.path == "/api/export/dynamics":
                    out_dir = db.BASE / "exports"; out_dir.mkdir(parents=True, exist_ok=True)
                    name = f"Динамика {q.get('year') or ''} {dt.date.today():%d.%m.%Y}.xlsx".replace("  ", " ")
                    return self.send_file(products.export_dynamics(con, q, out_dir / name), download_name=name)
                if u.path == "/api/movement": return self.send_json(companies.movement(con, q))
                if u.path == "/api/export/movement":
                    out_dir = db.BASE / "exports"; out_dir.mkdir(parents=True, exist_ok=True)
                    name = f"Корхона ҳаракати {q.get('year') or ''} {dt.date.today():%d.%m.%Y}.xlsx".replace("  ", " ")
                    return self.send_file(companies.export_movement(con, q, out_dir / name), download_name=name)
                if u.path == "/api/company/products": return self.send_json(products.company_products(con, q["inn"], int(q["year"]) if q.get("year") else None))
                if u.path == "/api/export/products":
                    out_dir = db.BASE / "exports"; out_dir.mkdir(parents=True, exist_ok=True)
                    name = f"Тармоқ ва маҳсулот {q.get('year') or ''} {dt.date.today():%d.%m.%Y}.xlsx".replace("  ", " ")
                    return self.send_file(products.export_xlsx(con, q, out_dir / name), download_name=name)
                if u.path == "/api/export/nomma":
                    out_dir = db.BASE / "exports"; out_dir.mkdir(parents=True, exist_ok=True)
                    name = f"Номма-ном {dt.date.today():%d.%m.%Y}.xlsx"
                    return self.send_file(report.export_nomma(con, q, out_dir / name), download_name=name)
                if u.path == "/api/export/svod_options":   # юклашдан олдинги модал: ўтган йил даври, мева-сабзавот қоидаси, Sozlamalar, режа
                    from . import svodx
                    o = svodx.options(con, q.get("date"))
                    o["plans"] = plans.choices(con, q.get("date") or report.last_data_date(con) or dt.date.today().isoformat())
                    return self.send_json(o)
                if u.path == "/api/export/svod_nomma":   # 1-варақ СВОД (карантин) + ҳар туман номма-ном
                    out_dir = db.BASE / "exports"; out_dir.mkdir(parents=True, exist_ok=True)
                    D = q.get("date") or report.last_data_date(con); nd = dt.date.fromisoformat(D) + dt.timedelta(days=1)
                    name = f"{nd:%d.%m.%Y} свод ва туманлар номма-ном.xlsx"
                    return self.send_file(report.export_svod_nomma(con, q, out_dir / name), download_name=name)
                if u.path == "/api/export/geo_trade":   # танланган давлат(лар): экспорт + импорт, туман/соҳа/номма-ном
                    out_dir = db.BASE / "exports"; out_dir.mkdir(parents=True, exist_ok=True)
                    name = trade.file_name(q)
                    return self.send_file(trade.export_xlsx(con, q, out_dir / name), download_name=name)
                if u.path == "/api/export/geo":
                    out_dir = db.BASE / "exports"; out_dir.mkdir(parents=True, exist_ok=True)
                    name = f"Экспорт географияси {dt.date.today():%d.%m.%Y}.xlsx"
                    return self.send_file(geo.export_xlsx(con, q, out_dir / name), download_name=name)
                if u.path in ("/api/export/companies", "/api/export/passport"):
                    out_dir = db.BASE / "exports"; out_dir.mkdir(parents=True, exist_ok=True)
                    if u.path.endswith("companies"):
                        name = f"Корхоналар {dt.date.today():%d.%m.%Y}.xlsx"; out = companies.export_list(con, q, out_dir / name)
                    else:
                        c = con.execute("SELECT name FROM companies WHERE inn=?", (q["inn"],)).fetchone()
                        safe = re.sub(r'[\\/:*?"<>|]', "_", (c["name"] if c else q["inn"]))[:60]
                        name = f"Паспорт {safe} {q['inn']}.xlsx"; out = companies.export_passport(con, q["inn"], out_dir / name)
                    return self.send_file(out, download_name=name)
                if u.path == "/api/calendar": return self.send_json(report.calendar(con, int(q["y"]), int(q["m"])))
                if u.path == "/api/day":
                    det = report.day_detail(con, q["date"])
                    det["uploads"] = [dict(r) for r in con.execute("""SELECT id, filename, loaded_at, status, note, rows_bukhara, rows_karantin, sum_sanoat, sum_meva, archive
                        FROM uploads WHERE report_dates LIKE ? ORDER BY id DESC""", (f'%"{q["date"]}"%',))]
                    return self.send_json(det)
                if u.path == "/api/uploads/file":
                    r = con.execute("SELECT filename, archive FROM uploads WHERE id=?", (int(q["id"]),)).fetchone()
                    f = (db.BASE / "gtd_archive" / r["archive"]) if r and r["archive"] else None
                    if not f or not f.exists():
                        f = next((x for x in (db.BASE / "gtd_archive").glob(f"*__{r['filename']}")), None) if r else None
                    if not f or not f.exists(): raise ValueError("Arxivda fayl topilmadi")
                    return self.send_file(f, download_name=r["filename"])
                if u.path == "/api/districts": return self.send_json(report.districts(con))
                if u.path == "/api/karantin":
                    D = q.get("date") or report.last_data_date(con)
                    rows = [dict(r) for r in con.execute("""SELECT report_date, inn, exporter, district_code, grown_district, tnved, product, country, netto, stat_usd, gtd_no
                        FROM gtd_rows WHERE voided=0 AND kind='meva' AND substr(report_date,1,7)=? AND report_date<=? ORDER BY report_date DESC, stat_usd DESC""", (D[:7], D))]
                    return self.send_json({"date": D, "by_district": report.karantin(con, D), "rows": rows, "opening_date": report.opening_date(con)})
                if u.path == "/api/companies":
                    sql = """SELECT inn,name,district_code,hudud,tarmoq,uyushma,rus_district,kind,product,source,confirmed,excluded,created_at,is_new,new_date,in_base,bukhara,bukhara_from,bukhara_to,
                             (SELECT min(report_date) FROM gtd_rows g WHERE g.inn=companies.inn AND g.voided=0) first_gtd,
                             EXISTS(SELECT 1 FROM template_inns t WHERE t.inn=companies.inn) in_template FROM companies WHERE 1=1"""
                    args = []
                    if q.get("district"): sql += " AND district_code=?"; args.append(q["district"])
                    if q.get("status") == "unconfirmed": sql += " AND confirmed=0"
                    if q.get("status") == "gtd": sql += " AND source='gtd'"
                    if q.get("status") == "nomma": sql += " AND source='nomma-nom'"
                    if q.get("status") == "new": sql += " AND new_date IS NOT NULL"
                    if q.get("status") == "notbase": sql += " AND in_base=0 AND source<>'gtd'"
                    if q.get("status") == "exporters": sql += " AND (EXISTS(SELECT 1 FROM template_inns t WHERE t.inn=companies.inn) OR EXISTS(SELECT 1 FROM gtd_rows g WHERE g.inn=companies.inn AND g.voided=0))"
                    sql += " ORDER BY confirmed, (new_date IS NOT NULL) DESC, new_date DESC, is_new DESC, (source='gtd') DESC, name"
                    rows = [dict(r) for r in con.execute(sql, args)]
                    if q.get("q"): rows = [r for r in rows if smart.match(q["q"], r["inn"], r["name"])]   # lotin/kirill farqsiz
                    return self.send_json(rows[:500])
                if u.path == "/api/uploads":
                    return self.send_json([dict(r) for r in con.execute("SELECT * FROM uploads ORDER BY id DESC LIMIT 200")])
                if u.path == "/api/audit":
                    return self.send_json([dict(r) for r in con.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 100")])
                if u.path == "/api/backups":
                    files = sorted(db.BACKUP_DIR.glob("export_*.db"), reverse=True) if db.BACKUP_DIR.exists() else []
                    return self.send_json([{"name": f.name, "size": f.stat().st_size, "mtime": dt.datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds")} for f in files])
                if u.path == "/api/integrity":
                    return self.send_json({"ok": db.integrity_ok(con)})
                if u.path == "/api/settings":
                    return self.send_json({r["key"]: r["value"] for r in con.execute("SELECT key,value FROM settings")})
                if u.path == "/api/tarmoqlar":
                    return self.send_json([r[0] for r in con.execute("SELECT DISTINCT trim(tarmoq) FROM companies WHERE source IN ('nomma-nom','gtd') AND tarmoq IS NOT NULL ORDER BY 1")])
                if u.path in ("/api/export/cumulative", "/api/export/day"):
                    D = q["date"]; ds = f"{D[8:10]}.{D[5:7]}.{D[:4]}"
                    if u.path.endswith("cumulative"):
                        nd = dt.date.fromisoformat(D) + dt.timedelta(days=1)
                        name = f"{nd:%d.%m.%Y} йил экспорт.xlsx"; out = db.BASE / "exports" / name
                        out.parent.mkdir(parents=True, exist_ok=True)
                        res = tpl.build(con, D, out)
                        with con: db.log(con, "export_cumulative", date=D, days=res["days"], new_rows=[x["inn"] for x in res["new_rows"]], warnings=res["warnings"])
                        return self.send_file(out, download_name=name, extra={"X-Export-Info": {k: res[k] for k in ("template_through", "days", "new_rows", "warnings", "meva", "sanoat_written")}})
                    else:
                        name = f"{ds} кунлик ГТД свод.xlsx"; out = db.BASE / "exports" / name
                        export.daily_workbook(con, D, out)
                    return self.send_file(out, download_name=name)
                return self.send_json({"error": f"«{u.path}» саҳифаси бу версияда йўқ — сайтни ёпиб, қайтадан ишга туширинг (эски нусха ишламоқда)."}, 404)
            finally:
                con.close()
        except Exception as e:
            return err_json(self, e, self.path)

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        try:
            origin = self.headers.get("Origin")
            if origin and urllib.parse.urlparse(origin).hostname not in ("127.0.0.1", "localhost"):
                return self.send_json({"error": "Tashqi sahifadan so'rov qabul qilinmaydi"}, 403)
            if u.path == "/api/quit":       # yangi nusxa eskisini almashtirmoqchi (token — export.lock faylidan)
                if (self.headers.get("X-Token") or "") != STATE["token"]:
                    return self.send_json({"error": "Token noto'g'ri"}, 403)
                self.send_json({"ok": True})
                print("Yangi nusxa ishga tushdi — bu oyna yopilmoqda.")
                threading.Thread(target=lambda: (time.sleep(0.3), release_lock(), os._exit(0)), daemon=True).start()
                return
            if u.path.startswith("/api/catalog/"):     # Каталог: расм/ҳужжат (катта тана) ва JSON амаллар
                self.require_write()
                n = int(self.headers.get("Content-Length") or 0)
                if n > 90 * 1024 * 1024: raise ValueError("Файл жуда катта (90 MB гача)")
                raw = self.rfile.read(n) if n > 0 else b""
                body = None if u.path == "/api/catalog/doc/upload" else json.loads(raw or b"{}")
                with WRITE_LOCK:
                    con = conn()
                    try: return self.send_json(catalog.http_post(con, u.path, body, raw, self.headers))
                    finally: con.close()
            if u.path == "/api/upload/preview":
                self.require_write()
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0 or n > 60 * 1024 * 1024: raise ValueError("Fayl bo'sh yoki juda katta")
                raw = self.rfile.read(n)
                fname = urllib.parse.unquote(self.headers.get("X-Filename") or "gtd.xls")
                ext = Path(fname).suffix.lower()
                if ext not in (".xls", ".xlsx"): raise ValueError("Faqat .xls yoki .xlsx fayl")
                token = hashlib.sha256(raw).hexdigest()
                inc = db.BASE / "incoming"; inc.mkdir(parents=True, exist_ok=True)
                p = inc / f"{token}{ext}"
                stage_write(p, raw)                      # atomic: .part -> os.replace (no half-written file, no antivirus race)
                stage_write(inc / f"{token}.name", fname.encode("utf-8"))
                stage_write(inc / f"{token}.date", (self.headers.get("X-Date") or "").encode("utf-8"))
                con = conn()
                try:
                    pv = daily.preview(con, p, expected_date=self.headers.get("X-Date") or None, replace=self.headers.get("X-Replace") == "1", data=raw)
                finally: con.close()
                pv["file"] = fname; pv["token"] = token
                pv.pop("_rows", None)
                return self.send_json(pv)
            if u.path == "/api/company/doc/upload":
                self.require_write()
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0 or n > 80 * 1024 * 1024: raise ValueError("Fayl bo'sh yoki juda katta (80 MB gacha)")
                raw = self.rfile.read(n)
                fname = urllib.parse.unquote(self.headers.get("X-Filename") or "fayl")
                with WRITE_LOCK:
                    con = conn()
                    try:
                        return self.send_json(companies.add_doc(con, self.headers.get("X-Inn") or "", fname, raw,
                                                                urllib.parse.unquote(self.headers.get("X-Note") or ""), self.headers.get("X-Date") or None))
                    finally:
                        con.close()
            if u.path == "/api/plans/import":
                self.require_write()
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0 or n > 20 * 1024 * 1024: raise ValueError("Fayl bo'sh yoki juda katta")
                raw = self.rfile.read(n)
                ext = Path(urllib.parse.unquote(self.headers.get("X-Filename") or "a.xlsx")).suffix.lower() or ".xlsx"
                if ext not in (".xlsx", ".xls"): raise ValueError("Faqat Excel fayl (.xlsx yoki .xls)")
                tmp = db.BASE / "incoming" / f"plan_{secrets.token_hex(4)}{ext}"; tmp.parent.mkdir(parents=True, exist_ok=True); tmp.write_bytes(raw)
                with WRITE_LOCK:
                    con = conn()
                    try: return self.send_json(plans.import_xlsx(con, int(self.headers.get("X-Id") or 0), tmp))
                    finally:
                        con.close(); tmp.unlink(missing_ok=True)
            if u.path == "/api/plans/import_svod":   # ҳар қандай режа Excel (универсал шаблон / вазирлик / СВОД) → янги режа, ойлар авто
                self.require_write()
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0 or n > 20 * 1024 * 1024: raise ValueError("Fayl bo'sh yoki juda katta")
                raw = self.rfile.read(n)
                ext = Path(urllib.parse.unquote(self.headers.get("X-Filename") or "a.xlsx")).suffix.lower() or ".xlsx"
                if ext not in (".xlsx", ".xls"): raise ValueError("Faqat Excel fayl (.xlsx yoki .xls)")
                tmp = db.BASE / "incoming" / f"plansvod_{secrets.token_hex(4)}{ext}"; tmp.parent.mkdir(parents=True, exist_ok=True); tmp.write_bytes(raw)
                with WRITE_LOCK:
                    con = conn()
                    try:
                        db.backup_if_stale("plan")
                        return self.send_json(plans.import_svod(con, tmp, int(self.headers.get("X-Year") or 0), self.headers.get("X-From") or "",
                                                                urllib.parse.unquote(self.headers.get("X-Title") or ""),
                                                                " · ".join(x for x in (urllib.parse.unquote(self.headers.get("X-Note") or "").strip(),
                                                                                       "Манба: " + urllib.parse.unquote(self.headers.get("X-Filename") or "")) if x)))
                    finally:
                        con.close(); tmp.unlink(missing_ok=True)
            if u.path == "/api/periods/import":
                self.require_write()
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0 or n > 20 * 1024 * 1024: raise ValueError("Fayl bo'sh yoki juda katta")
                raw = self.rfile.read(n)
                ext = Path(urllib.parse.unquote(self.headers.get("X-Filename") or "a.xlsx")).suffix.lower() or ".xlsx"
                tmp = db.BASE / "incoming" / f"period_{secrets.token_hex(4)}{ext}"; tmp.parent.mkdir(parents=True, exist_ok=True); tmp.write_bytes(raw)
                with WRITE_LOCK:
                    con = conn()
                    try: return self.send_json(periods.import_xlsx(con, int(self.headers.get("X-Year") or 0), int(self.headers.get("X-Months") or 0), tmp, self.headers.get("X-Set") or None))
                    finally:
                        con.close(); tmp.unlink(missing_ok=True)
            if u.path == "/api/contacts/import":
                self.require_write()
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0 or n > 40 * 1024 * 1024: raise ValueError("Fayl bo'sh yoki juda katta (40 MB gacha)")
                raw = self.rfile.read(n)
                fname = urllib.parse.unquote(self.headers.get("X-Filename") or "contacts.xlsx")
                with WRITE_LOCK:
                    con = conn()
                    try: return self.send_json(contacts_import.import_xlsx(con, fname, raw))
                    finally: con.close()
            if u.path == "/api/issue/file/upload":
                self.require_write()
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0 or n > 80 * 1024 * 1024: raise ValueError("Fayl bo'sh yoki juda katta (80 MB gacha)")
                raw = self.rfile.read(n)
                fname = urllib.parse.unquote(self.headers.get("X-Filename") or "fayl")
                with WRITE_LOCK:
                    con = conn()
                    try: return self.send_json(board.add_file(con, int(self.headers.get("X-Issue") or 0), fname, raw))
                    finally: con.close()
            if u.path == "/api/init/upload":
                self.require_write()
                kind = self.headers.get("X-Kind")
                if kind not in ("workbook", "baza"): raise ValueError("Noma'lum fayl turi")
                n = int(self.headers.get("Content-Length") or 0)
                fname = urllib.parse.unquote(self.headers.get("X-Filename") or "")
                ext = Path(fname).suffix.lower()
                if ext not in (".xls", ".xlsx"): raise ValueError("Faqat .xls yoki .xlsx")
                d = reinit.init_dir()
                for old in d.glob(f"{kind}.*"): old.unlink()
                (d / f"{kind}.name").write_text(fname, encoding="utf-8")
                with open(d / f"{kind}{ext}", "wb") as f:
                    left = n
                    while left > 0:
                        chunk = self.rfile.read(min(left, 1 << 20))
                        if not chunk: break
                        f.write(chunk); left -= len(chunk)
                return self.send_json({"ok": True, "name": fname, "size": n})
            body = self.body_json()
            with WRITE_LOCK:
                self.require_write()
                con = conn()
                try:
                    if u.path == "/api/upload/save":
                        token = body["token"]
                        p = next((db.BASE / "incoming").glob(f"{token}.xls*"), None)
                        if p is None: raise ValueError("Yuklangan fayl topilmadi — faylni qaytadan tanlang.")
                        raw = read_retry(p)
                        fname = (db.BASE / "incoming" / f"{token}.name").read_text(encoding="utf-8")
                        dfile = db.BASE / "incoming" / f"{token}.date"
                        exp = dfile.read_text(encoding="utf-8").strip() if dfile.exists() else ""
                        pv = daily.preview(con, p, expected_date=exp or None, replace=bool(body.get("replace")), data=raw)
                        pv["file"] = fname
                        res = daily.save(con, p, pv, accepted_candidates=body.get("accepted") or {}, answers=body.get("answers") or {}, data=raw)
                        safe = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", Path(fname).name)[:120] or "gtd.xls"
                        try:      # the rows are already saved; a failed archive copy must not look like a failed upload
                            arch = db.BASE / "gtd_archive" / f"{'_'.join(sorted(pv['dates']))}__{res['upload_id']}__{safe}"
                            arch.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, arch)
                            with con: con.execute("UPDATE uploads SET archive=? WHERE id=?", (arch.name, res["upload_id"]))
                        except Exception as e:
                            res["warning"] = f"Ma'lumot saqlandi, lekin fayl nusxasi arxivga yozilmadi: {e}"
                        for f in (p, db.BASE / "incoming" / f"{token}.name", dfile):
                            try: f.unlink()
                            except OSError: pass
                        return self.send_json(res)
                    if u.path == "/api/init/check":
                        con.close()
                        return self.send_json(reinit.check(body.get("mode")))
                    if u.path == "/api/reset":
                        if body.get("confirm") != "TOZALASH": raise ValueError("Tasdiqlash so'zi noto'g'ri")
                        bk = db.backup("before_reset")
                        db.reset_all(con, keep_manual=bool(body.get("keep_manual", True)))
                        tpl = db.BASE / "template.xlsx"
                        if tpl.exists(): shutil.move(str(tpl), str(db.BACKUP_DIR / f"template_before_reset_{dt.datetime.now():%Y-%m-%d_%H-%M-%S}.xlsx"))
                        for sub in ("init", "incoming"):
                            for f in (db.BASE / sub).glob("*"):
                                try: f.unlink()
                                except OSError: pass
                        return self.send_json({"ok": True, "backup": bk.name if bk else None})
                    if u.path == "/api/init/apply":
                        con.close()
                        return self.send_json(reinit.apply(body.get("mode")))
                    if u.path == "/api/uploads/void":
                        daily.void_upload(con, int(body["id"]), body.get("reason", ""))
                        return self.send_json({"ok": True})
                    if u.path == "/api/company/contacts":
                        companies.save_contacts(con, body["inn"], body); return self.send_json({"ok": True})
                    if u.path == "/api/company/person/save":
                        return self.send_json(companies.save_person(con, body))
                    if u.path == "/api/company/person/delete":
                        return self.send_json(companies.delete_person(con, int(body["id"])))
                    if u.path == "/api/issues/save":
                        return self.send_json(companies.save_issue(con, body))
                    if u.path == "/api/issues/move":
                        return self.send_json(board.move_issue(con, int(body["id"]), int(body["column_id"]), body.get("position")))
                    if u.path == "/api/issues/delete":
                        return self.send_json(board.delete_issue(con, int(body["id"])))
                    if u.path == "/api/issue/file/remove":
                        return self.send_json(board.remove_file(con, int(body["id"])))
                    if u.path == "/api/board/column/save":
                        return self.send_json(board.save_column(con, body))
                    if u.path == "/api/board/column/delete":
                        return self.send_json(board.delete_column(con, int(body["id"]), int(body["move_to"]) if body.get("move_to") else None))
                    if u.path == "/api/board/columns/reorder":
                        return self.send_json(board.reorder_columns(con, body.get("ids") or []))
                    if u.path == "/api/board/label/save":
                        return self.send_json(board.save_label(con, body))
                    if u.path == "/api/board/label/delete":
                        return self.send_json(board.delete_label(con, int(body["id"])))
                    if u.path == "/api/issue/comment/save":
                        return self.send_json(board.save_comment(con, body))
                    if u.path == "/api/issue/comment/delete":
                        return self.send_json(board.delete_comment(con, int(body["id"])))
                    if u.path == "/api/issue/check/save":
                        return self.send_json(board.save_check(con, body))
                    if u.path == "/api/issue/check/delete":
                        return self.send_json(board.delete_check(con, int(body["id"])))
                    if u.path == "/api/issue/check/reorder":
                        return self.send_json(board.reorder_checks(con, int(body["issue_id"]), body.get("ids") or []))
                    if u.path == "/api/company/doc/remove":
                        companies.remove_doc(con, int(body["id"])); return self.send_json({"ok": True})
                    if u.path == "/api/companies/update":
                        fields = {k: body[k] for k in ("district_code", "tarmoq", "uyushma", "hudud", "rus_district", "confirmed", "name") if k in body}
                        if "bukhara" in body: fields["bukhara"] = None if body["bukhara"] in ("", None) else int(body["bukhara"])
                        for k in ("bukhara_from", "bukhara_to"):
                            if k in body:
                                v = str(body[k] or "").strip()
                                if v and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v): raise ValueError("Sana формати: ЙЙЙЙ-ОО-КК")
                                fields[k] = v or None
                        if fields.get("bukhara_from") and fields.get("bukhara_to") and fields["bukhara_from"] > fields["bukhara_to"]:
                            raise ValueError("«дан» санаси «гача» санасидан кейин бўлмасин")
                        src_new = None
                        if "opening_source" in body:
                            src_new = str(body["opening_source"] or "customs")
                            if src_new not in dispute.SOURCES: raise ValueError("Йил боши манбаси: customs ёки template")
                        if not fields and src_new is None: raise ValueError("O'zgarish yo'q")
                        db.backup_if_stale("before_company_edit")
                        old = con.execute("SELECT * FROM companies WHERE inn=?", (body["inn"],)).fetchone()
                        with con:
                            if src_new is not None and old and (old["opening_source"] or "customs") != src_new:
                                # «Йил боши манбаси»: the sanoat opening rows of this company are rewritten at once (dispute.apply_source)
                                res = dispute.apply_source(con, body["inn"], src_new)
                                lab_s = {"customs": "Божхона базаси", "template": "Шаблон (қўлда)"}
                                db.event(con, body["inn"], "edit", f"Йил боши манбаси: {lab_s[old['opening_source'] or 'customs']} → {lab_s[src_new]} (янв–{report.MONTH_NAMES[dispute.base_month(con)-1].lower()} = {res['total']:,.3f} минг $)".replace(",", " "))
                                db.log(con, "opening_source_template" if src_new == "template" else "opening_source_customs", inn=body["inn"], **res)
                            if old and fields:
                                dn = {r["code"]: r["name_uz"] for r in con.execute("SELECT code, name_uz FROM districts")}
                                lab = {"district_code": "туман", "tarmoq": "тармоқ", "uyushma": "уюшма", "hudud": "ҳудуд", "rus_district": "рус тумани", "name": "номи", "bukhara": "Бухоро ҳолати",
                                       "bukhara_from": "Бухорода ҳисобга олиш бошланиши", "bukhara_to": "Бухорода ҳисобга олиш тугаши"}
                                show = lambda k, v: dn.get(v, v) if k == "district_code" else ({1: "Бухоро", 0: "Бухоро эмас", None: "номаълум"}.get(v, v) if k == "bukhara" else (f"{v[8:10]}.{v[5:7]}.{v[:4]}" if k in ("bukhara_from", "bukhara_to") and v else v))
                                for k, v in fields.items():
                                    norm = (lambda x: x) if k == "bukhara" else (lambda x: x or None)
                                    if k in lab and norm(old[k]) != norm(v):
                                        db.event(con, body["inn"], "edit", f"{lab[k].capitalize()}: {show(k, old[k]) or '—'} → {show(k, v) or '—'}")
                            if fields: con.execute(f"UPDATE companies SET {', '.join(k+'=?' for k in fields)}, updated_at=datetime('now','localtime') WHERE inn=?", [*fields.values(), body["inn"]])
                            if "bukhara" in fields or "bukhara_from" in fields or "bukhara_to" in fields:
                                # saved GTD rows follow the decision: sanoat inside the Bukhara period, not_bukhara outside (or everywhere when «Бухоро эмас»)
                                c = con.execute("SELECT in_base, bukhara, bukhara_from, bukhara_to, source FROM companies WHERE inn=?", (body["inn"],)).fetchone()
                                counted = bool(c and (c["in_base"] or c["bukhara"] == 1 or c["source"] == "gtd"))
                                if c and c["bukhara"] == 0: counted = False
                                lo, hi = (c["bukhara_from"] or "") if c else "", (c["bukhara_to"] or "9999") if c else "9999"
                                if counted:
                                    con.execute("UPDATE gtd_rows SET kind='sanoat' WHERE inn=? AND kind='not_bukhara' AND report_date>=? AND report_date<=?", (body["inn"], lo, hi))
                                    con.execute("UPDATE gtd_rows SET kind='not_bukhara' WHERE inn=? AND kind='sanoat' AND (report_date<? OR report_date>?)", (body["inn"], lo, hi))
                                else: con.execute("UPDATE gtd_rows SET kind='not_bukhara' WHERE inn=? AND kind='sanoat'", (body["inn"],))
                            if fields: db.log(con, "company_update", inn=body["inn"], **fields)
                        return self.send_json({"ok": True})
                    if u.path == "/api/backups/create":
                        p = db.backup("manual"); return self.send_json({"ok": True, "name": p.name if p else None})
                    if u.path == "/api/backups/restore":
                        name = Path(body["name"]).name
                        src = db.BACKUP_DIR / name
                        if not src.exists(): raise ValueError("Zaxira topilmadi")
                        test = db.connect(src)
                        ok = db.integrity_ok(test); test.close()
                        if not ok: raise ValueError("Zaxira fayli buzilgan — qaytarilmadi")
                        con.close()
                        db.backup("before_restore")
                        reinit.swap_db_copy(src)
                        con = conn()
                        db.log(con, "backup_restored", name=name); con.commit()
                        return self.send_json({"ok": True})
                    if u.path == "/api/plans/create":
                        vid = plans.create_version(con, int(body["year"]), body.get("effective_from") or "", body.get("title") or "", body.get("note") or "",
                                                   int(body["copy_from"]) if body.get("copy_from") else None, bool(body.get("from_workbook")))
                        return self.send_json({"ok": True, "id": vid})
                    if u.path == "/api/plans/save":
                        return self.send_json(plans.save_grid(con, int(body["id"]), body.get("rows") or [], body.get("meta")))
                    if u.path == "/api/plans/main":
                        plans.set_main(con, int(body["id"])); return self.send_json({"ok": True})
                    if u.path == "/api/plans/delete":
                        plans.delete_version(con, int(body["id"])); return self.send_json({"ok": True})
                    if u.path == "/api/prev_year":
                        return self.send_json(prev_year_save(con, body))
                    if u.path == "/api/periods/save":
                        return self.send_json(periods.save(con, int(body.get("year") or 0), int(body["months"]), body.get("rows") or [], body.get("set_id") or None))
                    if u.path == "/api/analysis/mahsulot/set/save":
                        return self.send_json(mahsulot.save_set(con, body))
                    if u.path == "/api/analysis/mahsulot/set/delete":
                        return self.send_json(mahsulot.delete_set(con, str(body.get("id") or "")))
                    if u.path == "/api/periods/delete":
                        return self.send_json(periods.delete(con, int(body.get("year") or 0), int(body["months"]), body.get("set_id") or None))
                    if u.path == "/api/fact_sets/create":
                        return self.send_json(periods.create_set(con, int(body.get("year") or 0), body.get("title") or "", body.get("note") or "", body.get("copy_from") or None))
                    if u.path == "/api/fact_sets/update":
                        return self.send_json(periods.update_set(con, int(body["id"]), body.get("title"), body.get("note"), bool(body.get("main"))))
                    if u.path == "/api/fact_sets/delete":
                        return self.send_json(periods.delete_set(con, int(body["id"])))
                    if u.path == "/api/settings":
                        allowed = {"prev_year_day_offset", "report_sign_pos", "report_sign_name"}
                        with con:
                            for k, v in body.items():
                                if k in allowed: db.set_setting(con, k, v)
                        return self.send_json({"ok": True})
                    return self.send_json({"error": f"«{u.path}» саҳифаси бу версияда йўқ — сайтни ёпиб, қайтадан ишга туширинг (эски нусха ишламоқда)."}, 404)
                finally:
                    try: con.close()
                    except Exception: pass
        except PermissionError as e:
            return self.send_json({"error": str(e)}, 423)
        except Exception as e:
            return err_json(self, e, self.path)

def bind(port):
    try: return ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError: return None

def read_lock() -> dict:
    try: return json.loads(lock_path().read_text(encoding="utf-8"))
    except Exception: return {}

def quit_running(port: int, token) -> bool:
    """Ishlab turgan nusxaga «yopil» deб so'raymiz. Token export.lock faylidan — faqat shu kompyuterdagi nusxa yopiladi."""
    if not token: return False
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/quit", data=b"{}", method="POST",
                                     headers={"X-Token": token, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False

def main():
    cfg = load_config()
    set_data_dir(cfg["data_path"])
    port = int(cfg["port"])
    url = f"http://127.0.0.1:{port}/"
    srv = bind(port)
    if srv is None:                      # port band: eski nusxани almashtirishga urinamiz
        info = read_lock()
        if quit_running(port, info.get("token")):
            for _ in range(24):
                time.sleep(0.25)
                srv = bind(port)
                if srv: break
        if srv is None:
            print("=" * 70)
            print(f"SAYT ALLAQACHON ISHLAB ТУРИБДИ (port {port}" + (f", PID {info.get('pid')}" if info.get("pid") else "") + ").")
            print("U ESKI КОД bilan ishlayapti — yangi o'zgarishlar ko'rinmaydi.")
            print("Uni yoping: ochiq qora oynани ✕ bilan yoping yoki Vazifalar boshqaruvchisида (Ctrl+Shift+Esc)")
            print("«python.exe» жараёнини tugating. So'ng shu faylни qaytadan ishga tushiring.")
            print("=" * 70)
            webbrowser.open(url); return
        print("Eski nusxa yopildi, yangi versiya ishga tushdi.")
    if not db.DB_PATH.exists():
        seed = ROOT / "seed" / "export.db"
        if seed.exists():
            shutil.copy2(seed, db.DB_PATH)
            print("Boshlang'ich baza nusxalandi:", db.DB_PATH)
    con = db.connect()
    if not db.integrity_ok(con):
        print("DIQQAT: baza butunlik tekshiruvidan o'tmadi! 'Nazorat va tarix' bo'limida zaxiradan qaytaring.")
    con.close()
    acquire_lock()
    threading.Thread(target=heartbeat, daemon=True).start()
    today = dt.date.today().isoformat()
    if not any(today in f.name for f in db.BACKUP_DIR.glob("export_*daily*.db")) if db.BACKUP_DIR.exists() else True:
        db.backup("daily")
    print(f"Buxoro Eksport Monitor ishlayapti: {url}\nBaza: {db.DB_PATH}\nTo'xtatish: bu oynani yoping (yoki Ctrl+C).")
    if STATE["readonly"]:
        print(f"DIQQAT: baza {STATE['lock_owner'].get('host')} kompyuterida ochiq — faqat ko'rish rejimi.")
    if cfg.get("open_browser", True):
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        release_lock()

if __name__ == "__main__":
    main()
