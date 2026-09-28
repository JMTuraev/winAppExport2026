"""Korxonalar: registry list, company profile (passport), district share, contacts, issues, documents, Excel.

Company export = monthly customs base items (≤ base date) + daily GTD rows (after it), voided excluded; kinds sanoat + meva (informational),
bnpz/memo only for the excluded companies (БНПЗ, SDK). District / region totals = sanoat + karantin meva (report.karantin), like the Dashboard.
"""
from __future__ import annotations
import json, re, shutil, datetime as dt
from pathlib import Path
from collections import defaultdict
from . import db, report, smart
from .xl import read_sheet, sheet_names, inn_str, num, _norm

MONTHS_UZ = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
MONTH_STEMS = ["январ", "феврал", "март", "апрел", "май", "июн", "июл", "август", "сентябр", "октябр", "ноябр", "декабр"]
KIND_UZ = {"muammo": "Муаммо", "vazifa": "Вазифа", "murojaat": "Мурожаат", "izoh": "Изоҳ"}

# GTD files name countries in Russian capitals, the monthly base in Uzbek: one name per country in the profile
COUNTRY_RU = [("АФГАН", "Афғонистон"), ("АЗЕРБ", "Озарбайжон"), ("АРМЕН", "Арманистон"), ("БЕЛАРУС", "Беларусь"), ("ГЕРМАН", "Германия"), ("ГРУЗ", "Грузия"),
    ("ИНДИЯ", "Ҳиндистон"), ("ИРАН", "Эрон"), ("КАЗАХ", "Қозоғистон"), ("КИТАЙ", "Хитой"), ("КОРЕЯ", "Корея"), ("КЫРГЫЗ", "Қирғизистон"), ("КИРГИЗ", "Қирғизистон"),
    ("ЛАТВ", "Латвия"), ("ЛИТВ", "Литва"), ("МАРОККО", "Марокаш"), ("ЕГИП", "Миср"), ("ОБЪЕД. АРАБ", "БАА"), ("ОБЪЕДИНЕННЫЕ АРАБ", "БАА"), ("ОАЭ", "БАА"),
    ("ОМАН", "Уммон"), ("ПАКИСТАН", "Покистон"), ("ПОЛЬША", "Польша"), ("РОССИ", "Россия"), ("СЛОВАК", "Словакия"), ("США", "АҚШ"), ("СОЕДИНЕННЫЕ ШТАТЫ", "АҚШ"),
    ("ТАДЖИК", "Тожикистон"), ("ТУРКМЕН", "Туркманистон"), ("ТУРЦИ", "Туркия"), ("УКРАИН", "Украина"), ("ФРАНЦ", "Франция"), ("ХОРВАТ", "Хорватия"),
    ("ЯПОНИ", "Япония"), ("ВЬЕТНАМ", "Ветнам"), ("ВЕНГР", "Венгрия"), ("ЮЖНАЯ АФРИКА", "Жанубий Африка"), ("ИТАЛ", "Италия"), ("ИСПАН", "Испания"),
    ("НИДЕРЛАНД", "Нидерландия"), ("ВЕЛИКОБРИТ", "Буюк Британия"), ("СОЕДИНЕННОЕ КОРОЛ", "Буюк Британия"), ("ИЗРАИЛ", "Исроил"), ("САУДОВ", "Саудия Арабистони"),
    ("АҚШ", "АҚШ"), ("БАА", "БАА"), ("КАТАР", "Қатар"), ("КУВЕЙТ", "Қувайт"), ("ИРАК", "Ироқ"), ("СИРИ", "Сурия"), ("МОНГОЛ", "Мўғулистон"), ("МОЛДОВ", "Молдова"), ("ЭСТОН", "Эстония"),
    ("БОЛГАР", "Болгария"), ("РУМЫН", "Руминия"), ("ЧЕХ", "Чехия"), ("АВСТРИЯ", "Австрия"), ("ШВЕЙЦАР", "Швейцария"), ("БЕЛЬГ", "Белгия"), ("КАНАД", "Канада"),
    ("МАЛАЙЗ", "Малайзия"), ("ИНДОНЕЗ", "Индонезия"), ("ТАИЛАНД", "Таиланд"), ("БАНГЛАДЕШ", "Бангладеш"), ("ШРИ-ЛАНК", "Шри-Ланка"), ("СЕРБ", "Сербия"), ("ГРЕЦ", "Греция")]

def country_uz(name) -> str:
    s = str(name or "").strip()
    if not s: return "—"
    up = s.upper()
    for key, uz in COUNTRY_RU:
        if up.startswith(key): return uz
    return s if (not s.isupper() or len(s) <= 4) else s.capitalize()   # АҚШ, БАА kabi qisqartmalar o'zgarmaydi

def year(con) -> int:
    return int(db.get_setting(con, "year") or dt.date.today().year)

def _today(con) -> str:
    return report.last_data_date(con) or dt.date.today().isoformat()

# ------------------------------------------------------------------ export aggregates
def _monthly(con, inn: str | None = None, y: int | None = None):
    """{inn: {"m": [12], "gtd": n, "last": date}} — for the site's year, or any past year of the customs base (y)."""
    y = str(y or year(con)); through = db.get_setting(con, "opening_through_date") or ""
    # "m" — korxona jami (sanoat + o'z meva qatorlari, ma'lumot uchun; BNPZ/SDK da bnpz/memo ham); "ms" — faqat sanoat (tuman/vilyoat jamisi uchun:
    # meva u yerda faqat karantin qoidasi bilan qo'shiladi, report.karantin)
    out = defaultdict(lambda: {"m": [0.0] * 12, "ms": [0.0] * 12, "gtd": 0, "last": None})
    f = " AND inn=?" if inn else ""; a = (inn,) if inn else ()
    # Same rules as the dashboard (report.company_amounts): «Бухоро эмас» companies count nowhere — neither their
    # monthly customs base nor their GTD; GTD kind not_bukhara never; bnpz / memo only inside the excluded companies' own rows (БНПЗ, SDK).
    skip = report.not_bukhara_inns(con); win = report.bukhara_windows(con)
    excl = {r["inn"] for r in con.execute("SELECT inn FROM companies WHERE coalesce(excluded,0)<>0")}   # 1 = SDK (memo), 2 = БНПЗ
    def kind_ok(i, k):
        if k in ("sanoat", "meva"): return True
        return k in ("bnpz", "memo") and i in excl
    def add(i, mi, k, v):
        o = out[i]; o["m"][mi] += v
        if k != "meva": o["ms"][mi] += v
    # «Йил боши манбаси = Шаблон»: the company's sanoat base months come from the imported template rows, not from items
    from . import dispute
    tset = dispute.template_inns(con) if int(y) == year(con) else set()
    if has_base_detail(con):
        for r in con.execute(f"""SELECT inn, month m, kind, sum(value) v, count(DISTINCT gtd) g, max(rdate) l
                                 FROM items WHERE regime='ЭК' AND year=?{f} GROUP BY inn, m, kind""", (int(y), *a)):
            if r["inn"] in skip or r["inn"] in win or not kind_ok(r["inn"], r["kind"]): continue
            if r["inn"] in tset and r["kind"] == "sanoat": continue
            add(r["inn"], r["m"] - 1, r["kind"], r["v"] or 0); o = out[r["inn"]]; o["gtd"] += r["g"]; o["last"] = max(filter(None, [o["last"], r["l"]]), default=None)
        for t_inn, mm in dispute.template_balances(con, int(y)).items():
            if t_inn in skip or t_inn in win or (inn and t_inn != inn) or t_inn not in tset: continue
            for mi, v in enumerate(mm):
                if v: add(t_inn, mi, "sanoat", v); out[t_inn]["last"] = max(filter(None, [out[t_inn]["last"], f"{y}-{mi+1:02d}-01"]), default=None)
        # limited Bukhara period (moved into / out of the region): base rows are taken by date, inside the period only
        for w_inn, w in win.items():
            if w_inn in skip or (inn and w_inn != inn): continue
            for r in con.execute("SELECT rdate, gtd, kind, value FROM items WHERE regime='ЭК' AND inn=? AND year=? AND rdate>=? AND rdate<=?", (w_inn, int(y), w[0], w[1])):
                if not kind_ok(w_inn, r["kind"]): continue
                add(w_inn, int(r["rdate"][5:7]) - 1, r["kind"], r["value"] or 0); o = out[w_inn]; o["last"] = max(filter(None, [o["last"], r["rdate"]]), default=None)
            o = out[w_inn]; o["gtd"] += con.execute("SELECT count(DISTINCT gtd) FROM items WHERE regime='ЭК' AND inn=? AND year=? AND rdate>=? AND rdate<=?", (w_inn, int(y), w[0], w[1])).fetchone()[0]
    else:   # database loaded before profiles existed: monthly totals only (products, countries, GTD appear after the base is loaded again)
        for r in con.execute(f"SELECT inn, month m, kind, sum(amount) v FROM opening_balances WHERE year=? AND kind<>'exclude'{f} GROUP BY inn, month, kind", (int(y), *a)):
            if r["inn"] in skip or not kind_ok(r["inn"], r["kind"]): continue
            if r["inn"] in win:
                w = win[r["inn"]]; first, last = f"{y}-{r['m']:02d}-01", f"{y}-{r['m']:02d}-31"
                if not (w[0] <= last and first <= w[1]): continue
            add(r["inn"], r["m"] - 1, r["kind"], r["v"] or 0)
    from .daily import is_bukhara
    meva_inns = {i for (i,) in con.execute("SELECT inn FROM template_inns WHERE category='meva'")} or \
                {i for (i,) in con.execute("SELECT inn FROM companies WHERE kind='meva' AND source='nomma-nom'")}
    comps = {r["inn"]: dict(r) for r in con.execute("SELECT inn, in_base, bukhara, source FROM companies")}
    for r in con.execute(f"""SELECT inn, kind, CAST(substr(report_date,6,2) AS INT) m, sum(stat_usd) v, count(DISTINCT gtd_no) g, max(report_date) l, min(report_date) f0
                             FROM gtd_rows WHERE voided=0 AND kind IN ('sanoat','meva','meva_x','bnpz','memo') AND report_date>? AND substr(report_date,1,4)=?{f}
                             GROUP BY inn, kind, m""", (through, y, *a)):
        if r["inn"] in skip or not kind_ok(r["inn"], r["kind"] if r["kind"] != "meva_x" else "meva"): continue
        mk = "meva" if r["kind"] in ("meva", "meva_x") else r["kind"]
        if r["inn"] in win and not (report.in_window(win, r["inn"], r["f0"]) and report.in_window(win, r["inn"], r["l"])):
            # the month straddles the period boundary: re-sum that month by day
            w = win[r["inn"]]; rr = con.execute("""SELECT sum(stat_usd) v, count(DISTINCT gtd_no) g, max(report_date) l FROM gtd_rows WHERE voided=0 AND inn=? AND kind=?
                AND report_date>? AND substr(report_date,1,7)=? AND report_date>=? AND report_date<=?""", (r["inn"], r["kind"], through, f"{y}-{r['m']:02d}", w[0], w[1])).fetchone()
            if not rr["v"]: continue
            add(r["inn"], r["m"] - 1, mk, rr["v"] or 0); o = out[r["inn"]]; o["gtd"] += rr["g"]; o["last"] = max(filter(None, [o["last"], rr["l"]]), default=None); continue
        if r["kind"] == "meva" and not is_bukhara(comps.get(r["inn"]), r["inn"], meva_inns): continue   # another region's meva-sabzavot (karantin rule)
        add(r["inn"], r["m"] - 1, mk, r["v"] or 0); o = out[r["inn"]]; o["gtd"] += r["g"]; o["last"] = max(filter(None, [o["last"], r["l"]]), default=None)
    return out

def district_totals(con, mon: dict, comps: dict, y: int | None = None, D: str | None = None) -> tuple:
    """({district_code: [12]}, {district_code: ytd}) — tuman jamisi Dashboard qoidasi bilan: sanoat (korxonalar, excluded'lardan tashqari)
    + meva-sabzavot FAQAT karantin qoidasi bilan (report.karantin: svod ytd + GTD meva o'stirilgan tuman bo'yicha). Korxona meva qatorlari kirmaydi."""
    from . import products
    y = int(y or year(con)); D = D or (_today(con) if y == year(con) else f"{y}-12-31")
    if not D.startswith(str(y)): D = f"{y}-12-31"
    dm = defaultdict(lambda: [0.0] * 12); dy = defaultdict(float)
    for inn, m in mon.items():
        c = comps.get(inn) or {}
        if c.get("excluded"): continue
        dc = c.get("district_code")
        for k in range(12): dm[dc][k] += m["ms"][k]
        dy[dc] += sum(m["ms"])
    for dc, mm in products.karantin_months(con, y, D).items():
        for k in range(12): dm[dc][k] += mm[k]
    for dc, v in report.karantin(con, D).items(): dy[dc] += v["ytd"]
    return dm, dy

def has_base_detail(con) -> bool:
    return con.execute("SELECT 1 FROM items WHERE regime='ЭК' LIMIT 1").fetchone() is not None or db.get_setting(con, "opening_source") != "customs"

def signals(ytd, month_v, last, today: str, excluded=False, share=None, month_share=None):
    """Signals without a ministry plan: the district weight of the company and how long it has been silent."""
    s = []
    if share is not None and share >= 10: s.append({"k": "big", "t": f"туман экспортининг {share:.0f}%", "lvl": "info"})
    if ytd > 0 and month_v <= 0: s.append({"k": "nomonth", "t": "шу ойда экспорт йўқ", "lvl": "warn"})
    if last and ytd > 0:
        gap = (dt.date.fromisoformat(today) - dt.date.fromisoformat(last)).days
        if gap >= 45: s.append({"k": "silent", "t": f"{gap} кун экспорт йўқ", "lvl": "warn"})
    return s

def list_companies(con, q: dict) -> dict:
    y = year(con); today = _today(con); cur_m = int(today[5:7])
    mon = _monthly(con)
    comps = {r["inn"]: dict(r) for r in con.execute("SELECT * FROM companies")}
    tpl = {r["inn"] for r in con.execute("SELECT DISTINCT inn FROM template_inns")}
    issues = defaultdict(int)
    for r in con.execute("SELECT inn, count(*) n FROM issues WHERE status='open' AND inn IS NOT NULL GROUP BY inn"): issues[r["inn"]] = r["n"]
    contacts = {r["inn"]: _contact_row(r) for r in con.execute("SELECT * FROM company_contacts")}
    dnames = {d["code"]: d["name_uz"] for d in report.districts(con)}
    def vals(key):   # the filters take several values at once: «a,b,c» — they are OR-ed
        return [x.strip() for x in str(q.get(key) or "").split(",") if x.strip()]
    statuses = vals("status") or ["exporters"]
    dists, tarmoqs, kinds = set(vals("district")), set(vals("tarmoq")), set(vals("kind"))
    inns = set(comps)
    # district weight: the district's own year-to-date total (Dashboard qoidasi: sanoat + karantin mevasi; БНПЗ / SDK alohida —
    # they must not swallow the district), so every company's share is measured against it
    dmon, d_total = district_totals(con, mon, comps, y, today)
    d_month = {dc: mm[cur_m - 1] for dc, mm in dmon.items()}
    rows = []
    for inn in inns:
        c = comps.get(inn) or {}; m = mon.get(inn) or {"m": [0.0] * 12, "gtd": 0, "last": None}
        ytd = sum(m["m"]); dc = c.get("district_code")
        dt_ = d_total.get(dc) or 0.0
        share = round(ytd / dt_ * 100, 1) if dt_ > 0 and ytd > 0 and not c.get("excluded") else None
        r = {"inn": inn, "name": c.get("name"), "district_code": dc,
             "district": dnames.get(c.get("district_code")), "tarmoq": c.get("tarmoq"),
             "uyushma": c.get("uyushma"), "kind": c.get("kind"), "ytd": round(ytd, 3), "month": round(m["m"][cur_m - 1], 3), "last": m["last"], "gtd": m["gtd"],
             "share": share, "district_ytd": round(dt_, 3), "rank": None,
             "month_share": round(m["m"][cur_m - 1] / d_month[dc] * 100, 1) if (d_month.get(dc) or 0) > 0 and m["m"][cur_m - 1] > 0 and not c.get("excluded") else None,
             "issues": issues.get(inn, 0), "new_date": c.get("new_date"),
             "in_template": inn in tpl, "in_base": c.get("in_base"), "bukhara": c.get("bukhara"), "bukhara_from": c.get("bukhara_from"), "bukhara_to": c.get("bukhara_to"), "source": c.get("source"), "confirmed": c.get("confirmed", 1),
             "excluded": c.get("excluded"), "registered": bool(c), "director": (contacts.get(inn) or {}).get("director"), "phone": ", ".join((contacts.get(inn) or {}).get("phones") or []) or None}
        r["signals"] = signals(ytd, r["month"], m["last"], today, bool(c.get("excluded")), share)
        rows.append(r)
    by_d = defaultdict(list)                       # rank inside the district (by year-to-date)
    for r in rows:
        if r["ytd"] > 0 and not r["excluded"]: by_d[r["district_code"]].append(r)
    for lst in by_d.values():
        for i, r in enumerate(sorted(lst, key=lambda x: -x["ytd"]), 1): r["rank"] = i
    d_count = {k: len(v) for k, v in by_d.items()}
    for r in rows: r["district_n"] = d_count.get(r["district_code"], 0)
    def st_ok(r, status):
        if status == "exporters": return r["ytd"] > 0 or r["in_template"]
        if status == "nophone": return (r["ytd"] > 0 or r["in_template"]) and not r["phone"]
        if status == "new": return bool(r["new_date"])
        if status == "big": return r["share"] is not None and r["share"] >= 10
        if status == "nomonth": return any(x["k"] == "nomonth" for x in r["signals"])
        if status == "issues": return bool(r["issues"])
        if status == "silent": return any(x["k"] == "silent" for x in r["signals"])
        if status == "notbase": return bool(r["registered"] and not r["in_base"] and r["source"] != "gtd")
        if status == "unconfirmed": return bool(r["registered"] and not r["confirmed"])
        if status == "noreg": return not r["registered"]
        if status == "all": return bool(r["registered"])
        return True
    def keep(r):
        if not any(st_ok(r, st) for st in statuses): return False       # several statuses: any of them is enough
        if dists and r["district_code"] not in dists: return False
        if tarmoqs and (r["tarmoq"] or "").strip() not in tarmoqs: return False
        if kinds and r["kind"] not in kinds: return False
        if q.get("q") and not smart.match(q["q"], r["inn"], r["name"]): return False   # lotin/kirill farqsiz
        return True
    rows = [r for r in rows if keep(r)]
    sort = q.get("sort") or "ytd"
    key = {"ytd": lambda r: -r["ytd"], "month": lambda r: -r["month"], "share": lambda r: -(r["share"] or 0),
           "last": lambda r: (r["last"] is None, "" if r["last"] is None else "~" + r["last"]), "name": lambda r: (r["name"] or "").lower(),
           "new": lambda r: (r["new_date"] is None, "" if not r["new_date"] else "~" + r["new_date"])}.get(sort, lambda r: -r["ytd"])
    if sort in ("last", "new"):
        f = "last" if sort == "last" else "new_date"
        rows.sort(key=lambda r: r[f] or "", reverse=True)
    else:
        rows.sort(key=key)
    kpi = {"exporters": sum(1 for inn in inns if sum((mon.get(inn) or {"m": [0]})["m"]) > 0),
           "nophone": sum(1 for inn in inns if (sum((mon.get(inn) or {"m": [0]})["m"]) > 0 or inn in tpl) and not (contacts.get(inn) or {}).get("phones")),
           "new": sum(1 for c in comps.values() if c.get("new_date")),
           "issues": con.execute("SELECT count(*) FROM issues WHERE status='open'").fetchone()[0],
           "overdue": con.execute("SELECT count(*) FROM issues WHERE status='open' AND due_date IS NOT NULL AND due_date<>'' AND due_date<?", (dt.date.today().isoformat(),)).fetchone()[0],
           "count": len(rows), "sum_ytd": round(sum(r["ytd"] for r in rows if not r["excluded"]), 3),      # «Жами» — alohida hisobdagilarsiz (БНПЗ, SDK)
           "sum_excluded": round(sum(r["ytd"] for r in rows if r["excluded"]), 3), "sum_all": round(sum(r["ytd"] for r in rows), 3),
           "sum_counted": round(sum(r["ytd"] for r in rows if not r["excluded"]), 3),
           "region_ytd": round(sum(v for v in d_total.values()), 3), "meva_rule": "karantin",
           "total": len(rows), "base_detail": has_base_detail(con), "base_legacy": db.items_legacy(con)}
    return {"year": y, "today": today, "month": cur_m, "rows": rows[: int(q.get("limit") or 1000)], "kpi": kpi,
            "tarmoqlar": sorted({(c.get("tarmoq") or "").strip() for c in comps.values() if c.get("tarmoq")})}

def names(con) -> list[dict]:
    """Companies worth picking in forms: exporters this year, номманом, anyone with an issue."""
    y = str(year(con))
    rows = {r["inn"]: r["name"] for r in con.execute(f"""SELECT inn, name FROM companies WHERE inn IN (
        SELECT inn FROM items WHERE regime='ЭК' AND year=? UNION SELECT inn FROM gtd_rows WHERE voided=0 UNION SELECT inn FROM template_inns
        UNION SELECT inn FROM issues WHERE inn IS NOT NULL UNION SELECT inn FROM company_contacts)""", (int(y),))}
    return sorted(({"inn": k, "name": v} for k, v in rows.items()), key=lambda x: (x["name"] or "").lower())

# ------------------------------------------------------------------ profile
def district_share(con, district_code, inn, cur_m: int, y: int | None = None) -> dict:
    """The company's weight inside its own district: year-to-date %, this month's %, rank, and the district by month."""
    if not district_code: return {"share": None, "month_share": None, "rank": None, "district_n": 0, "district_ytd": 0.0, "district_month": 0.0, "months": None}
    mon = _monthly(con, y=y)
    comps = {r["inn"]: dict(r) for r in con.execute("SELECT inn, district_code, excluded FROM companies WHERE district_code=?", (district_code,))}
    mine = mon.get(inn) or {"m": [0.0] * 12}
    # tuman jamisi Dashboard qoidasi bilan (sanoat + karantin mevasi); korxona o'rni — sanoat bo'yicha
    dmon, dtot = district_totals(con, {i: m for i, m in mon.items() if i in comps}, comps, y)
    dm = dmon.get(district_code) or [0.0] * 12
    tot = []
    for i, c in comps.items():
        if c.get("excluded"): continue
        m = mon.get(i) or {"m": [0.0] * 12}
        if sum(m["m"]) > 0: tot.append((sum(m["m"]), i))
    tot.sort(reverse=True)
    ytd = sum(mine["m"]); d_ytd = dtot.get(district_code) or 0.0; d_month = dm[cur_m - 1]
    excluded = bool((comps.get(inn) or {}).get("excluded"))
    return {"share": round(ytd / d_ytd * 100, 1) if d_ytd > 0 and ytd > 0 and not excluded else None,
            "month_share": round(mine["m"][cur_m - 1] / d_month * 100, 1) if d_month > 0 and mine["m"][cur_m - 1] > 0 and not excluded else None,
            "rank": next((n for n, (_, i) in enumerate(tot, 1) if i == inn), None), "district_n": len(tot),
            "district_ytd": round(d_ytd, 3), "district_month": round(d_month, 3), "months": [round(v, 3) for v in dm]}

def profile(con, inn: str, year_: int | None = None) -> dict:
    """Company passport for the site's year or any past year of the customs base (year_)."""
    cur_y = year(con); y = int(year_ or cur_y); past = y != cur_y
    today = _today(con) if not past else f"{y}-12-31"; cur_m = int(today[5:7]); through = db.get_setting(con, "opening_through_date") or ""
    c = con.execute("SELECT * FROM companies WHERE inn=?", (inn,)).fetchone()
    if not c: raise ValueError("Korxona topilmadi: " + inn)
    c = dict(c)
    dn = {d["code"]: d["name_uz"] for d in report.districts(con)}
    m = _monthly(con, inn, y).get(inn) or {"m": [0.0] * 12, "gtd": 0, "last": None}
    ytd = sum(m["m"])
    # share of the company's own district (year to date and the current month), and its place there
    dshare = district_share(con, c.get("district_code"), inn, cur_m, y)
    # products (HS4) and countries
    prods, countries, labels = defaultdict(lambda: [0.0, 0.0]), defaultdict(float), {}
    win = report.bukhara_windows(con); inw = lambda d: report.in_window(win, inn, d)
    for r in con.execute("""SELECT i.rdate, i.hs10 hs, i.tovar1, i.tovar2, d.country, i.netto, i.value FROM items i JOIN declarations d ON d.decl_id=i.decl_id
                            WHERE i.regime='ЭК' AND i.inn=? AND i.year=?""", (inn, y)):
        if not inw(r["rdate"]): continue
        k = (r["hs"] or "")[:4] or "—"; prods[k][0] += r["value"] or 0; prods[k][1] += r["netto"] or 0
        labels.setdefault(k, r["tovar2"] or r["tovar1"]); countries[country_uz(r["country"])] += r["value"] or 0
    for r in con.execute("SELECT report_date, tnved, product, country, netto, stat_usd FROM gtd_rows WHERE voided=0 AND inn=? AND report_date>? AND substr(report_date,1,4)=?", (inn, through, str(y))):
        if not inw(r["report_date"]): continue
        k = str(r["tnved"] or "")[:4] or "—"; prods[k][0] += r["stat_usd"] or 0; prods[k][1] += (r["netto"] or 0) / 1000
        labels.setdefault(k, (r["product"] or "")[:60]); countries[country_uz(r["country"])] += r["stat_usd"] or 0
    for r in con.execute("SELECT substr(tnved,1,4) k, product, sum(stat_usd) v FROM gtd_rows WHERE voided=0 AND inn=? GROUP BY k, product ORDER BY v DESC", (inn,)):
        if r["k"] in prods and r["product"] and not labels.get("gtd:" + r["k"]):
            labels["gtd:" + r["k"]] = re.sub(r"^\s*\d+[.)]\s*", "", r["product"]).strip()[:90]
    for k in list(prods):
        if labels.get("gtd:" + k): labels[k] = labels["gtd:" + k]
    if not labels or any(not v for v in labels.values()):
        for r in con.execute("SELECT hs4 k, tovar2, tovar1 FROM items WHERE hs4 IN (%s) GROUP BY k" % ",".join("?" * len(prods)), list(prods)):
            if not labels.get(r["k"]): labels[r["k"]] = r["tovar2"] or r["tovar1"]
    products = sorted(({"hs4": k, "name": labels.get(k), "value": round(v[0], 3), "netto_t": round(v[1], 3)} for k, v in prods.items()), key=lambda x: -x["value"])
    countries = sorted(({"country": k, "value": round(v, 3)} for k, v in countries.items()), key=lambda x: -x["value"])
    # GTD history (one line per declaration)
    hist = []
    for r in con.execute("""SELECT i.rdate d, i.gtd, d.country, count(*) items, sum(i.value) v, sum(i.netto) n, group_concat(DISTINCT coalesce(i.tovar2, i.tovar1)) pr
                            FROM items i JOIN declarations d ON d.decl_id=i.decl_id WHERE i.regime='ЭК' AND i.inn=? AND i.year=? GROUP BY i.rdate, i.gtd, d.country""", (inn, y)):
        hist.append({"date": r["d"], "gtd": r["gtd"], "country": country_uz(r["country"]), "items": r["items"], "value": round(r["v"] or 0, 3), "netto_t": round(r["n"] or 0, 3), "products": (r["pr"] or "")[:120], "src": "baza", "counted": inw(r["d"])})
    for r in con.execute("""SELECT report_date d, gtd_no gtd, country, count(*) items, sum(stat_usd) v, sum(netto) n, group_concat(DISTINCT substr(product,1,50)) pr, group_concat(DISTINCT kind) kinds
                            FROM gtd_rows WHERE voided=0 AND inn=? AND report_date>? AND substr(report_date,1,4)=? GROUP BY report_date, gtd_no, country""", (inn, through, str(y))):
        hist.append({"date": r["d"], "gtd": r["gtd"], "country": country_uz(r["country"]), "items": r["items"], "value": round(r["v"] or 0, 3), "netto_t": round((r["n"] or 0) / 1000, 3), "products": (r["pr"] or "")[:120], "src": "gtd", "kinds": r["kinds"],
                     "counted": inw(r["d"]) and c.get("bukhara") != 0 and (r["kinds"] or "") not in ("not_bukhara",)})
    hist.sort(key=lambda x: (x["date"] or "", x["gtd"] or ""), reverse=True)
    imp = [0.0] * 12
    for r in con.execute("SELECT month, sum(value) value FROM items WHERE regime='ИМ' AND inn=? AND year=? GROUP BY month", (inn, y)): imp[r["month"] - 1] = r["value"] or 0
    tpl = [dict(r) for r in con.execute("SELECT category, row, district, yellow FROM template_inns WHERE inn=?", (inn,))]
    contacts = con.execute("SELECT * FROM company_contacts WHERE inn=?", (inn,)).fetchone()
    # ---- the INN tree: years, product tree, logistics, prices (see _tree_extras)
    extra = _tree_extras(con, inn, y, cur_y, products, inw)
    return {"inn": inn, "year": y, "past": past, "today": today, "month": cur_m, "base_through": through or None, "base_detail": has_base_detail(con), "base_legacy": db.items_legacy(con), **extra,
            "company": {**c, "district": dn.get(c.get("district_code"))}, "contacts": _contact_row(contacts), "persons": persons_list(con, inn),
            "template": tpl, "district_share": dshare, "kpi": {"ytd": round(ytd, 3), "month": round(m["m"][cur_m - 1], 3), "last": m["last"], "gtd": m["gtd"],
            "countries": len([x for x in countries if x["value"]]), "products": len(products), "import_ytd": round(sum(imp), 3), **dshare},
            "months": [round(v, 3) for v in m["m"]], "district_months": dshare.get("months"), "import_months": [round(v, 3) for v in imp],
            "signals": signals(ytd, m["m"][cur_m - 1], m["last"], today, bool(c.get("excluded")), dshare.get("share")), "products": products[:15], "countries": countries[:15], "history": hist[:400],
            "history_count": len(hist), "issues": issues_list(con, {"inn": inn, "status": "all"}),
            "docs": [dict(r) for r in con.execute("SELECT id, filename, size, note, doc_date, uploaded_at FROM company_docs WHERE inn=? AND deleted=0 ORDER BY id DESC", (inn,))],
            "events": [dict(r) for r in con.execute("SELECT at, kind, text FROM company_events WHERE inn=? ORDER BY id DESC LIMIT 100", (inn,))]}

CONTACT_FIELDS = ("director", "phone", "phones", "address", "email", "note")
CONTACT_NAMES = {"director": "раҳбар", "phone": "телефон", "phones": "телефонлар", "address": "манзил", "email": "email", "note": "изоҳ"}

def norm_phone(v) -> str | None:
    """+998 90 123-45-67 for Uzbek numbers (9 local digits, with or without 998); other countries keep +<digits>."""
    raw = str(v or "").strip()
    if not raw: return None
    d = re.sub(r"\D", "", raw)
    if len(d) < 7: return None
    if len(d) == 9: d = "998" + d
    if len(d) == 12 and d.startswith("998"):
        return f"+998 {d[3:5]} {d[5:8]}-{d[8:10]}-{d[10:12]}"
    return "+" + d

def _phones(data, key="phones") -> list[str]:
    v = data.get(key)
    if isinstance(v, str):
        try: v = json.loads(v)
        except ValueError: v = [v]
    out = []
    for x in (v or []):
        p = norm_phone(x)
        if p and p not in out: out.append(p)
    return out

def _contact_row(r) -> dict:
    if not r: return {}
    d = dict(r); d.pop("legal_form", None)
    d["phones"] = _phones(d) or ([d["phone"]] if d.get("phone") else [])
    return d

def save_contacts(con, inn: str, data: dict):
    old = _contact_row(con.execute("SELECT * FROM company_contacts WHERE inn=?", (inn,)).fetchone())
    phones = _phones(data) if "phones" in data else _phones({"phones": [data.get("phone")]})
    vals = {k: (str(data.get(k) or "").strip() or None) for k in ("director", "address", "email", "note")}
    vals["phone"] = phones[0] if phones else None
    vals["phones"] = json.dumps(phones, ensure_ascii=False) if phones else None
    cols = list(vals)
    with con:
        con.execute(f"""INSERT INTO company_contacts(inn,{','.join(cols)},updated_at) VALUES(?,{','.join('?' * len(cols))},datetime('now','localtime'))
                        ON CONFLICT(inn) DO UPDATE SET {', '.join(f'{k}=excluded.{k}' for k in cols)}, updated_at=excluded.updated_at""", (inn, *[vals[k] for k in cols]))
        changed = [k for k in ("director", "phones", "address", "email", "note") if (old.get(k) if k != "phones" else (old.get("phones") or [])) != (vals[k] if k != "phones" else phones)]
        if changed: db.event(con, inn, "contacts", "Алоқа маълумотлари янгиланди: " + ", ".join(CONTACT_NAMES[k] for k in changed))

# ------------------------------------------------------------------ contact persons
def persons_list(con, inn: str) -> list[dict]:
    out = []
    for r in con.execute("SELECT * FROM company_persons WHERE inn=? ORDER BY position, id", (inn,)):
        d = dict(r); d["phones"] = _phones(d); out.append(d)
    return out

def save_person(con, data: dict) -> dict:
    inn = str(data.get("inn") or "").strip(); name = str(data.get("name") or "").strip()
    if not inn: raise ValueError("ИНН йўқ")
    if not name: raise ValueError("Исмини киритинг")
    role = str(data.get("role") or "").strip() or None; note = str(data.get("note") or "").strip() or None
    phones = _phones(data); pj = json.dumps(phones, ensure_ascii=False) if phones else None
    pid = int(data.get("id") or 0)
    with con:
        if pid:
            con.execute("UPDATE company_persons SET name=?, role=?, phones=?, note=?, updated_at=datetime('now','localtime') WHERE id=? AND inn=?", (name, role, pj, note, pid, inn))
            db.event(con, inn, "contacts", f"Алоқадор шахс янгиланди: {name}" + (f" ({role})" if role else ""))
        else:
            pos = (con.execute("SELECT coalesce(max(position),0) FROM company_persons WHERE inn=?", (inn,)).fetchone()[0] or 0) + 10
            pid = con.execute("INSERT INTO company_persons(inn,name,role,phones,note,position) VALUES(?,?,?,?,?,?)", (inn, name, role, pj, note, pos)).lastrowid
            db.event(con, inn, "contacts", f"Алоқадор шахс қўшилди: {name}" + (f" ({role})" if role else ""))
    return {"ok": True, "id": pid}

def delete_person(con, pid: int) -> dict:
    r = con.execute("SELECT inn, name FROM company_persons WHERE id=?", (pid,)).fetchone()
    if not r: raise ValueError("Топилмади")
    with con:
        con.execute("DELETE FROM company_persons WHERE id=?", (pid,))
        db.event(con, r["inn"], "contacts", f"Алоқадор шахс олиб ташланди: {r['name']}")
    return {"ok": True}

# ------------------------------------------------------------------ issues
def issues_list(con, q: dict) -> list[dict]:
    sql = """SELECT i.*, c.name company, c.district_code FROM issues i LEFT JOIN companies c ON c.inn=i.inn WHERE 1=1"""
    a = []
    st = q.get("status") or "open"
    if st == "open": sql += " AND i.status='open'"
    elif st == "closed": sql += " AND i.status='closed'"
    elif st == "overdue": sql += " AND i.status='open' AND i.due_date IS NOT NULL AND i.due_date<>'' AND i.due_date<?"; a.append(dt.date.today().isoformat())
    if q.get("inn"): sql += " AND i.inn=?"; a.append(q["inn"])
    if q.get("kind"): sql += " AND i.kind=?"; a.append(q["kind"])
    if q.get("district"): sql += " AND c.district_code=?"; a.append(q["district"])
    if q.get("column"): sql += " AND i.column_id=?"; a.append(int(q["column"]))
    if q.get("label"): sql += " AND i.id IN (SELECT issue_id FROM issue_label_links WHERE label_id=?)"; a.append(int(q["label"]))
    sql += " ORDER BY (i.status='open') DESC, CASE WHEN i.due_date IS NULL OR i.due_date='' THEN 1 ELSE 0 END, i.due_date, i.id DESC"
    today = dt.date.today().isoformat()
    out = []
    for r in con.execute(sql, a):
        d = dict(r)
        if q.get("q") and not smart.match(q["q"], d["title"], d["text"], d["company"], d["inn"], d["responsible"], d.get("basis_no")): continue
        d["overdue"] = bool(d["status"] == "open" and d["due_date"] and d["due_date"] < today); out.append(d)
    from . import board
    return board.enrich(con, out)

def save_issue(con, data: dict) -> dict:
    from . import board
    kind = data.get("kind") or "muammo"
    if kind not in KIND_UZ: raise ValueError("Noma'lum tur")
    title = (data.get("title") or "").strip()
    if not title: raise ValueError("Qisqa mazmunini yozing")
    inn = inn_str(data.get("inn")) or None
    if inn and not con.execute("SELECT 1 FROM companies WHERE inn=?", (inn,)).fetchone():
        raise ValueError("Bu INN bo'yicha korxona topilmadi: " + inn)
    fields = {"inn": inn, "kind": kind, "title": title, "text": (data.get("text") or "").strip() or None, "responsible": (data.get("responsible") or "").strip() or None,
              "due_date": (data.get("due_date") or "").strip() or None, "resolution": (data.get("resolution") or "").strip() or None}
    # 26.09.2026: устуворлик ва асос ҳужжат — faqat yuborilgan bo'lsa yangilanadi (eski chaqiruvlar ularni o'chirmaydi)
    if "priority" in data: fields["priority"] = data.get("priority") if data.get("priority") in board.PRIORITY else "normal"
    if "basis_kind" in data:
        bk = (data.get("basis_kind") or "").strip() or None
        if bk and bk not in board.BASIS: raise ValueError("Асос тури нотўғри")
        fields["basis_kind"] = bk
    for k in ("basis_no", "basis_date"):
        if k in data: fields[k] = (str(data.get(k) or "").strip()[:200] or None)
    status = data.get("status") or "open"
    if status not in ("open", "closed"): raise ValueError("Holat noto'g'ri")
    old = con.execute("SELECT * FROM issues WHERE id=?", (int(data["id"]),)).fetchone() if data.get("id") else None
    if data.get("id") and not old: raise ValueError("Yozuv topilmadi")
    # column ↔ status: an explicit column wins (status follows it); otherwise the status picks a column
    cols = {c["id"]: c for c in board.columns(con)}
    col = cols.get(int(data["column_id"])) if data.get("column_id") and int(data["column_id"]) in cols else None
    if col is not None and (old is None or col["id"] != old["column_id"] or (data.get("status") is None)):
        status = "closed" if col["is_done"] else "open"
    elif old is not None and status == old["status"] and old["column_id"] in cols:
        col = cols[old["column_id"]]
    else:
        cid = board.first_column(con, status == "closed"); col = cols.get(cid)
        if col is None: raise ValueError("Доскада устун йўқ — аввал устун қўшинг")
        status = "closed" if col["is_done"] else "open"
    now = dt.datetime.now().isoformat(sep=" ", timespec="seconds")
    with con:
        if old:
            closed_at = old["closed_at"] if status == old["status"] else (now if status == "closed" else None)
            moved = old["column_id"] != col["id"]
            pos = old["position"] if not moved else (con.execute("SELECT coalesce(max(position), 0) FROM issues WHERE column_id=?", (col["id"],)).fetchone()[0] or 0) + 10
            con.execute(f"UPDATE issues SET {', '.join(k + '=?' for k in fields)}, status=?, closed_at=?, column_id=?, position=?, column_at=?, updated_at=datetime('now','localtime') WHERE id=?",
                        (*fields.values(), status, closed_at, col["id"], pos, now if moved else (old["column_at"] or now), old["id"]))
            iid = old["id"]
            if status != old["status"]:
                db.event(con, inn or old["inn"], "issue", f"{KIND_UZ[kind]} {'ҳал қилинди' if status == 'closed' else 'қайта очилди'}: {title}")
            elif moved:
                db.event(con, inn or old["inn"], "issue", f"«{title}» → устун «{col['name']}»")
            for line in _issue_changes(con, old, fields, data, col if moved else None): board.log_issue(con, iid, line)
        else:
            pos = (con.execute("SELECT coalesce(max(position), 0) FROM issues WHERE column_id=?", (col["id"],)).fetchone()[0] or 0) + 10
            cur = con.execute(f"INSERT INTO issues({', '.join(fields)}, status, closed_at, column_id, position, column_at) VALUES({', '.join('?' * len(fields))}, ?, ?, ?, ?, ?)",
                              (*fields.values(), status, now if status == "closed" else None, col["id"], pos, now))
            iid = cur.lastrowid
            db.event(con, inn, "issue", f"{KIND_UZ[kind]} қўшилди: {title}")
            board.log_issue(con, iid, f"Карта яратилди · устун «{col['name']}»")
        if "labels" in data: board.set_issue_labels(con, iid, data.get("labels"))
        db.log(con, "issue_saved", id=iid, inn=inn, status=status, column=col["id"])
    return {"ok": True, "id": iid, "status": status, "column_id": col["id"]}

def _issue_changes(con, old, fields: dict, data: dict, new_col) -> list[str]:
    """Human lines for the card timeline: what the save changed (text edits are not logged — too noisy)."""
    from . import board
    out, d = [], lambda v: f"{v[8:10]}.{v[5:7]}.{v[:4]}" if v else "—"
    if new_col is not None:
        src = con.execute("SELECT name FROM issue_columns WHERE id=?", (old["column_id"],)).fetchone()
        out.append(f"«{src['name'] if src else '—'}» → «{new_col['name']}»")
    if fields["title"] != old["title"]: out.append(f"Номи ўзгартирилди: «{fields['title']}»")
    if fields["inn"] != old["inn"]:
        nm = con.execute("SELECT name FROM companies WHERE inn=?", (fields["inn"],)).fetchone() if fields["inn"] else None
        out.append(f"Корхона: {nm['name'] if nm else fields['inn']}" if fields["inn"] else "Корхона олиб ташланди (умумий карта)")
    if fields["due_date"] != old["due_date"]:
        out.append(f"Муддат белгиланди: {d(fields['due_date'])}" if not old["due_date"] else f"Муддат олиб ташланди" if not fields["due_date"] else f"Муддат ўзгарди: {d(old['due_date'])} → {d(fields['due_date'])}")
    if "priority" in fields and fields["priority"] != (old["priority"] or "normal"):
        out.append(f"Устуворлик: {board.PRIORITY.get(old['priority'] or 'normal')} → {board.PRIORITY[fields['priority']]}")
    if "basis_kind" in fields and (fields.get("basis_kind"), fields.get("basis_no"), fields.get("basis_date")) != (old["basis_kind"], old["basis_no"], old["basis_date"]) and fields.get("basis_kind"):
        out.append("Асос: " + " · ".join(x for x in (board.BASIS[fields["basis_kind"]], fields.get("basis_no"), d(fields.get("basis_date")) if fields.get("basis_date") else None) if x))
    if fields["resolution"] and fields["resolution"] != old["resolution"]: out.append("Натижа ёзилди")
    if "labels" in data:
        before = {r[0] for r in con.execute("SELECT label_id FROM issue_label_links WHERE issue_id=?", (old["id"],))}
        after = {int(x) for x in (data.get("labels") or []) if str(x).strip()}
        names = {r[0]: r[1] for r in con.execute("SELECT id, name FROM issue_labels")}
        add = [names[i] for i in after - before if i in names]; rem = [names[i] for i in before - after if i in names]
        if add: out.append("Ташкилот қўшилди: " + ", ".join(add))
        if rem: out.append("Ташкилот олиб ташланди: " + ", ".join(rem))
    return out

# ------------------------------------------------------------------ documents
def docs_dir() -> Path:
    p = db.BASE / "company_docs"; p.mkdir(parents=True, exist_ok=True); return p

def add_doc(con, inn: str, filename: str, data: bytes, note: str | None, doc_date: str | None) -> dict:
    inn = inn_str(inn)
    if not con.execute("SELECT 1 FROM companies WHERE inn=?", (inn,)).fetchone(): raise ValueError("Korxona topilmadi")
    safe = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", Path(filename).name)[:150] or "fayl"
    with con:
        cur = con.execute("INSERT INTO company_docs(inn, filename, stored, size, note, doc_date) VALUES(?,?,?,?,?,?)", (inn, safe, "", len(data), note or None, doc_date or None))
        did = cur.lastrowid; rel = f"{inn}/{did}__{safe}"
        (docs_dir() / inn).mkdir(parents=True, exist_ok=True); (docs_dir() / rel).write_bytes(data)
        con.execute("UPDATE company_docs SET stored=? WHERE id=?", (rel, did))
        db.event(con, inn, "doc", f"Ҳужжат қўшилди: {safe}" + (f" ({note})" if note else ""))
    return {"ok": True, "id": did}

def doc_path(con, did: int):
    r = con.execute("SELECT * FROM company_docs WHERE id=?", (did,)).fetchone()
    if not r: raise ValueError("Hujjat topilmadi")
    p = docs_dir() / r["stored"]
    if not p.exists(): raise ValueError("Fayl diskda topilmadi")
    return p, r["filename"]

def remove_doc(con, did: int):
    r = con.execute("SELECT * FROM company_docs WHERE id=? AND deleted=0", (did,)).fetchone()
    if not r: raise ValueError("Hujjat topilmadi")
    trash = docs_dir() / "_olib_tashlangan"; trash.mkdir(exist_ok=True)
    src = docs_dir() / r["stored"]
    if src.exists(): shutil.move(str(src), str(trash / f"{r['inn']}__{Path(r['stored']).name}"))
    with con:
        con.execute("UPDATE company_docs SET deleted=1 WHERE id=?", (did,))
        db.event(con, r["inn"], "doc", f"Ҳужжат олиб ташланди: {r['filename']}")

STATUS_UZ = {"exporters": "Экспортёрлар", "nophone": "Телефони йўқ", "new": "Янги корхоналар", "big": "Туманда улуши катта (10%+)", "nomonth": "Шу ойда экспорт йўқ",
             "silent": "45+ кун экспорт йўқ", "issues": "Очиқ муаммоли", "notbase": "Базада йўқ / Бухоро эмас", "unconfirmed": "Тасдиқланмаган",
             "noreg": "Реестрда йўқ", "all": "Бутун реестр"}

def _styles():
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    thin = Side(style="thin", color="C9CFCB")
    return {"h": Font(bold=True, color="FFFFFF"), "hf": PatternFill("solid", fgColor="0F6E63"), "b": Border(top=thin, bottom=thin, left=thin, right=thin),
            "c": Alignment(horizontal="center", vertical="center", wrap_text=True), "w": Alignment(vertical="top", wrap_text=True), "bold": Font(bold=True),
            "title": Font(bold=True, size=14), "sub": Font(italic=True, color="5A6470"), "tot": PatternFill("solid", fgColor="EEF1EE"),
            "red": Font(color="B42318"), "sec": Font(bold=True, size=12, color="0F6E63")}

def _clean(v):
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    return ILLEGAL_CHARACTERS_RE.sub("", v) if isinstance(v, str) else v

def export_list(con, q: dict, out: Path) -> Path:
    import openpyxl
    from openpyxl.utils import get_column_letter as L
    data = list_companies(con, {**q, "limit": 100000}); st = _styles()
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Корхоналар"
    dn = {d["code"]: d["name_uz"] for d in report.districts(con)}
    filt = [STATUS_UZ.get(q.get("status") or "exporters", "")]
    if q.get("district"): filt.append(dn.get(q["district"], q["district"]))
    if q.get("tarmoq"): filt.append(q["tarmoq"])
    if q.get("kind"): filt.append({"sanoat": "саноат", "meva": "мева-сабзавот"}.get(q["kind"], q["kind"]))
    if q.get("q"): filt.append(f"«{q['q']}»")
    ws["A1"] = f"Бухоро вилояти экспортёр корхоналари · {data['year']} йил"; ws["A1"].font = st["title"]
    ws["A2"] = f"{data['today'][8:10]}.{data['today'][5:7]}.{data['today'][:4]} ҳолатига · минг АҚШ доллари · " + " · ".join(filt); ws["A2"].font = st["sub"]
    hdr = ["№", "ИНН", "Корхона номи", "Туман", "Тармоқ", "Йил бошидан", f"{MONTHS_UZ[data['month'] - 1]} ойида", "Охирги экспорт", "ГТД сони",
           "Туман экспорти", "Туманда улуши", "Туманда ўрни", "Очиқ муаммо", "Янги (сана)", "Раҳбар", "Телефон"]
    widths = [5, 13, 40, 18, 22, 14, 13, 12, 8, 14, 13, 12, 9, 12, 24, 16]
    for i, (h, w) in enumerate(zip(hdr, widths), 1):
        c = ws.cell(4, i, h); c.font = st["h"]; c.fill = st["hf"]; c.alignment = st["c"]; c.border = st["b"]; ws.column_dimensions[L(i)].width = w
    ws.row_dimensions[4].height = 32
    r0 = 5
    for n, x in enumerate(data["rows"], 1):
        vals = [n, int(x["inn"]) if x["inn"].isdigit() and len(x["inn"]) <= 15 else x["inn"], x["name"], x["district"], x["tarmoq"], x["ytd"] or None, x["month"] or None,
                (dt.date.fromisoformat(x["last"]) if x["last"] else None), x["gtd"] or None, x["district_ytd"] or None,
                (x["share"] / 100 if x["share"] is not None else None), (f"{x['rank']}/{x['district_n']}" if x["rank"] else None),
                x["issues"] or None, (dt.date.fromisoformat(x["new_date"]) if x["new_date"] else None), x["director"], x["phone"]]
        for i, v in enumerate(vals, 1):
            c = ws.cell(r0 + n - 1, i, _clean(v)); c.border = st["b"]
            if i in (6, 7, 10): c.number_format = "#,##0.0"
            if i in (8, 14): c.number_format = "DD.MM.YYYY"
            if i == 11:
                c.number_format = "0.0%"
                if isinstance(v, (int, float)) and v >= 0.10: c.font = st["bold"]     # 10%+ of its district
            if i == 12: c.alignment = st["c"]
    last = r0 + len(data["rows"]) - 1
    t = last + 1
    ws.cell(t, 3, f"Жами: {len(data['rows'])} та корхона").font = st["bold"]
    for i in (6, 7):
        c = ws.cell(t, i, f"=SUM({L(i)}{r0}:{L(i)}{max(last, r0)})"); c.number_format = "#,##0.0"; c.font = st["bold"]
    c = ws.cell(t, 12, f'=IFERROR(F{t}/K{t},"")'); c.number_format = "0%"; c.font = st["bold"]
    for i in range(1, len(hdr) + 1): ws.cell(t, i).fill = st["tot"]; ws.cell(t, i).border = st["b"]
    ws.freeze_panes = "D5"; ws.auto_filter.ref = f"A4:{L(len(hdr))}{max(last, 4)}"
    ws.page_setup.orientation = "landscape"; ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0; ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = "4:4"
    wb.save(out); return out

def _tree_extras(con, inn: str, y: int, cur_y: int, products: list, inw) -> dict:
    """Years with export, totals per year, product tree, logistics (posts / transport / regime / deal), $/kg vs region, import structure."""
    from . import products as prod
    skip = report.not_bukhara_inns(con)
    years = sorted({r[0] for r in con.execute("SELECT DISTINCT year FROM items WHERE regime='ЭК' AND inn=?", (inn,))} |
                   {int(r[0]) for r in con.execute("SELECT DISTINCT substr(report_date,1,4) FROM gtd_rows WHERE voided=0 AND inn=?", (inn,))} | {cur_y})
    totals = {}
    for yy in years:
        mm = _monthly(con, inn, yy).get(inn)
        totals[yy] = round(sum(mm["m"]), 3) if mm else 0.0
    # logistics — customs base rows only (daily GTD files carry no post / transport)
    def agg(col, label=None):
        out = []
        for r in con.execute(f"""SELECT d.{col} k, sum(i.value) v, count(DISTINCT d.decl_id) g, sum(i.netto) n FROM items i JOIN declarations d ON d.decl_id=i.decl_id
                                 WHERE i.regime='ЭК' AND i.inn=? AND i.year=? GROUP BY k ORDER BY v DESC""", (inn, y)):
            out.append({"code": r["k"] or "—", "value": round(r["v"] or 0, 3), "gtd": r["g"], "netto_t": round(r["n"] or 0, 1)})
        return out
    posts = {r["code"]: r["name"] for r in con.execute("SELECT code, name FROM posts")}
    logistics = {"posts": [{**x, "name": posts.get(x["code"])} for x in agg("post")], "transport": [{**x, "name": TRANSPORT.get(x["code"])} for x in agg("transport")],
                 "proc": [{**x, "name": PROC.get(x["code"])} for x in agg("proc_code")], "deal": [{**x, "name": DEAL.get(x["code"])} for x in agg("deal_code")],
                 "base_only": True}
    # $/kg per HS4: the company vs the region (all Bukhara exporters, same year, same hs4)
    hs4s = [x["hs4"] for x in products if x["hs4"] != "—"]
    reg = {}
    if hs4s:
        for r in con.execute(f"""SELECT hs4, sum(value) v, sum(netto) n, count(DISTINCT inn) c FROM items WHERE regime='ЭК' AND year=? AND kind='sanoat'
                                 AND hs4 IN ({','.join('?' * len(hs4s))}) GROUP BY hs4""", (y, *hs4s)):
            reg[r["hs4"]] = (r["v"] or 0, r["n"] or 0, r["c"])
    for x in products:
        x["usd_kg"] = round(x["value"] / x["netto_t"], 2) if x["netto_t"] else None
        rv = reg.get(x["hs4"])
        x["region_usd_kg"] = round(rv[0] / rv[1], 2) if rv and rv[1] else None
        x["region_companies"] = rv[2] if rv else None
    # import structure (customs base, same year)
    imp_prod = [{"name": r["k"] or "—", "value": round(r["v"] or 0, 3), "netto_t": round(r["n"] or 0, 1)} for r in con.execute(
        """SELECT coalesce(sprav2, tovar2, hs4) k, sum(value) v, sum(netto) n FROM items WHERE regime='ИМ' AND inn=? AND year=? GROUP BY k ORDER BY v DESC LIMIT 10""", (inn, y))]
    return {"years": years, "year_totals": totals, "tree": prod.company_products(con, inn, y).get("items", []), "logistics": logistics, "import_products": imp_prod}

TRANSPORT = {"20": "Темир йўл", "30": "Автомобиль", "40": "Ҳаво", "10": "Денгиз", "50": "Почта", "70": "Қувур", "80": "Дарё", "90": "Ўз юриши"}
PROC = {"10": "Экспорт"}          # other regime / deal codes: names come from the customs classifier once it is loaded (dictionary)
DEAL = {}

def export_passport(con, inn: str, out: Path) -> Path:
    import openpyxl
    from openpyxl.utils import get_column_letter as L
    from openpyxl.chart import BarChart, LineChart, Reference
    p = profile(con, inn); c = p["company"]; k = p["kpi"]; ct = p["contacts"]; st = _styles()
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Паспорт"
    for col, w in zip("ABCDEF", (38, 16, 16, 14, 30, 16)): ws.column_dimensions[col].width = w
    ws["A1"] = c.get("name"); ws["A1"].font = st["title"]; ws.merge_cells("A1:F1")
    d = p["today"]; ws["A2"] = f"Корхона паспорти · ИНН {inn} · {d[8:10]}.{d[5:7]}.{d[:4]} ҳолатига · минг АҚШ доллари"; ws["A2"].font = st["sub"]; ws.merge_cells("A2:F2")
    row = 4
    def sec(title):
        nonlocal row
        ws.cell(row, 1, title).font = st["sec"]; row += 1
    def kv(label, value, fmt=None):
        nonlocal row
        a = ws.cell(row, 1, label); a.font = st["bold"]; a.border = st["b"]
        b = ws.cell(row, 2, _clean(value)); b.border = st["b"]; b.alignment = st["w"]
        if fmt: b.number_format = fmt
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=6); row += 1
    sec("Асосий маълумот")
    status = []
    if c.get("new_date"): status.append(f"янги экспортёр ({c['new_date'][8:10]}.{c['new_date'][5:7]}.{c['new_date'][:4]} да аниқланган)")
    if p["template"]: status.append("номма-номда бор")
    if c.get("in_base"): status.append("божхона базасида бор")
    elif c.get("bukhara") == 1: status.append("Бухоро деб тасдиқланган")
    elif c.get("bukhara") == 0: status.append("Бухоро эмас деб белгиланган")
    if c.get("bukhara") != 0 and (c.get("bukhara_from") or c.get("bukhara_to")):
        _d = lambda v: f"{v[8:10]}.{v[5:7]}.{v[:4]}" if v else ""
        status.append("Бухорода ҳисобга олинади: " + (f"{_d(c['bukhara_from'])} дан " if c.get("bukhara_from") else "") + (f"{_d(c['bukhara_to'])} гача" if c.get("bukhara_to") else ""))
    for lab, val in (("Туман", c.get("district")), ("Тармоқ", c.get("tarmoq")), ("Уюшма", c.get("uyushma")), ("Маҳсулот", c.get("product")),
                     ("Раҳбар", ct.get("director")), ("Телефон", ", ".join(ct.get("phones") or [])), ("Манзил", ct.get("address")),
                     ("Email", ct.get("email")), ("Изоҳ", ct.get("note")), ("Ҳолати", "; ".join(status))):
        kv(lab, val or "—")
    if p.get("persons"):
        row += 1; sec("Алоқадор шахслар")
        for ps in p["persons"]:
            kv(ps["name"] + (f" — {ps['role']}" if ps.get("role") else ""), (", ".join(ps.get("phones") or []) + (f"  ·  {ps['note']}" if ps.get("note") else "")) or "—")
    row += 1; sec("Кўрсаткичлар")
    for lab, val, fmt in (("Йил бошидан экспорт", k["ytd"], "#,##0.0"), (f"{MONTHS_UZ[p['month'] - 1]} ойида", k["month"], "#,##0.0"),
                          ("Охирги экспорт санаси", dt.date.fromisoformat(k["last"]) if k["last"] else "—", "DD.MM.YYYY"), ("ГТД сони", k["gtd"], "0"),
                          ("Туман экспорти (йил бошидан)", k["district_ytd"] or "—", "#,##0.0"),
                          ("Туман экспортидаги улуши", k["share"] / 100 if k["share"] is not None else "—", "0.0%"),
                          ("Туманда ўрни", f"{k['rank']} / {k['district_n']}" if k.get("rank") else "—", None),
                          ("Давлатлар сони", k["countries"], "0"), ("Импорт (йил бошидан, база)", k["import_ytd"], "#,##0.0")):
        kv(lab, val, fmt if not isinstance(val, str) else None)
    if p["signals"]: kv("Сигналлар", "; ".join(s["t"] for s in p["signals"]))
    row += 1; sec("Ойлар кесимида")
    hr = row
    for i, h in enumerate(["Ой", "Туман жами", "Корхона", "Улуши %"], 1):
        cc = ws.cell(row, i, h); cc.font = st["h"]; cc.fill = st["hf"]; cc.alignment = st["c"]; cc.border = st["b"]
    row += 1; first = row
    pm = p["district_months"] or [None] * 12
    for i in range(12):
        ws.cell(row, 1, MONTHS_UZ[i]).border = st["b"]
        a = ws.cell(row, 2, pm[i]); a.number_format = "#,##0.0"; a.border = st["b"]
        b = ws.cell(row, 3, p["months"][i] or None); b.number_format = "#,##0.0"; b.border = st["b"]
        e = ws.cell(row, 4, f'=IF(AND(ISNUMBER(B{row}),B{row}>0,ISNUMBER(C{row})),C{row}/B{row},"")'); e.number_format = "0%"; e.border = st["b"]
        row += 1
    ws.cell(row, 1, "Жами").font = st["bold"]
    for col in (2, 3):
        cc = ws.cell(row, col, f"=SUM({L(col)}{first}:{L(col)}{row - 1})"); cc.number_format = "#,##0.0"; cc.font = st["bold"]
    for i in range(1, 5): ws.cell(row, i).fill = st["tot"]; ws.cell(row, i).border = st["b"]
    ch = BarChart(); ch.type = "col"; ch.height = 7; ch.width = 16; ch.title = "Корхона ва туман экспорти"; ch.legend.position = "b"
    ch.add_data(Reference(ws, min_col=3, min_row=hr, max_row=first + 11), titles_from_data=True); ch.set_categories(Reference(ws, min_col=1, min_row=first, max_row=first + 11))
    if p["district_months"]:
        ln = LineChart(); ln.add_data(Reference(ws, min_col=2, min_row=hr, max_row=first + 11), titles_from_data=True); ch += ln
    ws.add_chart(ch, f"F{hr}")
    row += 2; sec("Маҳсулотлар (ТН ВЭД 4 белги)")
    for i, h in enumerate(["Маҳсулот", "Код", "Қиймати", "Нетто, т", "Улуши"], 1):
        cc = ws.cell(row, i, h); cc.font = st["h"]; cc.fill = st["hf"]; cc.border = st["b"]
    row += 1; tot = sum(x["value"] for x in p["products"]) or 1
    for x in p["products"][:12]:
        for i, v in enumerate([x["name"], x["hs4"], x["value"], x["netto_t"], x["value"] / tot], 1):
            cc = ws.cell(row, i, _clean(v)); cc.border = st["b"]; cc.number_format = {3: "#,##0.0", 4: "#,##0.0", 5: "0.0%"}.get(i, "General")
        row += 1
    row += 1; sec("Давлатлар")
    for i, h in enumerate(["Давлат", "Қиймати", "Улуши"], 1):
        cc = ws.cell(row, i, h); cc.font = st["h"]; cc.fill = st["hf"]; cc.border = st["b"]
    row += 1; tot = sum(x["value"] for x in p["countries"]) or 1
    for x in p["countries"][:12]:
        for i, v in enumerate([x["country"], x["value"], x["value"] / tot], 1):
            cc = ws.cell(row, i, _clean(v)); cc.border = st["b"]; cc.number_format = {2: "#,##0.0", 3: "0.0%"}.get(i, "General")
        row += 1
    opened = [i for i in p["issues"] if i["status"] == "open"]
    row += 1; sec(f"Очиқ муаммо ва вазифалар ({len(opened)})")
    if opened:
        for i, h in enumerate(["Мазмуни", "Тури", "Масъул", "Муддат", "Батафсил"], 1):
            cc = ws.cell(row, i, h); cc.font = st["h"]; cc.fill = st["hf"]; cc.border = st["b"]
        row += 1
        for it in opened:
            for i, v in enumerate([it["title"], KIND_UZ.get(it["kind"]), it["responsible"], it["due_date"], it["text"]], 1):
                cc = ws.cell(row, i, _clean(v)); cc.border = st["b"]; cc.alignment = st["w"]
                if i == 4 and it["overdue"]: cc.font = st["red"]
            row += 1
    else:
        ws.cell(row, 1, "йўқ"); row += 1
    if p["docs"]:
        row += 1; sec("Ҳужжатлар")
        for dd in p["docs"]:
            ws.cell(row, 1, _clean(dd["filename"])); ws.cell(row, 2, dd["doc_date"] or dd["uploaded_at"][:10]); ws.cell(row, 3, _clean(dd["note"])); row += 1
    ws.page_setup.orientation = "portrait"; ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0; ws.sheet_properties.pageSetUpPr.fitToPage = True
    wg = wb.create_sheet("ГТД тарихи")
    hdr = ["Сана", "ГТД", "Давлат", "Товар сони", "Нетто, т", "Қиймати", "Маҳсулотлар", "Манба"]
    for i, (h, w) in enumerate(zip(hdr, (11, 30, 16, 10, 10, 12, 60, 8)), 1):
        cc = wg.cell(1, i, h); cc.font = st["h"]; cc.fill = st["hf"]; wg.column_dimensions[L(i)].width = w
    for n, x in enumerate(p["history"], 2):
        for i, v in enumerate([dt.date.fromisoformat(x["date"]) if x["date"] else None, x["gtd"], x["country"], x["items"], x["netto_t"], x["value"], x["products"], "база" if x["src"] == "baza" else "ГТД"], 1):
            cc = wg.cell(n, i, _clean(v)); cc.number_format = {1: "DD.MM.YYYY", 5: "#,##0.00", 6: "#,##0.00"}.get(i, "General")
    wg.freeze_panes = "A2"
    wb.save(out); return out

# ------------------------------------------------------------------ korxona harakati (yildan yilga)
def _totals_upto(con, y: int, upto: str, sanoat_only: bool = False) -> dict:
    """{inn: value} — export of year y up to date `upto` (customs base items + daily GTD after the base), dashboard rules
    («Бухоро эмас» never, Bukhara period by date, memo/bnpz kinds never, other regions' meva never).
    sanoat_only=True: korxona meva qatorlarisiz (vilyoat jamisi uchun — meva u yerda faqat karantin qoidasi bilan)."""
    from .daily import is_bukhara
    skip = report.not_bukhara_inns(con); win = report.bukhara_windows(con)
    through = db.get_setting(con, "opening_through_date") or ""
    meva_inns = {i for (i,) in con.execute("SELECT inn FROM template_inns WHERE category='meva'")} or \
                {i for (i,) in con.execute("SELECT inn FROM companies WHERE kind='meva' AND source='nomma-nom'")}
    comps = {r["inn"]: dict(r) for r in con.execute("SELECT inn, in_base, bukhara, source, bukhara_from, bukhara_to FROM companies")}
    kinds_i = "('sanoat')" if sanoat_only else "('sanoat','meva')"; kinds_g = "('sanoat')" if sanoat_only else "('sanoat','meva','meva_x')"
    out = defaultdict(float)
    for r in con.execute(f"SELECT inn, rdate, kind, value FROM items WHERE regime='ЭК' AND year=? AND rdate<=? AND kind IN {kinds_i}", (y, upto)):
        if r["inn"] in skip or not report.in_window(win, r["inn"], r["rdate"]): continue
        out[r["inn"]] += r["value"] or 0
    if through.startswith(str(y)):
        for r in con.execute(f"SELECT inn, report_date d, kind, stat_usd FROM gtd_rows WHERE voided=0 AND kind IN {kinds_g} AND report_date>? AND report_date<=?", (through, upto)):
            if r["inn"] in skip or not report.in_window(win, r["inn"], r["d"]): continue
            if r["kind"] == "meva" and not is_bukhara(comps.get(r["inn"]), r["inn"], meva_inns, r["d"]): continue
            out[r["inn"]] += r["stat_usd"] or 0
    return out

def movement(con, q: dict) -> dict:
    """Yildan yilga korxona harakati: yangi (o'tgan yil eksporti yo'q), to'xtagan / hali yo'q (o'tgan yil bor, bu yil yo'q),
    davom etayotganlar (o'sgan / kamaygan — o'tgan yil xuddi shu davrga nisbatan)."""
    cur_y = year(con); y = int(q.get("year") or cur_y); past = y != cur_y
    today = _today(con) if not past else f"{y}-12-31"
    upto = today if today.startswith(str(y)) else f"{y}-12-31"
    same = f"{y - 1}{upto[4:]}"
    if same.endswith("02-29"): same = same[:-2] + "28"
    cur = _totals_upto(con, y, upto); prev_full = _totals_upto(con, y - 1, f"{y - 1}-12-31"); prev_same = _totals_upto(con, y - 1, same)
    comps = {r["inn"]: dict(r) for r in con.execute("SELECT inn, name, district_code, tarmoq, excluded, new_date FROM companies")}
    dn = {d["code"]: d["name_uz"] for d in report.districts(con)}
    dists = {x.strip() for x in str(q.get("district") or "").split(",") if x.strip()}
    last = {r["inn"]: r["l"] for r in con.execute("SELECT inn, max(rdate) l FROM items WHERE regime='ЭК' AND year=? GROUP BY inn", (y,))}
    if not past:
        for r in con.execute("SELECT inn, max(report_date) l FROM gtd_rows WHERE voided=0 AND kind IN ('sanoat','meva','meva_x') GROUP BY inn"):
            last[r["inn"]] = max(filter(None, [last.get(r["inn"]), r["l"]]))
    lastp = {r["inn"]: r["l"] for r in con.execute("SELECT inn, max(rdate) l FROM items WHERE regime='ЭК' AND year=? GROUP BY inn", (y - 1,))}
    rows = {"new": [], "stopped": [], "up": [], "down": []}
    for inn in set(cur) | set(prev_full):
        c = comps.get(inn) or {}
        if c.get("excluded"): continue
        if dists and c.get("district_code") not in dists: continue
        cv, pf, ps = round(cur.get(inn, 0.0), 3), round(prev_full.get(inn, 0.0), 3), round(prev_same.get(inn, 0.0), 3)
        if cv <= 0 and pf <= 0: continue
        r = {"inn": inn, "name": c.get("name") or inn, "district": dn.get(c.get("district_code")), "district_code": c.get("district_code"), "tarmoq": c.get("tarmoq"),
             "cur": cv, "prev_full": pf, "prev_same": ps, "growth": round((cv / ps - 1) * 100, 1) if ps > 0 and cv > 0 else None,
             "diff": round(cv - ps, 3), "last": last.get(inn), "last_prev": lastp.get(inn), "new_date": c.get("new_date")}
        if cv > 0 and pf <= 0: rows["new"].append(r)
        elif cv <= 0: rows["stopped"].append(r)
        elif cv >= ps: rows["up"].append(r)
        else: rows["down"].append(r)
    rows["new"].sort(key=lambda r: -r["cur"]); rows["stopped"].sort(key=lambda r: -r["prev_full"])
    rows["up"].sort(key=lambda r: -r["diff"]); rows["down"].sort(key=lambda r: r["diff"])
    def tot(lst, k): return round(sum(r[k] for r in lst), 3)
    years = sorted({r[0] for r in con.execute("SELECT DISTINCT year FROM items WHERE regime='ЭК'")} | {cur_y})
    # vilyoat / tuman jamisi Dashboard qoidasi bilan: sanoat (excluded'larsiz) + karantin mevasi; ўтган йил — faqat Sozlamalardagi baza
    from . import products
    excl = {i for i, c in comps.items() if c.get("excluded")}
    san = _totals_upto(con, y, upto, sanoat_only=True)
    region_total = sum(v for i, v in san.items() if i not in excl and (not dists or (comps.get(i) or {}).get("district_code") in dists))
    region_total += sum(a["total"] for a in products.karantin_period(con, y, f"{y}-01-01", upto, dists or None).values())
    hcode = next(iter(dists)) if len(dists) == 1 else "1706"
    prev_same_set = products.prev_settings(con, hcode, "all", f"{y}-01-01", upto); prev_full_set = products.prev_full_settings(con, hcode, "all", y)
    return {"year": y, "past": past, "upto": upto, "same": same, "years": [yy for yy in years if yy - 1 in years or yy == cur_y],
            "kpi": {"new": {"n": len(rows["new"]), "sum": tot(rows["new"], "cur")},
                    "stopped": {"n": len(rows["stopped"]), "sum": tot(rows["stopped"], "prev_full"), "sum_same": tot(rows["stopped"], "prev_same")},
                    "up": {"n": len(rows["up"]), "sum": tot(rows["up"], "cur"), "diff": tot(rows["up"], "diff")},
                    "down": {"n": len(rows["down"]), "sum": tot(rows["down"], "cur"), "diff": tot(rows["down"], "diff")},
                    "total": round(region_total, 3), "prev_same": round(prev_same_set, 3), "prev_full": round(prev_full_set, 3), "prev_source": "settings",
                    "total_companies": round(sum(cur.values()), 3), "prev_same_customs": round(sum(prev_same.values()), 3), "prev_full_customs": round(sum(prev_full.values()), 3),
                    "rows_prev_source": "customs", "meva_rule": "karantin",
                    "exporters": sum(1 for v in cur.values() if v > 0), "exporters_prev": sum(1 for v in prev_full.values() if v > 0)},
            "rows": rows, "districts": [{"code": c, "name": n} for c, n in sorted(dn.items(), key=lambda x: x[1])]}

def export_movement(con, q: dict, out):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter as L
    d = movement(con, q)
    thin = Side(style="thin", color="D6DBD8"); bd = Border(thin, thin, thin, thin)
    H = Font(bold=True, color="FFFFFF", size=10); HF = PatternFill("solid", fgColor="0F6E63")
    wb = openpyxl.Workbook(); first = True
    titles = {"new": "Янги экспортёрлар", "stopped": "Тўхтаган / ҳали йўқ", "up": "Ўсганлар", "down": "Камайганлар"}
    for key, title in titles.items():
        ws = wb.active if first else wb.create_sheet(); first = False; ws.title = re.sub(r'[\\/*?:\[\]]', "-", title)[:31]
        ws["A1"] = f"{title} — {d['year']} йил ({d['upto'][8:10]}.{d['upto'][5:7]} гача) vs {d['year'] - 1} · минг АҚШ доллари"; ws["A1"].font = Font(bold=True, size=13)
        hdr = ["№", "ИНН", "Корхона", "Туман", "Тармоқ", f"{d['year']}", f"{d['year'] - 1} шу давр", f"{d['year'] - 1} йил жами", "Ўсиш %", "Фарқ", "Охирги экспорт"]
        for i, (h, w) in enumerate(zip(hdr, [5, 13, 42, 18, 24, 13, 15, 15, 9, 12, 13]), 1):
            c = ws.cell(3, i, h); c.font = H; c.fill = HF; c.alignment = Alignment(horizontal="center"); c.border = bd; ws.column_dimensions[L(i)].width = w
        for n, r in enumerate(d["rows"][key], 1):
            for i, v in enumerate([n, r["inn"], r["name"], r["district"], r["tarmoq"], r["cur"], r["prev_same"], r["prev_full"], (r["growth"] or 0) / 100 if r["growth"] is not None else None, r["diff"], r["last"] or r["last_prev"]], 1):
                c = ws.cell(3 + n, i, v); c.border = bd
                if i in (6, 7, 8, 10): c.number_format = "#,##0.0"
                if i == 9: c.number_format = "0%"
        ws.freeze_panes = "A4"
    wb.save(out); return out
