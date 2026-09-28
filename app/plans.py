"""Reja (prognoz) — versiyalar bilan, oylar bo'yicha, tuman va tur kesimida.

Bir yil ichida reja o'zgarishi mumkin (masalan 1 sentyabrdan yangi reja). Har versiya `effective_from` sanasidan kuchga kiradi;
hisobot sanasi D uchun o'sha yilning effective_from <= D bo'lgan eng oxirgi versiyasi olinadi. Versiya bo'lmasa —
o'z jadvalingizdan (СВОД) o'qilgan eski `prognoz` jadvali ishlaydi (avvalgidek).

Atom birlik — oy: yillik = 12 oy yig'indisi, davr rejasi = yil boshidan joriy oy oxirigacha oylar yig'indisi (eski qoida bilan bir xil).
Viloyat qatori tumanlar yig'indisi (alohida kiritilmaydi).
"""
from __future__ import annotations
import datetime as dt, json
from collections import defaultdict
from . import db, report

KINDS = ("sanoat", "meva")
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

# ------------------------------------------------------------------ o'qish
def versions(con, year: int | None = None) -> list[dict]:
    ensure(con)
    w, a = ("WHERE year=?", (year,)) if year else ("", ())
    out = []
    for r in con.execute(f"SELECT * FROM plan_versions {w} ORDER BY year DESC, effective_from DESC, id DESC", a):
        d = dict(r)
        d["total"] = con.execute("SELECT coalesce(sum(amount),0) FROM plan_values WHERE version_id=?", (d["id"],)).fetchone()[0]
        out.append(d)
    return out

def effective_version(con, D: str) -> dict | None:
    """Hisobot sanasi D uchun amaldagi versiya (o'sha yil, effective_from <= D, eng oxirgisi)."""
    ensure(con)
    r = con.execute("SELECT * FROM plan_versions WHERE year=? AND effective_from<=? ORDER BY effective_from DESC, id DESC LIMIT 1", (int(D[:4]), D)).fetchone()
    return dict(r) if r else None

def values(con, version_id: int) -> dict:
    """{district_code: {kind: [12]}}"""
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
    return {"version": dict(v), "rows": rows, "totals": tot, "months": MONTHS}

def plan_for(con, D: str) -> dict | None:
    """report.prognoz bilan bir xil shakl: {district_code: {kind: {year_plan, m9_plan, period_plan, cur_month_plan, months}}}
    + '1706' viloyat (tumanlar yig'indisi). kind: all / sanoat / meva. Versiya bo'lmasa None."""
    v = effective_version(con, D)
    if not v: return None
    vals = values(con, v["id"]); m = int(D[5:7])
    out = defaultdict(dict)
    codes = [d["code"] for d in report.districts(con)]
    def pack(arr):
        return {"year_plan": round(sum(arr), 3), "m9_plan": round(sum(arr[:9]), 3), "period_plan": round(sum(arr[:m]), 3), "cur_month_plan": round(arr[m - 1], 3),
                "months": json.dumps({str(i + 1): round(x, 3) for i, x in enumerate(arr)}), "version_id": v["id"], "effective_from": v["effective_from"]}
    reg = {k: [0.0] * 12 for k in KINDS}
    for c in codes:
        arrs = {k: vals[c][k] for k in KINDS}
        for k in KINDS:
            out[c][k] = pack(arrs[k])
            for i in range(12): reg[k][i] += arrs[k][i]
        out[c]["all"] = pack([arrs["sanoat"][i] + arrs["meva"][i] for i in range(12)])
    for k in KINDS: out["1706"][k] = pack(reg[k])
    out["1706"]["all"] = pack([reg["sanoat"][i] + reg["meva"][i] for i in range(12)])
    return out

def period_plan(con, D_from: str, D_to: str, district_code: str | None = None, kind: str = "all") -> float | None:
    """Sana oralig'i uchun reja: oy butunicha (boshlanish oyi dan tugash oyi gacha). Versiya — D_to bo'yicha."""
    v = effective_version(con, D_to)
    if not v: return None
    vals = values(con, v["id"]); m0, m1 = int(D_from[5:7]), int(D_to[5:7])
    codes = [district_code] if district_code else [d["code"] for d in report.districts(con)]
    kinds = KINDS if kind == "all" else (kind,)
    return round(sum(vals[c][k][i] for c in codes for k in kinds for i in range(m0 - 1, m1)), 3)

# ------------------------------------------------------------------ yozish
def create_version(con, year: int, effective_from: str, title: str = "", note: str = "", copy_from: int | None = None, from_workbook: bool = False) -> int:
    ensure(con)
    if not effective_from or not effective_from.startswith(str(year)): raise ValueError("Kuchga kirish sanasi shu yil ichida bo'lishi kerak")
    with con:
        cur = con.execute("INSERT INTO plan_versions(year,effective_from,title,note,source) VALUES(?,?,?,?,?)",
                          (year, effective_from, title or f"{year} йил режаси ({effective_from[8:10]}.{effective_from[5:7]} дан)", note, "copy" if copy_from else ("workbook" if from_workbook else "manual")))
        vid = cur.lastrowid
        if copy_from:
            con.execute("INSERT INTO plan_values(version_id,district_code,kind,month,amount) SELECT ?,district_code,kind,month,amount FROM plan_values WHERE version_id=?", (vid, copy_from))
        elif from_workbook:
            # eski prognoz jadvalidan: oylik bo'linma bo'lsa u, bo'lmasa yillik 12 ga teng
            for r in con.execute("SELECT district_code, kind, year_plan, months FROM prognoz WHERE year=? AND kind IN ('sanoat','meva') AND length(district_code)=7", (year,)):
                arr = None
                if r["months"]:
                    try:
                        mm = json.loads(r["months"]); arr = [float(mm.get(str(i + 1), 0) or 0) for i in range(12)]
                    except Exception: arr = None
                if not arr or not any(arr): arr = [(r["year_plan"] or 0) / 12.0] * 12
                con.executemany("INSERT OR REPLACE INTO plan_values(version_id,district_code,kind,month,amount) VALUES(?,?,?,?,?)",
                                [(vid, r["district_code"], r["kind"], i + 1, round(a, 3)) for i, a in enumerate(arr)])
        db.log(con, "plan_version_created", id=vid, year=year, effective_from=effective_from, copy_from=copy_from, from_workbook=from_workbook)
    return vid

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
            ef = meta.get("effective_from") or v["effective_from"]
            if not ef.startswith(str(v["year"])): raise ValueError("Kuchga kirish sanasi shu yil ichida bo'lishi kerak")
            con.execute("UPDATE plan_versions SET title=?, note=?, effective_from=?, updated_at=datetime('now','localtime') WHERE id=?",
                        (meta.get("title") or v["title"], meta.get("note") or "", ef, version_id))
        db.log(con, "plan_saved", id=version_id, cells=n)
    return {"ok": True, "cells": n}

def delete_version(con, version_id: int):
    with con:
        con.execute("DELETE FROM plan_values WHERE version_id=?", (version_id,))
        con.execute("DELETE FROM plan_versions WHERE id=?", (version_id,))
        db.log(con, "plan_version_deleted", id=version_id)

# ------------------------------------------------------------------ Excel: shablon va yuklash
def template_xlsx(con, version_id: int | None, year: int, out):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter as L
    thin = Side(style="thin", color="999999"); bd = Border(thin, thin, thin, thin)
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Режа"
    ws["A1"] = f"Бухоро вилояти экспорт режаси — {year} йил (минг АҚШ доллари)"; ws["A1"].font = Font(name="Times New Roman", size=14, bold=True)
    ws["A2"] = "Ҳар туман учун 2 қатор (саноат, мева-сабзавот) × 12 ой. Йиллик = ойлар йиғиндиси (формула). Туман кодини ўзгартирманг."; ws["A2"].font = Font(italic=True, size=10, color="666666")
    hdr = ["Код", "Туман", "Тур"] + [m[:3] for m in MONTHS] + ["Йил жами"]
    for i, h in enumerate(hdr, 1):
        c = ws.cell(4, i, h); c.font = Font(name="Times New Roman", bold=True, size=11, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="0F6E63"); c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True); c.border = bd
    ws.column_dimensions["A"].width = 10; ws.column_dimensions["B"].width = 24; ws.column_dimensions["C"].width = 22
    for i in range(4, 17): ws.column_dimensions[L(i)].width = 11
    vals = values(con, version_id) if version_id else defaultdict(lambda: {k: [0.0] * 12 for k in KINDS})
    r0 = 5
    for d in report.districts(con):
        for k in KINDS:
            ws.cell(r0, 1, d["code"]); ws.cell(r0, 2, d["name_uz"]); ws.cell(r0, 3, KIND_UZ[k])
            for i in range(12):
                c = ws.cell(r0, 4 + i, round(vals[d["code"]][k][i], 3)); c.number_format = "#,##0.0"; c.border = bd
            c = ws.cell(r0, 16, f"=SUM(D{r0}:O{r0})"); c.number_format = "#,##0.0"; c.font = Font(bold=True); c.border = bd
            for i in (1, 2, 3): ws.cell(r0, i).border = bd
            if k == "meva": ws.cell(r0, 3).font = Font(color="7A6A00")
            r0 += 1
    ws.cell(r0, 2, "Вилоят жами").font = Font(bold=True)
    for i in range(4, 17):
        c = ws.cell(r0, i, f"=SUM({L(i)}5:{L(i)}{r0 - 1})"); c.number_format = "#,##0.0"; c.font = Font(bold=True); c.border = bd
    ws.freeze_panes = "D5"
    wb.save(out); return out

def import_xlsx(con, version_id: int, path) -> dict:
    from .xl import read_sheet, Header, num
    rows = read_sheet(path, 0)
    h = Header(rows, ["Код", "Туман", "Тур"])
    c_code, c_kind = h.col("Код"), h.col("Тур")
    mcols = [h.col(m[:3]) for m in MONTHS]
    known = {d["code"] for d in report.districts(con)}
    grid_rows, bad = [], 0
    for r in rows[h.row_idx + 1:]:
        code = str(r[c_code] or "").strip().split(".")[0]
        if code not in known: continue
        kt = str(r[c_kind] or "").lower()
        kind = "meva" if kt.startswith("мева") else ("sanoat" if kt.startswith("саноат") else None)
        if not kind: bad += 1; continue
        grid_rows.append({"district_code": code, "kind": kind, "months": [num(r[c]) for c in mcols]})
    if not grid_rows: raise ValueError("Faylda tuman qatorlari topilmadi — shablonni yuklab olib, uni to'ldiring")
    res = save_grid(con, version_id, grid_rows)
    return {"rows": len(grid_rows), "skipped": bad, **res}
