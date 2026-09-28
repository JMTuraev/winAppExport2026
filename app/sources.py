"""Opening data sources.

1) Monthly customs base ("SQL Hokimyat baza N oylik"): INN registry + sanoat opening balances (year start .. last release date)
   - all regimes of 'ЭК' count as export; month = «Расмийлаштирилган сана»
   - БНПЗ (reference.exclude_inns) is dropped entirely
   - meva-sabzavot goods (товар1 «Мева-сабзавот…», fallback HS 07/08) are NOT taken: meva is collected daily by the karantin rule
2) Daily workbook ("… йил экспорт.xlsx"): prognoz, meva-sabzavot opening (karantin svod), номманом company attributes, Excel template.
"""
from __future__ import annotations
import json, datetime as dt
from pathlib import Path
from collections import defaultdict
from . import db, init_import
from .xl import read_sheet, Header, inn_str, num, _norm

REGION = "1706"   # Buxoro viloyati

def _is_meva(tovar1, hs):
    t = str(tovar1 or "").lower()
    if t: return "мева" in t
    return str(hs or "")[:2] in ("07", "08")

def clean_name(v) -> str:
    """Customs exports write «(null)» for empty cells — treat it as empty."""
    t = str(v).strip() if v is not None else ""
    return "" if t.lower() in ("", "(null)", "null", "none") else t

def _base_sheet(path) -> str:
    """The customs base sheet: «База» (monthly file) or «база 2024-2025» (yearly file: both regimes, both years).
    A yearly file also has «база экспорт …» / «… имп» cuts — the full one is taken."""
    from .xl import sheet_names
    names = sheet_names(path)
    low = {n: _norm(n) for n in names}
    for n, l in low.items():
        if l == "база": return n
    full = [n for n, l in low.items() if l.startswith("база") and "экспорт" not in l and "имп" not in l]
    if full: return full[0]
    any_ = [n for n, l in low.items() if l.startswith("база")]
    if any_: return any_[0]
    raise ValueError("Faylda «База» varag'i topilmadi — bu bojxona bazasi emas.")

def _s(v):
    """Cell -> stripped text or None («(null)» is empty)."""
    if v is None: return None
    t = str(v).strip()
    return None if t.lower() in ("", "(null)", "null", "none", "nan") else t

def import_customs_base(con, path) -> dict:
    """Customs base (monthly «SQL Hokimyat baza N oylik» or yearly «… 12 oy YYYY») -> the INN tree.

    Every row of the file goes to declarations/items (both regimes). A year the file carries in full (12 months, the
    yearly «12 oy» file) is wiped and reloaded as a whole; a partial year is replaced month by month, months the file
    does not contain are kept (a monthly 2026 file carries Jan–Aug 2025 too; Sep–Dec 2025 from the yearly file stay).
    Columns are found by header name (Режим = ЭК/ИМ, Расмийлаштирилган сана → year/month, стат. стоимость 1000$ = value).
    The result carries `verify`: file totals vs the tree after the import, per year.
    Registry (companies) and dictionaries (hs_codes, countries, unions, posts) are updated from all rows.
    Opening balances / settings («yil boshidan sanoat») change only when the file's last year is the site's year or newer —
    an older yearly file (2025 for the 2026 site) is history for comparisons and touches nothing else."""
    k = _sheet_kind(path)
    if k != "baza": raise ValueError(WRONG_FILE[k] if k in ("gtd", "workbook") else "Faylda «База» varag'i topilmadi — bu bojxona oylik bazasi emas.")
    ref = db.reference(); exclude = set(ref.get("exclude_inns", {})); memo = set(ref.get("memo_inns", {}))
    rows = read_sheet(path, _base_sheet(path))
    h = Header(rows, ["ИНН", "Туман коди", "Режим"])
    col = lambda *n, req=True: h.col(*n, required=req)
    c_inn, c_dc, c_dn, c_reg = col("ИНН"), col("Туман коди"), col("туман номи"), col("Режим")
    c_short = col("Ташкилот киска номи", req=False); c_full = col("Ташкилот номи", req=False)
    if c_short is None and c_full is None: raise ValueError("Bazada «Ташкилот номи» ustuni topilmadi")
    c_t1 = col("товар1", req=False); c_hs = col("Код ТН ВЭД", req=False)
    c_val = col("стат. стоимость 1000$"); c_rdate = col("Расмийлаштирилган сана")
    c_post, c_gdate, c_gnum, c_item = col("Пост"), col("дата"), col("номер ГТД"), col("товар №")
    c_t2 = col("товар2", req=False); c_cn = col("страна отправлениеи назначение", "торгушая страна", req=False); c_net = col("Вес нетто тн", req=False)
    c_decl, c_cmdt = col("DECL_ID", req=False), col("CMDT_ID", req=False)
    c_proc, c_pnd, c_deal, c_g25 = col("Коди", req=False), col("ПНД", req=False), col("24-гр", req=False), col("G25", req=False)
    c_sp1, c_sp2, c_unit = col("справ товар 1", req=False), col("справ товар 2", req=False), col("ед. Из", req=False)
    c_qty, c_kg = col("количество", req=False), col("Вес нетто кг", req=False)
    c_inv, c_rusd, c_rcur = col("Фактурная стоимость", req=False), col("курс доллар", req=False), col("курс валют", req=False)
    c_tc, c_orig, c_need = col("торгушая страна", req=False), col("страна произхождние назначение", req=False), col("Нужд", req=False)
    c_ucode, c_uname, c_uflag = col("тармок коди", req=False), col("тармоқ номи", "тармок номи", req=False), col("тармок", req=False)
    c_cheg, c_evr, c_sng = col("CHEGARA", req=False), col("EVRAZES", req=False), col("SNG", req=False)
    g = lambda r, c: (_s(r[c]) if c is not None else None)
    body = [r for r in rows[h.row_idx + 1:] if r[c_rdate] and inn_str(r[c_inn])]
    ek = [r for r in body if str(r[c_reg] or "").strip().upper().startswith("ЭК")]
    if not ek: raise ValueError("Bazada eksport (ЭК) qatorlari topilmadi")
    through = max(str(r[c_rdate])[:10] for r in ek)
    year = int(through[:4])
    # the file replaces exactly the year-months it contains (a monthly 2026 file also carries January–August 2025 —
    # those months are refreshed, September–December 2025 from the yearly file stay untouched)
    parts = sorted({(int(str(r[c_rdate])[:4]), int(str(r[c_rdate])[5:7])) for r in body})
    years = sorted({y for y, _ in parts})
    # a year the file carries in full (all 12 months) is wiped as a whole — every old row of that year, whatever its
    # source or month, goes; a partial year (Jan–Aug 2025 inside a 2026 monthly file) is replaced month by month
    full_years = [y for y in years if len({m for yy, m in parts if yy == y}) == 12]
    month_parts = [(y, m) for y, m in parts if y not in full_years]
    cur_year = int(db.get_setting(con, "year") or 0)
    operational = year >= cur_year          # this file sets the site's «yil boshidan» state; older files are history only
    old_through = db.get_setting(con, "opening_through_date")
    if operational and old_through and db.get_setting(con, "opening_source") == "customs" and through < old_through:
        raise ValueError(f"Bu bojxona bazasi eski: {through[8:10]}.{through[5:7]}.{through[:4]} gacha, saytdagi baza esa {old_through[8:10]}.{old_through[5:7]}.{old_through[:4]} gacha. Eski baza yuklanmaydi.")
    # ---- registry (all rows, import and export) + dictionaries
    dists, seen = {}, {}
    hs_dict, countries, unions, posts = {}, {}, {}, set()
    for r in body:
        inn = inn_str(r[c_inn])
        dc = str(r[c_dc] or "").strip(); dn = str(r[c_dn] or "").strip()
        if dc and dn: dists[dc] = dn
        # individuals (Ж/ш, 14-digit PINFL) have «(null)» in the short-name column — fall back to the full name
        name = clean_name(r[c_short] if c_short is not None else None) or clean_name(r[c_full] if c_full is not None else None) or ""
        cur = seen.setdefault(inn, {"name": name, "district_code": dc, "product": r[c_t1] if c_t1 is not None else None,
                                    "full_name": clean_name(r[c_full] if c_full is not None else None) or None,
                                    "union_code": g(r, c_ucode), "union_name": g(r, c_uname), "base_kind": g(r, c_uflag)})
        if not cur["name"] and name: cur["name"] = name
        if not cur["full_name"] and c_full is not None: cur["full_name"] = clean_name(r[c_full]) or None
        hs = g(r, c_hs)
        if hs and hs not in hs_dict: hs_dict[hs] = (g(r, c_t1), g(r, c_t2), g(r, c_sp1), g(r, c_sp2), g(r, c_unit))
        cn = g(r, c_cn)
        if cn and cn not in countries:
            yes = lambda c: (1 if str(r[c] or "").strip().lower() == "yes" else 0) if c is not None else None
            countries[cn] = (yes(c_cheg), yes(c_evr), yes(c_sng))
        uc, un = g(r, c_ucode), g(r, c_uname)
        if uc and un and uc not in unions: unions[uc] = un
        p = g(r, c_post)
        if p: posts.add(p)
    # ---- declarations + items for the covered years
    decls, items = {}, []
    months = defaultdict(float); excluded = defaultdict(float); meva = defaultdict(float)
    balances = defaultdict(float); bnpz_bal = defaultdict(float)
    n_ek = n_im = 0
    for r in body:
        rdate = str(r[c_rdate])[:10]; y = int(rdate[:4])
        inn = inn_str(r[c_inn]); m = int(rdate[5:7]); v = num(r[c_val])
        regime = "ЭК" if str(r[c_reg] or "").strip().upper().startswith("ЭК") else "ИМ"
        post, gdate, gnum = str(r[c_post] or "").strip(), str(r[c_gdate] or "")[:10], str(r[c_gnum] or "").strip()
        gtd = f"{post}/{gdate}/{gnum}"
        item_no = inn_str(r[c_item]) or ""
        key = f"{gtd}#{item_no}"
        decl_id = g(r, c_decl) or f"{regime}:{gtd}:{inn}"
        cmdt_id = g(r, c_cmdt) or f"{decl_id}#{item_no or len(items)}"
        if decl_id not in decls:
            decls[decl_id] = (decl_id, inn, regime, g(r, c_proc), y, m, rdate, gdate or None, gnum or None, post or None, gtd,
                              g(r, c_deal), g(r, c_g25), g(r, c_pnd), g(r, c_tc), g(r, c_cn),
                              num(r[c_rusd]) if c_rusd is not None else None, num(r[c_rcur]) if c_rcur is not None else None)
        hs = g(r, c_hs)
        if regime == "ИМ":
            kind = "im"; n_im += 1
        else:
            n_ek += 1
            if inn in exclude: kind = "bnpz"
            elif _is_meva(r[c_t1] if c_t1 is not None else None, hs): kind = "meva"
            else: kind = "sanoat"
            if y == year and operational:
                if kind == "bnpz": excluded[m] += v; bnpz_bal[m] += v
                elif kind == "meva": meva[m] += v
                else: balances[(inn, m)] += v; months[m] += v
        netto = num(r[c_net]) if c_net is not None else None
        kg = num(r[c_kg]) if c_kg is not None else (netto * 1000 if netto is not None else None)
        items.append((cmdt_id, decl_id, inn, regime, y, m, rdate, gtd, key, item_no or None, hs, (hs or "")[:4] or None,
                      g(r, c_t1), g(r, c_t2), g(r, c_sp1), g(r, c_sp2), g(r, c_unit),
                      num(r[c_qty]) if c_qty is not None and _s(r[c_qty]) else None, kg, netto, v,
                      num(r[c_inv]) if c_inv is not None and _s(r[c_inv]) else None, g(r, c_orig), g(r, c_need), kind))
    with con:
        for code, name in dists.items():
            if not code.startswith(REGION): continue        # a stray Tashkent-region code in the base is not a Bukhara district
            con.execute("INSERT INTO districts(code,name_uz) VALUES(?,?) ON CONFLICT(code) DO UPDATE SET name_uz=excluded.name_uz", (code, name))
        added = 0; other_region = []
        for inn, c in seen.items():
            if not (c["district_code"] or "").startswith(REGION):
                # registered under another region's district: kept in the registry, but «Бухоро эмас» unless the user decides otherwise
                other_region.append(inn)
                if not con.execute("SELECT 1 FROM companies WHERE inn=?", (inn,)).fetchone():
                    con.execute("""INSERT INTO companies(inn,name,district_code,product,kind,source,confirmed,in_base,bukhara,full_name,union_code,union_name,base_kind)
                                   VALUES(?,?,NULL,?,'sanoat','baza',1,1,0,?,?,?,?)""",
                                (inn, c["name"], c["product"], c["full_name"], c["union_code"], c["union_name"], c["base_kind"])); added += 1
                continue
            if con.execute("SELECT 1 FROM companies WHERE inn=?", (inn,)).fetchone():
                con.execute("""UPDATE companies SET district_code=COALESCE(district_code, ?), in_base=1, full_name=COALESCE(?, full_name),
                               union_code=COALESCE(?, union_code), union_name=COALESCE(?, union_name), base_kind=COALESCE(?, base_kind) WHERE inn=?""",
                            (c["district_code"], c["full_name"], c["union_code"], c["union_name"], c["base_kind"], inn))
                if c["name"]:   # repair names that an older import stored as «(null)» / empty
                    con.execute("UPDATE companies SET name=? WHERE inn=? AND (name IS NULL OR trim(name)='' OR name='(null)')", (c["name"], inn))
                continue
            con.execute("""INSERT INTO companies(inn,name,district_code,product,kind,source,confirmed,in_base,full_name,union_code,union_name,base_kind)
                           VALUES(?,?,?,?,'sanoat','baza',1,1,?,?,?,?)""",
                        (inn, c["name"], c["district_code"], c["product"], c["full_name"], c["union_code"], c["union_name"], c["base_kind"])); added += 1
        for inn in memo: con.execute("UPDATE companies SET excluded=1, kind='memo' WHERE inn=?", (inn,))
        for inn in exclude: con.execute("UPDATE companies SET excluded=2, kind='exclude' WHERE inn=?", (inn,))
        con.executemany("INSERT INTO hs_codes(hs10,tovar1,tovar2,sprav1,sprav2,unit) VALUES(?,?,?,?,?,?) ON CONFLICT(hs10) DO UPDATE SET "
                        "tovar1=COALESCE(excluded.tovar1,tovar1), tovar2=COALESCE(excluded.tovar2,tovar2), sprav1=COALESCE(excluded.sprav1,sprav1), "
                        "sprav2=COALESCE(excluded.sprav2,sprav2), unit=COALESCE(excluded.unit,unit)", [(k, *v) for k, v in hs_dict.items()])
        con.executemany("INSERT INTO countries(name,chegara,evrazes,sng) VALUES(?,?,?,?) ON CONFLICT(name) DO UPDATE SET chegara=COALESCE(excluded.chegara,chegara), "
                        "evrazes=COALESCE(excluded.evrazes,evrazes), sng=COALESCE(excluded.sng,sng)", [(k, *v) for k, v in countries.items()])
        con.executemany("INSERT INTO unions(code,name) VALUES(?,?) ON CONFLICT(code) DO UPDATE SET name=excluded.name", list(unions.items()))
        con.executemany("INSERT OR IGNORE INTO posts(code,name) VALUES(?,NULL)", [(p,) for p in posts])
        # the covered years / year-months are replaced as a whole (rows of the old base_rows conversion included)
        old_rows = {y: con.execute("SELECT count(*) FROM items WHERE year=?", (y,)).fetchone()[0] for y in years}
        con.executemany("DELETE FROM items WHERE year=?", [(y,) for y in full_years])
        con.executemany("DELETE FROM declarations WHERE year=?", [(y,) for y in full_years])
        con.executemany("DELETE FROM items WHERE year=? AND month=?", month_parts)
        con.executemany("DELETE FROM declarations WHERE year=? AND month=?", month_parts)
        con.executemany("INSERT OR REPLACE INTO declarations(decl_id,inn,regime,proc_code,year,month,rdate,gdate,gtd_no,post,key,deal_code,transport,pnd,trade_country,country,rate_usd,rate_cur) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", list(decls.values()))
        con.executemany("INSERT OR REPLACE INTO items(cmdt_id,decl_id,inn,regime,year,month,rdate,gtd,key,item_no,hs10,hs4,tovar1,tovar2,sprav1,sprav2,unit,qty,net_kg,netto,value,invoice,origin,need_flag,kind) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", items)
        if not con.execute("SELECT 1 FROM items WHERE cmdt_id LIKE 'legacy%' LIMIT 1").fetchone():
            con.execute("DELETE FROM settings WHERE key='items_legacy'")
        rolled = 0.0
        if operational:
            # meva roll-forward: daily meva collected after the previous opening and up to the new one becomes part of the meva opening
            if old_through and through > old_through:
                for rr in con.execute("""SELECT district_code dc, sum(stat_usd) s FROM gtd_rows WHERE voided=0 AND kind='meva'
                                         AND report_date>? AND report_date<=? GROUP BY dc""", (old_through, through)).fetchall():
                    con.execute("""INSERT INTO karantin_opening(district_code,year,ytd,month,month_amt,through_date) VALUES(?,?,?,?,0,?)
                                   ON CONFLICT(district_code,year) DO UPDATE SET ytd=ytd+excluded.ytd, through_date=excluded.through_date""",
                                (rr["dc"], year, rr["s"], int(through[5:7]), through)); rolled += rr["s"]
            con.execute("UPDATE karantin_opening SET month=?, month_amt=0, through_date=? WHERE year=?", (int(through[5:7]), through, year))
            con.execute("DELETE FROM opening_balances WHERE year=?", (year,))
            con.executemany("INSERT INTO opening_balances(inn,kind,year,month,amount,through_date,source) VALUES(?,'sanoat',?,?,?,?,'customs')",
                            [(inn, year, m, round(v, 6), through if m == int(through[5:7]) else None) for (inn, m), v in balances.items() if v])
            bn_inn = next(iter(exclude), None)
            if bn_inn:
                con.executemany("INSERT INTO opening_balances(inn,kind,year,month,amount,through_date,source) VALUES(?,'bnpz',?,?,?,?,'customs')",
                                [(bn_inn, year, m, round(v, 6), None) for m, v in bnpz_bal.items() if v])
            db.set_setting(con, "opening_through_date", through)
            db.set_setting(con, "opening_source", "customs")
            db.set_setting(con, "opening_last_day", "[]")
            db.set_setting(con, "karantin_last_day", "{}")
            db.set_setting(con, "year", year)
        # verification: what the file holds vs what the tree now holds, year by year (rows and sums by regime / kind)
        verify = _verify(con, items, years, old_rows, full_years)
        db.log(con, "import_customs_base" if operational else "import_customs_history", file=Path(path).name, through=through, years=years,
               inns=len(seen), added=added, balances=len(balances), declarations=len(decls), items=len(items),
               full_years=full_years, verify_ok=all(v["ok"] for v in verify))
    # companies first seen here: fill номманом columns from reference / learned map
    if operational:
        from .daily import new_company_attrs
        hs_by_inn = defaultdict(list)
        for inn, code, a in db.inn_hs4(con, year=year): hs_by_inn[inn].append((code, a))
        with con:
            for r in con.execute("SELECT inn, district_code FROM companies WHERE hudud IS NULL AND source='baza'").fetchall():
                if not any(k[0] == r["inn"] for k in balances): continue
                a = new_company_attrs(con, r["district_code"], hs_by_inn.get(r["inn"], []))
                con.execute("""UPDATE companies SET hudud=?, rus_district=?, district_full=?, tarmoq=COALESCE(tarmoq, ?), uyushma=COALESCE(uyushma, ?) WHERE inn=?""",
                            (a["hudud"], a["rus_district"], a["district_full"], a["tarmoq"], a["uyushma"], r["inn"]))
    covered = con.execute("SELECT count(*), coalesce(sum(stat_usd),0) FROM gtd_rows WHERE voided=0 AND kind='sanoat' AND report_date<=?", (through,)).fetchone()
    return {"through": through, "old_through": old_through, "year": year, "years": years, "operational": operational,
            "months": {m: round(v, 3) for m, v in sorted(months.items())}, "sanoat_total": round(sum(months.values()), 3),
            "excluded_bnpz": round(sum(excluded.values()), 3), "meva_not_taken": round(sum(meva.values()), 3),
            "registry": {"inns": len(seen), "added": added, "districts": sum(1 for d in dists if d.startswith(REGION)), "other_region": other_region}, "exporters": len({i for i, _ in balances}),
            "tree": {"declarations": len(decls), "items": len(items), "export_items": n_ek, "import_items": n_im, "hs_codes": len(hs_dict),
                     "countries": len(countries), "unions": len(unions), "posts": len(posts)},
            "covered_gtd": {"rows": covered[0], "sum": round(covered[1], 3)}, "meva_rolled": round(rolled, 3),
            "full_years": full_years, "verify": verify, "verify_ok": all(v["ok"] for v in verify)}

def _verify(con, items, years, old_rows, full_years) -> list:
    """[{year, full, old_rows, file_rows, db_rows, file: {ek, im, sanoat, meva, bnpz}, db: {...}, ok}] — the file's own totals
    against the tree after the import. ok = row counts equal and every sum equal to 1 USD. Sums in ming USD.
    (items tuple: 3 regime, 4 year, 20 value, 24 kind)"""
    out = []
    for y in years:
        f = {"ek": 0.0, "im": 0.0, "sanoat": 0.0, "meva": 0.0, "bnpz": 0.0}; n = 0
        for it in items:
            if it[4] != y: continue
            n += 1; v = it[20] or 0.0
            if it[3] == "ИМ": f["im"] += v
            else:
                f["ek"] += v; f[it[24]] = f.get(it[24], 0.0) + v
        d = {"ek": 0.0, "im": 0.0, "sanoat": 0.0, "meva": 0.0, "bnpz": 0.0}; dn = 0
        for r in con.execute("SELECT regime, kind, count(*), coalesce(sum(value),0) FROM items WHERE year=? GROUP BY regime, kind", (y,)):
            dn += r[2]
            if r[0] == "ИМ": d["im"] += r[3]
            else:
                d["ek"] += r[3]; d[r[1]] = d.get(r[1], 0.0) + r[3]
        ok = n == dn and all(abs(f[k] - d[k]) < 0.001 for k in f)
        out.append({"year": y, "full": y in full_years, "old_rows": old_rows.get(y, 0), "file_rows": n, "db_rows": dn,
                    "file": {k: round(v, 3) for k, v in f.items()}, "db": {k: round(v, 3) for k, v in d.items()}, "ok": ok})
    return out

def _sheet_kind(path) -> str:
    from .xl import sheet_names
    names = [n.strip().lower() for n in sheet_names(path)]
    if "номманом" in names: return "workbook"
    if any(n.startswith("база") for n in names): return "baza"
    try:
        head = " ".join(_norm(v) for r in read_sheet(path, 0, max_rows=3) for v in r if v)
    except Exception:
        head = ""
    return "gtd" if "дата выгрузки" in head else "unknown"

WRONG_FILE = {
    "gtd": "Bu bojxonaning kunlik GTD fayli. Uni «Kunlik hisobot» bo'limida yuklang. Bu yerga o'z jadvalingiz kerak: «… йил экспорт.xls» (номманом va СВОД varaqlari bor fayl).",
    "baza": "Bu bojxonaning oylik bazasi. Uni «1. Bojxona oylik bazasi» bo'limida yuklang. Bu yerga o'z jadvalingiz kerak: «… йил экспорт.xls».",
    "workbook": "Bu o'z kunlik jadvalingiz («… йил экспорт»). Uni «2. O'z jadvalingiz» bo'limida yuklang.",
    "unknown": "Fayl turi aniqlanmadi: «номманом» yoki «База» varag'i, yoki «Дата выгрузки» ustuni topilmadi.",
}

XLSX_ONLY = ("Qo'lda o'giring: jadvalni Excelda oching → Файл → Сохранить как → «Книга Excel (*.xlsx)» va .xlsx faylni yuklang. "
             "Shablon formulalari bilan saqlanishi kerak, .xls dan formulalarni o'qib bo'lmaydi.")

def import_workbook(con, path, template_copy=None, display_name=None, sha=None) -> dict:
    """Own workbook = Excel template. From it: company attributes, prognoz, meva opening (aligned to the customs base),
    list of номманом companies (template_inns, yellow = new exporter) and the template date."""
    from . import tpl
    path = Path(path)
    if path.suffix.lower() != ".xlsx": raise ValueError(XLSX_ONLY)   # .xls is converted by Excel in reinit.check
    k = _sheet_kind(path)
    if k != "workbook": raise ValueError(WRONG_FILE[k] if k != "workbook" else "")
    through = db.get_setting(con, "opening_through_date")
    if not through or db.get_setting(con, "opening_source") != "customs":
        raise ValueError("Avval 1-qadam: bojxona oylik bazasini yuklang — kunlik jadvaldan meva-sabzavot shu sanaga moslab olinadi")
    info = tpl.inspect(Path(template_copy or path))
    cur_T, cur_sha = db.get_setting(con, "template_through"), db.get_setting(con, "template_sha")
    if sha and cur_sha == sha:
        raise ValueError(f"Bu jadval allaqachon shablon sifatida yuklangan ({db.get_setting(con, 'template_file')}) — qayta yuklash shart emas, hech narsa o'zgarmaydi.")
    if cur_T and info["through"] < cur_T:
        raise ValueError(f"Bu jadval eski: {tpl.dmy(info['label'])} йил, joriy shablon esa {tpl.dmy(cur_T)} gacha. "
                         "Eski jadval yuklanmaydi. Oldingi holatga qaytish kerak bo'lsa: «Nazorat va tarix» → «before_workbook» zaxirasini qaytaring.")
    continuity = None
    cur_path = tpl.template_path(con)
    if cur_T and cur_path.exists():
        try:
            continuity = tpl.compare_templates(con, cur_path, cur_T, Path(template_copy or path), info["through"])
        except Exception as e:
            continuity = {"error": str(e)}
    if info["through"] < through:
        raise ValueError(f"Jadval sanasi {tpl.dmy(info['label'])} — bojxona bazasidan ({tpl.dmy(through)} gacha) eski. "
                         f"Bazadan keyingi, eng oxirgi jadvalingizni yuklang.")
    if info["formula_bad"]:
        raise ValueError(f"Jadvaldagi {info['formula_bad']} ta formulani o'qib bo'lmadi — yangi korxona qatori qo'shilganda formulalar buzilishi mumkin.")
    year = int(through[:4]); base_month = int(through[5:7])
    comp = init_import.import_nomma_nom(con, path, year, through, with_balances=False)
    svod = init_import.import_svod_karantin(con, path, year, through, meva_align_month=base_month, meva_strict=False)
    tn = init_import.build_tnved_map(con)
    with con:
        con.execute("DELETE FROM template_inns")
        con.executemany("INSERT OR IGNORE INTO template_inns(inn,category,row,district,yellow) VALUES(?,?,?,?,?)",
                        [(x["inn"], x["cat"], x["row"], x["district"], 1 if x["yellow"] else 0) for x in info["rows"]])
        yellow = set(info["yellow"])
        for (inn,) in con.execute("SELECT DISTINCT inn FROM template_inns").fetchall():
            con.execute("UPDATE companies SET is_new=? WHERE inn=?", (1 if inn in yellow else 0, inn))
        for key in ("label", "through", "cur_month", "karantin_sheet"):
            db.set_setting(con, f"template_{key}", info[key])
        db.set_setting(con, "template_file", display_name or path.name)
        if sha:
            db.set_setting(con, "template_sha", sha)
            db.set_setting(con, "template_store", f"templates/{info['label']}_{sha[:8]}.xlsx")
        db.set_setting(con, "template_loaded_at", dt.datetime.now().isoformat(timespec="seconds"))
        db.log(con, "template_inspected", label=info["label"], through=info["through"], companies=info["companies"], yellow=len(yellow))
    gtd_after = con.execute("SELECT count(DISTINCT report_date), coalesce(sum(stat_usd),0) FROM gtd_rows WHERE voided=0 AND report_date>?", (info["through"],)).fetchone()
    info_out = {k: v for k, v in info.items() if k != "rows"}
    return {"through": through, "companies": comp, "svod": svod, "tnved_map": tn, "template": info_out, "continuity": continuity,
            "previous_template": {"through": cur_T, "file": db.get_setting(con, "template_file")} if cur_T else None,
            "gtd_after": {"days": gtd_after[0], "sum": round(gtd_after[1], 3)}}
