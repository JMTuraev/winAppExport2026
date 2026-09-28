"""Daily customs GTD file: parse -> classify Bukhara rows -> control checks -> save (transaction)."""
from __future__ import annotations
import hashlib, json, re, datetime as dt
from pathlib import Path
from . import db
from .xl import read_sheet, Header, inn_str, num, _norm

REGION_CODE = "1706"
REGION_RX = re.compile(r"бухар(?!ий)|buxoro(?!y)|bukhara|buxor(?!iy)|бухоро(?!й)", re.I)   # not «S.Buxoriy ko'chasi»
# an address that names another region («Kashkadara region … Karshi - Bukhara») is not a Bukhara candidate
OTHER_REGION_RX = re.compile(r"(кашкадар\w*|qashqadaryo|kashkadar\w*|самарканд\w*|samarqand|samarkand|навоий|навои\w*|navoiy|navoi|ташкент\w*|toshkent|tashkent|андижан\w*|andijon|andijan|"
                             r"наманган\w*|namangan|ферган\w*|farg\W?ona|fergana|сурхандар\w*|surxondaryo|surkhandar\w*|джизак\w*|jizzax|jizzakh|сырдар\w*|sirdaryo|syrdar\w*|"
                             r"хорезм\w*|xorazm|khorezm|каракалпак\w*|qoraqalpog\w*|karakalpak\w*)[\s,.'`ʻ‘’-]*(вилоят|viloyat|region|обл|respublika|республика)", re.I)
DISTRICT_KW = {  # keyword (lowercase, regex) -> district code
    # the customs .xls files write ғ/қ/ў/ҳ/‘ as \x1a, which xl.py strips: «шаҳри»→«шари», «Ғиждувон»→«иждувон»,
    # «Қоровулбозор»→«оровулбозор», «Пешкў»→«пешк» — every Cyrillic keyword below must also match the damaged form
    r"\bг\.?\s*бухара|город бухара|buxoro sh|бухоро ш|buxoro shah|бухоро шаҳ?ри": "1706401",
    r"\bг\.?\s*каган|город каган|kogon sh|когон ш|kogon shah|когон шаар|когон шаҳ?ри": "1706403",
    r"бухарский р|buxoro tuman|бухоро туман": "1706207",
    r"вабкент|vobkent|вобкент": "1706212",
    r"жондор|jondor": "1706246",
    r"каганский|kogon tuman|когон туман": "1706219",
    r"каракул(?!ов)|qorako|қ?оракў?л|qorakol": "1706230",          # not «Каракулова» (street)
    r"караулбазар|qorovulbozor|қ?оровулбозор|qoravulbozor": "1706232",
    r"\bалат|\bolot\b|олот": "1706204",
    r"пешк[уў]?|peshku": "1706240",
    r"ромитан|romitan|рамитан": "1706242",
    r"шафиркан|shofirkon|шофиркон": "1706258",
    r"гиждуван|g['’‘ʻ]?ijduvon|ғ?иждувон|gijduvon": "1706215",
}
COLS = {  # logical name -> header candidates (found by name; order is irrelevant)
    "inn": ["ИНН (гр.2)", "ИНН"], "date": ["Дата выгрузки"], "regime": ["Режим"],
    "exporter": ["Экспортер (гр.2)", "Экспортер"], "address": ["Адресс (гр.2)", "Адрес (гр.2)", "Адресс"],
    "country": ["Страна назначения"], "item_no": ["Номер товара"], "tnved": ["КОД ТНВЕД товара", "КОД ТНВЕД"],
    "product": ["Наименование товара"], "qty": ["Количество"], "netto": ["Нетто"],
    "stat_usd": ["Стат.стоимость в тыс.долл", "Стат,стоимость в тыс,долл", "Стат.стоимость"],
    "invoice_usd": ["Фактурная стоимость в тыс.долл", "Фактурная стоимость в тыс,долл"],
    "gtd_no": ["Код таможенного поста (G7.гр)", "Код таможенного поста (G7", "Код таможенного поста"],
    "grown_region": ["Область выращенной продукции"], "grown_district": ["Район (город) выращенной продукции", "Район (город) выращенной"],
}

def sha256(path, data: bytes | None = None) -> str:
    if data is not None: return hashlib.sha256(data).hexdigest()
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
    return h.hexdigest()

def parse_file(path, data: bytes | None = None) -> dict:
    from .xl import sheet_names
    names = [n.strip().lower() for n in sheet_names(path, data=data)]
    if "номманом" in names:
        raise ValueError("Bu o'z kunlik jadvalingiz («… йил экспорт»), bojxona GTD fayli emas. Uni Sozlamalar → «2. O'z jadvalingiz» bo'limida yuklang.")
    if "база" in names:
        raise ValueError("Bu bojxonaning oylik bazasi. Uni Sozlamalar → «1. Bojxona oylik bazasi» bo'limida yuklang.")
    rows = read_sheet(path, 0, data=data)
    try:
        h = Header(rows, ["ИНН", "Дата выгрузки", "Стат"])
    except ValueError:
        raise ValueError("Bu bojxonaning kunlik GTD fayli emas: «ИНН (гр.2)», «Дата выгрузки», «Стат.стоимость» ustunlari topilmadi.")
    hdr = rows[h.row_idx]
    cidx = {}
    missing = []
    for key, cands in COLS.items():
        c = h.col(*cands, required=False)
        if c is None: missing.append(cands[0])
        cidx[key] = c
    for must in ("inn", "date", "stat_usd", "gtd_no", "item_no"):
        if cidx[must] is None: raise ValueError("Bojxona faylida majburiy ustun topilmadi: " + COLS[must][0])
    out = []; empty_inn = 0
    for r in rows[h.row_idx + 1:]:
        if r[cidx["inn"]] in (None, "") and r[cidx["gtd_no"]] in (None, ""): continue
        rec = {k: (r[c] if c is not None else None) for k, c in cidx.items()}
        rec["inn"] = inn_str(rec["inn"])
        if not rec["inn"]: empty_inn += 1          # INN бўш: never a company / candidate; counted for the preview warning
        rec["stat_usd"] = num(rec["stat_usd"]); rec["invoice_usd"] = num(rec["invoice_usd"]); rec["netto"] = num(rec["netto"]); rec["qty"] = num(rec["qty"])
        rec["date"] = str(rec["date"] or "")[:10]
        rec["item_no"] = inn_str(rec["item_no"])
        rec["dedup_key"] = f"{rec['gtd_no']}#{rec['item_no']}"
        rec["raw"] = {str(hdr[i]): v for i, v in enumerate(r) if i < len(hdr) and hdr[i] not in (None, "")}
        out.append(rec)
    return {"rows": out, "columns_found": {k: (hdr[c] if c is not None else None) for k, c in cidx.items()}, "missing": missing, "n_cols": len(hdr), "empty_inn": empty_inn}

def guess_district(address: str) -> str | None:
    a = (address or "").lower()
    for rx, code in DISTRICT_KW.items():
        if re.search(rx, a): return code
    return None

def _dmy(iso): return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}" if iso else "—"

MEVA_HS = ("07", "08")

def in_period(c, d) -> bool:
    """Bukhara period of a company (bukhara_from..bukhara_to, either side open): does date d fall inside it?"""
    if not c: return True
    lo, hi = c.get("bukhara_from") or "", c.get("bukhara_to") or "9999"
    return lo <= (d or "") <= hi

def is_bukhara(c, inn=None, meva_inns=(), d=None) -> bool:
    """Bukhara exporter: customs base registry, confirmed Bukhara, a Bukhara company found in GTD, or a meva company of номманом; never when marked «not Bukhara».
    With a date d the company's Bukhara period is checked too (moved into / out of the region)."""
    if c and c.get("bukhara") == 0: return False
    if c and d and not in_period(c, d): return False
    if inn in meva_inns: return True
    return bool(c) and bool(c.get("in_base") or c.get("bukhara") == 1 or c.get("source") == "gtd")

def preview(con, path, expected_date: str | None = None, force: bool = False, replace: bool = False, data: bytes | None = None) -> dict:
    """Classify without writing. Returns everything the UI needs for the control panel.
    replace=True: saved uploads of the same day(s) will be voided on save, so their rows are not counted as duplicates."""
    path = Path(path)
    if data is None: data = path.read_bytes()      # one read; the file is never opened again (no Windows lock, no re-open error)
    p = parse_file(path, data=data)
    rows = p["rows"]
    digest = sha256(path, data=data)
    file_dates = {r["date"] for r in rows}
    same_day = []
    for u in con.execute("SELECT id, filename, report_dates, loaded_at, sum_sanoat, sum_meva FROM uploads WHERE status='saved' AND sha256<>?", (digest,)):
        ud = set(json.loads(u["report_dates"] or "[]"))
        if ud & file_dates:
            same_day.append({"id": u["id"], "filename": u["filename"], "loaded_at": u["loaded_at"], "dates": sorted(ud), "subset": ud <= file_dates,
                             "sum": round((u["sum_sanoat"] or 0) + (u["sum_meva"] or 0), 3)})
    reg = {r["inn"]: dict(r) for r in con.execute("SELECT inn,name,district_code,kind,confirmed,excluded,in_base,bukhara,bukhara_from,bukhara_to,source FROM companies")}
    dnames = {r["code"]: r["name_uz"] for r in con.execute("SELECT code,name_uz FROM districts")}
    skip_ids = [u["id"] for u in same_day] if replace else []
    existing_keys = set(k for (k,) in con.execute("SELECT dedup_key FROM gtd_rows WHERE voided=0" + (f" AND upload_id NOT IN ({','.join('?' * len(skip_ids))})" if skip_ids else ""), skip_ids))
    through = db.get_setting(con, "opening_through_date")
    base_keys = set(k for (k,) in con.execute("SELECT key FROM items WHERE regime='ЭК'"))
    drop_inns = set(db.reference().get("exclude_inns", {}))
    # meva-sabzavot companies of номманом: all their GTD rows go to their own номманом row (as the manual routine did)
    meva_inns = {i for (i,) in con.execute("SELECT inn FROM template_inns WHERE category='meva'")} or \
                {i for (i,) in con.execute("SELECT inn FROM companies WHERE kind='meva' AND source='nomma-nom'")}
    tpl_through = db.get_setting(con, "template_through")
    sanoat, meva, candidates, dups, other_region_meva, excluded_rows, warnings = [], [], [], [], [], [], []
    meva_x, not_bukhara = [], []
    in_base, dropped = [], []
    dates = {}
    empty_inn = []
    for r in rows:
        dates[r["date"]] = dates.get(r["date"], 0) + 1
        if not r["inn"]:
            empty_inn.append(r); continue        # INN бўш: not a Bukhara row, never a «new company» candidate (companies.inn='' would be written)
        if r["dedup_key"] in base_keys:
            in_base.append(r); continue          # already inside the monthly customs base (БНПЗ too): never counted twice
        if r["inn"] in drop_inns:
            r["kind"] = "bnpz"; r["district_code"] = "1706232"
            (dups if r["dedup_key"] in existing_keys else dropped).append(r); continue
        gr = str(r["grown_region"] or "")
        buk = is_bukhara(reg.get(r["inn"]), r["inn"], meva_inns, r["date"])
        if gr.strip():
            if gr.startswith(REGION_CODE):
                # grown in Bukhara: karantin svod by the grown district (any exporter); a Bukhara exporter also gets its номманом meva row
                gd = str(r["grown_district"] or "")[:7]
                r["kind"] = "meva"; r["district_code"] = gd if gd in dnames else None; r["buk_exporter"] = buk
                if not r["district_code"]:
                    r["ask"] = "md"; r["ask_key"] = f"md:{r['inn']}:{str(r['grown_district'] or '').strip()}"
                (dups if r["dedup_key"] in existing_keys else meva).append(r)
            elif buk:
                # Bukhara exporter, grown elsewhere: not karantin; the general svod's meva-sabzavot (номманом «Мева-сабзавотлар» row)
                r["kind"] = "meva_x"; r["district_code"] = reg.get(r["inn"], {}).get("district_code")
                (dups if r["dedup_key"] in existing_keys else meva_x).append(r)
            else:
                other_region_meva.append(r)  # other region's exporter and product: not Bukhara
            continue
        if r["inn"] in reg and reg[r["inn"]]["excluded"]:
            r["kind"] = "memo"; r["district_code"] = reg[r["inn"]]["district_code"]
            (dups if r["dedup_key"] in existing_keys else excluded_rows).append(r); continue
        if r["inn"] in reg and (reg[r["inn"]]["bukhara"] == 0 or not in_period(reg[r["inn"]], r["date"])):
            # «Бухоро эмас — ҳисобга киритилмасин» — also for a company that is in the customs base registry (e.g. BAHT SAMARQAND TEKS),
            # and a day outside the company's Bukhara period (moved into / out of the region)
            r["kind"] = "not_bukhara"; r["district_code"] = reg[r["inn"]]["district_code"]
            (dups if r["dedup_key"] in existing_keys else not_bukhara).append(r); continue
        if r["inn"] in reg and not (reg[r["inn"]]["in_base"] or reg[r["inn"]]["bukhara"] == 1 or reg[r["inn"]]["source"] == "gtd"):
            # listed only in номманом, not in the customs base registry: Bukhara must be confirmed (e.g. MOVEX LINE)
            addr = str(r["address"] or "")
            r["district_code"] = reg[r["inn"]]["district_code"]
            if reg[r["inn"]]["bukhara"] == 0:
                r["kind"] = "not_bukhara"; (dups if r["dedup_key"] in existing_keys else not_bukhara).append(r); continue
            r["kind"] = "sanoat"; r["candidate"] = True; r["nomma_only"] = True
            r["address_ok"] = bool(guess_district(addr) or (REGION_RX.search(addr) and not OTHER_REGION_RX.search(addr)))
            (dups if r["dedup_key"] in existing_keys else candidates).append(r); continue
        if r["inn"] in reg:
            r["kind"] = "sanoat"; r["district_code"] = reg[r["inn"]]["district_code"]
            if reg[r["inn"]]["confirmed"] == 0: r["unconfirmed"] = True
            if str(r["tnved"] or "").startswith(MEVA_HS): r["ask"] = "kind"; r["ask_key"] = f"k:{r['inn']}"
            (dups if r["dedup_key"] in existing_keys else sanoat).append(r)
        elif guess_district(str(r["address"] or "")) or (REGION_RX.search(str(r["address"] or "")) and not OTHER_REGION_RX.search(str(r["address"] or ""))):
            r["kind"] = "sanoat"; r["district_code"] = guess_district(str(r["address"] or "")); r["candidate"] = True
            (dups if r["dedup_key"] in existing_keys else candidates).append(r)
    # in-file duplicates
    seen = set(); infile_dup = 0
    for r in sanoat + meva + meva_x + not_bukhara + candidates + excluded_rows + dropped:
        if r["dedup_key"] in seen: infile_dup += 1
        seen.add(r["dedup_key"])
    checks = []
    def chk(ok, title, detail, level="warn"): checks.append({"ok": bool(ok), "level": "ok" if ok else level, "title": title, "detail": detail})
    nomma_only = {r["inn"]: r for r in candidates if r.get("nomma_only")}
    if nomma_only:
        chk(False, f"Bojxona bazasida yo'q korxona: {len(nomma_only)} ta — Buxoro korxonasimi?",
            "; ".join(f"{r['exporter']} ({r['inn']}) {sum(x['stat_usd'] for x in candidates if x['inn'] == r['inn']):,.2f} ming $ — manzil: {r['address']}" for r in nomma_only.values())
            + " · номманом da bor, lekin bojxona bazasida yo'q. Buxoro bo'lsa tumanini tanlang, bo'lmasa «qo'shilmasin» qoldiring (keyingi kunlarda so'ralmaydi).", "warn")
    if not_bukhara:
        per = {r["inn"] for r in not_bukhara if reg.get(r["inn"], {}).get("bukhara") != 0}
        chk(True, f"«Buxoro emas» deb belgilangan yoki Buxoro davridan tashqari: {len({r['inn'] for r in not_bukhara})} korxona, {sum(r['stat_usd'] for r in not_bukhara):,.2f} ming $",
            ", ".join(sorted({r['exporter'] + (" (davr tashqarisi)" if r["inn"] in per else "") for r in not_bukhara})) + " — hisobga olinmaydi (Korxonalar menyusida o'zgartirish mumkin)")
    if meva_x: chk(True, f"Buxoro korxonasi, boshqa viloyatda o'stirilgan meva-sabzavot: {len(meva_x)} qator, {sum(x['stat_usd'] for x in meva_x):,.2f} ming $",
                   ", ".join(sorted({x['exporter'] or x['inn'] for x in meva_x})) + " — karantin svodga kirmaydi; umumiy svodning meva-sabzavot qismiga (номманом «Мева-сабзавотлар» qatori) yoziladi")
    if tpl_through and any(d <= tpl_through for d in dates):
        chk(False, f"Excel shabloningiz {tpl_through[8:10]}.{tpl_through[5:7]}.{tpl_through[:4]} gacha", "bu kun jadvalingizda allaqachon bor — saytdagi hisob (dashboard, Korxonalar) uchun saqlanadi; Excelga faqat jadvalda yo'q (yangi) korxonalarning qatorlari qo'shiladi", "warn")
    if dropped: chk(True, f"БНПЗ: {len(dropped)} qator, {sum(x['stat_usd'] for x in dropped):,.2f} ming $",
                    "asosiy hisobotga kirmaydi; faqat «СВОД 450 млн» varag'ida Қоровулбозор tumaniga qo'shiladi")
    buk_in_base = [x for x in in_base if x["inn"] in reg]
    chk(not buk_in_base, "Oylik bojxona bazasida yo'q" if not buk_in_base else f"Oylik bazada allaqachon bor: {len(buk_in_base)} qator",
        f"{sum(x['stat_usd'] for x in buk_in_base):,.2f} ming $ — ikki marta qo'shilmaydi, tashlab yuboriladi" if buk_in_base else "ГТД lar bojxona oylik bazasi bilan takrorlanmaydi")
    n_reg = len(reg)
    chk(n_reg > 0, "Korxonalar reyestri bor" if n_reg else "Korxonalar reyestri bo'sh",
        f"{n_reg} ta INN" if n_reg else "Avval Sozlamalar → «Boshlang'ich ma'lumot» bo'limida bojxona oylik bazasini yuklang: Buxoro qatorlari INN bo'yicha ajratiladi", "bad")
    # address -> new company (candidate) and grown_region -> karantin meva-sabzavot: without them rows are silently lost, so the file is refused
    critical = {COLS["inn"][0], COLS["date"][0], COLS["address"][0], COLS["grown_region"][0]}
    chk(not p["missing"], "Ustunlar topildi", f"{p['n_cols']} ustun; kerakli {len(COLS)-len(p['missing'])}/{len(COLS)} nom bo'yicha aniqlandi" + (" · topilmadi: " + ", ".join(p["missing"]) if p["missing"] else "")
        + (" — «Адресс» ustunisiz yangi korxona, «Область выращенной продукции» ustunisiz karantin meva-sabzavot aniqlanmaydi: to'liq faylni yuklang" if any(m in critical for m in p["missing"]) else ""),
        "bad" if any(m in critical for m in p["missing"]) else "warn")
    if empty_inn:
        chk(False, f"INN бўш: {len(empty_inn)} қатор", f"{sum(r['stat_usd'] for r in empty_inn):,.2f} ming $ — INN siz qator korxonaga bog'lanmaydi, hisobga olinmaydi (ГТД: " + ", ".join(sorted({str(r['gtd_no']) for r in empty_inn})[:5]) + ")", "warn")
    prev = con.execute("SELECT filename, loaded_at FROM uploads WHERE sha256=? AND status='saved'", (digest,)).fetchone()
    chk(prev is None, "Fayl avval yuklanmagan" if prev is None else "Bu fayl allaqachon yuklangan", "hash mos kelmadi" if prev is None else f"«{prev['filename']}» ({prev['loaded_at']}) — aynan shu fayl; qayta saqlanmaydi", "bad")
    dl = sorted(dates)
    chk(len(dl) == 1, "Sana: " + (", ".join(dl) if dl else "—"), f"«Дата выгрузки» bo'yicha {len(dl)} kun" + ("" if len(dl) == 1 else " — kunlarga bo'lib saqlanadi"), "warn")
    if not expected_date:
        chk(False, "Kun tanlanmagan", "kalendardan fayl sanasini tanlang — har bir GTD o'z kuniga saqlanadi", "bad")
    else:
        chk(expected_date in dl, "Fayl sanasi = tanlangan kun" if expected_date in dl else f"Fayl boshqa kunga tegishli: {', '.join(_dmy(d) for d in dl)}",
            f"tanlangan kun {_dmy(expected_date)}" + ("" if expected_date in dl else f" — kalendarda {_dmy(dl[0]) if dl else '?'} ni tanlab, qayta yuklang"), "bad")
    if same_day:
        names = "; ".join(f"«{u['filename']}» ({u['loaded_at'][:16]}, {u['sum']:,.2f} ming $)" for u in same_day)
        if not replace:
            chk(False, "Bu kunga fayl allaqachon yuklangan", names + " — yangisini saqlash uchun «Eskisini almashtirish» ni belgilang: eski yuklash bekor qilinadi, tarixda qoladi", "bad")
        elif not all(u["subset"] for u in same_day):
            chk(False, "Almashtirib bo'lmaydi", "eski yuklash boshqa kunlarni ham o'z ichiga oladi (" + ", ".join(_dmy(d) for u in same_day for d in u["dates"]) + ") — uni «Nazorat va tarix» da bekor qiling", "bad")
        else:
            chk(True, "Almashtiriladi: " + names, "saqlanganda eski yuklash bekor qilinadi (o'chirilmaydi), o'rniga shu fayl yoziladi")
    if through and not force: chk(all(d > through for d in dl), "Sana qoldiq davridan keyin", f"yil boshidan {through} gacha bo'lgan davr номманом qoldig'idan olingan; undan oldingi sana takror bo'ladi", "bad")
    chk(not dups and not infile_dup, "Dublikat GTD yo'q", f"bazada bor: {len(dups)}, fayl ichida takror: {infile_dup}" if (dups or infile_dup) else f"{len(seen)} kalit (ГТД № + товар №) bazada uchramadi", "warn")
    new_c = [r for r in candidates if not r.get("nomma_only")]
    chk(not new_c, f"Yangi korxona: {len(set(r['inn'] for r in new_c))} ta tasdiqlang" if new_c else "Yangi korxona yo'q", "; ".join(f"{r['exporter']} ({r['inn']}) → {dnames.get(r['district_code'],'tuman aniqlanmadi')}" for r in {r['inn']: r for r in new_c}.values()) or "hamma INN reyestrda", "warn")
    if meva:
        mb = [r for r in meva if r.get("buk_exporter")]
        chk(True, f"Buxoro karantini (o'stirilgan joyi 1706): {len(meva)} qator, {sum(r['stat_usd'] for r in meva):,.2f} ming $",
            "karantin svodga o'stirilgan tuman bo'yicha" + (f"; shundan Buxoro korxonalari {sum(r['stat_usd'] for r in mb):,.2f} ming $ — umumiy svodning meva-sabzavot qismiga ham" if mb else ""))
    questions = {}
    for r in meva + sanoat:
        if not r.get("ask") or r["dedup_key"] in existing_keys: continue
        q = questions.setdefault(r["ask_key"], {"key": r["ask_key"], "type": r["ask"], "inn": r["inn"], "name": reg.get(r["inn"], {}).get("name") or r["exporter"],
                                                "district_code": reg.get(r["inn"], {}).get("district_code"), "grown": str(r["grown_district"] or "").strip(),
                                                "products": [], "rows": 0, "sum": 0.0})
        q["rows"] += 1; q["sum"] = round(q["sum"] + r["stat_usd"], 3)
        pr = (r["product"] or "")[:60]
        if pr and pr not in q["products"] and len(q["products"]) < 3: q["products"].append(pr)
    questions = list(questions.values())
    qm = [q for q in questions if q["type"] == "md"]; qk = [q for q in questions if q["type"] == "kind"]
    if qm: chk(False, f"Buxoro karantini, lekin tumani aniqlanmadi: {len(qm)} ta — tumanni tanlang",
               "; ".join(f"{q['name']} · «{q['grown'] or 'tuman ko‘rsatilmagan'}» · {q['sum']:,.2f} ming $" for q in qm) + " — tanlanmasa saqlanmaydi", "warn")
    if qk: chk(False, f"Meva-sabzavot kodi (07/08), o'stirilgan viloyati ko'rsatilmagan: {len(qk)} korxona — qayerga yozishni tanlang",
               "; ".join(f"{q['name']} · {q['sum']:,.2f} ming $" for q in qk) + " — sanoat, umumiy svod meva-sabzavoti yoki Buxoro karantini", "warn")
    if excluded_rows: chk(True, f"Alohida hisobdagi korxonalar (БНПЗ, SDK): {len(excluded_rows)} qator", "; ".join(f"{r['exporter']} {r['stat_usd']:.2f}" for r in excluded_rows[:5]) + " — asosiy jamiga qo'shilmaydi, номманом pastidagi alohida qatorga yoziladi")
    s_san = round(sum(r["stat_usd"] for r in sanoat), 3); s_mev = round(sum(r["stat_usd"] for r in meva), 3); s_cand = round(sum(r["stat_usd"] for r in candidates), 3)
    s_mx = round(sum(r["stat_usd"] for r in meva_x), 3)
    chk(True, "Nazorat summasi", f"saqlanadi: sanoat {s_san:,.2f} + karantin meva-sabzavot {s_mev:,.2f}" + (f" + svod meva-sabzavot {s_mx:,.2f}" if meva_x else "") + (f" + nomzodlar {s_cand:,.2f} (tasdiqlansa)" if candidates else ""))
    # company aggregation for the results table
    agg = {}
    for r in sanoat + candidates:
        a = agg.setdefault(r["inn"], {"inn": r["inn"], "name": reg.get(r["inn"], {}).get("name") or r["exporter"], "district": dnames.get(r["district_code"], "?"), "gtd": set(), "sum": 0.0, "candidate": r.get("candidate", False)})
        a["gtd"].add(r["gtd_no"]); a["sum"] += r["stat_usd"]
    companies = sorted(({**a, "gtd": len(a["gtd"]), "sum": round(a["sum"], 3)} for a in agg.values()), key=lambda x: -x["sum"])
    return {"file": path.name, "sha256": digest, "size": path.stat().st_size, "rows_total": len(rows), "dates": dates, "same_day": same_day, "replace": replace,
            "columns_found": p["columns_found"], "checks": checks, "can_save": all(c["ok"] or c["level"] != "bad" for c in checks),
            "counts": {"sanoat": len(sanoat), "meva": len(meva), "candidates": len(candidates), "dups": len(dups) + infile_dup, "other_region_meva": len(other_region_meva), "meva_x": len(meva_x), "not_bukhara": len(not_bukhara), "nomma_only": len(nomma_only), "excluded": len(excluded_rows), "in_base": len(buk_in_base), "bnpz": len(dropped), "new_inns": len(set(r["inn"] for r in candidates)), "empty_inn": len(empty_inn)},
            "sums": {"sanoat": s_san, "meva": s_mev, "meva_x": s_mx, "candidates": s_cand, "memo": round(sum(r["stat_usd"] for r in excluded_rows), 3)},
            "companies": companies, "questions": questions,
            "candidates": [{"inn": r["inn"], "name": r["exporter"], "address": r["address"], "district_code": r["district_code"], "district": dnames.get(r["district_code"]),
                            "nomma_only": bool(r.get("nomma_only")), "address_ok": bool(r.get("address_ok")),
                            "sum": round(sum(x["stat_usd"] for x in candidates if x["inn"] == r["inn"]), 3)} for r in {r["inn"]: r for r in candidates}.values()],
            "meva_rows": [{"date": r["date"], "inn": r["inn"], "name": r["exporter"], "grown_district": r["grown_district"], "product": (r["product"] or "")[:60], "country": r["country"], "netto": r["netto"], "stat_usd": r["stat_usd"]} for r in meva],
            "_rows": {"sanoat": sanoat, "meva": meva, "meva_x": meva_x, "not_bukhara": not_bukhara, "candidates": candidates, "memo": excluded_rows, "bnpz": dropped}}

_REF = None
def reference():
    global _REF
    if _REF is None:
        _REF = json.loads((Path(__file__).resolve().parent / "templates" / "reference.json").read_text(encoding="utf-8"))
    return _REF

def new_company_attrs(con, district_code, tnved_amounts):
    """Fill номманом columns for a company first seen in a GTD file: tarmoq/uyushma from HS code, district texts from neighbours
    (falls back to the built-in reference when the base has no номманом companies yet)."""
    out = {"tarmoq": None, "uyushma": None, "hudud": None, "rus_district": None, "district_full": None}
    by = {}
    for code, amt in tnved_amounts:
        by[code[:4]] = by.get(code[:4], 0) + amt
    for hs4, _ in sorted(by.items(), key=lambda x: -x[1]):
        m = con.execute("SELECT tarmoq, uyushma FROM tnved_map WHERE code=?", (hs4,)).fetchone() or \
            con.execute("SELECT tarmoq, uyushma FROM tnved_map WHERE code=?", (hs4[:2],)).fetchone()
        if m: out["tarmoq"], out["uyushma"] = m["tarmoq"], m["uyushma"]; break
        ref = reference()["tnved_map"].get(hs4) or reference()["tnved_map"].get(hs4[:2])
        if ref: out["tarmoq"], out["uyushma"] = ref; break
    if district_code:
        for col in ("hudud", "rus_district", "district_full"):
            r = con.execute(f"""SELECT {col} v, count(*) n FROM companies WHERE district_code=? AND source='nomma-nom' AND {col} IS NOT NULL
                               AND trim({col})<>'' AND typeof({col})='text' GROUP BY {col} ORDER BY n DESC LIMIT 1""", (district_code,)).fetchone()
            out[col] = r["v"] if r else (reference()["districts"].get(district_code) or {}).get(col)
    return out

def apply_answers(pv: dict, answers: dict | None, district_codes) -> None:
    """Questions of the preview: md:<inn>:<grown> -> {district_code}; k:<inn> -> {kind: sanoat|meva_x|meva, district_code (for meva)}."""
    answers = answers or {}
    missing = []
    for q in pv.get("questions", []):
        a = answers.get(q["key"]) or {}
        if q["type"] == "md" and a.get("district_code") not in district_codes: missing.append(q["name"])
        if q["type"] == "kind" and (a.get("kind") not in ("sanoat", "meva_x", "meva") or (a.get("kind") == "meva" and a.get("district_code") not in district_codes)): missing.append(q["name"])
    if missing: raise ValueError("Meva-sabzavot savollariga javob bering: " + ", ".join(dict.fromkeys(missing)))
    for r in list(pv["_rows"]["meva"]) + list(pv["_rows"]["sanoat"]):
        a = answers.get(r.get("ask_key") or "")
        if not a: continue
        if r["ask"] == "md": r["district_code"] = a["district_code"]
        elif a["kind"] == "meva": r["kind"] = "meva"; r["district_code"] = a["district_code"]
        elif a["kind"] == "meva_x": r["kind"] = "meva_x"

def save(con, path, preview_data: dict | None = None, accepted_candidates: dict | None = None, backup=True, answers: dict | None = None, data: bytes | None = None) -> dict:
    """Write the file's Bukhara rows in ONE transaction. accepted_candidates: {inn: {district_code, name}} for new companies to add."""
    pv = preview_data or preview(con, path, data=data)
    if not pv["can_save"]:
        raise ValueError("Saqlab bo'lmaydi: " + "; ".join(c["title"] for c in pv["checks"] if not c["ok"] and c["level"] == "bad"))
    apply_answers(pv, answers, {r[0] for r in con.execute("SELECT code FROM districts")})
    accepted_candidates = accepted_candidates or {}
    rows = list(pv["_rows"]["sanoat"]) + list(pv["_rows"]["meva"]) + list(pv["_rows"].get("meva_x", [])) + list(pv["_rows"].get("not_bukhara", [])) + list(pv["_rows"].get("memo", [])) + list(pv["_rows"].get("bnpz", []))
    new_inns = []; nomma_yes, nomma_no = {}, set()
    for r in pv["_rows"]["candidates"]:
        if r.get("nomma_only"):
            if r["inn"] in accepted_candidates:
                r["district_code"] = accepted_candidates[r["inn"]].get("district_code") or r["district_code"]; nomma_yes[r["inn"]] = r["district_code"]
            else:
                r = dict(r); r["kind"] = "not_bukhara"; nomma_no.add(r["inn"])
            rows.append(r); continue
        if r["inn"] in accepted_candidates:
            r["district_code"] = accepted_candidates[r["inn"]].get("district_code") or r["district_code"]; rows.append(r)
            if r["inn"] not in new_inns: new_inns.append(r["inn"])
    uniq, seen_keys = [], set()
    for r in rows:
        if r["dedup_key"] in seen_keys: continue
        seen_keys.add(r["dedup_key"]); uniq.append(r)
    rows = uniq
    if backup: db.backup("before_upload")
    with con:
        cur = con.execute("INSERT INTO uploads(filename,sha256,report_dates,rows_total,rows_bukhara,rows_karantin,rows_dup,sum_sanoat,sum_meva,new_inns,status) VALUES(?,?,?,?,?,?,?,?,?,?,'saved')",
            (pv["file"], pv["sha256"], json.dumps(sorted(pv["dates"])), pv["rows_total"], sum(1 for r in rows if r["kind"] == "sanoat"), sum(1 for r in rows if r["kind"] == "meva"), pv["counts"]["dups"],
             round(sum(r["stat_usd"] for r in rows if r["kind"] == "sanoat"), 3), round(sum(r["stat_usd"] for r in rows if r["kind"] == "meva"), 3), json.dumps(new_inns)))
        uid = cur.lastrowid
        if pv.get("replace"):
            for u in pv.get("same_day", []):
                con.execute("UPDATE gtd_rows SET voided=1, dedup_key=dedup_key || '#void' || upload_id WHERE upload_id=? AND voided=0", (u["id"],))
                con.execute("UPDATE uploads SET status='voided', note=? WHERE id=?", (f"almashtirildi: yangi yuklash #{uid}", u["id"]))
            if pv.get("same_day"): db.log(con, "upload_replaced", old=[u["id"] for u in pv["same_day"]], new=uid)
        for inn in new_inns:
            c = accepted_candidates[inn]
            own = [x for x in rows if x["inn"] == inn]
            r = max(own, key=lambda x: x["stat_usd"])
            attrs = new_company_attrs(con, r["district_code"], [(str(x["tnved"] or ""), x["stat_usd"]) for x in own])
            con.execute("""INSERT INTO companies(inn,name,district_code,hudud,tarmoq,rus_district,uyushma,district_full,kind,product,source,confirmed)
                           VALUES(?,?,?,?,?,?,?,?,'sanoat',?,'gtd',?)
                           ON CONFLICT(inn) DO UPDATE SET district_code=excluded.district_code, confirmed=excluded.confirmed""",
                        (inn, (c.get("name") if str(c.get("name") or "").strip().lower() not in ("", "(null)") else None) or r["exporter"], r["district_code"], attrs["hudud"], attrs["tarmoq"], attrs["rus_district"], attrs["uyushma"],
                         attrs["district_full"], r["product"], 1 if r["district_code"] else 0))
        # companies known only from the customs base get their номманом columns on first appearance
        for inn in sorted({x["inn"] for x in rows if x["kind"] == "sanoat"} - set(new_inns)):
            c = con.execute("SELECT source, hudud, district_code FROM companies WHERE inn=?", (inn,)).fetchone()
            if c and c["source"] == "baza" and not c["hudud"]:
                own = [x for x in rows if x["inn"] == inn]
                a = new_company_attrs(con, c["district_code"], [(str(x["tnved"] or ""), x["stat_usd"]) for x in own])
                con.execute("""UPDATE companies SET hudud=?, rus_district=?, district_full=?, tarmoq=COALESCE(tarmoq, ?), uyushma=COALESCE(uyushma, ?),
                               product=COALESCE(?, product), updated_at=datetime('now','localtime') WHERE inn=?""",
                            (a["hudud"], a["rus_district"], a["district_full"], a["tarmoq"], a["uyushma"], max(own, key=lambda x: x["stat_usd"])["product"], inn))
        con.executemany("""INSERT INTO gtd_rows(upload_id,report_date,dedup_key,kind,inn,exporter,district_code,regime,tnved,product,country,qty,netto,stat_usd,invoice_usd,gtd_no,item_no,grown_region,grown_district,raw)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [(uid, r["date"], r["dedup_key"], r["kind"], r["inn"], r["exporter"], r["district_code"], str(r["regime"] or ""), str(r["tnved"] or ""), r["product"], r["country"], r["qty"], r["netto"], r["stat_usd"], r["invoice_usd"], r["gtd_no"], r["item_no"], r["grown_region"], r["grown_district"], json.dumps(r["raw"], ensure_ascii=False, default=str)) for r in rows])
        for inn, dc in nomma_yes.items():
            con.execute("UPDATE companies SET bukhara=1, district_code=COALESCE(?, district_code), updated_at=datetime('now','localtime') WHERE inn=?", (dc, inn))
            db.event(con, inn, "bukhara", "ГТД юклашда «Бухоро корхонаси» деб тасдиқланди")
        for inn in nomma_no:
            con.execute("UPDATE companies SET bukhara=0, updated_at=datetime('now','localtime') WHERE inn=?", (inn,))
            db.event(con, inn, "bukhara", "ГТД юклашда «Бухоро эмас» деб белгиланди")
        if nomma_yes or nomma_no: db.log(con, "bukhara_decision", yes=sorted(nomma_yes), no=sorted(nomma_no))
        # new exporter: not in the template's номманом -> «yangi korxona» with the day it was found
        in_tpl = {i for (i,) in con.execute("SELECT inn FROM template_inns")} or \
                 {i for (i,) in con.execute("SELECT inn FROM companies WHERE source='nomma-nom'")}
        first_day = {}
        for x in rows:
            if x["kind"] == "sanoat" and x["inn"] not in in_tpl:
                first_day[x["inn"]] = min(first_day.get(x["inn"], x["date"]), x["date"])
        for inn, d in first_day.items():
            had = con.execute("SELECT new_date FROM companies WHERE inn=?", (inn,)).fetchone()
            con.execute("UPDATE companies SET is_new=1, new_date=COALESCE(new_date, ?) WHERE inn=?", (d, inn))
            if had is not None and not had["new_date"]:
                db.event(con, inn, "new", f"Янги экспортёр сифатида аниқланди ({d[8:10]}.{d[5:7]}.{d[:4]}, «{pv['file']}»)")
        # control sum after write
        got = con.execute("SELECT round(sum(stat_usd),3) FROM gtd_rows WHERE upload_id=?", (uid,)).fetchone()[0] or 0
        want = round(sum(r["stat_usd"] for r in rows), 3)
        if abs(got - want) > 0.001: raise RuntimeError(f"Nazorat summasi mos emas: yozildi {got}, kutilgan {want} — tranzaksiya bekor qilindi")
        db.log(con, "upload_saved", upload_id=uid, file=pv["file"], rows=len(rows), sum=want, new_inns=new_inns)
    return {"upload_id": uid, "rows": len(rows), "sum": want, "new_inns": new_inns}

def void_upload(con, upload_id: int, reason: str = ""):
    db.backup("before_void")
    with con:
        con.execute("UPDATE gtd_rows SET voided=1, dedup_key=dedup_key || '#void' || upload_id WHERE upload_id=? AND voided=0", (upload_id,))   # key is free for a re-upload
        con.execute("UPDATE uploads SET status='voided', note=? WHERE id=?", (reason, upload_id))
        db.log(con, "upload_voided", upload_id=upload_id, reason=reason)
