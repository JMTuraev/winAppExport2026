"""«Баҳсли корхоналар» — the user's Excel template (номманом, Jan..base month typed by hand) vs the customs base.

Owner's rule (Jafar, 19.09.2026), decided per company in its profile (companies.opening_source):
  (a) «Бухоро» + opening_source='template' — the template's monthly values are the truth: they are imported into
      opening_balances (source='template') so the site shows them everywhere and the Excel keeps its cells.
  (b) «Бухоро» + opening_source='customs' (default) — the customs base is the truth: tpl.build rewrites the
      company's Jan..base-month cells in номманом with the base values (only for disputed companies).
  (c) «Бухоро эмас» (bukhara=0) — the company appears nowhere: the site skips it, tpl.build clears its month cells.
  (d) in the base but not in the template — tpl.build adds a yellow row with the base monthly values.
"""
from __future__ import annotations
from collections import defaultdict
from . import db

DIFF_MIN = 1.0          # ming $: a month differing by less is 2-decimal rounding of the template, not a dispute
SOURCES = ("customs", "template")

def year(con) -> int:
    from .companies import year as _y
    return _y(con)

def base_month(con) -> int:
    """Last month covered by the customs base (0 when there is none / another year)."""
    through = db.get_setting(con, "opening_through_date") or ""
    return int(through[5:7]) if through and int(through[:4]) == year(con) else 0

def template_inns(con) -> set:
    return {r["inn"] for r in con.execute("SELECT inn FROM companies WHERE opening_source='template'")}

def template_balances(con, y: int | None = None) -> dict:
    """{inn: [12]} — sanoat months imported from the template (opening_balances.source='template')."""
    out = defaultdict(lambda: [0.0] * 12)
    for r in con.execute("SELECT inn, month, amount FROM opening_balances WHERE year=? AND kind='sanoat' AND source='template'", (y or year(con),)):
        out[r["inn"]][r["month"] - 1] += r["amount"]
    return dict(out)

def template_rows(con, wb=None, lay=None, path=None) -> dict:
    """{inn: {"months": [12], "row", "name", "district", "key"}} — sanoat rows of номманом with their month cells."""
    from . import tpl
    if wb is None:
        p = path or tpl.template_path(con)
        if not p.exists(): return {}
        wb = tpl.load(p)
    lay = lay or tpl.nomma_layout(wb)
    ws = wb[lay["sheet"]]
    mcol = {c.column: tpl._month_of(c.value) for c in ws[lay["header_row"]] if c.column in lay["cols"]["months"]}
    out = {}
    for b in lay["blocks"]:
        for x in b["rows"]:
            if x["cat"] != "sanoat" or x["inn"] in out: continue
            m = [0.0] * 12
            for col, mo in mcol.items():
                if mo: m[mo - 1] += tpl._cell_number(ws.cell(x["row"], col).value) or 0.0
            out[x["inn"]] = {"months": [round(v, 3) for v in m], "row": x["row"], "name": x["name"], "district": b["name"], "key": b["key"]}
    return out

def customs_months(con, y: int, inn: str | None = None) -> dict:
    """{inn: [12]} — what the customs base says (items kind='sanoat'; older DBs: opening_balances source='customs')."""
    from .companies import has_base_detail
    out = defaultdict(lambda: [0.0] * 12)
    f = " AND inn=?" if inn else ""; a = (inn,) if inn else ()
    if has_base_detail(con):
        for r in con.execute(f"SELECT inn, month m, sum(value) v FROM items WHERE regime='ЭК' AND kind='sanoat' AND year=?{f} GROUP BY inn, m", (y, *a)):
            out[r["inn"]][r["m"] - 1] += r["v"] or 0.0
    else:
        for r in con.execute(f"SELECT inn, month m, sum(amount) v FROM opening_balances WHERE year=? AND kind='sanoat' AND source<>'template'{f} GROUP BY inn, m", (y, *a)):
            out[r["inn"]][r["m"] - 1] += r["v"] or 0.0
    return dict(out)

def effective_months(con, y: int) -> dict:
    """{inn: [12]} — the site's current opening (opening_balances kind='sanoat', whatever the source)."""
    out = defaultdict(lambda: [0.0] * 12)
    for r in con.execute("SELECT inn, month, amount FROM opening_balances WHERE year=? AND kind='sanoat'", (y,)):
        out[r["inn"]][r["month"] - 1] += r["amount"]
    return dict(out)

def decision_of(c: dict | None, in_template: bool) -> str:
    if c is None: return "unknown"
    if c.get("bukhara") == 0: return "not_bukhara"
    if (c.get("opening_source") or "customs") == "template": return "template"
    return "customs" if in_template else "add_row"

def disputes(con, wb=None, lay=None) -> list:
    """Companies whose template Jan..base-month values differ from the customs base (any month by >= DIFF_MIN)."""
    y = year(con); bm = base_month(con)
    if not bm: return []
    tpl_rows = template_rows(con, wb, lay)
    base = customs_months(con, y)
    comp = {r["inn"]: dict(r) for r in con.execute("SELECT * FROM companies")}
    dn = {r["code"]: r["name_uz"] for r in con.execute("SELECT code, name_uz FROM districts")}
    excl = {i for i, c in comp.items() if c.get("excluded")}
    out = []
    for inn in sorted(set(tpl_rows) | set(base)):
        if inn in excl: continue
        c = comp.get(inn)
        t = tpl_rows.get(inn); tm = (t["months"] if t else [0.0] * 12)[:bm]; bmm = base.get(inn, [0.0] * 12)[:bm]
        if not t and c and c.get("bukhara") == 0: continue          # base-only and «Бухоро эмас»: nowhere already
        if not t and not any(round(v, 3) for v in bmm): continue
        d = [round(a - b, 3) for a, b in zip(tm, bmm)]
        if max((abs(x) for x in d), default=0) < DIFF_MIN: continue
        out.append({"inn": inn, "name": (c or {}).get("name") or (t or {}).get("name") or inn,
                    "district": dn.get((c or {}).get("district_code")) or (t or {}).get("district"), "district_code": (c or {}).get("district_code"),
                    "in_template": bool(t), "in_base": bool(c and c.get("in_base")) or inn in base, "bukhara": (c or {}).get("bukhara"),
                    "opening_source": (c or {}).get("opening_source") or "customs", "registered": c is not None,
                    "template_months": [round(v, 3) for v in tm], "base_months": [round(v, 3) for v in bmm],
                    "template_total": round(sum(tm), 3), "base_total": round(sum(bmm), 3), "diff": round(sum(tm) - sum(bmm), 3),
                    "months_diff": d, "decision": decision_of(c, bool(t))})
    out.sort(key=lambda r: -abs(r["diff"]) if r["diff"] else 0)
    return out

def apply_source(con, inn: str, source: str) -> dict:
    """Rewrite the company's sanoat opening rows: 'template' — from the stored номманом (months <= base month);
    'customs' — from the customs base items. Caller commits. Returns {"months": [12], "total", "source"}."""
    if source not in SOURCES: raise ValueError("Йил боши манбаси: customs ёки template")
    y = year(con); bm = base_month(con)
    if not bm: raise ValueError("Божхона базаси юкланмаган — йил боши манбасини ўзгартириб бўлмайди")
    if source == "template":
        t = template_rows(con).get(inn)
        if not t: raise ValueError("Бу корхона шаблон номманомида (саноат қатори) йўқ — шаблон манба бўла олмайди")
        months = t["months"][:bm] + [0.0] * (12 - bm)
    else:
        months = customs_months(con, y, inn).get(inn, [0.0] * 12)
    through = db.get_setting(con, "opening_through_date")
    con.execute("DELETE FROM opening_balances WHERE inn=? AND year=? AND kind='sanoat'", (inn, y))
    con.executemany("INSERT INTO opening_balances(inn,kind,year,month,amount,through_date,source) VALUES(?,'sanoat',?,?,?,?,?)",
                    [(inn, y, m + 1, round(v, 6), through if m + 1 == bm else None, source) for m, v in enumerate(months) if round(v, 6)])
    con.execute("UPDATE companies SET opening_source=?, updated_at=datetime('now','localtime') WHERE inn=?", (source, inn))
    return {"months": [round(v, 3) for v in months], "total": round(sum(months), 3), "source": source}

TPL_T1 = "Шаблон (қўлда киритилган йил боши)"     # tovar1 / country label of the synthetic rows below

def template_items(con, y: int, f: str, t: str, inn: str | None = None) -> list:
    """Item-like rows for the analytics (Тармоқ / Динамика / Ҳисоботлар / География) of companies whose opening comes from
    the template: one row per month (dated the 1st), no HS / country / netto. The items rows of these companies are skipped there."""
    tset = template_inns(con)
    if not tset: return []
    out = []
    for r in con.execute("SELECT inn, month, amount FROM opening_balances WHERE year=? AND kind='sanoat' AND source='template'" + (" AND inn=?" if inn else ""),
                         (y, *((inn,) if inn else ()))):
        if r["inn"] not in tset: continue
        rdate = f"{y}-{r['month']:02d}-01"
        if not (f <= rdate <= t): continue
        out.append({"inn": r["inn"], "rdate": rdate, "gtd": f"tpl:{r['inn']}:{r['month']}", "hs10": "", "hs4": "", "tovar1": TPL_T1, "tovar2": None,
                    "sprav1": None, "sprav2": None, "value": r["amount"], "netto": 0.0, "kind": "sanoat", "country": None})
    return out
