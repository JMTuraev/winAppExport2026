"""Opening data in two independent steps (run from Sozlamalar):
  baza     — monthly customs base: registry + sanoat opening (sources.import_customs_base)
  workbook — own workbook (.xlsx) = Excel template; also prognoz, meva-sabzavot opening, company attributes (sources.import_workbook)
Each step: check (run on a copy of the live DB, show the summary) -> apply (backup + swap).
"""
from __future__ import annotations
import os, shutil, json, sqlite3, datetime as dt
from pathlib import Path
from . import db, init_import, sources

def init_dir() -> Path:
    p = db.BASE / "init"; p.mkdir(parents=True, exist_ok=True); return p

def _file(kind: str):
    # files are removed by «Bazani tozalash»; after a successful apply the uploaded file is removed as well
    for p in init_dir().glob(f"{kind}.*"):
        if p.suffix.lower() in (".xls", ".xlsx"): return p
    return None

def _live_state():
    st = db.DB_PATH.stat()
    con = sqlite3.connect(str(db.DB_PATH))
    try: ups = con.execute("SELECT count(*) FROM uploads").fetchone()[0]
    finally: con.close()
    return {"mtime": st.st_mtime_ns, "uploads": ups}

def check(mode: str) -> dict:
    if mode not in ("baza", "workbook"): raise ValueError("Noma'lum qadam")
    f = _file(mode)
    if not f: raise ValueError("Fayl tanlanmagan" if mode == "baza" else "O'z jadvalingiz fayli tanlanmagan")
    from .daily import sha256
    orig_sha = sha256(f)
    new_path = init_dir() / "export_new.db"
    for suf in ("", "-journal"): Path(str(new_path) + suf).unlink(missing_ok=True)
    live = _live_state()
    shutil.copy2(db.DB_PATH, new_path)
    new = db.connect(new_path)
    try:
        if mode == "baza":
            res = sources.import_customs_base(new, f)
        else:
            from . import tpl
            if f.suffix.lower() == ".xls":
                k = sources._sheet_kind(f)
                if k != "workbook": raise ValueError(sources.WRONG_FILE.get(k, sources.WRONG_FILE["unknown"]))
                conv = init_dir() / "workbook_excel.xlsx"
                try:
                    tpl.xls_to_xlsx(f, conv)
                except Exception as e:
                    raise ValueError(f"Jadvalni .xlsx ga o'girib bo'lmadi ({e}). " + sources.XLSX_ONLY)
                f = conv
            tpl_new = init_dir() / "template_new.xlsx"
            tpl.sanitize(f, tpl_new)              # the user's workbook as is (formulas, external links); only \x1a removed
            nm = init_dir() / "workbook.name"
            res = sources.import_workbook(new, f, tpl_new, display_name=nm.read_text(encoding="utf-8") if nm.exists() else f.name, sha=orig_sha)
            names = {r["code"]: r["name_uz"] for r in new.execute("SELECT code,name_uz FROM districts")}
            for x in res["svod"]["meva_by_district"]: x["name"] = names.get(x["code"], x["code"])
        with new:
            db.set_setting(new, "init_mode", mode)
            db.set_setting(new, "init_live", json.dumps(live))
    except Exception:
        new.close(); new_path.unlink(missing_ok=True); (init_dir() / "template_new.xlsx").unlink(missing_ok=True); raise
    finally:
        (init_dir() / "workbook_excel.xlsx").unlink(missing_ok=True)
    new.close()
    res["mode"] = mode; res["file"] = f.name
    nm = init_dir() / f"{mode}.name"
    if nm.exists(): res["file"] = nm.read_text(encoding="utf-8")
    return res

def _flush(path: Path) -> None:
    """Push the copy to disk before renaming. Windows needs a writable handle for fsync; failure here is not fatal."""
    try:
        with open(path, "r+b") as f:
            f.flush(); os.fsync(f.fileno())
    except OSError:
        pass

def swap_db_copy(src) -> None:
    """Restore from a backup file without removing it."""
    tmp = Path(str(db.DB_PATH) + ".new")
    shutil.copy2(src, tmp); _flush(tmp)
    os.replace(tmp, db.DB_PATH)
    Path(str(db.DB_PATH) + "-journal").unlink(missing_ok=True)

def swap_db(src: Path) -> None:
    """Replace the live database atomically (copy next to it, flush, rename)."""
    tmp = Path(str(db.DB_PATH) + ".new")
    shutil.copy2(src, tmp); _flush(tmp)
    os.replace(tmp, db.DB_PATH)
    Path(str(db.DB_PATH) + "-journal").unlink(missing_ok=True)
    Path(src).unlink(missing_ok=True)

def apply(mode: str | None = None) -> dict:
    new_path = init_dir() / "export_new.db"
    if not new_path.exists(): raise ValueError("Avval «Tekshirish» ni bosing")
    new = sqlite3.connect(str(new_path))
    get = lambda k: (new.execute("SELECT value FROM settings WHERE key=?", (k,)).fetchone() or [None])[0]
    checked_mode = get("init_mode"); live_then = json.loads(get("init_live") or "{}"); store = get("template_store")
    if mode and checked_mode and mode != checked_mode:
        raise ValueError(f"«Tekshirish» boshqa qadamda bosilgan ({'бojxona bazasi' if checked_mode == 'baza' else 'o`z jadvalingiz'}) — shu qadamda «Tekshirish» ni qayta bosing")
    mode = checked_mode
    new.execute("DELETE FROM settings WHERE key IN ('init_mode','init_live')"); new.commit(); new.close()
    if _live_state() != live_then:
        new_path.unlink(missing_ok=True)
        raise ValueError("Tekshiruvdan keyin bazada o'zgarish bo'ldi (masalan GTD yuklandi) — «Tekshirish» ni qayta bosing")
    if mode == "workbook":
        tpl_new = init_dir() / "template_new.xlsx"
        if not tpl_new.exists():
            new_path.unlink(missing_ok=True); raise ValueError("Shablon fayli topilmadi — «Tekshirish» ni qayta bosing")
        target = db.BASE / (store or "template.xlsx")      # versions are kept: a DB backup restore finds its own template
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tpl_new, target)                       # template first, then the DB that points to it
    bk = db.backup(f"before_{mode}")
    swap_db(new_path)                                   # atomic: a crash mid-copy must not leave a truncated export.db
    (init_dir() / "template_new.xlsx").unlink(missing_ok=True)
    for f in init_dir().glob(f"{mode}.*"):
        try: f.unlink()
        except OSError: pass
    con = db.connect()
    with con: db.log(con, f"init_{mode}_applied", backup=bk.name if bk else None)
    con.close()
    return {"ok": True, "mode": mode, "backup": bk.name if bk else None}
