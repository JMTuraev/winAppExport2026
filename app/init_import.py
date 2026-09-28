"""One-time initialisation:
- registry (INN -> district) from the monthly customs base,
- companies (all номманом columns) + monthly opening balances from the daily workbook,
- prognoz + meva-sabzavot (karantin) opening from 'СВОД (карантин) …'.
"""
from __future__ import annotations
import json, re, sys, zipfile, shutil
from pathlib import Path
from . import db
from .xl import read_sheet, Header, inn_str, num, _norm, sheet_names, find_sheet

MONTHS_UZ = ["январ", "феврал", "март", "апрел", "май", "июн", "июл", "август", "сентябр", "октябр", "ноябр", "декабр"]
KARANTIN_SVOD = "СВОД (карантин)"      # matched by letters only, the plan number in the name is ignored
GOVERNOR_SVOD = "СВОД млн"              # «СВОД 450 млн» — viloyat hokimi svodi (БНПЗ shu yerga qo'shiladi)
EXT_RX = re.compile(r"\[\d+\]")

def col_letter(i: int) -> str:  # 0-based
    s = ""; i += 1
    while i: i, r = divmod(i - 1, 26); s = chr(65 + r) + s
    return s

# ---------------------------------------------------------------- номманом
def import_nomma_nom(con, path, year, through_date, with_balances=True):
    exclude = set(db.reference().get("exclude_inns", {}))
    rows = read_sheet(path, "номманом")
    h = Header(rows, ["ИНН", "Корхона номи", "Ҳудуди"])
    hdr = rows[h.row_idx]
    c_no, c_inn, c_name, c_hud = h.col("№"), h.col("ИНН"), h.col("Корхона номи"), h.col("Ҳудуди")
    c_tot = h.col("Экспорти ҳажми жами", "жами"); c_tar = h.col("Тармоқ"); c_prod = h.col("Маҳсулоти"); c_day = h.col("1 кунда")
    mcols = {}
    for i, v in enumerate(hdr):
        s = _norm(v)
        for mi, m in enumerate(MONTHS_UZ):
            if m in s and "ойида" in s: mcols[mi + 1] = i
    if len(mcols) < 2: raise ValueError("номманом: oy ustunlari topilmadi")
    cur_month = int(through_date[5:7])
    if with_balances and cur_month not in mcols: raise ValueError(f"номманом: joriy oy ({cur_month}) ustuni topilmadi")
    dmap = {r["name_uz"]: r["code"] for r in con.execute("SELECT code,name_uz FROM districts WHERE length(code)=7")}
    cur_district = None; order = 0; in_memo = False
    companies, balances, day_amounts = [], [], []
    for r in rows[h.row_idx + 1:]:
        inn = inn_str(r[c_inn]); name = r[c_name].strip() if isinstance(r[c_name], str) else r[c_name]
        if not inn and isinstance(name, str) and name.upper() == "ЖАМИ":
            in_memo = True; continue
        if not inn and name in dmap and isinstance(r[c_no], (int, float)) and not in_memo:
            cur_district = dmap[name]; order += 1
            con.execute("UPDATE districts SET order_no=? WHERE code=?", (order, cur_district)); continue
        if not inn or not name or inn in exclude: continue
        extras = {col_letter(i): v for i, v in enumerate(r) if i > c_tar and i != c_prod and v not in (None, "")}
        tail = [v for v in r[c_tar + 1:] if isinstance(v, str)]
        kind = "meva" if any("мева" in v.lower() for v in tail) else "sanoat"
        rus = next((v for v in tail if re.search(r"город|район", v, re.I)), None)
        uyu = next((v for v in tail if re.match(r"\d\d_", v)), None)
        dfull = next((v for v in tail if v.strip() in dmap), None)
        dcode = dmap.get(dfull.strip()) if dfull else cur_district
        if in_memo:
            kind = "memo"
            hud = str(r[c_hud] or "").strip()
            dcode = next((c for n, c in dmap.items() if hud and n.startswith(hud[:6])), dcode)
        companies.append((inn, name, dcode, r[c_hud], r[c_tar], rus, uyu, dfull, kind, r[c_prod], json.dumps(extras, ensure_ascii=False, default=str), 1 if in_memo else 0))
        if in_memo:
            if num(r[c_tot]): balances.append((inn, "memo", year, 0, round(num(r[c_tot]), 6), through_date))
            continue
        for m, ci in mcols.items():
            amt = num(r[ci])
            if amt: balances.append((inn, kind, year, m, round(amt, 6), through_date if m == cur_month else None))
        if num(r[c_day]): day_amounts.append((inn, kind, num(r[c_day])))
    with con:
        for c in companies:
            ex = con.execute("SELECT source, kind FROM companies WHERE inn=?", (c[0],)).fetchone()
            if ex and ex["source"] == "nomma-nom":
                # same INN listed twice (e.g. sanoat + meva rows): keep the first row's attributes
                continue
            con.execute("""INSERT INTO companies(inn,name,district_code,hudud,tarmoq,rus_district,uyushma,district_full,kind,product,extras,excluded,source,confirmed)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,'nomma-nom',1)
                ON CONFLICT(inn) DO UPDATE SET name=excluded.name,district_code=excluded.district_code,hudud=excluded.hudud,tarmoq=excluded.tarmoq,
                rus_district=excluded.rus_district,uyushma=excluded.uyushma,district_full=excluded.district_full,kind=excluded.kind,product=excluded.product,
                extras=excluded.extras,excluded=excluded.excluded,source='nomma-nom',updated_at=datetime('now','localtime')""", c)
        if with_balances:
            con.execute("DELETE FROM opening_balances WHERE year=?", (year,))
            con.executemany("INSERT INTO opening_balances(inn,kind,year,month,amount,through_date,source) VALUES(?,?,?,?,?,?,'nomma-nom')", balances)
            db.set_setting(con, "opening_through_date", through_date)
            db.set_setting(con, "opening_source", "workbook")
            db.set_setting(con, "opening_last_day", json.dumps(day_amounts, ensure_ascii=False))
            db.set_setting(con, "year", year)
        db.log(con, "import_nomma_nom", file=str(path), companies=len(companies), balances=len(balances))
    return {"companies": len(companies), "balances": len(balances) if with_balances else 0, "months": sorted(mcols)}

# ---------------------------------------------------------------- СВОД (карантин): prognoz + meva opening
def _svod_layout(rows):
    """Locate columns of the karantin svod sheet by header text."""
    hi = next(i for i, r in enumerate(rows[:8]) if any(isinstance(v, str) and "прогнози" in v.lower() for v in r))
    top = [_norm(v) for v in rows[hi]]
    sub_i = next(i for i in range(hi + 1, hi + 6) if sum(1 for v in rows[i] if isinstance(v, str) and _norm(v).startswith("амалда")) >= 2)
    sub = [_norm(v) for v in rows[sub_i]]
    def top_col(rx):
        return next(i for i, v in enumerate(top) if re.search(rx, v))
    c_period = top_col(r"^жами январ"); c_month = top_col(r"^шундан .* ойида"); 
    def under(start, label):
        return next(i for i in range(start, len(sub)) if sub[i].startswith(label))
    L = {"name": 1, "district": 2, "year_plan": top_col(r"прогнози жами"), "m9_plan": top_col(r"9 ойлик"),
         "period_plan": under(c_period, "прогноз"), "period_fact": under(c_period, "амалда"),
         "month_plan": under(c_month, "прогноз"), "month_fact": under(c_month, "амалда"), "day_fact": under(c_month, "1 кунда"),
         "prev_base": top_col(r"^\d{4} йил .*ҳолатида"), "data_row": sub_i + 1}
    m = re.search(r"(\d{4}) йил (\d+) (\w+) ҳолатида", top[L["prev_base"]])
    L["prev_base_label"] = rows[hi][L["prev_base"]]
    L["month_label"] = str(rows[hi][c_month] or "")
    return L

MONTH_STEMS = ["январ", "феврал", "март", "апрел", "май", "июн", "июл", "август", "сентябр", "октябр", "ноябр", "декабр"]
MONTH_NAMES = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]

def import_svod_karantin(con, path, year, through_date, sheet=KARANTIN_SVOD, meva_align_month=None, meva_strict=True):
    """prognoz + meva opening. meva_align_month: month of the customs base; the workbook's meva YTD is cut to the end of that month.
    meva_strict=False: a workbook of a later month only refreshes prognoz; the meva opening stays as it is."""
    real = find_sheet(sheet_names(path), sheet)
    if not real: raise ValueError(f"Jadvalda «{sheet} …» varag'i topilmadi")
    sheet = real
    rows = read_sheet(path, sheet)
    L = _svod_layout(rows)
    wb_month = next((i + 1 for i, st in enumerate(MONTH_STEMS) if st in _norm(L.get("month_label", ""))), None)
    meva_skipped = False
    if meva_align_month:
        if wb_month not in (meva_align_month, meva_align_month + 1) and not meva_strict:
            meva_skipped = True
        elif wb_month not in (meva_align_month, meva_align_month + 1):
            raise ValueError(f"Kunlik jadval «{MONTH_NAMES[wb_month-1] if wb_month else '?'}» oyi holatida, bojxona bazasi esa {MONTH_NAMES[meva_align_month-1]} oyi oxirigacha. "
                             f"Meva-sabzavotni moslash uchun {MONTH_NAMES[meva_align_month-1]} yoki {MONTH_NAMES[meva_align_month % 12]} oyidagi jadvalni yuklang.")
    # prev-year base day count: read from the /273*(...) formula if the source is xlsx, else default 273
    base_days = 273
    dmap = {r["name_uz"].strip(): r["code"] for r in con.execute("SELECT code,name_uz FROM districts WHERE length(code)=7")}
    prog, kar = [], []
    cur = None
    con.execute("INSERT OR IGNORE INTO districts(code,name_uz,order_no) VALUES('1706','Бухоро вилояти',0)")
    for r in rows[L["data_row"]:]:
        name = str(r[L["name"]] or "").strip()
        if not name: continue
        dname = str(r[L["district"]] or "").strip()
        low = name.lower()
        if cur is None and low.endswith("жами"):
            kind = "all" if "вилоят" in low else ("sanoat" if low.startswith("саноат") else ("meva" if low.startswith("мева") else None))
            if kind:
                prog.append(("1706", year, kind, num(r[L["year_plan"]]), num(r[L["m9_plan"]]), num(r[L["period_plan"]]), num(r[L["month_plan"]]), num(r[L["prev_base"]]), base_days))
            continue
        if name in dmap: cur = dmap[name]; kind = "all"
        elif cur and dmap.get(dname) == cur and name.lower().startswith("саноат"): kind = "sanoat"
        elif cur and dmap.get(dname) == cur and name.lower().startswith("мева"): kind = "meva"
        else: continue
        prog.append((cur, year, kind, num(r[L["year_plan"]]), num(r[L["m9_plan"]]), num(r[L["period_plan"]]), num(r[L["month_plan"]]), num(r[L["prev_base"]]), base_days))
        if kind == "meva" and not meva_skipped:
            ytd, mon = num(r[L["period_fact"]]), num(r[L["month_fact"]])
            if meva_align_month and wb_month == meva_align_month + 1:
                ytd, mon = ytd - mon, 0.0          # drop the workbook's current (next) month — it comes from daily GTD
            kar.append((cur, year, ytd, meva_align_month or int(through_date[5:7]), mon, through_date, 0.0 if meva_align_month else num(r[L["day_fact"]])))
    with con:
        con.executemany("""INSERT INTO prognoz(district_code,year,kind,year_plan,m9_plan,period_plan,cur_month_plan,prev_year_base,prev_year_base_days) VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(district_code,year,kind) DO UPDATE SET year_plan=excluded.year_plan,m9_plan=excluded.m9_plan,period_plan=excluded.period_plan,
            cur_month_plan=excluded.cur_month_plan,prev_year_base=excluded.prev_year_base,prev_year_base_days=excluded.prev_year_base_days""", prog)
        con.executemany("""INSERT INTO karantin_opening(district_code,year,ytd,month,month_amt,through_date) VALUES(?,?,?,?,?,?)
            ON CONFLICT(district_code,year) DO UPDATE SET ytd=excluded.ytd,month=excluded.month,month_amt=excluded.month_amt,through_date=excluded.through_date""", [k[:6] for k in kar])
        if not meva_skipped:
            db.set_setting(con, "karantin_last_day", json.dumps({k[0]: k[6] for k in kar if k[6]}))
            if meva_align_month: db.set_setting(con, "meva_source", f"workbook:{Path(path).name}")
        db.set_setting(con, "prev_year_base_label", str(L["prev_base_label"]).replace("\n", " "))
        db.set_setting(con, "karantin_sheet", sheet)
        db.log(con, "import_svod_karantin", file=Path(path).name, sheet=sheet, prognoz=len(prog), karantin=len(kar))
    return {"prognoz": len(prog), "karantin": len(kar), "meva_ytd": round(sum(k[2] for k in kar), 3), "workbook_month": wb_month, "sheet": sheet, "meva_skipped": meva_skipped,
            "meva_by_district": [{"code": k[0], "ytd": round(k[2], 3)} for k in kar]}

def build_tnved_map(con):
    """Learn HS code -> (tarmoq, uyushma) from номманом companies and their export structure in the customs base."""
    votes = {}
    comps = {r["inn"]: r for r in con.execute("SELECT inn, tarmoq, uyushma FROM companies WHERE source='nomma-nom' AND tarmoq IS NOT NULL AND kind='sanoat'")}
    rows = [{"tarmoq": comps[i]["tarmoq"], "uyushma": comps[i]["uyushma"], "hs4": h, "amount": a} for i, h, a in db.inn_hs4(con) if i in comps]
    for r in rows:
        w = max(r["amount"], 0.001)
        for code in (r["hs4"], r["hs4"][:2]):
            v = votes.setdefault(code, {})
            key = (r["tarmoq"].strip(), r["uyushma"])
            v[key] = v.get(key, 0) + w
    with con:
        con.execute("DELETE FROM tnved_map")
        for code, v in votes.items():
            (tar, uy), w = max(v.items(), key=lambda x: x[1])
            if uy is None:  # take the most common uyushma for this tarmoq
                uy = next((k[1] for k, _ in sorted(v.items(), key=lambda x: -x[1]) if k[0] == tar and k[1]), None)
            con.execute("INSERT INTO tnved_map(code,tarmoq,uyushma,votes) VALUES(?,?,?,?)", (code, tar, uy, w))
        # companies known only from the customs base: tarmoq/uyushma by their main HS code
        filled = 0
        main_hs = {}
        for i, h, a in db.inn_hs4(con):
            if a > main_hs.get(i, ("", -1))[1]: main_hs[i] = (h, a)
        for r in con.execute("SELECT inn FROM companies WHERE source='baza' AND tarmoq IS NULL").fetchall():
            r = {"inn": r["inn"], "hs4": main_hs.get(r["inn"], (None,))[0]}
            if not r["hs4"]: continue
            m = con.execute("SELECT tarmoq, uyushma FROM tnved_map WHERE code IN (?,?) ORDER BY length(code) DESC LIMIT 1", (r["hs4"], r["hs4"][:2])).fetchone()
            if m:
                con.execute("UPDATE companies SET tarmoq=?, uyushma=? WHERE inn=?", (m["tarmoq"], m["uyushma"], r["inn"])); filled += 1
    return {"codes": len(votes), "baza_companies_filled": filled}
