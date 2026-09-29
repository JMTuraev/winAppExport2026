"""Reja (prognoz) — versiyalar bilan, oylar bo'yicha, tuman va tur kesimida.

Bir yilga bir nechta nomli reja bo'lishi mumkin; jadval tortishda keraklisi tanlanadi, tanlanmasa — yilning «★ asosiy» rejasi
(29.09.2026 dan `effective_from` ishlatilmaydi — eski ustun, har doim yil boshi). Versiya bo'lmasa —
o'z jadvalingizdan (СВОД) o'qilgan eski `prognoz` jadvali ishlaydi (avvalgidek).

Atom birlik — oy: yillik = 12 oy yig'indisi, davr rejasi = yil boshidan joriy oy oxirigacha oylar yig'indisi (eski qoida bilan bir xil).
Viloyat qatori tumanlar yig'indisi (alohida kiritilmaydi). Istisno (28.09.2026): СВОД'dan (jadval yoki Excel) yaratilganda rasmiy viloyat
raqami tumanlar yig'indisidan farq qilsa, farq `district_code='1706'` qatorlarida «tuzatma» sifatida saqlanadi: viloyat = yig'indi + tuzatma
(tumanlar qo'lda tahrirlansa ham tuzatma o'zgarmaydi).

Oylik avto-bo'linma (28.09.2026): СВОД'da faqat yillik, davr (yanvar–N oy) va N-oy prognozi bor → `split_months`:
N-oy = oy prognozi; 1..N−1 oylar = (davr − oy)/(N−1) teng; N+1..12 = (yillik − davr)/(12−N) teng. N-oy kunlaridagi hisobotda
yillik/davr/oy raqamlari manbadagi bilan aynan bir xil chiqadi. Kunlik hisobotda istalgan versiyani tanlash mumkin (`plan_for(..., version_id)`).
"""
from __future__ import annotations
import datetime as dt, json
from collections import defaultdict
from . import db, report

KINDS = ("sanoat", "meva")
REGION = "1706"   # plan_values da faqat rasmiy viloyat raqami tuzatmasi (yig'indidan farqi)
KIND_UZ = {"sanoat": "Саноат маҳсулотлари", "meva": "Мева-сабзавотлар"}
MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS plan_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, effective_from TEXT NOT NULL,   -- YYYY-MM-DD
  title TEXT, note TEXT, source TEXT, created_at TEXT DEFAULT (datetime('now','localtime')), updated_at TEXT
);
CREATE TABLE IF NOT EXISTS plan_values (
  version_id INTEGER NOT NULL REFERENCES plan_versions(id) ON DELETE CASCADE,
  district_code TEXT NOT NULL, kind TEXT NOT NULL, month INTEGER NOT NULL, amount REAL NOT NULL DEFAULT 0,
  PRIMARY KEY (version_id, district_code, kind, month)
);
"""

def ensure(con):
    con.executescript(SCHEMA)
    if "main" not in {r[1] for r in con.execute("PRAGMA table_info(plan_versions)")}:
        # 29.09.2026: кучга кириш санаси ўрнига — йилнинг «★ асосий» режаси (танланмаганда шу олинади)
        con.execute("ALTER TABLE plan_versions ADD COLUMN main INTEGER NOT NULL DEFAULT 0")
        for (y,) in con.execute("SELECT DISTINCT year FROM plan_versions").fetchall():
            r = con.execute("SELECT id FROM plan_versions WHERE year=? ORDER BY effective_from DESC, id DESC LIMIT 1", (y,)).fetchone()
            if r: con.execute("UPDATE plan_versions SET main=1 WHERE id=?", (r[0],))
    if "block_to" not in {r[1] for r in con.execute("PRAGMA table_info(plan_versions)")}:
        # 29.09.2026: ўтган давр — битта блок (январь–N жами), ойларга бўлинмайди. Блок жами N-ой катагида, 1..N−1 = 0.
        # Реж N-ойгача (N ҳам) бўлган саналар учун «мос эмас» — ҳисобот юкланмайди.
        con.execute("ALTER TABLE plan_versions ADD COLUMN block_to INTEGER NOT NULL DEFAULT 0")

# ------------------------------------------------------------------ o'qish
def versions(con, year: int | None = None) -> list[dict]:
    ensure(con)
    w, a = ("WHERE year=?", (year,)) if year else ("", ())
    out = []
    for r in con.execute(f"SELECT * FROM plan_versions {w} ORDER BY year DESC, main DESC, id DESC", a):
        d = dict(r)
        d["total"] = con.execute("SELECT coalesce(sum(amount),0) FROM plan_values WHERE version_id=?", (d["id"],)).fetchone()[0]
        out.append(d)
    return out

def cards(con) -> list[dict]:
    """Sozlamalar → «Режалар» карталари (29.09.2026): ҳар версия — номи, йили, кучга кириш санаси, манбаси, вилоят жами
    (саноат / мева / жами, расмий тузатма билан), 12 ой (мини диаграмма учун) ва «амалда» белгиси (жорий йилда — охирги
    маълумот кунида, бошқа йилларда — йил охирида амалдаги версия)."""
    ensure(con)
    codes = [d["code"] for d in report.districts(con)]
    last = report.last_data_date(con) or dt.date.today().isoformat()
    eff_cache = {}
    def eff_id(y):
        if y not in eff_cache:
            D = last if int(last[:4]) == y else f"{y}-12-31"
            v = effective_version(con, D); eff_cache[y] = v["id"] if v else None
        return eff_cache[y]
    out = []
    for v in versions(con):
        vals = values(con, v["id"]); has_adj = REGION in vals
        mon = {k: [sum(vals[c][k][i] for c in codes) + (vals[REGION][k][i] if has_adj else 0.0) for i in range(12)] for k in KINDS}
        allm = [mon["sanoat"][i] + mon["meva"][i] for i in range(12)]
        bt = int(v.get("block_to") or 0)
        if bt:   # мини-диаграмма: блок ойлари — ўртача (оч рангда)
            avg = sum(allm[:bt]) / bt; allm = [avg] * bt + allm[bt:]
        filled = con.execute("SELECT count(DISTINCT district_code||'|'||kind) FROM plan_values WHERE version_id=? AND district_code<>?", (v["id"], REGION)).fetchone()[0]
        out.append({**{k: v[k] for k in ("id", "year", "effective_from", "title", "note", "source", "created_at", "updated_at", "main", "block_to")},
                    "sanoat": round(sum(mon["sanoat"]), 3), "meva": round(sum(mon["meva"]), 3), "all": round(sum(allm), 3),
                    "months": [round(x, 3) for x in allm], "filled": filled, "cells": len(codes) * len(KINDS), "region_adj": has_adj,
                    "effective": eff_id(v["year"]) == v["id"]})
    return out

MONTHS_GEN = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]

def block_label(b: int) -> str:
    return f"январь–{MONTHS_GEN[b - 1]}" if b and b > 1 else (MONTHS_GEN[0] if b == 1 else "")

def covers(v: dict | None, D: str) -> bool:
    """Режа D санасига мосми: ўтган давр блоки (январь–N) бўлса, фақат N+1-ойдан бошлаб."""
    return bool(v) and int(D[5:7]) > int(v.get("block_to") or 0)

def cover_error(v: dict, D: str) -> str:
    return (f"«{v['title']}» режасида {block_label(v['block_to'])} битта жами сифатида берилган — "
            f"{D[8:10]}.{D[5:7]}.{D[:4]} санаси учун мос режа йўқ. Бошқа режа танланг ёки Созламалар → Режалар'да бу давр учун режа қўшинг.")

def require_cover(con, D: str, plan):
    """Excel юклашдан олдин: танланган (ёки стандарт) режа D санасига мос бўлмаса — хато (юклаб бўлмайди)."""
    ensure(con)
    if plan == "table": return
    if plan:
        v = get_version(con, plan)
        if not v: raise ValueError("Танланган режа топилмади — ойнани ёпиб, қайта очинг")
        if not covers(v, D): raise ValueError(cover_error(v, D))
        return
    vs = versions(con, int(D[:4]))
    if vs and not any(covers(v, D) for v in vs):
        raise ValueError(f"{D[8:10]}.{D[5:7]}.{D[:4]} санаси учун Созламалардаги режалардан ҳеч бири мос эмас (" +
                         "; ".join(f"«{v['title']}» — {block_label(v['block_to'])} блок" for v in vs if v.get("block_to")) +
                         "). Бу давр учун режа қўшинг.")

def effective_version(con, D: str) -> dict | None:
    """D йилининг стандарт режаси: «★ асосий» (бўлмаса — энг охирги қўшилгани). Кучга кириш санаси ишлатилмайди (29.09.2026):
    керакли режа жадвал тортишда танланади, танланмаса — асосийси."""
    ensure(con)
    for r in con.execute("SELECT * FROM plan_versions WHERE year=? AND block_to<? ORDER BY main DESC, id DESC LIMIT 1", (int(D[:4]), int(D[5:7]))):
        return dict(r)
    return None

def set_main(con, version_id: int):
    v = get_version(con, version_id)
    if not v: raise ValueError("Режа топилмади")
    with con:
        con.execute("UPDATE plan_versions SET main=CASE WHEN id=? THEN 1 ELSE 0 END WHERE year=?", (v["id"], v["year"]))
        db.log(con, "plan_main_set", id=v["id"], year=v["year"])

def get_version(con, version_id) -> dict | None:
    ensure(con)
    r = con.execute("SELECT * FROM plan_versions WHERE id=?", (int(version_id),)).fetchone()
    return dict(r) if r else None

def values(con, version_id: int) -> dict:
    """{district_code: {kind: [12]}} (+ '1706' — viloyat tuzatmasi, bo'lsa)"""
    out = defaultdict(lambda: {k: [0.0] * 12 for k in KINDS})
    for r in con.execute("SELECT district_code, kind, month, amount FROM plan_values WHERE version_id=?", (version_id,)):
        if r["kind"] in KINDS and 1 <= r["month"] <= 12: out[r["district_code"]][r["kind"]][r["month"] - 1] = r["amount"] or 0.0
    return out

def grid(con, version_id: int) -> dict:
    v = con.execute("SELECT * FROM plan_versions WHERE id=?", (version_id,)).fetchone()
    if not v: raise ValueError("Reja versiyasi topilmadi")
    vals = values(con, version_id)
    rows = []
    for d in report.districts(con):
        for k in KINDS:
            m = vals[d["code"]][k]
            rows.append({"district_code": d["code"], "district": d["name_uz"], "kind": k, "months": [round(x, 3) for x in m], "year": round(sum(m), 3)})
    tot = {k: [round(sum(vals[d["code"]][k][i] for d in report.districts(con)), 3) for i in range(12)] for k in KINDS}
    adj = {k: round(sum(vals[REGION][k]), 3) for k in KINDS} if REGION in vals else {k: 0.0 for k in KINDS}
    adj_m = {k: [round(x, 3) for x in vals[REGION][k]] for k in KINDS} if REGION in vals else {k: [0.0] * 12 for k in KINDS}
    return {"version": dict(v), "rows": rows, "totals": tot, "region_adj": adj, "region_adj_months": adj_m, "months": MONTHS}

def plan_for(con, D: str, version_id=None) -> dict | None:
    """report.prognoz bilan bir xil shakl: {district_code: {kind: {year_plan, m9_plan, period_plan, cur_month_plan, months}}}
    + '1706' viloyat (tumanlar yig'indisi + rasmiy tuzatma). kind: all / sanoat / meva.
    version_id — kunlik hisobotda tanlangan versiya; bo'lmasa D sanasida amaldagi versiya. Versiya bo'lmasa None."""
    v = get_version(con, version_id) if version_id else effective_version(con, D)
    if version_id and not v: raise ValueError("Tanlangan reja versiyasi topilmadi (o'chirilgan bo'lishi mumkin) — oynani yopib, qayta oching")
    if not v: return None
    if not covers(v, D): raise ValueError(cover_error(v, D))
    bt = int(v.get("block_to") or 0)
    vals = values(con, v["id"]); m = int(D[5:7])
    out = defaultdict(dict)
    codes = [d["code"] for d in report.districts(con)]
    def pack(arr):
        return {"year_plan": round(sum(arr), 3), "m9_plan": round(sum(arr[:9]), 3), "period_plan": round(sum(arr[:m]), 3), "cur_month_plan": round(arr[m - 1], 3),
                "months": json.dumps({str(i + 1): round(x, 3) for i, x in enumerate(arr) if i >= bt}), "version_id": v["id"], "effective_from": v["effective_from"],
                "block_to": bt}
    reg = {k: [0.0] * 12 for k in KINDS}
    for c in codes:
        arrs = {k: vals[c][k] for k in KINDS}
        for k in KINDS:
            out[c][k] = pack(arrs[k])
            for i in range(12): reg[k][i] += arrs[k][i]
        out[c]["all"] = pack([arrs["sanoat"][i] + arrs["meva"][i] for i in range(12)])
    if REGION in vals:   # rasmiy viloyat raqami tuzatmasi
        for k in KINDS:
            for i in range(12): reg[k][i] += vals[REGION][k][i]
    for k in KINDS: out["1706"][k] = pack(reg[k])
    out["1706"]["all"] = pack([reg["sanoat"][i] + reg["meva"][i] for i in range(12)])
    return out

def period_plan(con, D_from: str, D_to: str, district_code: str | None = None, kind: str = "all") -> float | None:
    """Sana oralig'i uchun reja: oy butunicha (boshlanish oyi dan tugash oyi gacha). Versiya — D_to bo'yicha."""
    v = effective_version(con, D_to)
    if not v: return None
    vals = values(con, v["id"]); m0, m1 = int(D_from[5:7]), int(D_to[5:7])
    bt = int(v.get("block_to") or 0)
    if bt and m0 > 1 and m0 <= bt: return None   # давр блок ичидан бошланади — ойлик режа йўқ
    codes = [district_code] if district_code else [d["code"] for d in report.districts(con)] + ([REGION] if REGION in vals else [])
    kinds = KINDS if kind == "all" else (kind,)
    return round(sum(vals[c][k][i] for c in codes for k in kinds for i in range(m0 - 1, m1)), 3)

# ------------------------------------------------------------------ yozish
def create_version(con, year: int, effective_from: str = "", title: str = "", note: str = "", copy_from: int | None = None, from_workbook: bool = False) -> int:
    ensure(con)
    if not year or not (2000 <= int(year) <= 2100): raise ValueError("Йилни киритинг")
    effective_from = f"{year}-01-01"   # эски устун (ишлатилмайди)
    first = not con.execute("SELECT 1 FROM plan_versions WHERE year=? LIMIT 1", (year,)).fetchone()
    with con:
        cur = con.execute("INSERT INTO plan_versions(year,effective_from,title,note,source,main) VALUES(?,?,?,?,?,?)",
                          (year, effective_from, title or f"{year} йил режаси", note, "copy" if copy_from else ("workbook" if from_workbook else "manual"), 1 if first else 0))
        vid = cur.lastrowid
        if copy_from:
            con.execute("INSERT INTO plan_values(version_id,district_code,kind,month,amount) SELECT ?,district_code,kind,month,amount FROM plan_values WHERE version_id=?", (vid, copy_from))
            con.execute("UPDATE plan_versions SET block_to=(SELECT block_to FROM plan_versions WHERE id=?) WHERE id=?", (copy_from, vid))
        elif from_workbook:
            # eski prognoz jadvalidan (shablon СВОДи): oylik bo'linma bo'lsa u, bo'lmasa avto-bo'linma (yillik · davr · oy)
            m = workbook_month(con, year)
            rows, region = {}, {}
            for r in con.execute("SELECT district_code, kind, year_plan, period_plan, cur_month_plan, months FROM prognoz WHERE year=? AND kind IN ('sanoat','meva')", (year,)):
                arr = None
                if r["months"]:
                    try:
                        mm = json.loads(r["months"]); arr = [float(mm.get(str(i + 1), 0) or 0) for i in range(12)]
                    except Exception: arr = None
                if not arr or not any(arr): arr = split_months(r["year_plan"], r["period_plan"], r["cur_month_plan"], m)
                if len(r["district_code"]) == 7: rows[(r["district_code"], r["kind"])] = arr
                elif r["district_code"] == REGION: region[r["kind"]] = arr
            _write_values(con, vid, rows, region)
        db.log(con, "plan_version_created", id=vid, year=year, effective_from=effective_from, copy_from=copy_from, from_workbook=from_workbook)
    return vid

# ------------------------------------------------------------------ oylik avto-bo'linma va СВОД'dan versiya
def split_months(year_amt, period_amt, month_amt, m: int) -> list[float]:
    """Yillik, davr (yanvar–m oy) va m-oy prognozidan 12 oy: m-oy = oy prognozi; 1..m−1 = (davr − oy) teng;
    m+1..12 = (yillik − davr) teng. Qoldiq (yaxlitlash) har blokning oxirgi oyiga — bloklar yig'indisi aniq saqlanadi."""
    y, p, c = float(year_amt or 0), float(period_amt or 0), float(month_amt or 0)
    m = min(max(int(m or 12), 1), 12)
    arr = [0.0] * 12
    def fill(i0, i1, total):   # [i0, i1) oylar, yig'indi = total
        n = i1 - i0
        if n <= 0: return
        each = round(total / n, 6)
        for i in range(i0, i1): arr[i] = each
        arr[i1 - 1] = round(total - each * (n - 1), 6)
    if m == 1: arr[0] = round(p if p else c, 6)
    else:
        arr[m - 1] = round(c, 6); fill(0, m - 1, p - c)
    fill(m, 12, y - p)
    return arr

def workbook_month(con, year: int) -> int:
    """Shablon СВОДи qaysi oy holatida (prognoz jadvalidagi davr/oy prognozi shu oyga tegishli)."""
    m = db.get_setting(con, "template_cur_month")
    try:
        if m and 1 <= int(m) <= 12: return int(m)
    except (TypeError, ValueError): pass
    last = report.last_data_date(con) or f"{year}-12-31"
    return int(last[5:7]) if int(last[:4]) == year else 12

def _write_values(con, vid: int, rows: dict, region: dict):
    """rows: {(code, kind): [12]}; region: {kind: [12]} — rasmiy viloyat raqami (bo'lsa) → tuzatma = rasmiy − tumanlar yig'indisi."""
    con.executemany("INSERT OR REPLACE INTO plan_values(version_id,district_code,kind,month,amount) VALUES(?,?,?,?,?)",
                    [(vid, c, k, i + 1, round(a, 6)) for (c, k), arr in rows.items() for i, a in enumerate(arr)])
    for k, off in region.items():
        if k not in KINDS or not off: continue
        adj = [off[i] - sum(arr[i] for (c, kk), arr in rows.items() if kk == k) for i in range(12)]
        if any(abs(a) > 0.0005 for a in adj):
            con.executemany("INSERT OR REPLACE INTO plan_values(version_id,district_code,kind,month,amount) VALUES(?,?,?,?,?)",
                            [(vid, REGION, k, i + 1, round(a, 6)) for i, a in enumerate(adj)])

MONTH_STEMS = ["январ", "феврал", "март", "апрел", "май", "июн", "июл", "август", "сентябр", "октябр", "ноябр", "декабр"]

def parse_svod(con, path) -> dict:
    """«СВОД (карантин)» варағи (вазирлик/кунлик ҳисобот шакли) дан режа: туман × тур бўйича йиллик, давр ва ой прогнози.
    Устунлар сарлавҳа матни бўйича топилади: «… прогнози жами», «Жами январь–… ойларида» → прогноз, «Шундан … ойида» → прогноз."""
    import re
    from .xl import read_sheet, sheet_names, find_sheet, _norm
    names = sheet_names(path)
    sheet = find_sheet(names, "СВОД (карантин)") or find_sheet(names, "СВОД") or next((n for n in names if "свод" in n.lower()), None)
    if not sheet: raise ValueError("Faylda «СВОД (карантин)» varag'i topilmadi — kunlik hisobot (свод + туманлар номма-ном) yoki vazirlik СВОД faylini yuklang")
    rows = read_sheet(path, sheet)
    hi = next((i for i, r in enumerate(rows[:10]) if any(isinstance(v, str) and "прогнози" in v.lower() for v in r)), None)
    if hi is None: raise ValueError("СВОД varag'ida «… йил прогнози жами» sarlavhasi topilmadi")
    top = [_norm(v) for v in rows[hi]]
    sub_i = next((i for i in range(hi + 1, min(hi + 6, len(rows))) if sum(1 for v in rows[i] if isinstance(v, str) and _norm(v).startswith("прогноз")) >= 2), None)
    if sub_i is None: raise ValueError("СВОД varag'ida «прогноз / амалда» qatori topilmadi")
    sub = [_norm(v) for v in rows[sub_i]]
    def top_col(rx):
        return next((i for i, v in enumerate(top) if re.search(rx, v)), None)
    c_year, c_per, c_mon = top_col(r"прогнози жами"), top_col(r"^жами январ"), top_col(r"^шундан .*ойида")
    if None in (c_year, c_per, c_mon): raise ValueError("СВОД sarlavhasida «прогнози жами», «Жами январь–…» yoki «Шундан … ойида» ustuni topilmadi")
    def under(start):
        return next((i for i in range(start, len(sub)) if sub[i].startswith("прогноз")), None)
    c_pp, c_mp = under(c_per), under(c_mon)
    c_name = top_col(r"туманлар номи") or 1
    m = next((i + 1 for i, st in enumerate(MONTH_STEMS) if st in top[c_mon]), None)
    if not m: raise ValueError("«Шундан … ойида» sarlavhasidan oy aniqlanmadi")
    dmap = {re.sub(r"\s+", " ", r["name_uz"]).strip().lower(): r["code"] for r in con.execute("SELECT code,name_uz FROM districts WHERE length(code)=7")}
    def num(v):
        if v is None or v == "": return None
        try: return float(str(v).replace(" ", "").replace(",", "."))
        except ValueError: return None
    cur, found, region = None, {}, {}
    for r in rows[sub_i + 1:]:
        name = re.sub(r"\s+", " ", str(r[c_name] or "")).strip().lower() if c_name < len(r) else ""
        if not name: continue
        if name in dmap: cur = dmap[name]; continue
        kind = "sanoat" if name.startswith("саноат") else ("meva" if name.startswith("мева") else None)
        if not kind: continue
        vals = tuple(num(r[c]) if c is not None and c < len(r) else None for c in (c_year, c_pp, c_mp))
        if name.endswith("жами") and cur is None: region[kind] = vals; continue
        if cur: found[(cur, kind)] = vals
    need = {(c, k) for c in dmap.values() for k in KINDS}
    miss = need - set(found)
    if len(miss) == len(need): raise ValueError("СВОД varag'ida tumanlar qatorlari topilmadi")
    return {"sheet": sheet, "month": m, "rows": found, "region": region, "missing": sorted(miss)}

# ------------------------------------------------------------------ УНИВЕРСАЛ Excel ўқувчи (29.09.2026)
# Битта йўл: ҳар қандай режа Excel'и — ўз шаблонимиз (Код · Туман · Тур · Йиллик · 12 ой), вазирлик шакли
# («2026 йил режа» · «январь–август» · сентябрь…декабрь), кунлик ҳисобот СВОДи («прогнози жами» · «Жами январь–сентябрь» ·
# «Шундан сентябрь ойида»). Устунлар сарлавҳа матнидан топилади:
#   битта ой («сентябрь», «Сен») → шу ой;  оралиқ («январь–август», «9 ойлик») → оралиқдаги бўш ойларга тенг бўлинади;
#   йиллик («2026 йил режа», «прогнози жами», «Йиллик») → қолган бўш ойларга тенг бўлинади.
# Қаторлар: туман номи ёки коди + «саноат» / «мева» сўзи. «Амалда», «фарқ», «%» устунлари эътиборга олинмайди.
import re as _re
_MON_RX = _re.compile(r"(?<![а-яёўқғҳa-z])(янв|фев|мар|апр|май|июн|июл|авг|сен|окт|ноя|дек|yanv|fev|mart|apr|may|iyun|iyul|avg|sen|okt|noy|dek)", _re.I)
_MON_IX = {"янв": 1, "фев": 2, "мар": 3, "апр": 4, "май": 5, "июн": 6, "июл": 7, "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12,
           "yanv": 1, "fev": 2, "mart": 3, "apr": 4, "may": 5, "iyun": 6, "iyul": 7, "avg": 8, "sen": 9, "okt": 10, "noy": 11, "dek": 12}
_SKIP_RX = _re.compile(r"амалда|факт|фарқ|фарк|%|нисбатан|ўсиш|бажарил|т/р|№|код|туман|тур|ҳудуд|тармоқ")
_YEAR_RX = _re.compile(r"режа|прогноз|йиллик|reja|prognoz|yillik")

def _col_kind(label: str):
    """Сарлавҳа → ('m', ойлар) | ('y', None) | None"""
    t = label.lower().replace("ё", "е")
    if not t or _SKIP_RX.search(t): return None
    ms = [_MON_IX[x.lower()] for x in _MON_RX.findall(t)]
    if len(ms) == 1: return ("m", [ms[0]])
    if len(ms) == 2 and ms[0] <= ms[1]: return ("m", list(range(ms[0], ms[1] + 1)))
    if len(ms) > 2: return None
    mm = _re.search(r"(\d{1,2})\s*ойлик", t)
    if mm and 1 <= int(mm.group(1)) <= 12: return ("m", list(range(1, int(mm.group(1)) + 1)))
    if _YEAR_RX.search(t) or t in ("жами", "йил жами", "йил"): return ("y", None)
    return None

def _num(v):
    if v is None or v == "": return None
    if isinstance(v, (int, float)): return float(v)
    try: return float(str(v).replace(" ", "").replace("\u00a0", "").replace(",", "."))
    except ValueError: return None

def _compose(cells: dict, year_v):
    """cells: {tuple(months): value}. Аввал битта ойлар, кейин кичик оралиқлар, охирида йиллик — бўш ойларга тенг бўлинади."""
    arr = [None] * 12; warn = None
    for months, v in sorted(cells.items(), key=lambda kv: len(kv[0])):
        if v is None: continue
        idx = [m - 1 for m in months]
        if len(idx) == 1: arr[idx[0]] = v; continue
        free = [i for i in idx if arr[i] is None]
        rest = v - sum(arr[i] for i in idx if arr[i] is not None)
        if not free:
            if abs(rest) > 0.5: warn = f"{months[0]}–{months[-1]} ой: {v:,.1f} ≠ ойлар йиғиндиси"
            continue
        each = rest / len(free)
        for i in free: arr[i] = each
    if year_v is not None:
        free = [i for i in range(12) if arr[i] is None]
        rest = year_v - sum(a for a in arr if a is not None)
        if free:
            for i in free: arr[i] = rest / len(free)
        elif abs(rest) > 0.5: warn = f"йиллик {year_v:,.1f} ≠ 12 ой йиғиндиси {year_v - rest:,.1f}"
    return [round(a or 0.0, 6) for a in arr], warn

def _parse_sheet(rows, dmap, codes):
    first = None
    def row_district(r):
        for v in r:
            if v is None: continue
            t = _re.sub(r"\s+", " ", str(v)).strip().lower()
            if t in dmap: return dmap[t]
            c = t.split(".")[0]
            if c in codes: return c
        return None
    def row_kind(r):
        for v in r:
            if isinstance(v, str):
                t = v.lower()
                if "саноат" in t or "sanoat" in t: return "sanoat"
                if "мева" in t or "meva" in t: return "meva"
        return None
    def row_region(r):
        return any(isinstance(v, str) and ("вилоят" in v.lower() or "viloyat" in v.lower()) for v in r)
    for i, r in enumerate(rows[:40]):
        if row_district(r) or (row_kind(r) and i > 0): first = i; break
    if first is None or first == 0: return None
    ncol = max(len(r) for r in rows[:first + 1])
    labels = []
    for c in range(ncol):
        parts = [str(rows[i][c]).strip() for i in range(max(0, first - 8), first) if c < len(rows[i]) and rows[i][c] not in (None, "") and not isinstance(rows[i][c], (int, float))]
        labels.append(" ".join(parts))
    cols = {}; ycol = None
    for c, lab in enumerate(labels):
        k = _col_kind(lab)
        if not k: continue
        if k[0] == "y":
            if ycol is None: ycol = c
        else:
            key = tuple(k[1])
            if key not in cols.values(): cols[c] = key
    if not cols and ycol is None: return None
    singles = {m[0] for m in cols.values() if len(m) == 1}
    block_to = max([m[-1] for m in cols.values() if len(m) > 1 and m[0] == 1] or [0])
    while block_to and block_to in singles: block_to -= 1
    if block_to < 2: block_to = 0
    found, region, cur, warns = {}, {}, None, []
    for r in rows[first:]:
        d = row_district(r); k = row_kind(r)
        if d and not k: cur = d; continue
        if not k:
            if row_region(r): cur = "REG"
            continue
        code = d or cur
        if row_region(r) and not d: code = "REG"
        if code is None: code = "REG"   # туман бошланмасидан олдинги «Саноат … жами» — вилоят
        vals = {}
        for c, months in cols.items():
            v = _num(r[c]) if c < len(r) else None
            if v is not None: vals[months] = v
        yv = _num(r[ycol]) if ycol is not None and ycol < len(r) else None
        if not vals and yv is None: continue
        arr, w = _compose(vals, yv)
        if code == "REG": region.setdefault(k, arr)
        elif (code, k) not in found:
            found[(code, k)] = arr
            if w: warns.append(f"{code}/{k}: {w}")
    if not found: return None
    if block_to:   # ўтган давр — битта жами (N-ой катагида), ойларга бўлинмайди
        def lump(arr): t = sum(arr[:block_to]); return [0.0] * (block_to - 1) + [round(t, 6)] + arr[block_to:]
        found = {k: lump(a) for k, a in found.items()}; region = {k: lump(a) for k, a in region.items()}
    return {"rows": found, "region": region, "warn": warns, "block_to": block_to,
            "cols": {labels[c]: f"{m[0]}–{m[-1]}" if len(m) > 1 else str(m[0]) for c, m in cols.items()}, "ycol": labels[ycol] if ycol is not None else None,
            "year_hint": next((int(x) for lab in labels for x in _re.findall(r"(20\d\d)", lab)), None)}

def parse_any(con, path) -> dict:
    """Универсал: ҳар варақни текширади, туман×тур қаторлари энг кўп топилганини олади."""
    from .xl import read_sheet, sheet_names
    dmap = {_re.sub(r"\s+", " ", r["name_uz"]).strip().lower(): r["code"] for r in con.execute("SELECT code,name_uz FROM districts WHERE length(code)=7")}
    codes = set(dmap.values())
    best = None
    for sh in sheet_names(path):
        try: rows = read_sheet(path, sh, max_rows=400)
        except Exception: continue
        p = _parse_sheet(rows, dmap, codes)
        if p and (best is None or len(p["rows"]) > len(best["rows"])): best = {**p, "sheet": sh}
    if not best:
        raise ValueError("Excel'да режа топилмади. Керак: туман номи (ёки коди) + «саноат» / «мева» қаторлари ва ой / йиллик режа устунлари. "
                         "«Шаблон» ни юклаб олиб тўлдиринг ёки вазирлик шаклидаги файлни юкланг.")
    need = {(c, k) for c in codes for k in KINDS}
    best["missing"] = sorted(need - set(best["rows"]))
    return best

def import_any(con, path, year: int, effective_from: str, title: str = "", note: str = "", version_id: int | None = None) -> dict:
    """Универсал Excel → янги режа (version_id йўқ) ёки мавжуд режани алмаштириш (version_id)."""
    p = parse_any(con, path)
    region = {k: arr for k, arr in p["region"].items() if any(arr)}
    if version_id:
        v = get_version(con, version_id)
        if not v: raise ValueError("Режа топилмади")
        vid, year = v["id"], v["year"]
        db.backup_if_stale("plan")
        with con:
            con.execute("DELETE FROM plan_values WHERE version_id=?", (vid,))
            _write_values(con, vid, p["rows"], region)
            con.execute("UPDATE plan_versions SET block_to=?, updated_at=datetime('now','localtime') WHERE id=?", (p["block_to"], vid))
            db.log(con, "plan_xlsx_imported", id=vid, rows=len(p["rows"]), sheet=p["sheet"])
    else:
        vid = create_version(con, year, effective_from, title, note)
        with con:
            con.execute("UPDATE plan_versions SET source='xlsx', block_to=? WHERE id=?", (p["block_to"], vid))
            _write_values(con, vid, p["rows"], region)
            db.log(con, "plan_xlsx_imported", id=vid, rows=len(p["rows"]), sheet=p["sheet"])
    pf = plan_for(con, f"{year}-12-31", vid)["1706"] if p["block_to"] < 12 else None
    if pf is None:   # бутун йил блок — фақат йиллик
        tot = {k: round(sum(sum(a) for (c, kk), a in p["rows"].items() if kk == k), 3) for k in KINDS}; tot["all"] = round(tot["sanoat"] + tot["meva"], 3)
        return {"id": vid, "rows": len(p["rows"]), "missing": p["missing"], "sheet": p["sheet"], "warn": p["warn"][:10], "cols": p["cols"], "ycol": p["ycol"],
                "year_hint": p["year_hint"], "block_to": p["block_to"], "block": block_label(p["block_to"]), "total": tot, "months": []}
    return {"id": vid, "rows": len(p["rows"]), "block_to": p["block_to"], "block": block_label(p["block_to"]), "missing": p["missing"], "sheet": p["sheet"], "warn": p["warn"][:10], "cols": p["cols"], "ycol": p["ycol"],
            "year_hint": p["year_hint"], "total": {k: pf[k]["year_plan"] for k in ("sanoat", "meva", "all")},
            "months": [round(x, 3) for x in json.loads(pf["all"]["months"]).values()]}

def parse_fact_column(con, path, col_rx: str) -> dict:
    """Excel'даги битта «амалда» устуни (сарлавҳаси col_rx га мос) → {(tuman, tur): қиймат}. Қаторлар — туман + саноат/мева."""
    from .xl import read_sheet, sheet_names
    dmap = {_re.sub(r"\s+", " ", r["name_uz"]).strip().lower(): r["code"] for r in con.execute("SELECT code,name_uz FROM districts WHERE length(code)=7")}
    rx = _re.compile(col_rx, _re.I)
    for sh in sheet_names(path):
        rows = read_sheet(path, sh, max_rows=400)
        col = next((c for r in rows[:10] for c, v in enumerate(r) if isinstance(v, str) and rx.search(_re.sub(r"\s+", " ", v))), None)
        if col is None: continue
        out, cur = {}, None
        for r in rows:
            cells = [_re.sub(r"\s+", " ", str(v)).strip().lower() for v in r if isinstance(v, str)]
            d = next((dmap[t] for t in cells if t in dmap), None)
            k = "sanoat" if any(t.startswith("саноат") for t in cells) else ("meva" if any(t.startswith("мева") for t in cells) else None)
            if d and not k: cur = d; continue
            if not k or any("жами" in t for t in cells if t.startswith(("саноат", "мева"))): continue
            code = d or cur
            v = _num(r[col]) if col < len(r) else None
            if code and v is not None: out[(code, k)] = v
        if out: return {"sheet": sh, "values": out}
    raise ValueError("Excel'да «амалда» устуни ёки туман қаторлари топилмади")

def seed_fact_set(con, path, it: dict) -> int:
    from . import periods
    p = parse_fact_column(con, path, it.get("column") or r"амалдаги")
    year, months = int(it["year"]), int(it["months"])
    r = periods.create_set(con, year, it["title"], it.get("note") or "")
    periods.save(con, year, months, [{"district_code": c, "kind": k, "fact": v} for (c, k), v in p["values"].items()], r["id"])
    if it.get("main"): periods.update_set(con, r["id"], main=True)
    return r["id"]

def seed_once(con):
    """Бир марталик режа қўшиш: data/init/plans_seed.json — [{key, file, year, title, note, main}]. Ҳар key фақат бир марта
    (settings «plan_seed:<key>»); файл data/init ичида. Сервер қайта ишга тушганда ўзи қўшади (29.09.2026)."""
    f = db.BASE / "init" / "plans_seed.json"
    if not f.exists(): return
    try: items = json.loads(f.read_text(encoding="utf-8"))
    except Exception: return
    if isinstance(items, dict):   # {"remove": [seed kalitlari], "add": [...]}
        for key in items.get("remove") or []:   # avval avtomatik qo'shilgan (foydalanuvchi o'chirgan) rejani olib tashlash — bir marta
            try:
                val = db.get_setting(con, key) or ""
                if val.startswith("ok:") and val[3:].isdigit():
                    if get_version(con, int(val[3:])): delete_version(con, int(val[3:]))
                    db.set_setting(con, key, "removed"); con.commit()
            except Exception: pass
        for it in items.get("fact_sets") or []:   # «Амалда» тўплами (ўтган йил натижаси) — бир марта
            key = "fact_seed:" + str(it.get("key"))
            try:
                if db.get_setting(con, key): continue
                x = db.BASE / "init" / it["file"]
                if not x.exists(): continue
                db.set_setting(con, key, "pending"); con.commit()
                sid = seed_fact_set(con, x, it)
                db.set_setting(con, key, f"ok:{sid}"); con.commit()
            except Exception as e:
                try: db.set_setting(con, key, f"err:{e}"[:300]); con.commit()
                except Exception: pass
        items = items.get("add") or []
    for it in items:
        key = "plan_seed:" + str(it.get("key") or it.get("file"))
        try:
            if db.get_setting(con, key): continue
            x = db.BASE / "init" / it["file"]
            if not x.exists(): continue
            db.set_setting(con, key, "pending"); con.commit()   # параллел уланишлар иккинчи марта қўшмасин
            r = import_any(con, x, int(it["year"]), "", it.get("title") or "", it.get("note") or "")
            if it.get("main"): set_main(con, r["id"])
            db.set_setting(con, key, f"ok:{r['id']}"); con.commit()
        except Exception as e:
            try: db.set_setting(con, key, f"err:{e}"[:300]); con.commit()
            except Exception: pass

def import_svod(con, path, year: int, effective_from: str, title: str = "", note: str = "") -> dict:
    """Эски ном (мослик учун) — универсал ўқувчига йўналтирилади."""
    return import_any(con, path, year, effective_from, title, note)

def choices(con, D: str) -> dict:
    """Кунлик ҳисобот модали учун: D йилидаги версиялар + шаблон (СВОД) прогнози, ҳар бири вилоят жами (йиллик / давр / ой) билан."""
    year = int(D[:4]); eff = effective_version(con, D)
    items = []
    def tot(pv):
        r = (pv or {}).get("1706") or {}
        return {k: {"year": (r.get(k) or {}).get("year_plan"), "period": (r.get(k) or {}).get("period_plan"), "month": (r.get(k) or {}).get("cur_month_plan")} for k in ("sanoat", "meva", "all")}
    for v in versions(con, year):
        ok = covers(v, D)
        items.append({"id": v["id"], "title": v["title"], "effective_from": v["effective_from"], "main": v.get("main", 0), "source": v["source"],
                      "block_to": v.get("block_to") or 0, "block": block_label(v.get("block_to") or 0), "covers": ok,
                      "total": tot(plan_for(con, D, v["id"])) if ok else None})
    # жадвал (шаблон СВОДи) прогнози — фақат Созламаларда шу йил учун режа бўлмаса (эски усул)
    has_table = not items and bool(con.execute("SELECT 1 FROM prognoz WHERE year=? AND year_plan IS NOT NULL LIMIT 1", (year,)).fetchone())
    table = tot(report.prognoz(con, year, D, plan="table")) if has_table else None
    return {"effective": eff["id"] if eff else ("table" if has_table else None), "items": items, "table": table,
            "table_label": db.get_setting(con, "template_label")}

def save_grid(con, version_id: int, rows: list[dict], meta: dict | None = None) -> dict:
    """rows: [{district_code, kind, months:[12]}]; meta: title, note, effective_from."""
    ensure(con)
    v = con.execute("SELECT * FROM plan_versions WHERE id=?", (version_id,)).fetchone()
    if not v: raise ValueError("Reja versiyasi topilmadi")
    db.backup_if_stale("plan")
    n = 0
    with con:
        for r in rows:
            k = r.get("kind"); c = str(r.get("district_code") or "")
            if k not in KINDS or len(c) != 7: continue
            months = r.get("months") or []
            for i in range(12):
                try: a = float(str(months[i]).replace(" ", "").replace(",", ".")) if i < len(months) and str(months[i]).strip() not in ("", "None") else 0.0
                except ValueError: a = 0.0
                con.execute("INSERT OR REPLACE INTO plan_values(version_id,district_code,kind,month,amount) VALUES(?,?,?,?,?)", (version_id, c, k, i + 1, round(a, 3))); n += 1
        if meta:
            con.execute("UPDATE plan_versions SET title=?, note=?, updated_at=datetime('now','localtime') WHERE id=?",
                        (meta.get("title") or v["title"], meta.get("note") or "", version_id))
        db.log(con, "plan_saved", id=version_id, cells=n)
    return {"ok": True, "cells": n}

def delete_version(con, version_id: int):
    v = get_version(con, version_id)
    with con:
        con.execute("DELETE FROM plan_values WHERE version_id=?", (version_id,))
        con.execute("DELETE FROM plan_versions WHERE id=?", (version_id,))
        if v and v.get("main"):   # асосий ўчса — шу йилнинг энг охиргиси асосий
            con.execute("UPDATE plan_versions SET main=1 WHERE id=(SELECT id FROM plan_versions WHERE year=? ORDER BY id DESC LIMIT 1)", (v["year"],))
        db.log(con, "plan_version_deleted", id=version_id)

# ------------------------------------------------------------------ Excel: shablon va yuklash
def template_xlsx(con, version_id: int | None, year: int, out):
    """Универсал режа шаблони: Код · Туман · Тур · Йиллик режа · [Ўтган давр: январь–N жами] · қолган ойлар.
    Ўтган давр: режанинг блоки бўлса — шу; янги режа жорий йил учун бўлса — охирги тўлган ойгача; бошқа йилларда — йўқ (12 ой)."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter as L
    thin = Side(style="thin", color="999999"); bd = Border(thin, thin, thin, thin)
    v = get_version(con, version_id) if version_id else None
    if v: bt = int(v.get("block_to") or 0)
    else:
        last = report.last_data_date(con) or ""
        bt = int(last[5:7]) - 1 if last[:4] == str(year) else 0
        if bt < 2: bt = 0
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Режа"
    ws["A1"] = f"Бухоро вилояти экспорт режаси — {year} йил (минг АҚШ доллари)"; ws["A1"].font = Font(name="Times New Roman", size=14, bold=True)
    ws["A2"] = ("Қандай тўлдирилади: «Йиллик режа» ни ёзинг; маълум ойларни ёзинг — бўш ойлар йиллик қолдиғидан тенг бўлинади. "
                "Фақат йиллик ёзилса — 12 ойга тенг. Туман кодини ўзгартирманг.")
    ws["A2"].font = Font(italic=True, size=10, color="666666")
    ws["A3"] = ((f"«{block_label(bt).capitalize()}» — ўтган давр битта жами: ойларга бўлинмайди, бу давр ичидаги саналарга ҳисобот бу режа билан юкланмайди. "
                 if bt else "") + "Вазирлик шакли («январь–август» + ойлар) ҳам шу тугма орқали тўғридан-тўғри юкланади.")
    ws["A3"].font = Font(italic=True, size=10, color="666666")
    mhdr = ([block_label(bt).capitalize() + " (жами)"] if bt else []) + MONTHS[bt:]
    hdr = ["Код", "Туман", "Тур", "Йиллик режа"] + mhdr
    for i, h in enumerate(hdr, 1):
        c = ws.cell(5, i, h); c.font = Font(name="Times New Roman", bold=True, size=11, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="B8860B" if i == 4 else ("5A6470" if bt and i == 5 else "0F6E63"))
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True); c.border = bd
    ws.row_dimensions[5].height = 32
    ws.column_dimensions["A"].width = 10; ws.column_dimensions["B"].width = 24; ws.column_dimensions["C"].width = 24; ws.column_dimensions["D"].width = 14
    for i in range(5, 5 + len(mhdr)): ws.column_dimensions[L(i)].width = 11
    if bt: ws.column_dimensions["E"].width = 16
    vals = values(con, version_id) if version_id else None
    last_col = 4 + len(mhdr)
    r0 = 6
    for d in report.districts(con):
        for k in KINDS:
            ws.cell(r0, 1, d["code"]); ws.cell(r0, 2, d["name_uz"]); ws.cell(r0, 3, KIND_UZ[k])
            arr = vals[d["code"]][k] if vals else None
            cells = ([sum(arr[:bt])] if bt else []) + arr[bt:] if arr else [None] * len(mhdr)
            c = ws.cell(r0, 4, round(sum(arr), 3) if arr else None); c.number_format = "#,##0.0"; c.font = Font(bold=True); c.border = bd
            c.fill = PatternFill("solid", fgColor="FFF8E1")
            for i, x in enumerate(cells):
                c = ws.cell(r0, 5 + i, round(x, 3) if x is not None else None); c.number_format = "#,##0.0"; c.border = bd
                if bt and i == 0: c.fill = PatternFill("solid", fgColor="EEF1EF")
            for i in (1, 2, 3): ws.cell(r0, i).border = bd
            if k == "meva": ws.cell(r0, 3).font = Font(color="7A6A00")
            r0 += 1
    ws.cell(r0, 2, "Вилоят жами (текшириш)").font = Font(bold=True)
    for i in range(4, last_col + 1):
        c = ws.cell(r0, i, f"=SUM({L(i)}6:{L(i)}{r0 - 1})"); c.number_format = "#,##0.0"; c.font = Font(bold=True); c.border = bd
    ws.freeze_panes = "E6"
    wb.save(out); return out

def import_xlsx(con, version_id: int, path) -> dict:
    """Режа муҳарририда «Excel юклаш» — универсал ўқувчи (шаблон ёки вазирлик шакли), режа рақамлари алмаштирилади."""
    return import_any(con, path, 0, "", version_id=version_id)
