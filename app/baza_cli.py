"""Bojxona bazasini brauzersiz yuklash (Baza_yuklash.bat).

  python -m app.baza_cli                      -> kiritiladiganMalumotlar papkasidagi eng yangi «… baza …» faylini oladi
  python -m app.baza_cli "D:\\...\\fayl.xlsx"   -> ko'rsatilgan faylni oladi

Saytdagi «Sozlamalar → 1. Bojxona bazasi» bilan aynan bir xil yo'l: fayl init/ ga nusxalanadi, baza NUSXASIDA import
qilinadi (reinit.check), natija va tekshiruv jadvali ko'rsatiladi, «ha» deyilsa zaxira olinib almashtiriladi (reinit.apply).
Yillik «12 oy» fayl: undagi yillar (2024, 2025) saytdan to'liq tozalanib qayta yuklanadi; joriy yil (2026) tegilmaydi.
Sayt ochiq bo'lsa ham ishlaydi (almashtirish atomar), lekin yuklash paytida saytda GTD yuklamang.
"""
from __future__ import annotations
import sys, json, shutil, re
from pathlib import Path

def _cfg_data_dir() -> Path:
    from . import db
    app_dir = Path(__file__).resolve().parent.parent
    cfg = {"data_dir": "data"}
    c = app_dir / "config.json"
    if c.exists(): cfg.update(json.loads(c.read_text(encoding="utf-8")))
    d = Path(cfg["data_dir"])
    if not d.is_absolute(): d = app_dir / d
    d = d.resolve()
    db.BASE = d; db.DB_PATH = d / "export.db"; db.BACKUP_DIR = d / "backups"
    return d

def _pick_file(arg: str | None) -> Path:
    if arg:
        p = Path(arg)
        if not p.exists(): raise SystemExit(f"Fayl topilmadi: {p}")
        return p
    root = Path(__file__).resolve().parent.parent.parent / "kiritiladiganMalumotlar"
    cands = [p for p in root.glob("*.xls*") if not p.name.startswith("~$") and re.search(r"baza|база", p.name, re.I)]
    if not cands: raise SystemExit(f"{root} ichida «baza» so'zi bor .xlsx fayl topilmadi. Fayl yo'lini argument qilib bering.")
    cands.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    print("Topilgan fayllar (eng yangisi birinchi):")
    for i, p in enumerate(cands, 1): print(f"  {i}. {p.name}  ({p.stat().st_size // 1048576} MB)")
    ans = input("Qaysi biri? [1]: ").strip() or "1"
    return cands[int(ans) - 1]

def _fmt(v): return f"{v:,.1f}".replace(",", " ")

def main(argv):
    data_dir = _cfg_data_dir()
    from . import db, reinit
    if not db.DB_PATH.exists(): raise SystemExit(f"Baza topilmadi: {db.DB_PATH} — avval saytni bir marta ishga tushiring.")
    f = _pick_file(argv[0] if argv else None)
    print(f"\nFayl: {f}\nBaza: {db.DB_PATH}\n")
    d = reinit.init_dir()
    for old in d.glob("baza.*"): old.unlink()
    (d / "baza.name").write_text(f.name, encoding="utf-8")
    shutil.copy2(f, d / f"baza{f.suffix.lower()}")
    print("Tekshirilmoqda (baza nusxasida import, 1–2 daqiqa)…")
    try:
        r = reinit.check("baza")
    except Exception as e:
        raise SystemExit(f"XATO: {e}")
    T = r.get("tree", {})
    print(f"\n{'Tarixiy baza' if r.get('operational') is False else 'Joriy baza'}: {', '.join(map(str, r.get('years', [])))} yil"
          f" · to'liq tozalanib qayta yuklanadigan yillar: {', '.join(map(str, r.get('full_years', []))) or '—'}")
    print(f"Daraxt: {T.get('declarations', 0):,} GTD · {T.get('items', 0):,} tovar qatori (eksport {T.get('export_items', 0):,}, import {T.get('import_items', 0):,})"
          f" · reyestr {r['registry']['inns']:,} INN, yangi {r['registry']['added']}")
    print("\nTekshiruv (fayl ↔ sayt daraxti), ming $:")
    print(f"{'yil':>5} {'qator fayl':>11} {'qator sayt':>11} {'eksport ЭК':>12} {'sanoat':>11} {'meva':>10} {'BNPZ':>10} {'import ИМ':>13}  holat")
    for v in r.get("verify", []):
        print(f"{v['year']:>5} {v['file_rows']:>11,} {v['db_rows']:>11,} {_fmt(v['db']['ek']):>12} {_fmt(v['db']['sanoat']):>11} {_fmt(v['db']['meva']):>10} {_fmt(v['db']['bnpz']):>10} {_fmt(v['db']['im']):>13}  {'MOS' if v['ok'] else 'FARQ!'}")
    if not r.get("verify_ok", True):
        print("\nDIQQAT: fayl va sayt daraxti orasida farq bor — almashtirilmaydi.")
        (d / "export_new.db").unlink(missing_ok=True); return 2
    ans = input("\nSaytdagi bazani shu bilan almashtiraymi? (zaxira olinadi) [ha/yo'q]: ").strip().lower()
    if ans not in ("ha", "h", "y", "yes", "да"):
        (d / "export_new.db").unlink(missing_ok=True); print("Bekor qilindi, sayt o'zgarmadi."); return 1
    res = reinit.apply("baza")
    print(f"\nTAYYOR. Zaxira: {res.get('backup')}\nSayt ochiq bo'lsa sahifani yangilang (F5).")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
