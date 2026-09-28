"""Ҳисоботлар → «Маҳсулотлар таҳлили» (26.09.2026, Jafar talabi: «паррандачилик бўйича маълумот керак, кейин бошқа соҳалар ҳам сўралади»).

Tarmoq (tovar1, multi-select) → uning ichidagi mahsulotlar (tovar2 → sprav2, multi-select) tanlanadi; bir nechta tarmoqdan
aralash tanlash mumkin (masalan паррандачилик = «Тирик ҳайвонлар»dagi Товуқ + «Озиқ-овқат»dagi Тухум). Tanlov «тўплам» bo'lib
saqlanadi (settings.product_sets) — keyin boshqa sohalar uchun ham shu yerdan.
Natija: joriy yil davri va o'tgan yilning xuddi shu davri — mahsulotlar, korxonalar (holati bilan), korxona × mahsulot, tumanlar,
davlatlar, oylar. Manba va qoidalar — products._rows (Тармоқ ва маҳсулот sahifasi va Тармоқлар таҳлили bilan bir xil):
bojxona bazasi + keyingi kunlik GTD, «Бухоро эмас» chiqariladi, Buxoro davri, БНПЗ/SDK faqat memo=1 da; meva-sabzavot
karantin qoidasi korxona/mahsulotga bog'lanmagani uchun faqat saноat hisobidagi qatorlar.
"""
from __future__ import annotations
import datetime as dt, json, re, uuid
from collections import defaultdict
from pathlib import Path
from . import db, report, tahlil, products as P

SETS_KEY = "product_sets"
BUILTIN = [{"id": "poultry", "name": "Паррандачилик", "builtin": True, "hs4": ["0105", "0207", "0209", "0407", "0408", "0505"],
            "names": ["Паррандачилик ускуналари"],
            "hint": "тирик парранда, парранда гўшти ва ёғи, тухум, пат (ТН ВЭД 0105, 0207, 0209, 0407, 0408, 0505) + паррандачилик ускуналари (импорт)"}]
MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]


def _t1(r) -> str:
    return str(r[2]).replace(" (саноат ҳисобида)", "")      # экспорт ва импорт бир хил калит билан солиштирилсин


def _key(r) -> str:
    return f"{_t1(r)}|{r[3]}|{r[5]}"


def _imp_rows(con, y: int, f: str, t: str, comp: dict, q: dict, hs: dict, hs4: dict) -> list:
    """Import qatorlari (bojxona bazasi items regime='ИМ', kunlik GTD da import yo'q) — _rows bilan bir xil tuple.
    Qoidalar trade.import_recs kabi: faqat Buxoro korxonalari («Бухоро эмас» yo'q, Buxoro davri), tuman filtri; БНПЗ/SDK — faqat memo=1."""
    from .companies import country_uz
    dsel = {x for x in str(q.get("district") or "").split(",") if x}
    memo = str(q.get("memo") or "0") == "1"
    out = []
    for r in con.execute("""SELECT i.inn, i.rdate, i.gtd, i.hs10, i.tovar1, i.tovar2, i.sprav1, i.sprav2, i.value, i.netto, d.country
                            FROM items i JOIN declarations d ON d.decl_id=i.decl_id
                            WHERE i.regime='ИМ' AND i.year=? AND i.rdate>=? AND i.rdate<=?""", (y, f, t)):
        c = comp.get(r["inn"])
        if c is None or c.get("bukhara") == 0: continue
        if not ((c.get("bukhara_from") or "") <= r["rdate"] <= (c.get("bukhara_to") or "9999")): continue
        if c.get("excluded") and not memo: continue
        if dsel and c.get("district_code") not in dsel: continue
        code = r["hs10"] or ""
        d = hs.get(code) or hs4.get(code[:4]) or {}
        t1 = r["tovar1"] or d.get("tovar1") or P.OTHER
        out.append((r["inn"], code, t1, r["tovar2"] or d.get("tovar2") or code[:4] or "—", r["sprav1"] or d.get("sprav1") or t1,
                    r["sprav2"] or d.get("sprav2") or (code[:6] or "—"), r["value"] or 0.0, r["netto"] or 0.0, r["gtd"],
                    country_uz(r["country"]), "baza", r["rdate"], "im"))
    return out


def import_last(con, y: int) -> str:
    return con.execute("SELECT max(rdate) FROM items WHERE regime='ИМ' AND year=?", (y,)).fetchone()[0] or ""


def _ctx(con, q):
    comp = {r["inn"]: dict(r) for r in con.execute(
        "SELECT inn, name, full_name, district_code, tarmoq, kind, excluded, in_base, bukhara, bukhara_from, bukhara_to, source FROM companies")}
    meva_inns = {i for (i,) in con.execute("SELECT inn FROM template_inns WHERE category='meva'")} or \
                {i for (i,) in con.execute("SELECT inn FROM companies WHERE kind='meva' AND source='nomma-nom'")}
    keep = P.sanoat_only(P._keeper(con, {"district": q.get("district") or "", "memo": q.get("memo") or "0", "kind": "sanoat"}, comp, meva_inns))
    return comp, keep, P._hs_dict(con), P._hs4_dict(con)


def _list(v) -> list:
    if not v: return []
    if isinstance(v, list): return [str(x) for x in v if str(x)]
    try:
        x = json.loads(v)
        return [str(i) for i in x if str(i)] if isinstance(x, list) else []
    except Exception:
        return []


# ------------------------------------------------------------------ katalog va to'plamlar
def sets(con) -> list:
    try: own = json.loads(db.get_setting(con, SETS_KEY, "[]") or "[]")
    except Exception: own = []
    return BUILTIN + [s for s in own if isinstance(s, dict) and s.get("id")]


def save_set(con, body: dict) -> dict:
    name = (body.get("name") or "").strip()
    if not name: raise ValueError("Тўплам номини ёзинг")
    keys, cats = _list(body.get("keys")), _list(body.get("cats"))
    if not keys and not cats: raise ValueError("Камида битта тармоқ ёки маҳсулот танланг")
    own = [s for s in sets(con) if not s.get("builtin")]
    sid = body.get("id") or ""
    if any(s["id"] == sid for s in BUILTIN): sid = ""        # тайёр тўплам ўзгармайди — нусхаси сақланади
    if sid and any(s["id"] == sid for s in own):
        for s in own:
            if s["id"] == sid: s.update({"name": name, "keys": keys, "cats": cats})
    else:
        sid = "s" + uuid.uuid4().hex[:8]
        own.append({"id": sid, "name": name, "keys": keys, "cats": cats})
    with con: db.set_setting(con, SETS_KEY, json.dumps(own, ensure_ascii=False))
    return {"ok": True, "id": sid, "sets": sets(con)}


def delete_set(con, sid: str) -> dict:
    own = [s for s in sets(con) if not s.get("builtin") and s["id"] != sid]
    with con: db.set_setting(con, SETS_KEY, json.dumps(own, ensure_ascii=False))
    return {"ok": True, "sets": sets(con)}


def catalog(con, q: dict) -> dict:
    """Tarmoq → guruh (tovar2) → mahsulot (sprav2): eksport va import — joriy yil (oxirgi kungacha) va o'tgan yil to'liq qiymati,
    HS-4 kodlari, korxonalar soni. Import — faqat bojxona bazasi."""
    cy = int(db.get_setting(con, "year") or dt.date.today().year)
    y = int(q.get("year") or cy)
    last = report.last_data_date(con) or dt.date.today().isoformat()
    comp, keep, hs, hs4 = _ctx(con, {"memo": q.get("memo")})
    agg = {}
    spans = ((y, f"{y}-01-01", last if y == cy else f"{y}-12-31", 0), (y - 1, f"{y - 1}-01-01", f"{y - 1}-12-31", 1))
    for src, off in (("ex", 0), ("im", 2)):
        for yy, f, t, i in spans:
            rows = P._rows(con, yy, f, t, comp, keep, hs, hs4) if src == "ex" else _imp_rows(con, yy, f, t, comp, {"memo": q.get("memo")}, hs, hs4)
            for r in rows:
                k = _key(r)
                a = agg.get(k)
                if a is None: a = agg[k] = {"key": k, "t1": _t1(r), "t2": r[3], "name": r[5], "v": [0.0] * 4, "hs": set(), "inn": set(), "iinn": set()}
                a["v"][off + i] += r[6] or 0.0; a["hs"].add((r[1] or "")[:4]); (a["inn"] if src == "ex" else a["iinn"]).add(r[0])
    W = lambda v: v[0] + v[1] / 1000 + (v[2] + v[3] / 1000) / 1000
    R = lambda v: {"cur": round(v[0], 1), "prev": round(v[1], 1), "icur": round(v[2], 1), "iprev": round(v[3], 1)}
    tree = {}
    for a in agg.values():
        t = tree.setdefault(a["t1"], {"t1": a["t1"], "v": [0.0] * 4, "groups": {}})
        g = t["groups"].setdefault(a["t2"], {"t2": a["t2"], "v": [0.0] * 4, "items": []})
        for i in range(4): t["v"][i] += a["v"][i]; g["v"][i] += a["v"][i]
        g["items"].append({"key": a["key"], "name": a["name"], **R(a["v"]), "w": W(a["v"]),
                           "hs": sorted(h for h in a["hs"] if h), "companies": len(a["inn"]), "icompanies": len(a["iinn"])})
    out = []
    for t in sorted(tree.values(), key=lambda t: -W(t["v"])):
        groups = []
        for g in sorted(t["groups"].values(), key=lambda g: -W(g["v"])):
            g["items"].sort(key=lambda x: -x.pop("w"))
            groups.append({"t2": g["t2"], **R(g["v"]), "items": g["items"]})
        out.append({"t1": t["t1"], **R(t["v"]), "groups": groups})
    ss = []
    for s in sets(con):
        s = dict(s)
        if s.get("hs4") or s.get("names"):     # тайёр тўплам — ТН ВЭД ва номлар бўйича, каталогдаги мос маҳсулотлар
            want, names = set(s.get("hs4") or []), set(s.get("names") or [])
            s["keys"] = sorted(a["key"] for a in agg.values() if (a["hs"] & want and a["name"] != "Паррандачилик ускуналари") or a["name"] in names)
            s["cats"] = []
        ss.append(s)
    return {"year": y, "prev_year": y - 1, "last_date": last, "import_last": import_last(con, y), "tree": out, "sets": ss}


def meta(con) -> dict:
    cy = int(db.get_setting(con, "year") or dt.date.today().year)
    years = [r[0] for r in con.execute("SELECT DISTINCT year FROM items WHERE regime='ЭК' ORDER BY year")]
    if cy not in years: years.append(cy)
    return {"year": cy, "years": [y for y in years if y - 1 in years] or years, "default_months": tahlil.default_months(con),
            "last_date": report.last_data_date(con), "opening_through": db.get_setting(con, "opening_through_date") or "",
            "districts": [{"code": d["code"], "name": d["name_uz"]} for d in report.districts(con)]}


# ------------------------------------------------------------------ hisob
def _status(pv, cv, y):
    if pv == 0: return "new", "янги"
    if cv == 0: return "stop", f"{y} йил экспорт қилмаган"
    return ("up", "кўпайган") if cv >= pv else ("down", "камайган")


def _agg(sides, comp: dict, dn: dict, sel, y: int, py: int, per: dict) -> dict:
    """sides = ((0, rows_prev), (1, rows_cur)) -> mahsulotlar, korxonalar, tumanlar, davlatlar, oylar, jamilar."""
    Z = lambda: [0.0, 0.0, 0.0, 0.0]     # prev_n, prev_v, cur_n, cur_v
    prods, cos, dists, ctrs = defaultdict(Z), defaultdict(Z), defaultdict(Z), defaultdict(Z)
    cp = defaultdict(Z)                    # (inn, key)
    months = [[0.0, 0.0] for _ in range(12)]
    S2 = lambda: [set(), set()]
    pinfo, pinn, dinn, cinn, cctr = {}, defaultdict(S2), defaultdict(S2), defaultdict(S2), defaultdict(set)
    for side, rows in sides:
        off = side * 2
        for r in rows:
            k = _key(r)
            if not sel(k): continue
            n, v = r[7] or 0.0, r[6] or 0.0
            inn = r[0]; dc = (comp.get(inn) or {}).get("district_code") or ""; ctry = r[9] or "—"
            pinfo.setdefault(k, {"t1": _t1(r), "t2": r[3], "name": r[5], "hs": set()})["hs"].add((r[1] or "")[:4])
            for bucket, kk in ((prods, k), (cos, inn), (dists, dc), (ctrs, ctry), (cp, (inn, k))):
                bucket[kk][off] += n; bucket[kk][off + 1] += v
            pinn[k][side].add(inn); dinn[dc][side].add(inn); cinn[ctry][side].add(inn)
            cctr[(inn, side)].add(ctry)
            months[int(str(r[11])[5:7]) - 1][side] += v
    def row(a): return {"prev_n": a[0], "prev_v": a[1], "cur_n": a[2], "cur_v": a[3]}
    tot = [sum(a[i] for a in prods.values()) for i in range(4)]
    plist = []
    for k, a in prods.items():
        if not (a[1] or a[3]): continue
        i = pinfo[k]
        plist.append({"key": k, "t1": i["t1"], "t2": i["t2"], "name": i["name"], "hs": ", ".join(sorted(h for h in i["hs"] if h)),
                      "prev_c": len(pinn[k][0]), "cur_c": len(pinn[k][1]), **row(a)})
    plist.sort(key=lambda p: (-p["cur_v"], -p["prev_v"]))
    byinn = defaultdict(list)
    for (i2, k), v in cp.items():
        if v[1] or v[3]: byinn[i2].append({"name": pinfo[k]["name"], **row(v)})
    clist = []
    for inn, a in cos.items():
        if not (a[1] or a[3]): continue
        c = comp.get(inn) or {}
        g, st = _status(a[1], a[3], y)
        clist.append({"inn": inn, "name": c.get("name") or c.get("full_name") or inn, "full_name": c.get("full_name") or "",
                      "district": dn.get(c.get("district_code")) or "—", "group": g, "status": st,
                      "countries": sorted(cctr[(inn, 1)]) or [f"{x} ({py})" for x in sorted(cctr[(inn, 0)])],
                      "products": sorted(byinn[inn], key=lambda p: (-p["cur_v"], -p["prev_v"])), **row(a)})
    clist.sort(key=lambda c: (-c["cur_v"], -c["prev_v"]))
    for i, c in enumerate(clist, 1): c["no"] = i
    dlist = [{"code": code, "name": dn.get(code) or "Аниқланмаган", "prev_c": len(dinn[code][0]), "cur_c": len(dinn[code][1]), **row(a)}
             for code, a in dists.items() if a[1] or a[3]]
    dlist.sort(key=lambda d: (-d["cur_v"], -d["prev_v"]))
    ctl = [{"name": k, "prev_c": len(cinn[k][0]), "cur_c": len(cinn[k][1]), **row(a)} for k, a in ctrs.items() if a[1] or a[3]]
    ctl.sort(key=lambda d: (-d["cur_v"], -d["prev_v"]))
    grp = defaultdict(int)
    for c in clist: grp[c["group"]] += 1
    last_m = int(per["to"][5:7])
    mon = [{"m": i + 1, "name": MONTHS[i], "prev_v": months[i][0], "cur_v": months[i][1]} for i in range(12)
           if int(per["from"][5:7]) <= i + 1 <= last_m]
    return {"count": len(clist), "groups": dict(grp), "prev_n": tot[0], "prev_v": tot[1], "cur_n": tot[2], "cur_v": tot[3],
            "prev_companies": sum(1 for c in clist if c["prev_v"]), "cur_companies": sum(1 for c in clist if c["cur_v"]),
            "products": plist, "companies": clist, "districts": dlist, "countries": ctl, "months": mon}


def _imp_period(con, per: dict) -> dict:
    """Import — faqat bojxona bazasi: joriy yil davri bazaning oxirgi sanasigacha qisqartiriladi, o'tgan yil — xuddi shu kunlar."""
    il = import_last(con, per["year"])
    p = dict(per)
    if il and il < per["to"]:
        p["to"] = il; p["prev_to"] = f"{per['prev_year']}{il[4:]}"
        if p["prev_to"].endswith("02-29"): p["prev_to"] = p["prev_to"][:-2] + "28"
        d0, d1 = dt.date.fromisoformat(p["from"]), dt.date.fromisoformat(il)
        p["label"] = f"{d0.day} {tahlil.MONTHS_GEN[d0.month - 1]} – {d1.day} {tahlil.MONTHS_GEN[d1.month - 1]}"
        p["cut"] = True
    p["data_to"] = min(p["to"], il) if il else p["to"]
    return p


def build(con, q: dict) -> dict:
    keys, cats = set(_list(q.get("keys"))), set(_list(q.get("cats")))
    if not keys and not cats: raise ValueError("Тармоқ ёки маҳсулот танланг")
    sel = lambda k: k in keys or k.split("|", 1)[0] in cats     # тармоқ тўлиқ (cats, келажакдаги янги маҳсулотлари билан) ёки алоҳида маҳсулот (keys)
    per = tahlil._period(con, q)
    y, py = per["year"], per["prev_year"]
    comp, keep, hs, hs4 = _ctx(con, q)
    dn = {d["code"]: d["name_uz"] for d in report.districts(con)}
    rp = P._rows(con, py, per["prev_from"], per["prev_to"], comp, keep, hs, hs4)
    rc = P._rows(con, y, per["from"], per["to"], comp, keep, hs, hs4)
    ex = _agg(((0, rp), (1, rc)), comp, dn, sel, y, py, per)
    ex["region_prev_v"] = sum(r[6] or 0.0 for r in rp); ex["region_cur_v"] = sum(r[6] or 0.0 for r in rc)   # вилоят саноат экспорти (шу давр, шу филтрлар)
    ip = _imp_period(con, per)
    ipr = _imp_rows(con, py, ip["prev_from"], ip["prev_to"], comp, q, hs, hs4)
    icr = _imp_rows(con, y, ip["from"], ip["to"], comp, q, hs, hs4)
    im = _agg(((0, ipr), (1, icr)), comp, dn, sel, y, py, ip)
    im["region_prev_v"] = sum(r[6] or 0.0 for r in ipr); im["region_cur_v"] = sum(r[6] or 0.0 for r in icr)
    im["period"] = ip
    # sarlavha
    sname = (q.get("set_name") or "").strip()
    if not sname:
        names = sorted({p["name"] for p in ex["products"] + im["products"]}, key=lambda n: n) if keys else sorted(cats)
        sname = (", ".join(names[:3]) + (f" ва бошқа {len(names) - 3} та" if len(names) > 3 else "")) if names else "танланган"
    title = (q.get("title") or "").strip() or \
        f"Бухоро вилоятидан «{sname}» маҳсулотлари экспорти\n({py}-{y} йиллар {per['label']})"
    im["title"] = (f"{(q.get('title') or '').strip()} — импорт" if (q.get("title") or "").strip() else
                   f"Бухоро вилояти корхоналарининг «{sname}» маҳсулотлари импорти\n({py}-{y} йиллар {ip['label']})")
    return {"title": title, "set_name": sname, "period": per, "unit": "минг долл", **ex, "imp": im,
            "last_date": report.last_data_date(con)}


# ------------------------------------------------------------------ Excel (26.09.2026, Jafar: 4 varaq, «2026 йил паррандачилик лойиҳалари.xlsx» dizaynida)
def _detail(rows, sel, comp: dict, dn: dict) -> list:
    """Korxona × mahsulot × davlat qatorlari (tonna, ming $) — qiymat bo'yicha kamayish tartibida."""
    acc = defaultdict(lambda: [0.0, 0.0])
    for r in rows:
        k = _key(r)
        if not sel(k): continue
        a = acc[(r[0], r[5], r[9] or "—")]; a[0] += r[7] or 0.0; a[1] += r[6] or 0.0
    out = []
    for (inn, prod, ctry), (n, v) in acc.items():
        if v <= 0.0005 and n <= 0.0005: continue
        c = comp.get(inn) or {}
        out.append({"inn": inn, "district": dn.get(c.get("district_code")) or "—", "name": c.get("name") or c.get("full_name") or inn,
                    "product": prod, "netto": n, "value": v, "country": ctry})
    out.sort(key=lambda x: (-x["value"], x["district"], x["name"]))
    return out


def export_xlsx(con, q: dict, out: Path) -> Path:
    """6 varaq: Жами экспорт, Жами импорт ({py} va {y} yonma-yon, korxona × mahsulot), keyin Экспорт {py} (тўлиқ йил), Экспорт {y} (йил бошидан), Импорт {py}, Импорт {y}.
    Ustunlar: Т/р · Туман · Корхона · Маҳсулот · тонна · минг $ · давлат. Davr tanlovi Excelga ta'sir qilmaydi (doim yil to'liq / yil boshidan)."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.cell.rich_text import CellRichText, TextBlock
    from openpyxl.cell.text import InlineFont
    keys, cats = set(_list(q.get("keys"))), set(_list(q.get("cats")))
    if not keys and not cats: raise ValueError("Тармоқ ёки маҳсулот танланг")
    sel = lambda k: k in keys or k.split("|", 1)[0] in cats
    cy = int(db.get_setting(con, "year") or dt.date.today().year)
    y = int(q.get("year") or cy); py = y - 1
    last = report.last_data_date(con) or dt.date.today().isoformat()
    ex_to = last if y == cy else f"{y}-12-31"
    im_to = import_last(con, y) or f"{y}-12-31"
    comp, keep, hs, hs4 = _ctx(con, q)
    dn = {d["code"]: d["name_uz"] for d in report.districts(con)}
    sname = (q.get("set_name") or "").strip()
    if not sname:
        sname = ", ".join(sorted(cats)[:2]) if cats else ", ".join(sorted({k.split("|")[-1] for k in keys})[:3])
    D = lambda iso: f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}"
    sheets = [
        (f"Экспорт {py}", "ex", py, f"{py}-01-01", f"{py}-12-31", f"{py} йилда", "экспорти", "Экспорт қилинган давлат"),
        (f"Экспорт {y}", "ex", y, f"{y}-01-01", ex_to, f"{y} йил {D(ex_to)} ҳолатига", "экспорти", "Экспорт қилинган давлат"),
        (f"Импорт {py}", "im", py, f"{py}-01-01", f"{py}-12-31", f"{py} йилда", "импорти", "Импорт қилинган давлат"),
        (f"Импорт {y}", "im", y, f"{y}-01-01", im_to, f"{y} йил {D(im_to)} ҳолатига", "импорти", "Импорт қилинган давлат"),
    ]
    TNR = "Times New Roman"
    med, thin = Side(style="medium"), Side(style="thin")
    BM = Border(med, med, med, med); BT = Border(thin, thin, thin, thin)
    HF = PatternFill("solid", fgColor="DDEBF7"); TF = PatternFill("solid", fgColor="FCE4D6")
    C = Alignment(horizontal="center", vertical="center", wrap_text=True)
    L = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)
    RED = "FFC00000"
    wb = openpyxl.Workbook(); wb.remove(wb.active)
    # ---- 2 та жамловчи варақ: «Жами экспорт», «Жами импорт» — намунадагидек остма-ост: ЖАМИ → {y} йил бўлими → {py} йил бўлими
    def summary(kind, what, ctry_h):
        secs = []
        for yy, f, t in ((y, f"{y}-01-01", ex_to if kind == "ex" else im_to), (py, f"{py}-01-01", f"{py}-12-31")):
            rows = P._rows(con, yy, f, t, comp, keep, hs, hs4) if kind == "ex" else _imp_rows(con, yy, f, t, comp, q, hs, hs4)
            lbl = f"{yy} йил ({D(t)} ҳолатига)" if yy == y else f"{yy} йил (тўлиқ)"
            secs.append((yy, lbl, _detail(rows, sel, comp, dn)))
        ws = wb.create_sheet("Жами экспорт" if kind == "ex" else "Жами импорт")
        ws.merge_cells("A1:G1")
        ws["A1"] = CellRichText([TextBlock(InlineFont(rFont=TNR, sz=16, b=True), "Бухоро вилоятидаги корхоналарнинг "),
                                 TextBlock(InlineFont(rFont=TNR, sz=16, b=True, color=RED, u="single"), sname.upper()),
                                 TextBlock(InlineFont(rFont=TNR, sz=16, b=True), f" маҳсулотлари {what}: "),
                                 TextBlock(InlineFont(rFont=TNR, sz=16, b=True, color=RED, u="single"), f"{y} ва {py} йиллар")])
        ws["A1"].alignment = C; ws.row_dimensions[1].height = 48
        hdr = ["Т/р", "Туман (шаҳар) номи", "Корхона номи", "Маҳсулот номи", "Ҳажми,\nтонна", "Қиймати,\nминг АҚШ доллари", ctry_h]
        for i, (h, w) in enumerate(zip(hdr, [7, 20, 42, 38, 13, 17, 22]), 1):
            c = ws.cell(2, i, h); c.font = Font(name=TNR, size=12, bold=True); c.fill = HF; c.alignment = C; c.border = BM
            ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
        ws.row_dimensions[2].height = 44
        def band(rr, text, e, f_, g, size=13):
            ws.merge_cells(f"B{rr}:D{rr}"); ws[f"B{rr}"] = text; ws[f"E{rr}"] = e; ws[f"F{rr}"] = f_; ws[f"G{rr}"] = g
            for i in range(1, 8):
                c = ws.cell(rr, i); c.font = Font(name=TNR, size=size, bold=True, color=RED); c.fill = TF; c.alignment = C; c.border = BM
            ws[f"E{rr}"].number_format = "#,##0.0"; ws[f"F{rr}"].number_format = "#,##0.0"; ws.row_dimensions[rr].height = 32
        r = 4; heads = []
        allc = {x["inn"] for _, _, lst in secs for x in lst}
        for yy, lbl, lst in secs:
            hr_ = r; heads.append(hr_); r += 1; first = r
            for x in lst:
                vals = [f"=SUBTOTAL(3,$B${first}:B{r})", x["district"], x["name"], x["product"], round(x["netto"], 3), round(x["value"], 3), x["country"]]
                for i, v in enumerate(vals, 1):
                    c = ws.cell(r, i, v); c.font = Font(name=TNR, size=11); c.border = BT
                    c.alignment = L if i in (3, 4) else C
                ws.cell(r, 5).number_format = "#,##0.0"; ws.cell(r, 6).number_format = "#,##0.0"
                ws.row_dimensions[r].height = 30 if max(len(x["name"]), len(x["product"])) > 40 else 22
                r += 1
            n = len(lst); ncomp = len({x["inn"] for x in lst}); nctry = len({x["country"] for x in lst})
            band(hr_, f"{lbl} — жами {ncomp} та корхона" if n else f"{lbl} — маълумот йўқ",
                 f"=SUBTOTAL(9,E{first}:E{r - 1})" if n else 0, f"=SUBTOTAL(9,F{first}:F{r - 1})" if n else 0, f"{nctry} та давлат" if n else "", size=12)
            if not n:
                ws.cell(r, 2, "Танланган маҳсулотлар бўйича бу даврда маълумот йўқ").font = Font(name=TNR, size=11, italic=True); r += 1
        band(3, f"ЖАМИ {y} ва {py} йиллар — {len(allc)} та корхона", "=" + "+".join(f"E{h}" for h in heads), "=" + "+".join(f"F{h}" for h in heads), "")
        last = r - 1
        ws.freeze_panes = "A4"
        ws.print_title_rows = "1:3"; ws.print_area = f"A1:G{max(last, 4)}"
        ws.page_setup.orientation = "landscape"; ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0; ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.print_options.horizontalCentered = True
        ws.page_margins.left = ws.page_margins.right = 0.4; ws.page_margins.top = ws.page_margins.bottom = 0.5
        ws.oddFooter.center.text = f"{ws.title} · &P / &N"; ws.oddFooter.center.size = 9
    summary("ex", "экспорти", "Экспорт қилинган давлат"); summary("im", "импорти", "Импорт қилинган давлат")
    for title, kind, yy, f, t, when, what, ctry_h in sheets:
        rows = _detail(P._rows(con, yy, f, t, comp, keep, hs, hs4) if kind == "ex" else _imp_rows(con, yy, f, t, comp, q, hs, hs4), sel, comp, dn)
        ws = wb.create_sheet(title)
        # 1-қатор: сарлавҳа (йил ва соҳа қизил, намунадагидек)
        ws.merge_cells("A1:G1")
        ws["A1"] = CellRichText([TextBlock(InlineFont(rFont=TNR, sz=16, b=True, color=RED, u="single"), when),
                                 TextBlock(InlineFont(rFont=TNR, sz=16, b=True), " Бухоро вилоятидаги корхоналарнинг "),
                                 TextBlock(InlineFont(rFont=TNR, sz=16, b=True, color=RED, u="single"), sname.upper()),
                                 TextBlock(InlineFont(rFont=TNR, sz=16, b=True), f" маҳсулотлари {what}")])
        ws["A1"].alignment = C; ws.row_dimensions[1].height = 48
        hdr = ["Т/р", "Туман (шаҳар) номи", "Корхона номи", "Маҳсулот номи", "Ҳажми,\nтонна", "Қиймати,\nминг АҚШ доллари", ctry_h]
        widths = [7, 20, 42, 38, 13, 17, 22]
        for i, (h, w) in enumerate(zip(hdr, widths), 1):
            c = ws.cell(2, i, h); c.font = Font(name=TNR, size=12, bold=True); c.fill = HF; c.alignment = C; c.border = BM
            ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
        ws.row_dimensions[2].height = 44
        n = len(rows); first, lastr = 4, 3 + n
        ncomp = len({r["inn"] for r in rows}); nctry = len({r["country"] for r in rows})
        # 3-қатор: жами
        ws.merge_cells("B3:D3")
        ws["B3"] = f"Жами {ncomp} та корхона" if n else "Маълумот йўқ"
        ws["E3"] = f"=SUBTOTAL(9,E{first}:E{lastr})" if n else 0
        ws["F3"] = f"=SUBTOTAL(9,F{first}:F{lastr})" if n else 0
        ws["G3"] = f"{nctry} та давлат" if n else ""
        for i in range(1, 8):
            c = ws.cell(3, i); c.font = Font(name=TNR, size=13, bold=True, color=RED); c.fill = TF; c.alignment = C; c.border = BM
        ws["E3"].number_format = "#,##0.0"; ws["F3"].number_format = "#,##0.0"; ws.row_dimensions[3].height = 30
        for k, r in enumerate(rows):
            rr = first + k
            vals = [f"=SUBTOTAL(3,$B${first}:B{rr})", r["district"], r["name"], r["product"], round(r["netto"], 3), round(r["value"], 3), r["country"]]
            for i, v in enumerate(vals, 1):
                c = ws.cell(rr, i, v); c.font = Font(name=TNR, size=11); c.border = BT
                c.alignment = L if i in (3, 4) else C
            ws.cell(rr, 5).number_format = "#,##0.0"; ws.cell(rr, 6).number_format = "#,##0.0"
            ws.row_dimensions[rr].height = 30 if max(len(r["name"]), len(r["product"])) > 40 else 22
        if not n:
            ws.cell(4, 2, "Танланган маҳсулотлар бўйича бу даврда маълумот йўқ").font = Font(name=TNR, size=11, italic=True)
        ws.freeze_panes = "A4"
        if n: ws.auto_filter.ref = f"A2:G{lastr}"
        ws.print_title_rows = "1:3"; ws.print_area = f"A1:G{max(lastr, 4)}"
        ws.page_setup.orientation = "landscape"; ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0; ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.print_options.horizontalCentered = True
        ws.page_margins.left = ws.page_margins.right = 0.4; ws.page_margins.top = ws.page_margins.bottom = 0.5
        ws.oddFooter.center.text = f"{title} · &P / &N"; ws.oddFooter.center.size = 9
    try:
        from openpyxl.workbook.properties import CalcProperties
        wb.calculation = CalcProperties(fullCalcOnLoad=True)
    except Exception: pass
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out
