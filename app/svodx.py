"""«Свод (карантин) + туманлар номма-ном» Excel — юклашдан олдинги танловлар (24.09.2026, Жафар).

Модал ойнада уч қисм:
  1. Ўтган йил даври (божхона базасидан, аниқ сана бўйича):
       month_back — ўтган йилнинг олдинги ой охиригача (масалан 23.09 учун: 2025 йил 8 ойлик, 1 сентябрь ҳолатига)
       same_day   — ўтган йилнинг айнан шу кунигача   (23.09 учун: 2025 йил 23 сентябрь ҳолатига, 1.01–22.09)
       month_full — ўтган йилнинг шу ой охиригача      (23.09 учун: 2025 йил 9 ойлик, 1 октябрь ҳолатига)
  2. Мева-сабзавот қоидаси (жорий йил ҳам, ўтган йил ҳам):
       karantin — Бухорода етиштирилган (карантин рўйхати, экспортёридан қатъи назар), туман — етиштирилган жой
       exporter — Бухоро корхоналари экспорт қилган мева-сабзавот (етиштирилган жойидан қатъи назар), туман — корхона
  3. settings — «Sozlamalar»да киритилган ўтган йил кўрсаткичи (Тугаган йиллар натижалари / ўтган йил базаси).
       Танланса 1 ва 2 қисм ўчади: ўтган йил — Sozlamalar рақами, мева-сабзавот — карантин (расмий қоида).

Божхона базасида ўтган йил мева-сабзавотининг «етиштирилган жойи» йўқ — карантин қоидасида ўтган йил мева-сабзавоти
«Sozlamalar»даги натижалардан (ой охирида аниқ, оралиқда интерполяция) олинади; манба модалда кўрсатилади.
"""
from __future__ import annotations
import datetime as dt, calendar, json
from collections import defaultdict
from . import db, report, periods

PREV_MODES = ("month_back", "same_day", "month_full", "settings")
MEVA_MODES = ("karantin", "exporter")
MONTHS_GEN = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]


# ------------------------------------------------------------------ даврлар
def prev_end(D: str, mode: str) -> dt.date | None:
    """Ўтган йил даврининг охирги куни (шу кун ҳам киради). month_back январда йўқ (None)."""
    d = dt.date.fromisoformat(D); y = d.year - 1
    if mode == "month_back":
        if d.month == 1: return None
        return dt.date(y, d.month - 1, calendar.monthrange(y, d.month - 1)[1])
    if mode == "same_day":
        return dt.date(y, d.month, min(d.day, calendar.monthrange(y, d.month)[1]))
    if mode == "month_full":
        return dt.date(y, d.month, calendar.monthrange(y, d.month)[1])
    raise ValueError(mode)

def _as_of(end: dt.date) -> str:
    """«1 сентябрь ҳолатига» — давр охиридан кейинги кун."""
    n = end + dt.timedelta(days=1)
    return f"{n.day} {MONTHS_GEN[n.month - 1]}"

def period_label(D: str, mode: str) -> dict:
    """{short, col, cmp} — модал ва Excel сарлавҳалари учун."""
    if mode == "settings":
        return {"short": "«Sozlamalar»даги ўтган йил кўрсаткичи", "col": None, "cmp": None}
    end = prev_end(D, mode)
    if end is None: return {"short": "—", "col": None, "cmp": None}
    y = end.year
    if mode == "same_day":
        return {"short": f"{y} йил {_as_of(end)} ҳолатига (1.01–{end:%d.%m})",
                "col": f"{y} йил \n{_as_of(end)} ҳолатида амалдаги экспорт", "cmp": f"{y} йилнинг \nшу кунига нисбатан"}
    m = end.month
    return {"short": f"{y} йил {m} ойлик якуни ({_as_of(end)} ҳолатига)",
            "col": f"{y} йил \n{m} ойлик ({_as_of(end)} ҳолатида) амалдаги экспорт", "cmp": f"{y} йил {m} ойлигига нисбатан"}


# ------------------------------------------------------------------ ўтган йил (божхона базаси)
def _excluded_inns(con) -> set:
    """Жорий йилда ҳам ҳисобга кирмайдиганлар: «Бухоро эмас» ва алоҳида ҳисоб (SDK ва ҳ.к.)."""
    return report.not_bukhara_inns(con) | {r["inn"] for r in con.execute("SELECT inn FROM companies WHERE excluded=1")}

def base_prev(con, end: dt.date, kind: str) -> dict:
    """{district_code: сумма} — ўтган йил 1 январь – end, божхона базаси (items, ЭК), корхона тумани бўйича.
    kind: sanoat | meva (meva — Бухоро корхоналари экспорт қилган, етиштирилган жойидан қатъи назар). БНПЗ кирмайди."""
    skip = _excluded_inns(con); win = report.bukhara_windows(con)
    dist = {r["inn"]: r["district_code"] for r in con.execute("SELECT inn, district_code FROM companies")}
    out = defaultdict(float)
    for r in con.execute("""SELECT inn, rdate, sum(value) s FROM items WHERE regime='ЭК' AND kind=? AND year=? AND rdate<=?
                            GROUP BY inn, rdate""", (kind, end.year, end.isoformat())):
        if r["inn"] in skip or not report.in_window(win, r["inn"], r["rdate"]): continue
        out[dist.get(r["inn"]) or "?"] += r["s"] or 0.0
    return dict(out)

def karantin_prev(con, D: str, end: dt.date, code: str) -> tuple[float, str, str]:
    """Ўтган йил карантин мева-сабзавоти end кунигача: (қиймат, режим, изоҳ). Божхона базасида етиштирилган жой йўқ —
    Sozlamalar натижалари (N ойлик) + эски ўтган йил базаси якорлари бўйича; якорь бўлмаса 0."""
    y = int(D[:4])
    pts = [(d, v) for d, v, _ in periods.anchors(con, y, code, "meva")]
    names = {d: l for d, _, l in periods.anchors(con, y, report.REGION, "meva")}
    r = con.execute("SELECT prev_year_base, prev_year_base_days FROM prognoz WHERE year=? AND district_code=? AND kind='meva'", (y, code)).fetchone()
    if r and r["prev_year_base"] is not None and not any(d == int(r["prev_year_base_days"] or 273) for d, _ in pts):   # N ойлик натижа базадан устун
        days = int(r["prev_year_base_days"] or 273); pts.append((days, float(r["prev_year_base"])))
        names.setdefault(days, (db.get_setting(con, "prev_year_base_label") or f"ўтган йил базаси ({days} кун)").strip())
    if not pts: return 0.0, "none", "Sozlamalarda ўтган йил мева-сабзавот натижаси йўқ"
    day = end.timetuple().tm_yday
    v, mode = periods.interpolate(pts, day)
    srt = sorted({0, *(d for d, _ in pts)}); names.setdefault(0, "1 январь")
    if mode == "exact": note = f"«{names.get(day, '')}» (аниқ)"
    elif mode == "interp":
        lo = max(d for d in srt if d < day); hi = min(d for d in srt if d > day)
        note = f"«{names.get(lo, '')}» ва «{names.get(hi, '')}» орасида интерполяция"
    else: note = f"«{names.get(srt[-1], '')}» дан кунлик ўртача суръат билан"
    return v, mode, note


# ------------------------------------------------------------------ жорий йил мева-сабзавот (экспортёр бўйича)
def exporter_meva_current(con, D: str) -> dict:
    """{inn: {"m": [12], "day": x}} — Бухоро корхоналари экспорт қилган мева-сабзавот, жорий йил 1 январь – D.
    Бошланғич қолдиқ санасигача — божхона базаси (items, kind meva), ундан кейин — кунлик ГТД (Бухоро корхонасининг
    meva қаторлари + бошқа вилоятда етиштирилган meva_x)."""
    year = int(D[:4]); through = report.opening_date(con) or ""
    skip = _excluded_inns(con); win = report.bukhara_windows(con)
    out = defaultdict(lambda: {"m": [0.0] * 12, "day": 0.0})
    has_ob = con.execute("SELECT 1 FROM opening_balances WHERE year=? AND kind='meva' LIMIT 1", (year,)).fetchone()
    lim = min(through, D) if through else ""
    if not has_ob and lim:
        for r in con.execute("""SELECT inn, rdate, sum(value) s FROM items WHERE regime='ЭК' AND kind='meva' AND year=? AND rdate<=?
                                GROUP BY inn, rdate""", (year, lim)):
            if r["inn"] in skip or not report.in_window(win, r["inn"], r["rdate"]): continue
            out[r["inn"]]["m"][int(r["rdate"][5:7]) - 1] += r["s"] or 0.0
            if r["rdate"] == D: out[r["inn"]]["day"] += r["s"] or 0.0
    for (inn, kind), a in report.company_amounts(con, D).items():   # ГТД: қолдиқ санасидан кейин (Бухоро экспортёрлари)
        if kind != "meva" or inn in skip: continue
        for i, v in enumerate(a["m"]): out[inn]["m"][i] += v
        out[inn]["day"] += a["day"]
    return {k: v for k, v in out.items() if any(v["m"]) or v["day"]}


# ------------------------------------------------------------------ модал учун маълумот
def options(con, D: str | None = None) -> dict:
    D = D or report.last_data_date(con)
    if not D: raise ValueError("База бўш")
    month = int(D[5:7]); codes = [d["code"] for d in report.districts(con)]
    # жорий йил
    kar = report.karantin(con, D)
    cur_kar = sum(v["ytd"] for c, v in kar.items())
    cur_exp = sum(sum(a["m"]) for a in exporter_meva_current(con, D).values())
    cur_san = sum(sum(a["m"]) for (i, k), a in report.company_amounts(con, D).items() if k == "sanoat")
    per = []
    for mode in ("month_back", "same_day", "month_full"):
        end = prev_end(D, mode); lab = period_label(D, mode)
        if end is None:
            per.append({"mode": mode, "label": lab["short"], "disabled": True}); continue
        san = sum(base_prev(con, end, "sanoat").values())
        mexp = sum(base_prev(con, end, "meva").values())
        kv, km, kn = karantin_prev(con, D, end, report.REGION)
        per.append({"mode": mode, "label": lab["short"], "end": end.isoformat(), "sanoat": round(san, 1),
                    "meva": {"karantin": round(kv, 1), "karantin_mode": km, "karantin_note": kn, "exporter": round(mexp, 1)}})
    st = {k: report.prev_year_amount(con, report.REGION, k, D) for k in ("sanoat", "meva")}
    info = periods.prev_info(con, D)
    has_base = con.execute("SELECT 1 FROM prognoz WHERE year=? AND district_code=? AND prev_year_base IS NOT NULL", (int(D[:4]), report.REGION)).fetchone()
    stext = info.get("text") or (f"Ўтган йил базаси «{(db.get_setting(con, 'prev_year_base_label') or '').strip()}», {report.prev_year_days(con, D)} кунга мутаносиб" if has_base else "")
    # 25.09.2026 (Жафар): Sozlamalar → Тугаган йиллар натижалари — киритилган N ойлик даврлар рўйхати, аниқ рақам билан
    # (интерполяциясиз). Стандарт танлов — жорий ойга тенг ёки ундан кичик энг катта давр (сентябрда 9 ойлик).
    # 29.09.2026: даврлар «Амалда» тўпламлари бўйича (бир йилда бир нечта ном: Вазирлик, Ҳокимият …) — асосийси биринчи
    py = int(D[:4]) - 1; plist = []
    for p in periods.list_periods(con):
        if p["year"] != py or not p["filled"]: continue
        plist.append({"set_id": p["set_id"], "set_title": p.get("set_title") or "", "main": bool(p.get("set_main")),
                      "months": p["months"], "label": p["label"], "sanoat": round(p["by_kind"].get("sanoat") or 0.0, 1), "meva": round(p["by_kind"].get("meva") or 0.0, 1)})
    plist.sort(key=lambda x: (not x["main"], x["set_id"] or 0, x["months"]))
    mains = [p for p in plist if p["main"]] or plist
    default = max([p["months"] for p in mains if p["months"] <= month] or [p["months"] for p in mains] or [0])
    default_set = (mains[0]["set_id"] if mains else None)
    return {"date": D, "as_of": (dt.date.fromisoformat(D) + dt.timedelta(days=1)).isoformat(), "month": month,
            "current": {"sanoat": round(cur_san, 1), "meva": {"karantin": round(cur_kar, 1), "exporter": round(cur_exp, 1)}},
            "periods": per,
            "settings": {"available": bool(info.get("mode") != "none" or has_base), "text": stext,
                         "sanoat": round(st["sanoat"], 1), "meva": round(st["meva"], 1),
                         "periods": plist, "default_months": default, "default_set": default_set,
                         "sets": [{"id": x["id"], "title": x["title"], "main": bool(x["main"])} for x in periods.year_sets(con, py)]}}


# ------------------------------------------------------------------ дашбордга танловларни қўллаш
def apply(con, d: dict, prev_mode: str, meva_mode: str, sp=None, fs=None) -> dict:
    """dashboard() натижасини танловлар бўйича ўзгартиради: мева-сабзавот (жорий йил), ўтган йил (ҳар туман/тур), сарлавҳалар.
    sp — settings режимида Sozlamalardaги N ойлик давр (ой сони): ўтган йил ҳар туман/тур учун ўша даврнинг АНИҚ рақами;
    "auto" ёки йўқ бўлса — эски тартиб (кунга интерполяция, dashboard() берган prev)."""
    if prev_mode not in PREV_MODES: raise ValueError("Ўтган йил даври нотўғри")
    if meva_mode not in MEVA_MODES: raise ValueError("Мева-сабзавот қоидаси нотўғри")
    if prev_mode == "settings": meva_mode = "karantin"
    D = d["date"]; cm = d["month"]
    comps = [c for c in d["companies"] if c["t"] != "meva"]   # номма-номда карантин қатори ёки экспортёрлар — икки марта эмас
    if meva_mode == "exporter":
        cmap = report.companies_map(con); md = defaultdict(lambda: {"ytd": 0.0, "month": 0.0, "day": 0.0})
        for inn, a in exporter_meva_current(con, D).items():
            c = cmap.get(inn, {}); dc = c.get("district_code")
            comps.append({"inn": inn, "name": c.get("name") or inn, "d": dc, "t": "meva", "tarmoq": "Мева-сабзавот",
                          "m": [round(x, 3) for x in a["m"][:cm]], "day": round(a["day"], 3), "total": round(sum(a["m"]), 3)})
            md[dc]["ytd"] += sum(a["m"]); md[dc]["month"] += a["m"][cm - 1]; md[dc]["day"] += a["day"]
        for x in d["districts"]: x["meva"] = {k: round(v, 3) for k, v in md.get(x["code"], {"ytd": 0, "month": 0, "day": 0}).items()}
    d["companies"] = comps
    # ўтган йил
    if prev_mode != "settings":
        end = prev_end(D, prev_mode)
        san = base_prev(con, end, "sanoat") if end else {}
        mev = (base_prev(con, end, "meva") if meva_mode == "exporter" else
               {x["code"]: karantin_prev(con, D, end, x["code"])[0] for x in d["districts"]}) if end else {}
        for x in d["districts"]:
            s, m = san.get(x["code"], 0.0), mev.get(x["code"], 0.0)
            for k, v in (("sanoat", s), ("meva", m), ("all", s + m)):
                x["plan"].setdefault(k, {})["prev"] = v
        rs, rm = sum(san.values()), sum(mev.values())
        for k, v in (("sanoat", rs), ("meva", rm), ("all", rs + rm)): d.setdefault("region_plan", {}).setdefault(k, {})["prev"] = v
        lab = period_label(D, prev_mode)
        d["prev_col_label"], d["prev_cmp_label"] = lab["col"], lab["cmp"]
        src = "божхона базаси" + (", мева-сабзавот (карантин) — Sozlamalar натижаларидан" if meva_mode == "karantin" else "")
        d["prev_year_source"] = {"mode": prev_mode, "text": f"Ўтган йил — {lab['short']}, {src}"}
    else:
        py = int(D[:4]) - 1
        sp = int(sp) if sp is not None and str(sp).isdigit() and 1 <= int(sp) <= 12 else None
        pid = periods.find(con, py, sp, fs) if sp else None
        st = periods.get_set(con, fs) if fs else periods.get_set(con, periods.main_set(con, py))
        if pid:
            for x in d["districts"]:
                s = periods._value(con, pid, x["code"], "sanoat") or 0.0; m = periods._value(con, pid, x["code"], "meva") or 0.0
                for k, v in (("sanoat", s), ("meva", m), ("all", s + m)):
                    x["plan"].setdefault(k, {})["prev"] = v
            rs = periods._value(con, pid, report.REGION, "sanoat") or 0.0; rm = periods._value(con, pid, report.REGION, "meva") or 0.0
            for k, v in (("sanoat", rs), ("meva", rm), ("all", rs + rm)): d.setdefault("region_plan", {}).setdefault(k, {})["prev"] = v
            lbl = periods.label(py, sp)
            d["prev_col_label"] = f"{py} йил \n{sp} ойлик амалдаги экспорт"; d["prev_cmp_label"] = f"{py} йил {sp} ойлигига нисбатан"
            d["prev_year_source"] = {"mode": "settings", "text": f"Ўтган йил — Sozlamalar → Амалда" + (f" «{st['title']}»" if st else "") + f": «{lbl}» (аниқ рақам)"}
            d["settings_months"] = sp
        else:
            d["prev_col_label"] = f"{py} йилнинг \nшу кунигача амалдаги экспорт"; d["prev_cmp_label"] = f"{py} йилнинг \nшу кунига нисбатан"
    d["meva_mode"] = meva_mode; d["prev_mode"] = prev_mode
    return d
