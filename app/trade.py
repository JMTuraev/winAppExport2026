"""Davlat bo'yicha tashqi savdo (eksport + import) — Экспорт географияси sahifasidagi Excel tugmasi, davlat tanlanganda.
Eksport: geo.py bilan bir xil qoidalar (joriy davr — karantin qoidasi, o'tgan yil — bojxona bazasi), shuning uchun
jamilar sahifadagi ro'yxat bilan teng. Import: bojxona bazasi (items regime='ИМ'), faqat Buxoro korxonalari
(«Бухоро эмас» — yo'q, Buxoro davri hisobga olinadi), davlat — «страна отправления» (declarations.country)."""
from __future__ import annotations
import datetime as dt
from collections import defaultdict
from . import db, report, geo

OTHER = "Туман аниқланмаган"
NOSECT = "Соҳа аниқланмаган"
NOTARM = "Тармоқ белгиланмаган"


# ------------------------------------------------------------------ records
class _Ctx:
    def __init__(self, con, q):
        from . import dispute
        self.con = con
        self.targets = geo._vals(q, "country")
        self.dists, self.tarmoqs, self.kinds = geo._vals(q, "district"), geo._vals(q, "tarmoq"), geo._vals(q, "kind")
        self.with_memo = str(q.get("memo") or "1") != "0"
        self.through = db.get_setting(con, "opening_through_date") or ""
        self.comp = {r["inn"]: dict(r) for r in con.execute(
            "SELECT inn, name, district_code, tarmoq, kind, excluded, bukhara, bukhara_from, bukhara_to FROM companies")}
        self.tset = dispute.template_inns(con)
        self.hs = {r["hs10"]: dict(r) for r in con.execute("SELECT hs10, tovar1, tovar2, sprav1 FROM hs_codes")}
        self.dn = {d["code"]: d["name_uz"] for d in report.districts(con)}
        self.dorder = [d["code"] for d in report.districts(con)]

    def in_bukhara(self, c, d):
        if c is None or c.get("bukhara") == 0: return False
        return (c.get("bukhara_from") or "") <= d <= (c.get("bukhara_to") or "9999")


def _rec(ctx, inn, name, dc, tarmoq, d, value, netto, hs10, tovar1, tovar2, pname, gtd, excl):
    return {"inn": inn, "name": name, "dc": dc or "", "tarmoq": (tarmoq or "").strip(), "date": d, "value": value or 0.0,
            "netto": netto or 0.0, "hs4": (hs10 or "")[:4], "tovar1": tovar1 or NOSECT, "tovar2": tovar2 or "—",
            "pname": pname, "gtd": gtd, "excl": bool(excl)}


def export_recs(ctx: _Ctx, f: str, t: str, karantin: bool) -> list:
    """Eksport qatorlari (geo.rows/geo.country bilan bir xil filtr). karantin=True — joriy davr qoidasi (meva faqat GTD karantin);
    False — o'tgan yil (bojxona bazasi, meva items dan). Alohida hisob (БНПЗ/SDK) qatorlari excl=True bilan qaytadi."""
    from .companies import country_uz, has_base_detail
    from . import dispute
    con, out = ctx.con, []

    def kind_ok(k):
        if k in ("bnpz", "memo"): return True                 # excl belgisi bilan, keyin with_memo bo'yicha ajratiladi
        if k in ("meva", "meva_x"): return not karantin
        return k == "sanoat"

    def keep(c, d):
        if not ctx.in_bukhara(c, d): return False
        if ctx.dists and c.get("district_code") not in ctx.dists: return False
        if ctx.tarmoqs and (c.get("tarmoq") or "").strip() not in ctx.tarmoqs: return False
        if ctx.kinds and c.get("kind") not in ctx.kinds: return False
        return True

    if has_base_detail(con):
        src = list(con.execute("""SELECT i.inn, i.rdate, i.gtd, d.country, i.value, i.netto, i.hs10, i.tovar1, i.tovar2, i.sprav1, i.kind
                                  FROM items i JOIN declarations d ON d.decl_id=i.decl_id
                                  WHERE i.regime='ЭК' AND i.rdate>=? AND i.rdate<=?""", (f, t)))
        tpl = [{**x, "hs10": "", "sprav1": None} for x in (dispute.template_items(con, int(t[:4]), f, t) if ctx.tset else [])]
        for r in src + tpl:
            if not kind_ok(r["kind"]): continue
            if r["inn"] in ctx.tset and r["kind"] == "sanoat" and not str(r["gtd"] or "").startswith("tpl:"): continue
            cn = country_uz(r["country"]) if r["country"] else dispute.TPL_T1
            if cn not in ctx.targets: continue
            c = ctx.comp.get(r["inn"])
            if not keep(c, r["rdate"]): continue
            excl = bool(c.get("excluded")) or r["kind"] in ("bnpz", "memo")
            out.append(_rec(ctx, r["inn"], c.get("name"), c.get("district_code"), c.get("tarmoq"), r["rdate"], r["value"], r["netto"],
                            r["hs10"], r["tovar1"], r["tovar2"], r["sprav1"] or r["tovar2"] or r["tovar1"], r["gtd"], excl))
    th = ctx.through
    for r in con.execute("SELECT inn, exporter, district_code dc, report_date, gtd_no, country, stat_usd, netto, tnved, product, kind "
                         "FROM gtd_rows WHERE voided=0 AND report_date>=? AND report_date<=?" + (" AND report_date>?" if th else ""),
                         (f, t, *((th,) if th else ()))):
        if r["kind"] in geo.KIND_SKIP or country_uz(r["country"]) not in ctx.targets: continue
        h = ctx.hs.get(str(r["tnved"] or "")) or {}
        if karantin and r["kind"] == "meva":           # karantin qoidasi: o'stirilgan tuman bo'yicha
            if ctx.kinds and "meva" not in ctx.kinds: continue
            if ctx.dists and (r["dc"] or "?") not in ctx.dists: continue
            if ctx.tarmoqs and "Мева-сабзавот" not in ctx.tarmoqs: continue
            c = ctx.comp.get(r["inn"]) or {}
            nm, dc, tarm, excl = c.get("name") or r["exporter"], r["dc"], "Мева-сабзавот", False
        else:
            if not kind_ok(r["kind"]): continue
            c = ctx.comp.get(r["inn"])
            if not keep(c, r["report_date"]): continue
            nm, dc, tarm = c.get("name"), c.get("district_code"), c.get("tarmoq")
            excl = bool(c.get("excluded")) or r["kind"] in ("bnpz", "memo")
        out.append(_rec(ctx, r["inn"], nm, dc, tarm, r["report_date"], r["stat_usd"], (r["netto"] or 0) / 1000, str(r["tnved"] or ""),
                        h.get("tovar1"), h.get("tovar2"), h.get("sprav1") or h.get("tovar2") or (r["product"] or "")[:60] or None, r["gtd_no"], excl))
    return out


def import_recs(ctx: _Ctx, f: str, t: str) -> list:
    """Import qatorlari — bojxona bazasi. Faqat tuman filtri qo'llanadi (tarmoq/tur — eksport tushunchalari)."""
    from .companies import country_uz
    out = []
    for r in ctx.con.execute("""SELECT i.inn, i.rdate, i.gtd, d.country, i.value, i.netto, i.hs10, i.tovar1, i.tovar2, i.sprav1
                                FROM items i JOIN declarations d ON d.decl_id=i.decl_id
                                WHERE i.regime='ИМ' AND i.rdate>=? AND i.rdate<=?""", (f, t)):
        if country_uz(r["country"]) not in ctx.targets: continue
        c = ctx.comp.get(r["inn"])
        if not ctx.in_bukhara(c, r["rdate"]): continue
        if ctx.dists and c.get("district_code") not in ctx.dists: continue
        out.append(_rec(ctx, r["inn"], c.get("name"), c.get("district_code"), c.get("tarmoq"), r["rdate"], r["value"], r["netto"],
                        r["hs10"], r["tovar1"], r["tovar2"], r["sprav1"] or r["tovar2"] or r["tovar1"], r["gtd"], c.get("excluded")))
    return out


def _split(ctx, recs):
    """(hisobdagi, alohida hisobdagi) — «Алоҳида ҳисоб» belgisi o'chiq bo'lsa БНПЗ/SDK chetga olinadi."""
    if ctx.with_memo: return recs, []
    return [r for r in recs if not r["excl"]], [r for r in recs if r["excl"]]


def _sum(recs): return sum(r["value"] for r in recs)


def _group(cur, prev, key):
    g = defaultdict(lambda: {"cur": 0.0, "prev": 0.0, "inns": set(), "pinns": set(), "gtd": set(), "netto": 0.0})
    for r in cur:
        o = g[key(r)]; o["cur"] += r["value"]; o["inns"].add(r["inn"]); o["gtd"].add(r["gtd"]); o["netto"] += r["netto"]
    for r in prev:
        o = g[key(r)]; o["prev"] += r["value"]; o["pinns"].add(r["inn"])
    return g


# ------------------------------------------------------------------ data
def build(con, q: dict) -> dict:
    ctx = _Ctx(con, q)
    if not ctx.targets: raise ValueError("Давлат танланмаган")
    f, t = geo._period(con, q)
    y = int(t[:4])

    def back(d, n=1):
        s = f"{int(d[:4]) - n}{d[4:]}"
        return s[:-2] + "28" if s.endswith("02-29") else s
    pf, pt = back(f), back(t)
    # import ma'lumoti faqat bojxona bazasi sanasigacha — solishtirish ham shu kungacha
    imp_last = con.execute("SELECT max(rdate) FROM items WHERE regime='ИМ'").fetchone()[0] or ""
    it = min(t, imp_last) if imp_last else t
    ipt = back(it) if it >= f else pt

    ex_c, ex_cx = _split(ctx, export_recs(ctx, f, t, True))
    ex_p, ex_px = _split(ctx, export_recs(ctx, pf, pt, False))
    im_c, im_cx = _split(ctx, import_recs(ctx, f, it) if it >= f else [])
    im_p, im_px = _split(ctx, import_recs(ctx, pf, ipt) if it >= f else [])

    # yillar dinamikasi va oylar (joriy yil: 01.01 — t, o'tgan yillar butun)
    years = []
    for yy in (y - 2, y - 1, y):
        a, b = f"{yy}-01-01", (t if yy == y else f"{yy}-12-31")
        e, _ = _split(ctx, export_recs(ctx, a, b, yy == y))
        i_, _ = _split(ctx, import_recs(ctx, a, min(b, imp_last) if imp_last else b))
        years.append({"year": yy, "to": b, "exp": e, "imp": i_})
    return {"ctx": ctx, "f": f, "t": t, "pf": pf, "pt": pt, "it": it, "ipt": ipt, "imp_last": imp_last,
            "ex_c": ex_c, "ex_p": ex_p, "im_c": im_c, "im_p": im_p, "ex_cx": ex_cx, "ex_px": ex_px, "im_cx": im_cx, "im_px": im_px,
            "years": years, "title": ", ".join(sorted(ctx.targets))}


# ------------------------------------------------------------------ Excel
def export_xlsx(con, q: dict, out) -> object:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter as L
    D = build(con, q); ctx = D["ctx"]
    dmy = lambda s: f"{s[8:10]}.{s[5:7]}.{s[:4]}" if s else "—"
    thin = Side(style="thin", color="C9D1CD"); BD = Border(thin, thin, thin, thin)
    HF, HFont = PatternFill("solid", fgColor="0F6E63"), Font(bold=True, color="FFFFFF", size=10)
    TF, DF, SF = PatternFill("solid", fgColor="D6E9E4"), PatternFill("solid", fgColor="EEF5F3"), PatternFill("solid", fgColor="F7F9F8")
    NUM, PCT, INT = '#,##0.0;[Red]-#,##0.0;"–"', '0.0%;[Red]-0.0%;"–"', '#,##0;-#,##0;"–"'
    WRAP = Alignment(wrap_text=True, vertical="center")
    per_cur, per_prev = f"{dmy(D['f'])} — {dmy(D['t'])}", f"{dmy(D['pf'])} — {dmy(D['pt'])}"
    iper_cur, iper_prev = f"{dmy(D['f'])} — {dmy(D['it'])}", f"{dmy(D['pf'])} — {dmy(D['ipt'])}"
    if D["it"] < D["f"]:
        iper_cur = iper_prev = f"маълумот йўқ (божхона базаси {dmy(D['imp_last'])} гача)"
    filt = []
    if ctx.dists: filt.append("туман: " + ", ".join(ctx.dn.get(x, x) for x in sorted(ctx.dists)))
    if ctx.tarmoqs: filt.append("тармоқ: " + ", ".join(sorted(ctx.tarmoqs)) + " (фақат экспорт)")
    if ctx.kinds: filt.append("тур: " + ", ".join({"sanoat": "саноат", "meva": "мева-сабзавот"}.get(k, k) for k in sorted(ctx.kinds)) + " (фақат экспорт)")
    filt.append("алоҳида ҳисоб (БНПЗ, SDK): " + ("киритилган" if ctx.with_memo else "киритилмаган"))

    wb = openpyxl.Workbook()

    def setup(ws, widths, landscape=True):
        for i, w in enumerate(widths, 1): ws.column_dimensions[L(i)].width = w
        ws.page_setup.orientation = "landscape" if landscape else "portrait"
        ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.print_options.horizontalCentered = True
        ws.page_margins.left = ws.page_margins.right = 0.4

    def title(ws, text, sub, ncol):
        ws.cell(1, 1, text).font = Font(bold=True, size=14, color="0F3D38")
        ws.cell(2, 1, sub).font = Font(italic=True, size=10, color="5A6470")
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
        ws.row_dimensions[1].height = 22

    def head(ws, r, cols):
        for i, h in enumerate(cols, 1):
            c = ws.cell(r, i, h); c.font = HFont; c.fill = HF; c.border = BD
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.row_dimensions[r].height = 32

    def row(ws, r, vals, fmts, fill=None, bold=False, indent=0):
        for i, (v, fm) in enumerate(zip(vals, fmts), 1):
            c = ws.cell(r, i, v); c.border = BD
            if fm: c.number_format = fm
            if fill: c.fill = fill
            if bold: c.font = Font(bold=True)
            if i == 2 and indent: c.alignment = Alignment(indent=indent, vertical="center")

    def section(ws, r, text, ncol):
        c = ws.cell(r, 1, text); c.font = Font(bold=True, size=12, color="0F6E63")
        return r + 1

    gr = lambda cur, prev: (cur / prev - 1) if prev else None

    # ---------------- 1. Умумий
    ws = wb.active; ws.title = "Умумий"
    setup(ws, [46, 16, 16, 15, 12], landscape=False)
    title(ws, f"Бухоро вилояти — {D['title']} билан ташқи савдо", "минг АҚШ доллари · манба: божхона базаси ва кунлик ГТД", 5)
    r = 4
    ws.cell(r, 1, "Давр:").font = Font(bold=True); ws.cell(r, 2, f"экспорт {per_cur}; импорт {iper_cur}"); r += 1
    ws.cell(r, 1, "Ўтган йил шу давр:").font = Font(bold=True); ws.cell(r, 2, f"экспорт {per_prev}; импорт {iper_prev}"); r += 1
    ws.cell(r, 1, "Филтрлар:").font = Font(bold=True); ws.cell(r, 2, "; ".join(filt)); r += 2
    head(ws, r, ["Кўрсаткич", "Жорий давр", "Ўтган йил шу давр", "Фарқи", "Ўсиш, %"]); r += 1
    E, Ep, I, Ip = _sum(D["ex_c"]), _sum(D["ex_p"]), _sum(D["im_c"]), _sum(D["im_p"])
    for lbl, a, b, bold in [("Товар айланмаси (экспорт + импорт)", E + I, Ep + Ip, True), ("  Экспорт", E, Ep, False),
                            ("  Импорт", I, Ip, False), ("Савдо сальдоси (экспорт − импорт)", E - I, Ep - Ip, True)]:
        row(ws, r, [lbl, a, b, a - b, gr(a, b) if lbl != "Савдо сальдоси (экспорт − импорт)" else None], [None, NUM, NUM, NUM, PCT],
            fill=TF if bold else None, bold=bold); r += 1
    if D["it"] < D["t"] and D["it"] >= D["f"]:
        Es = sum(x["value"] for x in D["ex_c"] if x["date"] <= D["it"]); Eps = sum(x["value"] for x in D["ex_p"] if x["date"] <= D["ipt"])
        row(ws, r, [f"Бир хил давр ({dmy(D['f'])[:5]} — {dmy(D['it'])}): товар айланмаси", Es + I, Eps + Ip, Es + I - Eps - Ip, gr(Es + I, Eps + Ip)],
            [None, NUM, NUM, NUM, PCT], fill=SF); ws.cell(r, 1).alignment = WRAP; ws.row_dimensions[r].height = 28; r += 1
        row(ws, r, [f"  шундан экспорт ({dmy(D['f'])[:5]} — {dmy(D['it'])})", Es, Eps, Es - Eps, gr(Es, Eps)], [None, NUM, NUM, NUM, PCT], fill=SF); r += 1
    nE = lambda recs: len({x["inn"] for x in recs}); nG = lambda recs: len({x["gtd"] for x in recs})
    for lbl, a, b in [("Экспортёр корхоналар, сони", nE(D["ex_c"]), nE(D["ex_p"])), ("Импортёр корхоналар, сони", nE(D["im_c"]), nE(D["im_p"])),
                      ("Экспорт ГТД, сони", nG(D["ex_c"]), nG(D["ex_p"])), ("Импорт ГТД, сони", nG(D["im_c"]), nG(D["im_p"]))]:
        row(ws, r, [lbl, a, b, a - b, gr(a, b)], [None, INT, INT, INT, PCT]); r += 1
    if not ctx.with_memo and (D["ex_cx"] or D["im_cx"] or D["ex_px"] or D["im_px"]):
        r += 1; ws.cell(r, 1, "Алоҳида ҳисобдаги корхоналар (БНПЗ, SDK) — юқоридаги жамига киритилмаган:").font = Font(italic=True, bold=True); r += 1
        for lbl, a, b in [("  Экспорт", _sum(D["ex_cx"]), _sum(D["ex_px"])), ("  Импорт", _sum(D["im_cx"]), _sum(D["im_px"]))]:
            if not (a or b): continue
            row(ws, r, [lbl, a, b, a - b, gr(a, b)], [None, NUM, NUM, NUM, PCT], fill=SF); r += 1

    r += 1; r = section(ws, r, "Йиллар кесимида", 5)
    head(ws, r, ["Йил", "Экспорт", "Импорт", "Товар айланмаси", "Сальдо"]); r += 1
    for Y in D["years"]:
        e, i_ = _sum(Y["exp"]), _sum(Y["imp"])
        lab = f"{Y['year']} йил" + (f" (01.01 — {dmy(Y['to'])[:5]})" if Y["year"] == D["years"][-1]["year"] else "")
        row(ws, r, [lab, e, i_, e + i_, e - i_], [None, NUM, NUM, NUM, NUM]); r += 1

    r += 1; y0, y1 = D["years"][-1], D["years"][-2]
    r = section(ws, r, f"Ойлар кесимида ({y0['year']} ва {y1['year']})", 5)
    head(ws, r, ["Ой", f"Экспорт {y0['year']}", f"Экспорт {y1['year']}", f"Импорт {y0['year']}", f"Импорт {y1['year']}"]); r += 1
    OY = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
    def bym(recs):
        m = [0.0] * 12
        for x in recs: m[int(x["date"][5:7]) - 1] += x["value"]
        return m
    m = [bym(y0["exp"]), bym(y1["exp"]), bym(y0["imp"]), bym(y1["imp"])]
    em, im_ = int(D["t"][5:7]), int((min(D["t"], D["imp_last"]) if D["imp_last"] else D["t"])[5:7])
    for k in range(12):
        v = [m[0][k] if k < em else None, m[1][k], m[2][k] if k < im_ else None, m[3][k]]
        row(ws, r, [OY[k]] + v, [None, NUM, NUM, NUM, NUM]); r += 1
    row(ws, r, ["Жами"] + [sum(m[j]) for j in range(4)], [None, NUM, NUM, NUM, NUM], fill=TF, bold=True); r += 2
    notes = [
        "Изоҳлар:",
        "• Экспорт — сайтдаги «Экспорт географияси» саҳифаси қоидалари бўйича (жамилар саҳифадаги давлат қатори билан тенг). "
        "Мева-сабзавот жорий даврда фақат карантин қоидаси бўйича (ГТД); божхона базаси давридаги карантин мевасида давлат кесими йўқ — бу ерга кирмайди.",
        f"• Импорт — божхона базасидан (охирги сана {dmy(D['imp_last'])}); кунлик ГТД фақат экспорт. Давлат — жўнатувчи давлат (ГТД 15-устун).",
        "• Ўтган йил шу давр — божхона базаси (давлат кесимида Созламалардаги натижалар йўқ).",
        "• Фақат Бухоро корхоналари: «Бухоро эмас» белгиланганлар ҳисобга олинмайди, Бухорода ҳисобга олиш даври инобатга олинади.",
    ]
    for n in notes:
        c = ws.cell(r, 1, n); c.alignment = Alignment(wrap_text=True, vertical="top")
        c.font = Font(bold=(n == "Изоҳлар:"), size=9, color="5A6470")
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
        ws.row_dimensions[r].height = 14 if n == "Изоҳлар:" else 40
        r += 1
    ws.freeze_panes = None

    # ---------------- 2. Экспорт / Импорт (tahlil varaqlari)
    def dname(dc): return ctx.dn.get(dc, OTHER)
    def dsort(keys): return sorted(keys, key=lambda k: (ctx.dorder.index(k) if k in ctx.dorder else 999, k))

    def analysis(name, cur, prev, per, pper, is_exp):
        ws = wb.create_sheet(name)
        setup(ws, [6, 52, 15, 15, 14, 11, 10, 12, 10, 12])
        word = "экспорти" if is_exp else "импорти"
        title(ws, f"Бухоро вилоятининг {D['title']} билан {word}",
              f"{per} · ўтган йил: {pper} · минг АҚШ доллари", 10)
        tot, ptot = _sum(cur), _sum(prev)
        cols = ["№", "", "Жорий давр", "Ўтган йил шу давр", "Фарқи", "Ўсиш, %", "Улуши, %", "Корхоналар", "ГТД", "Нетто, т"]
        fm = [INT, None, NUM, NUM, NUM, PCT, PCT, INT, INT, NUM]
        r = 4

        def block(r, heading, first_col, g, order, sub=None):
            r = section(ws, r, heading, 10); head(ws, r, cols[:1] + [first_col] + cols[2:]); r += 1
            for n, k in enumerate(order, 1):
                o = g[k]
                row(ws, r, [n, k, o["cur"], o["prev"], o["cur"] - o["prev"], gr(o["cur"], o["prev"]),
                            o["cur"] / tot if tot else None, len(o["inns"]), len(o["gtd"]), o["netto"]], fm, fill=DF if sub else None, bold=bool(sub))
                r += 1
                if sub:
                    for s, so in sub(k):
                        row(ws, r, [None, s, so["cur"], so["prev"], so["cur"] - so["prev"], gr(so["cur"], so["prev"]),
                                    so["cur"] / tot if tot else None, len(so["inns"]), len(so["gtd"]), so["netto"]], fm, indent=2)
                        r += 1
            row(ws, r, [None, "Жами", tot, ptot, tot - ptot, gr(tot, ptot), 1 if tot else None,
                        len({x["inn"] for x in cur}), len({x["gtd"] for x in cur}), sum(x["netto"] for x in cur)], fm, fill=TF, bold=True)
            return r + 2

        # tumanlar
        g = _group(cur, prev, lambda x: dname(x["dc"]))
        order = [dname(k) for k in dsort({x["dc"] for x in cur + prev})]
        order = list(dict.fromkeys(order))
        r = block(r, "1. Туманлар кесимида", "Туман", g, order)
        # sohalar (tovar1 -> tovar2)
        g1 = _group(cur, prev, lambda x: x["tovar1"])
        g2 = _group(cur, prev, lambda x: (x["tovar1"], x["tovar2"]))
        o1 = sorted(g1, key=lambda k: (-g1[k]["cur"], -g1[k]["prev"]))
        sub = lambda k: sorted(((k2[1], v) for k2, v in g2.items() if k2[0] == k), key=lambda z: (-z[1]["cur"], -z[1]["prev"]))
        r = block(r, "2. Соҳалар (товар гуруҳлари) кесимида", "Соҳа / маҳсулот гуруҳи", g1, o1, sub=sub)
        if is_exp:
            g3 = _group(cur, prev, lambda x: x["tarmoq"] or NOTARM)
            r = block(r, "3. Корхона тармоқлари кесимида", "Тармоқ", g3, sorted(g3, key=lambda k: (-g3[k]["cur"], -g3[k]["prev"])))
        # mahsulotlar HS4
        nm = {}
        for x in sorted(cur + prev, key=lambda x: -x["value"]):
            nm.setdefault(x["hs4"] or "—", x["pname"])
        g4 = _group(cur, prev, lambda x: x["hs4"] or "—")
        o4 = sorted(g4, key=lambda k: (-g4[k]["cur"], -g4[k]["prev"]))
        r = section(ws, r, f"{4 if is_exp else 3}. Маҳсулотлар (ТН ВЭД 4 белги)", 10)
        head(ws, r, ["№", "Маҳсулот", "Жорий давр", "Ўтган йил шу давр", "Фарқи", "Ўсиш, %", "Улуши, %", "Корхоналар", "ТН ВЭД", "Нетто, т"]); r += 1
        for n, k in enumerate(o4, 1):
            o = g4[k]
            row(ws, r, [n, nm.get(k) or "—", o["cur"], o["prev"], o["cur"] - o["prev"], gr(o["cur"], o["prev"]),
                        o["cur"] / tot if tot else None, len(o["inns"]), k, o["netto"]], fm[:8] + ["@", NUM]); r += 1
        row(ws, r, [None, "Жами", tot, ptot, tot - ptot, gr(tot, ptot), 1 if tot else None, len({x["inn"] for x in cur}), None,
                    sum(x["netto"] for x in cur)], fm, fill=TF, bold=True); r += 2
        ws.freeze_panes = "C4"
        return ws

    # ---------------- 3. Номма-ном
    def nomma(name, cur, prev, per, pper, is_exp):
        ws = wb.create_sheet(name)
        cols = ["№", "№ туман", "ИНН", "Корхона номи", "Тармоқ" if is_exp else "Асосий соҳа", "Асосий маҳсулот", "Жорий давр",
                "Ўтган йил шу давр", "Фарқи", "Ўсиш, %", "Туман ичида, %", "ГТД", "Нетто, т", "Охирги сана"]
        setup(ws, [6, 7, 16, 40, 22, 34, 14, 14, 13, 10, 11, 8, 11, 12])
        word = "экспортёр" if is_exp else "импортёр"
        title(ws, f"{D['title']} — {word} корхоналар номма-ном", f"{per} · ўтган йил: {pper} · минг АҚШ доллари", len(cols))
        r = 4; head(ws, r, cols); r += 1
        g = defaultdict(lambda: {"cur": 0.0, "prev": 0.0, "gtd": set(), "netto": 0.0, "last": None, "name": None, "dc": None,
                                 "tarmoq": None, "p": defaultdict(float), "s": defaultdict(float)})
        for x in cur:
            o = g[x["inn"]]; o["cur"] += x["value"]; o["gtd"].add(x["gtd"]); o["netto"] += x["netto"]
            o["last"] = max(filter(None, [o["last"], x["date"]])); o["p"][x["pname"] or "—"] += x["value"]; o["s"][x["tovar1"]] += x["value"]
            o["name"] = o["name"] or x["name"]; o["dc"] = o["dc"] or x["dc"]; o["tarmoq"] = o["tarmoq"] or x["tarmoq"]
        for x in prev:
            o = g[x["inn"]]; o["prev"] += x["value"]
            o["name"] = o["name"] or x["name"]; o["dc"] = o["dc"] or x["dc"]; o["tarmoq"] = o["tarmoq"] or x["tarmoq"]
            o.setdefault("pp", defaultdict(float))[x["pname"] or "—"] += x["value"]
            o.setdefault("ps", defaultdict(float))[x["tovar1"]] += x["value"]
        by_d = defaultdict(list)
        for inn, o in g.items(): by_d[o["dc"] or ""].append((inn, o))
        n = 0; tot, ptot = _sum(cur), _sum(prev)
        for dc in dsort(by_d):
            lst = sorted(by_d[dc], key=lambda z: (-z[1]["cur"], -z[1]["prev"], z[1]["name"] or ""))
            dc_cur, dc_prev = sum(o["cur"] for _, o in lst), sum(o["prev"] for _, o in lst)
            row(ws, r, [None, None, None, f"{dname(dc)} ({len([1 for _, o in lst if o['cur']])} та)" if any(o["cur"] for _, o in lst) else f"{dname(dc)} (жорий даврда йўқ)", None, None, dc_cur, dc_prev,
                        dc_cur - dc_prev, gr(dc_cur, dc_prev), dc_cur / tot if tot else None,
                        len({gg for _, o in lst for gg in o["gtd"]}), sum(o["netto"] for _, o in lst), None],
                [None] * 6 + [NUM, NUM, NUM, PCT, PCT, INT, NUM, None], fill=DF, bold=True)
            r += 1
            for k, (inn, o) in enumerate(lst, 1):
                n += 1
                prod_src = o["p"] or o.get("pp") or {}
                prod = max(prod_src, key=prod_src.get) if prod_src else None
                sect_src = o["s"] or o.get("ps") or {}
                sect = max(sect_src, key=sect_src.get) if sect_src else None
                row(ws, r, [n, k, inn, o["name"] or inn, (o["tarmoq"] or "") if is_exp else sect, prod, o["cur"], o["prev"],
                            o["cur"] - o["prev"], gr(o["cur"], o["prev"]), o["cur"] / dc_cur if dc_cur else None, len(o["gtd"]),
                            o["netto"], dmy(o["last"]) if o["last"] else None],
                    [INT, INT, "@", None, None, None, NUM, NUM, NUM, PCT, PCT, INT, NUM, None])
                ws.cell(r, 4).alignment = WRAP; ws.cell(r, 6).alignment = WRAP
                r += 1
        row(ws, r, [None, None, None, f"Жами: {len([1 for o in g.values() if o['cur']])} та корхона", None, None, tot, ptot, tot - ptot,
                    gr(tot, ptot), 1 if tot else None, len({x["gtd"] for x in cur}), sum(x["netto"] for x in cur), None],
            [None] * 6 + [NUM, NUM, NUM, PCT, PCT, INT, NUM, None], fill=TF, bold=True)
        ws.freeze_panes = "E5"; ws.auto_filter.ref = f"A4:{L(len(cols))}{r - 1}"
        ws.print_title_rows = "4:4"
        return ws

    def matrix(ws, r, heading, cur):
        """Соҳалар (қатор) × туманлар (устун), жорий давр."""
        g1 = defaultdict(float); mx = defaultdict(float)
        for x in cur: g1[x["tovar1"]] += x["value"]; mx[(x["tovar1"], x["dc"])] += x["value"]
        secs = sorted((k for k in g1 if g1[k]), key=lambda k: -g1[k]); dks = dsort({x["dc"] for x in cur})
        r = section(ws, r, heading, 3)
        if not secs:
            ws.cell(r, 2, "маълумот йўқ"); return r + 2
        hdr = ["№", "Соҳа", "Жами"] + [dname(dc).replace(" тумани", " т.").replace(" шаҳри", " ш.") for dc in dks]
        for i, h in enumerate(hdr, 1):
            c = ws.cell(r, i, h); c.font = HFont; c.fill = HF; c.border = BD
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.row_dimensions[r].height = 34; r += 1
        for n, s_ in enumerate(secs, 1):
            row(ws, r, [n, s_, g1[s_]] + [mx[(s_, dc)] for dc in dks], [INT, None] + [NUM] * (len(dks) + 1))
            ws.cell(r, 2).alignment = WRAP; r += 1
        row(ws, r, [None, "Жами", sum(g1.values())] + [sum(mx[(s_, dc)] for s_ in secs) for dc in dks], [None, None] + [NUM] * (len(dks) + 1), fill=TF, bold=True)
        return r + 2

    analysis("Экспорт", D["ex_c"], D["ex_p"], per_cur, per_prev, True)
    analysis("Импорт", D["im_c"], D["im_p"], iper_cur, iper_prev, False)
    nomma("Экспорт номма-ном", D["ex_c"], D["ex_p"], per_cur, per_prev, True)
    nomma("Импорт номма-ном", D["im_c"], D["im_p"], iper_cur, iper_prev, False)
    ws = wb.create_sheet("Соҳа × туман")
    setup(ws, [5, 38, 13] + [11] * 14)
    title(ws, f"{D['title']} — соҳалар ва туманлар кесими", "жорий давр · минг АҚШ доллари", 12)
    r = matrix(ws, 4, f"Экспорт ({per_cur})", D["ex_c"])
    matrix(ws, r, f"Импорт ({iper_cur})", D["im_c"])
    wb.save(out); return out


def file_name(q: dict) -> str:
    import re
    cs = sorted(geo._vals(q, "country"))
    nm = ", ".join(cs) if len(cs) <= 3 else f"{', '.join(cs[:3])} ва б."
    nm = re.sub(r'[\\/:*?"<>|]', "_", nm)
    return f"{nm} — экспорт ва импорт {dt.date.today():%d.%m.%Y}.xlsx"
