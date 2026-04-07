#!/usr/bin/env python3
"""
Beyond East — Working Capital Strategy Command Centre
Masood Retail Private Limited | MG Apparel Integration
Run: streamlit run beyondeast_dashboard.py
"""

import os, json
from datetime import datetime, date, timedelta
from pathlib import Path

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

# ══════════════════════════════════════════════════════════════════════════════
#  DEFAULTS  (from Working Capital & Budget files — June 30, 2026)
# ══════════════════════════════════════════════════════════════════════════════
COMPANY    = "Beyond East | Masood Retail Private Limited"
TARGET_DIR = Path(__file__).parent
STATE_FILE = TARGET_DIR / "BeyondEast_WC_State.json"

DEFAULTS = dict(
    # ── P&L ──────────────────────────────────────────────────────────────────
    annual_sales        = 1_100_000_000,
    annual_cogs         = 626_906_779,
    cost_of_capital     = 0.20,
    # YTD actuals (8 months to Feb-26)
    ytd_gross_rev       = 678_818_059,
    ytd_net_rev         = 576_786_359,
    ytd_cogs            = 395_985_470,   # absolute value
    ytd_gp              = 180_800_888,
    ytd_stores_opex     = 196_359_194,   # absolute
    ytd_corp_oh         = 141_104_399,   # absolute
    ytd_ebitda          = -151_181_561,
    ytd_budget_rev      = 716_281_899,
    ytd_budget_ebitda   = -117_684_989,
    # FY26 budget
    fy26_net_rev        = 607_018_558,
    fy26_cogs           = 138_768_149,   # absolute
    fy26_gp             = 468_250_409,
    fy26_stores_opex    = 318_400_571,   # absolute
    fy26_corp_oh        = 194_967_509,   # absolute
    fy26_ebitda         = -117_684_989,
    # FY25 actuals
    fy25_net_rev        = 383_744_044,
    fy25_cogs           = 246_979_432,   # absolute
    fy25_gp             = 136_764_612,
    fy25_stores_opex    = 192_818_034,   # absolute
    fy25_corp_oh        = 98_296_000,    # absolute
    fy25_ebitda         = -125_937_899,
    # ── Working Capital ───────────────────────────────────────────────────────
    wip_days_fcst       = 29.29,
    wip_days_tgt        = 16.18,
    fg_total_days_fcst  = 121.39,
    fg_total_days_tgt   = 92.57,
    fg_winter_fcst      = 70_000_000,
    fg_winter_tgt       = 0,
    fg_summer_fcst      = 194_039_061,
    fg_others_fcst      = 21_000_000,
    raw_mat_fcst        = 10_000_000,
    mg_pay_days_fcst    = 248.03,
    mg_pay_days_tgt     = 232.89,
    oth_pay_days_fcst   = 170.98,
    oth_pay_days_tgt    = 136.05,
    ecom_rec_fcst       = 15_000_000,
    ecom_rec_tgt        = 10_000_000,
    cash_bank           = 35_374_577,
    nwc_fcst            = -303_652_471,
    # ── Machinery ─────────────────────────────────────────────────────────────
    num_machines        = 28,
    machine_cost_usd    = 43_000,
    usd_pkr             = 280,
    install_cost        = 2_000_000,
    machine_life_yrs    = 10,
    pcs_per_mach_day    = 40,
    op_days             = 300,
    outsource_cost_pc   = 130,
    inhouse_cost_pc     = 60,
    operator_wage_mo    = 40_000,
    ops_per_mach        = 1,
    annual_power        = 1_200_000,
    annual_maint        = 500_000,
)

# ══════════════════════════════════════════════════════════════════════════════
#  CALCULATION ENGINE
# ══════════════════════════════════════════════════════════════════════════════
def calc(d):
    """Derive all computed metrics from the input dict d."""
    dc = d["annual_cogs"] / 365
    ds = d["annual_sales"] / 365

    wip_bal   = d["wip_days_fcst"] * dc
    wip_tgt   = d["wip_days_tgt"]  * dc
    fg_bal    = d["fg_total_days_fcst"] * dc
    fg_tgt    = d["fg_total_days_tgt"]  * dc
    mg_bal    = d["mg_pay_days_fcst"]  * dc
    mg_tgt    = d["mg_pay_days_tgt"]   * dc
    oth_bal   = d["oth_pay_days_fcst"] * dc
    oth_tgt   = d["oth_pay_days_tgt"]  * dc

    wip_release  = (d["wip_days_fcst"]  - d["wip_days_tgt"])  * dc
    fg_release   = (d["fg_total_days_fcst"] - d["fg_total_days_tgt"]) * dc
    dead_release = d["fg_winter_fcst"] - d["fg_winter_tgt"]
    mg_relief    = (d["mg_pay_days_tgt"] - d["mg_pay_days_fcst"]) * dc   # negative = paydown cost
    oth_relief   = (d["oth_pay_days_tgt"] - d["oth_pay_days_fcst"]) * dc  # positive = extend
    rec_release  = d["ecom_rec_fcst"] - d["ecom_rec_tgt"]

    total_wc_release = wip_release + fg_release + dead_release + mg_relief + oth_relief + rec_release
    annual_wc_benefit = total_wc_release * d["cost_of_capital"]

    # Machinery
    capex       = d["num_machines"] * d["machine_cost_usd"] * d["usd_pkr"] + d["install_cost"]
    capacity    = d["num_machines"] * d["pcs_per_mach_day"] * d["op_days"]
    gross_sav   = capacity * (d["outsource_cost_pc"] - d["inhouse_cost_pc"])
    run_cost    = (d["operator_wage_mo"] * d["ops_per_mach"] * d["num_machines"] * 12
                  + d["annual_power"] + d["annual_maint"])
    net_sav     = gross_sav - run_cost
    payback     = capex / net_sav if net_sav > 0 else 99
    annual_depr = capex / d["machine_life_yrs"]
    roi_yr1     = (net_sav - capex) / capex

    total_annual_benefit = net_sav + annual_wc_benefit
    net_3yr     = net_sav * 3 - capex

    # ── WC Interest Cost Breakdown ────────────────────────────────────────────
    # Annual financing cost of each WC component at cost_of_capital
    inv_total_fcst  = (d["wip_days_fcst"] + d["fg_total_days_fcst"]) * dc + d["raw_mat_fcst"]
    inv_total_tgt   = (d["wip_days_tgt"]  + d["fg_total_days_tgt"])  * dc
    rec_total_fcst  = d["ecom_rec_fcst"]
    rec_total_tgt   = d["ecom_rec_tgt"]
    pay_total_fcst  = d["mg_pay_days_fcst"]  * dc + d["oth_pay_days_fcst"] * dc
    pay_total_tgt   = d["mg_pay_days_tgt"]   * dc + d["oth_pay_days_tgt"]  * dc

    wc_int_inv_fcst  = inv_total_fcst  * d["cost_of_capital"]   # cost of holding inventory
    wc_int_rec_fcst  = rec_total_fcst  * d["cost_of_capital"]   # cost of receivables
    wc_int_pay_fcst  = pay_total_fcst  * d["cost_of_capital"]   # benefit from payables (negative = saving)
    wc_net_cost_fcst = wc_int_inv_fcst + wc_int_rec_fcst - wc_int_pay_fcst

    wc_int_inv_tgt   = inv_total_tgt   * d["cost_of_capital"]
    wc_int_rec_tgt   = rec_total_tgt   * d["cost_of_capital"]
    wc_int_pay_tgt   = pay_total_tgt   * d["cost_of_capital"]
    wc_net_cost_tgt  = wc_int_inv_tgt  + wc_int_rec_tgt  - wc_int_pay_tgt

    wc_interest_improvement = wc_net_cost_fcst - wc_net_cost_tgt  # positive = saving

    return dict(
        dc=dc, ds=ds,
        wip_bal=wip_bal, wip_tgt_bal=wip_tgt,
        fg_bal=fg_bal, fg_tgt_bal=fg_tgt,
        mg_bal=mg_bal, mg_tgt_bal=mg_tgt,
        oth_bal=oth_bal, oth_tgt_bal=oth_tgt,
        wip_release=wip_release, fg_release=fg_release,
        dead_release=dead_release, mg_relief=mg_relief,
        oth_relief=oth_relief, rec_release=rec_release,
        total_wc_release=total_wc_release,
        annual_wc_benefit=annual_wc_benefit,
        capex=capex, capacity=capacity, gross_sav=gross_sav,
        run_cost=run_cost, net_sav=net_sav, payback=payback,
        annual_depr=annual_depr, roi_yr1=roi_yr1,
        total_annual_benefit=total_annual_benefit, net_3yr=net_3yr,
        # WC interest cost breakdown
        wc_int_inv_fcst=wc_int_inv_fcst, wc_int_rec_fcst=wc_int_rec_fcst,
        wc_int_pay_fcst=wc_int_pay_fcst, wc_net_cost_fcst=wc_net_cost_fcst,
        wc_int_inv_tgt=wc_int_inv_tgt,   wc_int_rec_tgt=wc_int_rec_tgt,
        wc_int_pay_tgt=wc_int_pay_tgt,   wc_net_cost_tgt=wc_net_cost_tgt,
        wc_interest_improvement=wc_interest_improvement,
        inv_total_fcst=inv_total_fcst,    inv_total_tgt=inv_total_tgt,
        pay_total_fcst=pay_total_fcst,    pay_total_tgt=pay_total_tgt,
    )

def build_levers(d, c):
    """Return levers ranked by priority."""
    levers = [
        dict(id="dead", title="Clear Winter 25 Dead Stock",
             category="Inventory", cash=c["dead_release"], urgency=5, difficulty=2,
             timeline="0–60 days", owner="MD / Retail Head", rag="RED",
             why=(f"PKR {c['dead_release']/1e6:.0f}M of Winter 25 stock earns nothing and depreciates daily. "
                  f"Every week of delay deepens the required markdown. Fastest cash lever you have."),
             actions=["Count Winter 25 stock by SKU and location this week",
                      "Launch 40–50% in-store markdown in Week 2",
                      "Approach 2–3 B2B bulk buyers for remaining stock in Week 3",
                      "Accept 60–70% markdown if needed — cash now beats inventory later",
                      "Track sell-through weekly; escalate to MD if below 5%/week"]),
        dict(id="wip", title="Bring EMB In-House (Ricoma Machines)",
             category="Manufacturing", cash=c["wip_release"] + c["net_sav"],
             urgency=4, difficulty=3, timeline="1–3 months install, then ongoing",
             owner="Operations / MGA", rag="AMBER",
             why=(f"Outsourced EMB = 30 days lead time. In-house = 10 days. "
                  f"That 20-day cut releases PKR {c['wip_release']/1e6:.0f}M from WIP "
                  f"plus PKR {c['net_sav']/1e6:.0f}M annual EMB cost saving. "
                  f"Payback: {c['payback']:.1f} years."),
             actions=["Confirm Ricoma machine order placement this week",
                      "Prepare MGA Multan floor space; hire 28 operators @ PKR 40K/month",
                      "Month 2: machines arrive — 2-week install + training",
                      "Month 3: first bulk batches go in-house; track pcs/day vs 40 target",
                      "Monthly KPI: WIP days must reach 16 by Month 6"]),
        dict(id="fg", title="Enforce FG Inventory DIO Discipline",
             category="Inventory", cash=c["fg_release"],
             urgency=3, difficulty=3, timeline="3–6 months",
             owner="Buying / Planning", rag="AMBER",
             why=(f"FG at {d['fg_total_days_fcst']:.0f} days vs target {d['fg_total_days_tgt']:.0f}. "
                  f"Releasing PKR {c['fg_release']/1e6:.0f}M requires intake control, not cost cuts."),
             actions=["Freeze all new FG purchase orders until DIO drops below 100 days",
                      "Weekly DIO review: MD + Buying + Retail Head",
                      "Implement open-to-buy — link intake to sell-through",
                      "Resume intake only when DIO hits target band",
                      "KPI: FG days — RED >110, AMBER 95–110, GREEN <95"]),
        dict(id="oth_pay", title="Extend Other Creditor Terms",
             category="Payables", cash=abs(c["oth_relief"]) if c["oth_relief"] > 0 else c["oth_relief"],
             urgency=3, difficulty=2, timeline="60–90 days",
             owner="CFO / Procurement", rag="AMBER",
             why=(f"Other creditors at {d['oth_pay_days_fcst']:.0f} days vs "
                  f"target {d['oth_pay_days_tgt']:.0f}. Top 10 vendors represent 80% of balance. "
                  f"Standard 45-day terms = PKR {abs(c['oth_relief'])/1e6:.0f}M cash relief."),
             actions=["List top 10 creditors by balance this week",
                      "Approach each with a 45-day net terms proposal",
                      "Offer volume commitment + preferred supplier status",
                      "Issue formal Supplier Policy document (Month 2)",
                      "KPI: DPO for others reviewed monthly"]),
        dict(id="mg_pay", title="Structured MG Payables Pay-Down",
             category="Payables", cash=c["mg_relief"],
             urgency=4, difficulty=3, timeline="6–12 months",
             owner="CFO / MD", rag="RED",
             why=(f"PKR {d['mg_pay_days_fcst']*d['annual_cogs']/365/1e6:.0f}M owed to MG at "
                  f"{d['mg_pay_days_fcst']:.0f} days DPO — 8+ months. "
                  f"This puts the entire supply chain at relationship risk. A pay-down plan is non-negotiable."),
             actions=["Schedule MD-level meeting with MG Apparel this week",
                      "Present a formal 12-month pay-down schedule",
                      "Pay PKR 10–15M/month from dead stock + WIP proceeds",
                      "Offset some balance against new season production credits",
                      "Red line: never drop below 180 days DPO until EBITDA is positive"]),
        dict(id="ecom", title="Accelerate E-Commerce Settlement",
             category="Receivables", cash=c["rec_release"],
             urgency=3, difficulty=1, timeline="1–2 weeks",
             owner="E-Commerce Manager", rag="GREEN",
             why=(f"PKR {d['ecom_rec_fcst']/1e6:.0f}M stuck in e-com receivables. "
                  f"T+3 settlement with Daraz frees PKR {c['rec_release']/1e6:.0f}M in one call."),
             actions=["Call Daraz account manager — request T+3 settlement this week",
                      "Process all orders same-day so settlement clock starts immediately",
                      "KPI: receivables balance checked every Monday — must stay below PKR 10M"]),
    ]
    for lv in levers:
        lv["score"] = (lv["urgency"] * abs(lv["cash"])) / (lv["difficulty"] * 10_000_000)
    levers.sort(key=lambda x: x["score"], reverse=True)
    return levers

# ══════════════════════════════════════════════════════════════════════════════
#  CASH FLOW PROJECTION
# ══════════════════════════════════════════════════════════════════════════════
def build_cashflow(d, c, periods=12, weekly=False):
    """
    Build a forward cash flow projection table with proper operating line items.
    Sections: (A) Operating Receipts/Payments, (B) WC Initiatives, (C) Net & Cumulative.
    """
    n = periods
    step_label = "Week" if weekly else "Month"
    today = date.today()

    labels = []
    for i in range(1, n + 1):
        if weekly:
            dt = today + timedelta(weeks=i)
            labels.append(f"Wk {i} ({dt.strftime('%d %b')})")
        else:
            mo = (today.month - 1 + i) % 12 + 1
            yr = today.year + (today.month - 1 + i) // 12
            labels.append(datetime(yr, mo, 1).strftime("%b-%y"))

    # ── Operating line items (YTD run-rate, annualised) ───────────────────────
    # Use YTD actuals * 12/8 for annualised run-rate
    ann_rev   = d["ytd_net_rev"]      * 12 / 8
    ann_cogs  = d["ytd_cogs"]         * 12 / 8
    ann_store = d["ytd_stores_opex"]  * 12 / 8
    ann_corp  = d["ytd_corp_oh"]      * 12 / 8

    div = 52 if weekly else 12
    per_rev   =  ann_rev   / div
    per_cogs  = -ann_cogs  / div   # negative (cash out)
    per_store = -ann_store / div   # negative
    per_corp  = -ann_corp  / div   # negative
    per_gp    = [per_rev + per_cogs] * n
    per_ebitda= [per_rev + per_cogs + per_store + per_corp] * n

    rev_cf   = [per_rev]   * n
    cogs_cf  = [per_cogs]  * n
    store_cf = [per_store] * n
    corp_cf  = [per_corp]  * n

    # ── WC initiative ramp profiles ────────────────────────────────────────────
    def ramp(total, profile):
        p = profile[:n]
        while len(p) < n: p.append(p[-1] if p else 0)
        s = sum(p)
        return [total * w / s if s else 0 for w in p]

    if weekly:
        dead_profile = [8,9,10,10,9,8,7,6,5,4,3,2] + [1]*max(0,n-12)
        wip_profile  = [0,0,0,0,1,2,3,4,5,5,5,5]   + [4]*max(0,n-12)
        fg_profile   = [0,0,1,1,2,2,3,3,4,4,4,4]   + [3]*max(0,n-12)
        oth_profile  = [0,0,0,1,1,2,2,3,3,3,3,3]   + [2]*max(0,n-12)
        mg_profile   = [1,1,1,1,1,1,1,1,1,1,1,1]   + [1]*max(0,n-12)
        ecom_profile = [3,3,2,2,1,1,1,1,0,0,0,0]   + [0]*max(0,n-12)
    else:
        dead_profile = [15,20,20,15,10,8,5,3,2,1,1,0]
        wip_profile  = [0,0,5,10,15,15,15,12,10,8,6,4]
        fg_profile   = [0,0,2,5,8,10,12,14,14,12,12,11]
        oth_profile  = [0,0,2,5,10,15,18,15,12,10,8,5]
        mg_profile   = [8,8,8,9,9,9,9,9,9,9,9,9]
        ecom_profile = [20,20,15,15,10,10,5,5,0,0,0,0]

    dead_cf = ramp(c["dead_release"],  dead_profile[:n])
    wip_cf  = ramp(c["wip_release"],   wip_profile[:n])
    fg_cf   = ramp(c["fg_release"],    fg_profile[:n])
    oth_cf  = ramp(abs(c["oth_relief"]) if c["oth_relief"] > 0 else 0, oth_profile[:n])
    mg_cf   = ramp(c["mg_relief"],     mg_profile[:n])   # negative = cash out (paydown)
    ecom_cf = ramp(c["rec_release"],   ecom_profile[:n])

    net_cf = [
        rev_cf[i] + cogs_cf[i] + store_cf[i] + corp_cf[i]
        + dead_cf[i] + wip_cf[i] + fg_cf[i]
        + oth_cf[i] + mg_cf[i] + ecom_cf[i]
        for i in range(n)
    ]

    cum = 0
    cum_cf = []
    for v in net_cf:
        cum += v
        cum_cf.append(cum)

    df = pd.DataFrame({
        f"{step_label}":                  labels,
        # A. Operating
        "Sales Receipts (PKR M)":         [round(v/1e6,1) for v in rev_cf],
        "COGS Payments (PKR M)":          [round(v/1e6,1) for v in cogs_cf],
        "Gross Profit (PKR M)":           [round(v/1e6,1) for v in per_gp],
        "Stores Opex (PKR M)":            [round(v/1e6,1) for v in store_cf],
        "Corp Overhead (PKR M)":          [round(v/1e6,1) for v in corp_cf],
        "Operating EBITDA (PKR M)":       [round(v/1e6,1) for v in per_ebitda],
        # B. WC Initiatives
        "Dead Stock Proceeds (PKR M)":    [round(v/1e6,1) for v in dead_cf],
        "WIP Release (PKR M)":            [round(v/1e6,1) for v in wip_cf],
        "FG Release (PKR M)":             [round(v/1e6,1) for v in fg_cf],
        "Other Pay. Extension (PKR M)":   [round(v/1e6,1) for v in oth_cf],
        "MG Pay-Down (PKR M)":            [round(v/1e6,1) for v in mg_cf],
        "E-com Collection (PKR M)":       [round(v/1e6,1) for v in ecom_cf],
        # C. Totals
        "Net Cash Flow (PKR M)":          [round(v/1e6,1) for v in net_cf],
        "Cumulative (PKR M)":             [round(v/1e6,1) for v in cum_cf],
    })
    return df

# ══════════════════════════════════════════════════════════════════════════════
#  FORMATTERS
# ══════════════════════════════════════════════════════════════════════════════
def pkr(v):
    if v is None: return "–"
    neg = v < 0;  v = abs(v)
    if v >= 1e9:   s = f"PKR {v/1e9:.1f}B"
    elif v >= 1e6: s = f"PKR {v/1e6:.1f}M"
    elif v >= 1e3: s = f"PKR {v/1e3:.0f}K"
    else:          s = f"PKR {v:,.0f}"
    return f"({s})" if neg else s

def rag(status):
    c = {"RED":("#f85149","#4d1b1b"),"AMBER":("#d29922","#3d2a00"),"GREEN":("#3fb950","#1a4731")}
    fg, bg = c.get(status, ("#e6edf3","#21262d"))
    return f'<span style="background:{bg};color:{fg};padding:2px 10px;border-radius:10px;font-weight:700;font-size:.74rem">{status}</span>'

def stars(n):
    return "●"*n + "○"*(5-n)

# ══════════════════════════════════════════════════════════════════════════════
#  STATE
# ══════════════════════════════════════════════════════════════════════════════
def _load():
    if STATE_FILE.exists():
        try: return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except: pass
    return {}

def _save(data):
    try: STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except: pass

if "d" not in st.session_state:
    saved = _load()
    st.session_state.d = {**DEFAULTS, **saved.get("assumptions", {})}
if "actuals" not in st.session_state:
    st.session_state.actuals = _load().get("actuals", {})

# ══════════════════════════════════════════════════════════════════════════════
#  PAGE CONFIG + CSS
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Beyond East — WC Command Centre",
                   page_icon="🎯", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
/* ── Base font — readable everywhere ── */
html, body, [class*="css"], .stMarkdown, .stText, p, li, td, th, label, span {
    font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif !important;
    font-size: 15px !important;
    line-height: 1.65 !important;
    color: #e6edf3 !important;
}
/* ── Sidebar ── */
section[data-testid="stSidebar"]     { background:#0d1117; }
section[data-testid="stSidebar"] *   { color:#e6edf3 !important; font-size:14px !important; }
/* ── Main padding ── */
.main .block-container { padding-top:1.2rem; padding-bottom:2.5rem; max-width:1400px; }
/* ── Metric cards ── */
div[data-testid="metric-container"]  { background:#161b22; border:1px solid #30363d;
                                       border-radius:12px; padding:16px 20px; }
div[data-testid="metric-container"] label {
    font-size:12px !important; color:#8b949e !important;
    text-transform:uppercase; letter-spacing:.06em; font-weight:600 !important; }
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size:1.55rem !important; font-weight:800 !important; color:#e6edf3 !important; }
div[data-testid="metric-container"] [data-testid="stMetricDelta"] {
    font-size:12px !important; }
/* ── Headings ── */
h1 { color:#58a6ff !important; font-size:1.9rem !important; font-weight:800 !important; }
h2 { color:#79c0ff !important; font-size:1.4rem !important; font-weight:700 !important; }
h3 { color:#a5d6ff !important; font-size:1.15rem !important; font-weight:700 !important; }
/* ── Section header ── */
.sh { font-size:14px !important; font-weight:700; color:#58a6ff; letter-spacing:.04em;
      border-bottom:2px solid #30363d; padding-bottom:5px; margin:16px 0 10px; text-transform:uppercase; }
/* ── Action cards ── */
.card { background:#161b22; border:1px solid #30363d; border-radius:12px;
        padding:18px 20px; margin-bottom:14px; }
.card-title { font-size:16px !important; font-weight:700; color:#e6edf3; margin-bottom:6px; }
.card-cash  { font-size:22px !important; font-weight:800; margin:8px 0; }
.card-why   { font-size:14px !important; color:#c9d1d9; line-height:1.65; margin-bottom:10px; }
.act        { font-size:14px !important; color:#cdd9e5; padding:3px 0; display:block; }
.act::before{ content:"→ "; color:#3fb950; font-weight:700; }
/* ── Alert boxes ── */
.alert { background:#4d1b1b; border:1px solid #f85149; border-radius:10px;
         padding:14px 18px; font-size:14px !important; line-height:1.7; }
.warn  { background:#3d2a00; border:1px solid #d29922; border-radius:10px;
         padding:14px 18px; font-size:14px !important; line-height:1.7; }
.info  { background:#1a3045; border:1px solid #388bfd; border-radius:10px;
         padding:14px 18px; font-size:14px !important; line-height:1.7; }
/* ── Dataframe text ── */
.stDataFrame td, .stDataFrame th { font-size:13px !important; }
/* ── Input labels ── */
.stNumberInput label, .stTextInput label, .stSelectbox label,
.stRadio label, .stCheckbox label {
    font-size:13px !important; font-weight:600 !important; color:#c9d1d9 !important; }
/* ── Expander ── */
.streamlit-expanderHeader { font-size:15px !important; font-weight:600 !important; }
/* ── Tab labels ── */
button[data-baseweb="tab"] { font-size:14px !important; font-weight:600 !important; }
</style>
""", unsafe_allow_html=True)

CHART = dict(paper_bgcolor="#0d1117", plot_bgcolor="#161b22",
             font_color="#e6edf3", font_size=11,
             xaxis=dict(gridcolor="#21262d"), yaxis=dict(gridcolor="#21262d"),
             legend=dict(bgcolor="#161b22", bordercolor="#30363d"),
             margin=dict(t=20, b=5, l=5, r=5))

# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🎯 Beyond East")
    st.markdown("**WC Command Centre**")
    st.caption("Masood Retail Pvt. Ltd.")
    st.markdown("---")
    page = st.radio("Navigation", [
        "🚨  Command Centre",
        "📊  Financial Model",
        "📋  Action Plan & Roadmap",
        "🏭  Machinery ROI",
        "📅  Cash Flow Forecast",
    ], label_visibility="collapsed")
    st.markdown("---")
    d = st.session_state.d
    c = calc(d)
    st.markdown("**Live Totals**")
    st.markdown(f"WC release: **{pkr(c['total_wc_release'])}**")
    st.markdown(f"Annual benefit: **{pkr(c['total_annual_benefit'])}**")
    pb_icon = "🟢" if c["payback"] < 2 else ("🟡" if c["payback"] < 4 else "🔴")
    st.markdown(f"EMB payback: **{pb_icon} {c['payback']:.1f} yrs**")
    st.markdown("---")
    col_s, col_r = st.columns(2)
    if col_s.button("💾 Save", width="stretch"):
        _save({"assumptions": st.session_state.d, "actuals": st.session_state.actuals})
        st.success("Saved.")
    if col_r.button("↺ Reset", width="stretch"):
        st.session_state.d = dict(DEFAULTS)
        st.rerun()
    st.caption("As at June 30, 2026")

# ══════════════════════════════════════════════════════════════════════════════
#  HELPER — EDITABLE ASSUMPTIONS PANEL  (reused across pages)
# ══════════════════════════════════════════════════════════════════════════════
def assumptions_panel(prefix="cc"):
    """Render editable input cells and update session_state.d. Returns updated d."""
    d = st.session_state.d
    st.markdown('<div class="sh">Edit Assumptions — all pages update live</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown("**Inventory**")
        d["wip_days_fcst"]      = st.number_input("WIP Days (Fcst)",       value=float(d["wip_days_fcst"]),      step=0.5,  key=f"{prefix}_wip_f")
        d["wip_days_tgt"]       = st.number_input("WIP Days (Target)",      value=float(d["wip_days_tgt"]),       step=0.5,  key=f"{prefix}_wip_t")
        d["fg_total_days_fcst"] = st.number_input("FG Days (Fcst)",         value=float(d["fg_total_days_fcst"]), step=1.0,  key=f"{prefix}_fg_f")
        d["fg_total_days_tgt"]  = st.number_input("FG Days (Target)",       value=float(d["fg_total_days_tgt"]),  step=1.0,  key=f"{prefix}_fg_t")
        d["fg_winter_fcst"]     = st.number_input("Dead Stock (PKR M)",     value=float(d["fg_winter_fcst"]/1e6), step=1.0,  key=f"{prefix}_dead") * 1e6
        d["fg_winter_tgt"]      = st.number_input("Dead Stock Target (PKR M)", value=float(d["fg_winter_tgt"]/1e6), step=1.0, key=f"{prefix}_dead_t") * 1e6

    with c2:
        st.markdown("**Payables**")
        d["mg_pay_days_fcst"]   = st.number_input("MG DPO (Fcst)",          value=float(d["mg_pay_days_fcst"]),   step=1.0,  key=f"{prefix}_mg_f")
        d["mg_pay_days_tgt"]    = st.number_input("MG DPO (Target)",         value=float(d["mg_pay_days_tgt"]),    step=1.0,  key=f"{prefix}_mg_t")
        d["oth_pay_days_fcst"]  = st.number_input("Other Pay DPO (Fcst)",    value=float(d["oth_pay_days_fcst"]),  step=1.0,  key=f"{prefix}_oth_f")
        d["oth_pay_days_tgt"]   = st.number_input("Other Pay DPO (Target)",  value=float(d["oth_pay_days_tgt"]),   step=1.0,  key=f"{prefix}_oth_t")
        d["ecom_rec_fcst"]      = st.number_input("E-com Rec (PKR M)",       value=float(d["ecom_rec_fcst"]/1e6),  step=0.5,  key=f"{prefix}_rec_f") * 1e6
        d["ecom_rec_tgt"]       = st.number_input("E-com Rec Target (PKR M)",value=float(d["ecom_rec_tgt"]/1e6),   step=0.5,  key=f"{prefix}_rec_t") * 1e6

    with c3:
        st.markdown("**P&L**")
        d["annual_sales"]       = st.number_input("Annual Sales (PKR M)",    value=float(d["annual_sales"]/1e6),   step=10.0, key=f"{prefix}_sales") * 1e6
        d["annual_cogs"]        = st.number_input("Annual COGS (PKR M)",     value=float(d["annual_cogs"]/1e6),    step=10.0, key=f"{prefix}_cogs")  * 1e6
        d["ytd_ebitda"]         = st.number_input("YTD EBITDA (PKR M)",      value=float(d["ytd_ebitda"]/1e6),     step=5.0,  key=f"{prefix}_ebitda") * 1e6
        d["ytd_gross_rev"]      = st.number_input("YTD Gross Sales (PKR M)", value=float(d["ytd_gross_rev"]/1e6),  step=10.0, key=f"{prefix}_ytd_rev") * 1e6
        d["fy26_ebitda"]        = st.number_input("FY26 Budget EBITDA (PKR M)", value=float(d["fy26_ebitda"]/1e6), step=5.0,  key=f"{prefix}_bud_e") * 1e6

    with c4:
        st.markdown("**Capital / Rates**")
        d["cost_of_capital"]    = st.number_input("Cost of Capital (%)",     value=float(d["cost_of_capital"]*100),step=0.5,  key=f"{prefix}_coc") / 100
        d["usd_pkr"]            = st.number_input("USD/PKR Rate",            value=float(d["usd_pkr"]),            step=1.0,  key=f"{prefix}_fx")
        d["cash_bank"]          = st.number_input("Cash & Bank (PKR M)",     value=float(d["cash_bank"]/1e6),      step=1.0,  key=f"{prefix}_cash") * 1e6
        d["fg_summer_fcst"]     = st.number_input("FG Summer (PKR M)",       value=float(d["fg_summer_fcst"]/1e6), step=5.0,  key=f"{prefix}_fg_sum") * 1e6
        d["fg_others_fcst"]     = st.number_input("FG Others (PKR M)",       value=float(d["fg_others_fcst"]/1e6), step=1.0,  key=f"{prefix}_fg_oth") * 1e6

    st.session_state.d = d
    return d

# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 1 — COMMAND CENTRE
# ══════════════════════════════════════════════════════════════════════════════
if "Command" in page:
    st.title("WC Strategy Command Centre")
    st.caption(f"{COMPANY}  |  June 30, 2026")

    with st.expander("✏️ Edit Assumptions (overwrite any value — all outputs update instantly)", expanded=False):
        d = assumptions_panel("cc")
    d = st.session_state.d
    c = calc(d)
    levers = build_levers(d, c)

    # ── ALERT BANNER ──────────────────────────────────────────────────────────
    ytd_gap    = d["ytd_gross_rev"] - d["ytd_budget_rev"]
    ebitda_gap = d["ytd_ebitda"]    - d["fy26_ebitda"]
    st.markdown(f"""<div class="alert">
<b>⚠ FINANCIAL ALERT — YTD to Feb-26</b><br>
Sales <b>{pkr(abs(ytd_gap))} {'below' if ytd_gap<0 else 'above'} budget</b>.
EBITDA = <b>{pkr(d['ytd_ebitda'])} loss</b>
({pkr(abs(ebitda_gap))} {'worse' if ebitda_gap<0 else 'better'} than plan).
Actual COGS = <b>{d['ytd_cogs']/d['ytd_gross_rev']*100:.0f}%</b> of sales vs
<b>{d['fy26_cogs']/d['fy26_net_rev']*100:.0f}%</b> budgeted.
Cash action is not optional.
</div>""", unsafe_allow_html=True)
    st.markdown("")

    # ── KPI ROW ───────────────────────────────────────────────────────────────
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Total WC Release",   pkr(c["total_wc_release"]))
    c2.metric("Dead Stock (urgent)",pkr(d["fg_winter_fcst"]), delta="Depreciating daily", delta_color="inverse")
    c3.metric("WIP Release",        pkr(c["wip_release"]))
    c4.metric("MG Payables",        pkr(d["mg_pay_days_fcst"]*d["annual_cogs"]/365),
              delta=f"{d['mg_pay_days_fcst']:.0f} days DPO", delta_color="inverse")
    c5.metric("YTD EBITDA",         pkr(d["ytd_ebitda"]), delta_color="off")

    st.markdown("---")

    # ── TOP 3 ACTIONS ─────────────────────────────────────────────────────────
    st.markdown("### Top 3 Actions — Do These This Week")
    cols = st.columns(3)
    for col, lv in zip(cols, levers[:3]):
        cash_color = "#3fb950" if lv["cash"] >= 0 else "#f85149"
        with col:
            st.markdown(f"""<div class="card">
<div style="margin-bottom:6px">{rag(lv['rag'])} &nbsp;<span style="color:#8b949e;font-size:.78rem">{lv['category']}</span></div>
<div class="card-title">{lv['title']}</div>
<div class="card-cash" style="color:{cash_color}">{'+'if lv['cash']>=0 else ''}{pkr(lv['cash'])}</div>
<div class="card-why">{lv['why']}</div>
<div style="font-size:.78rem;color:#8b949e">⏱ {lv['timeline']}  |  👤 {lv['owner']}</div>
<hr style="border-color:#30363d;margin:8px 0">
<div style="font-size:.78rem;font-weight:700;color:#58a6ff;margin-bottom:4px">FIRST STEP:</div>
<div class="act">{lv['actions'][0]}</div>
</div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── CASH WATERFALL + DIAGNOSIS ────────────────────────────────────────────
    col_wf, col_diag = st.columns([3, 2])

    with col_wf:
        st.markdown('<div class="sh">Net Cash Release by Lever (PKR M)</div>', unsafe_allow_html=True)
        names   = [lv["title"].replace(" (Ricoma Machines)","").replace("Structured ","")[:30] for lv in levers]
        impacts = [lv["cash"]/1e6 for lv in levers]
        colors  = ["#3fb950" if v >= 0 else "#f85149" for v in impacts]
        fig = go.Figure(go.Bar(x=names, y=impacts, marker_color=colors,
                               text=[f"{'+'if v>=0 else ''}{v:.0f}M" for v in impacts],
                               textposition="outside", cliponaxis=False))
        fig.add_hline(y=0, line_dash="dot", line_color="#8b949e")
        net = sum(impacts)
        fig.add_annotation(x=.98, y=.95, xref="paper", yref="paper",
            text=f"<b>Net: PKR {net:.0f}M</b>", showarrow=False,
            font=dict(size=12, color="#58a6ff"),
            bgcolor="#161b22", bordercolor="#30363d", borderwidth=1)
        fig.update_layout(**{**CHART, "height":300,
                             "xaxis":dict(gridcolor="#21262d", tickangle=-15, tickfont=dict(size=9)),
                             "yaxis":dict(gridcolor="#21262d", title="PKR M"), "showlegend":False})
        st.plotly_chart(fig, width="stretch")

    with col_diag:
        st.markdown('<div class="sh">Health Diagnosis</div>', unsafe_allow_html=True)
        items = [
            ("Dead Stock",          d["fg_winter_fcst"]/1e6,      0,                            "PKR 70M idle — clear now",           "RED"),
            ("WIP Days",            d["wip_days_fcst"],            d["wip_days_tgt"],            f"{d['wip_days_fcst']:.0f} vs {d['wip_days_tgt']:.0f} target","RED"),
            ("FG Days",             d["fg_total_days_fcst"],       d["fg_total_days_tgt"],       f"{d['fg_total_days_fcst']:.0f} vs {d['fg_total_days_tgt']:.0f} target","AMBER"),
            ("MG DPO",              d["mg_pay_days_fcst"],         120,                          f"{d['mg_pay_days_fcst']:.0f} days — relationship risk","RED"),
            ("Other Pay DPO",       d["oth_pay_days_fcst"],        d["oth_pay_days_tgt"],        f"{d['oth_pay_days_fcst']:.0f} vs {d['oth_pay_days_tgt']:.0f} target","AMBER"),
            ("E-com Receivables",   d["ecom_rec_fcst"]/1e6,        d["ecom_rec_tgt"]/1e6,       "Easy win — T+3 settlement","GREEN"),
            ("YTD EBITDA (PKR M)",  d["ytd_ebitda"]/1e6,           0,                           f"PKR {d['ytd_ebitda']/1e6:.0f}M loss","RED"),
        ]
        for label, val, tgt, note, status in items:
            st.markdown(f"{rag(status)} &nbsp; **{label}** — {note}", unsafe_allow_html=True)
            st.markdown("")

    # ── EBITDA BRIDGE ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="sh">EBITDA Bridge — FY25 Actual → FY26 Budget</div>', unsafe_allow_html=True)
    bridge_x = ["FY25 EBITDA", "Revenue\nGrowth", "COGS\nChange", "Opex\nChange", "FY26 Budget\nEBITDA"]
    rev_delta  = (d["fy26_net_rev"]  - d["fy25_net_rev"])  / 1e6
    cogs_delta = (d["fy26_cogs"]     - d["fy25_cogs"])     / 1e6 * -1
    opex_delta = ((d["fy26_stores_opex"] + d["fy26_corp_oh"]) - (d["fy25_stores_opex"] + d["fy25_corp_oh"])) / 1e6 * -1
    bridge_y   = [d["fy25_ebitda"]/1e6, rev_delta, cogs_delta, opex_delta, d["fy26_ebitda"]/1e6]
    bclr = ["#388bfd"] + ["#3fb950" if v >= 0 else "#f85149" for v in bridge_y[1:-1]] + ["#bc8cff"]
    fig_br = go.Figure(go.Bar(x=bridge_x, y=bridge_y, marker_color=bclr,
                               text=[f"{v:+.0f}M" for v in bridge_y], textposition="outside", cliponaxis=False))
    fig_br.add_hline(y=0, line_dash="dot", line_color="#8b949e")
    fig_br.update_layout(**{**CHART, "height":280, "showlegend":False,
                            "yaxis":dict(gridcolor="#21262d", title="PKR M"),
                            "xaxis":dict(gridcolor="#21262d")})
    st.plotly_chart(fig_br, width="stretch")

    st.markdown(f"""<div class="warn">
<b>⚠ Budget Assumption Gap:</b> FY26 budget assumes COGS at
{d['fy26_cogs']/d['fy26_net_rev']*100:.0f}% of net revenue, but YTD actual COGS is
{d['ytd_cogs']/d['ytd_gross_rev']*100:.0f}% of gross sales. The GP budget of {pkr(d['fy26_gp'])} is likely
<b>unreachable without a cost-card reforecast</b>. WC improvements are necessary but not sufficient.
</div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 2 — FINANCIAL MODEL  (merged Financial Health + Scenario Modeller)
# ══════════════════════════════════════════════════════════════════════════════
elif "Financial" in page:
    st.title("Financial Model — Edit Any Number, See Full Impact")
    st.caption("All assumptions are live. Change any cell and every metric, chart and table updates instantly.")

    with st.expander("✏️ Edit All Assumptions", expanded=True):
        d = assumptions_panel("fm")
    d = st.session_state.d
    c = calc(d)
    levers = build_levers(d, c)

    st.markdown("---")

    # ── KPI IMPACT ROW ────────────────────────────────────────────────────────
    k1,k2,k3,k4,k5,k6 = st.columns(6)
    k1.metric("Total WC Release",    pkr(c["total_wc_release"]))
    k2.metric("Annual WC Benefit",   pkr(c["annual_wc_benefit"]))
    k3.metric("Net EMB Saving/yr",   pkr(c["net_sav"]))
    k4.metric("Combined Annual Ben.", pkr(c["total_annual_benefit"]))
    k5.metric("EMB Payback",          f"{c['payback']:.1f} yrs")
    gp_pct = (d["annual_sales"] - d["annual_cogs"]) / d["annual_sales"] * 100
    k6.metric("Implied GP%",          f"{gp_pct:.1f}%",
              delta=f"Budget GP%: {d['fy26_gp']/d['fy26_net_rev']*100:.1f}%")

    st.markdown("---")

    col_l, col_r = st.columns(2)

    with col_l:
        # P&L comparison
        st.markdown('<div class="sh">P&L: FY25 Actual vs FY26 Budget vs YTD Run-Rate</div>', unsafe_allow_html=True)
        pl_items = ["Net Revenue","Gross Profit","Stores Opex","Corp OH","EBITDA"]
        fy25 = [d["fy25_net_rev"], d["fy25_gp"], -d["fy25_stores_opex"], -d["fy25_corp_oh"], d["fy25_ebitda"]]
        fy26 = [d["fy26_net_rev"], d["fy26_gp"], -d["fy26_stores_opex"], -d["fy26_corp_oh"], d["fy26_ebitda"]]
        ytd_ann = [d["ytd_net_rev"]*12/8, d["ytd_gp"]*12/8,
                   -d["ytd_stores_opex"]*12/8, -d["ytd_corp_oh"]*12/8, d["ytd_ebitda"]*12/8]
        fig_pl = go.Figure()
        for nm, vals, clr in [("FY25 Actuals", fy25,"#8b949e"),
                               ("FY26 Budget",  fy26,"#388bfd"),
                               ("YTD Run-Rate", ytd_ann,"#f85149")]:
            fig_pl.add_trace(go.Bar(name=nm, x=pl_items, y=[v/1e6 for v in vals], marker_color=clr, opacity=0.85))
        fig_pl.add_hline(y=0, line_dash="dot", line_color="#8b949e")
        fig_pl.update_layout(**{**CHART, "barmode":"group", "height":320,
                                "yaxis":dict(gridcolor="#21262d", title="PKR M"),
                                "xaxis":dict(gridcolor="#21262d")})
        st.plotly_chart(fig_pl, width="stretch")
        st.caption("YTD run-rate = YTD × 12/8 months annualised.")

        # WC lever waterfall
        st.markdown('<div class="sh">WC Cash Release — Updated from Your Inputs</div>', unsafe_allow_html=True)
        lv_names   = [lv["title"].replace(" (Ricoma Machines)","")[:28] for lv in levers]
        lv_impacts = [lv["cash"]/1e6 for lv in levers]
        fig_lv = go.Figure(go.Bar(x=lv_names, y=lv_impacts,
                                   marker_color=["#3fb950" if v>=0 else "#f85149" for v in lv_impacts],
                                   text=[f"{'+'if v>=0 else ''}{v:.0f}M" for v in lv_impacts],
                                   textposition="outside", cliponaxis=False))
        fig_lv.add_hline(y=0, line_dash="dot", line_color="#8b949e")
        fig_lv.update_layout(**{**CHART, "height":280, "showlegend":False,
                                "yaxis":dict(gridcolor="#21262d", title="PKR M"),
                                "xaxis":dict(gridcolor="#21262d", tickangle=-15, tickfont=dict(size=9))})
        st.plotly_chart(fig_lv, width="stretch")

    with col_r:
        # WC ratio table — live
        st.markdown('<div class="sh">WC Ratios — Live</div>', unsafe_allow_html=True)
        dc = d["annual_cogs"] / 365
        ratio_rows = [
            ("WIP Days",         d["wip_days_fcst"],       d["wip_days_tgt"],        True,  pkr(c["wip_release"])),
            ("FG Days",          d["fg_total_days_fcst"],  d["fg_total_days_tgt"],   True,  pkr(c["fg_release"])),
            ("Dead Stock",       d["fg_winter_fcst"]/1e6,  d["fg_winter_tgt"]/1e6,   True,  pkr(c["dead_release"])),
            ("MG DPO",           d["mg_pay_days_fcst"],    d["mg_pay_days_tgt"],     False, pkr(c["mg_relief"])),
            ("Other Pay DPO",    d["oth_pay_days_fcst"],   d["oth_pay_days_tgt"],    False, pkr(abs(c["oth_relief"]))),
            ("E-com Rec (M)",    d["ecom_rec_fcst"]/1e6,   d["ecom_rec_tgt"]/1e6,   True,  pkr(c["rec_release"])),
        ]
        rdf = []
        for label, fcst, tgt, lower_better, cash_imp in ratio_rows:
            gap  = fcst - tgt
            good = gap <= 0 if lower_better else gap >= 0
            rdf.append({"Metric":label, "Current":round(fcst,1), "Target":round(tgt,1),
                        "Gap":round(gap,1), "Cash Impact":cash_imp,
                        "Status":"✅ On Track" if good else "❌ Behind"})
        st.dataframe(pd.DataFrame(rdf), hide_index=True, width="stretch", height=260)

        # Inventory composition pie
        st.markdown('<div class="sh">Inventory Composition (Current)</div>', unsafe_allow_html=True)
        fig_pie = go.Figure(go.Pie(
            labels=["WIP","FG Summer","Dead Stock","FG Others","Raw Mat."],
            values=[c["wip_bal"], d["fg_summer_fcst"], d["fg_winter_fcst"],
                    d["fg_others_fcst"], d["raw_mat_fcst"]],
            hole=0.45, marker_colors=["#388bfd","#3fb950","#f85149","#8b949e","#d29922"],
        ))
        fig_pie.update_layout(**{**CHART, "height":220,
                                 "annotations":[{"text":"Inventory","x":0.5,"y":0.5,
                                                 "font_size":10,"showarrow":False,"font_color":"#8b949e"}]})
        st.plotly_chart(fig_pie, width="stretch")

        # ── WC Interest Cost section ──────────────────────────────────────────
        st.markdown('<div class="sh">WC Interest Cost — Annual Financing Burden</div>', unsafe_allow_html=True)
        st.caption(f"At {d['cost_of_capital']*100:.0f}% cost of capital. Payables finance you (benefit); inventory & receivables cost you.")
        wc_int_rows = [
            ("Inventory Holding Cost",   c["wc_int_inv_fcst"],  c["wc_int_inv_tgt"],  True),
            ("Receivables Financing Cost",c["wc_int_rec_fcst"], c["wc_int_rec_tgt"],  True),
            ("Payables Financing Benefit",c["wc_int_pay_fcst"], c["wc_int_pay_tgt"],  False),
            ("Net WC Financing Cost",     c["wc_net_cost_fcst"], c["wc_net_cost_tgt"], True),
        ]
        wc_int_df = []
        for label, fcst, tgt, lower_better in wc_int_rows:
            saving = fcst - tgt
            good   = saving > 0 if lower_better else saving < 0
            wc_int_df.append({
                "Head":           label,
                "Current (PKR M)": round(fcst/1e6, 1),
                "At Target (PKR M)":round(tgt/1e6,  1),
                "Annual Saving (PKR M)": round(saving/1e6, 1),
                "Impact":         "✅ Saving" if good else ("➡ Same" if saving==0 else "❌ Cost"),
            })
        st.dataframe(pd.DataFrame(wc_int_df), hide_index=True, use_container_width=True)
        st.markdown(f"""<div class="info" style="margin-top:6px">
<b>Total WC interest cost improvement:</b> {pkr(c['wc_interest_improvement'])}/yr —
the annual saving from moving all WC levers to target at {d['cost_of_capital']*100:.0f}% CoC.
Payables (PKR {c['pay_total_fcst']/1e6:.0f}M) currently finance {pkr(c['wc_int_pay_fcst'])}/yr of your working capital.
</div>""", unsafe_allow_html=True)

        # Key diagnostics
        st.markdown('<div class="sh">Diagnostic Alerts</div>', unsafe_allow_html=True)
        cogs_actual_pct = d["ytd_cogs"] / d["ytd_gross_rev"] * 100
        cogs_budget_pct = d["fy26_cogs"] / d["fy26_net_rev"] * 100
        st.markdown(f"""<div class="alert" style="margin-bottom:8px">
<b>COGS Over-Run:</b> Actual {cogs_actual_pct:.0f}% vs budget {cogs_budget_pct:.0f}%.
GP budget of {pkr(d['fy26_gp'])} is likely unachievable.
</div>""", unsafe_allow_html=True)
        st.markdown(f"""<div class="warn" style="margin-bottom:8px">
<b>MG Payables:</b> {d['mg_pay_days_fcst']:.0f} days DPO = {pkr(d['mg_pay_days_fcst']*dc)} owed.
8+ months of supplier exposure — a pay-down plan is non-negotiable.
</div>""", unsafe_allow_html=True)
        st.markdown(f"""<div class="info">
<b>Revenue Miss:</b> Only {abs((d['ytd_gross_rev']-d['ytd_budget_rev'])/d['ytd_budget_rev']*100):.1f}% below budget.
This is a COGS + WC problem, not primarily a revenue problem.
</div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 3 — ACTION PLAN & ROADMAP  (merged)
# ══════════════════════════════════════════════════════════════════════════════
elif "Action" in page:
    d = st.session_state.d
    c = calc(d)
    levers = build_levers(d, c)

    st.title("Action Plan & Execution Roadmap")
    st.caption("6 levers ranked by priority. Expand each for step-by-step execution detail + 12-month roadmap below.")

    # ── Summary table ─────────────────────────────────────────────────────────
    st.markdown('<div class="sh">All Levers — Priority Ranked</div>', unsafe_allow_html=True)
    rows = []
    for i, lv in enumerate(levers, 1):
        rows.append({"Rank":f"#{i}", "Action":lv["title"], "Category":lv["category"],
                     "Cash Impact":pkr(lv["cash"]), "Urgency":"⚡"*lv["urgency"],
                     "Difficulty":stars(lv["difficulty"]),
                     "Timeline":lv["timeline"], "Owner":lv["owner"], "Status":lv["rag"]})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    st.markdown("---")
    st.markdown("### Execution Detail")

    for i, lv in enumerate(levers, 1):
        cash_str = f"{'+'if lv['cash']>=0 else ''}{pkr(lv['cash'])}"
        with st.expander(f"#{i}  {lv['title']}  |  {cash_str}  |  {lv['timeline']}", expanded=(i<=2)):
            col_l, col_r = st.columns([2,1])
            with col_l:
                st.markdown(f"**Why this matters:**  {lv['why']}")
                st.markdown("**Step-by-step actions:**")
                for act in lv["actions"]:
                    st.markdown(f"→ {act}")
            with col_r:
                st.markdown(f"**Cash impact:** {cash_str}")
                st.markdown(f"**Urgency:** {'⚡'*lv['urgency']} {lv['urgency']}/5")
                st.markdown(f"**Difficulty:** {stars(lv['difficulty'])} {lv['difficulty']}/5")
                st.markdown(f"**Timeline:** {lv['timeline']}")
                st.markdown(f"**Owner:** {lv['owner']}")

    st.markdown("---")
    st.markdown("### 12-Month Execution Roadmap")

    total_r = c["total_wc_release"]
    dc = d["annual_cogs"] / 365

    months_list = ["Jul-25","Aug-25","Sep-25","Oct-25","Nov-25","Dec-25",
                   "Jan-26","Feb-26","Mar-26","Apr-26","May-26","Jun-26"]

    roadmap = [
        ("Jul-25","MD","Schedule MG pay-down meeting. Count dead stock by SKU. Call Daraz T+3.",
         c["rec_release"]*0.5 + c["dead_release"]*0.05, "🔴"),
        ("Aug-25","Retail Head","Launch in-store markdown (40–50%). B2B buyer outreach for dead stock.",
         c["dead_release"]*0.30, "🔴"),
        ("Sep-25","Ops/MGA","Ricoma machines arrive + install. First EMB batches in-house.",
         c["dead_release"]*0.55 + c["wip_release"]*0.10, "🟡"),
        ("Oct-25","Ops+Buying","Full EMB in-house. Freeze FG intake. Open-to-buy live.",
         c["dead_release"]*0.75 + c["wip_release"]*0.30, "🟡"),
        ("Nov-25","CFO","Finalise top 10 vendor terms (45-day net). MG pay-down PKR 10M.",
         c["dead_release"]*0.85 + c["wip_release"]*0.50 + abs(c["oth_relief"])*0.25, "🟡"),
        ("Dec-25","MD+CFO","Year-end WC review. MG PKR 15M from dead stock proceeds.",
         c["dead_release"] + c["wip_release"]*0.65 + abs(c["oth_relief"])*0.45, "🟡"),
        ("Jan-26","Buying","New season: strict DIO. No intake until FG days below 100.",
         c["dead_release"] + c["wip_release"]*0.80 + abs(c["oth_relief"])*0.60, "🟢"),
        ("Feb-26","E-com","E-com T+3 confirmed. Receivables below PKR 10M.",
         c["dead_release"] + c["wip_release"]*0.90 + c["rec_release"] + abs(c["oth_relief"])*0.70, "🟢"),
        ("Mar-26","CFO","All creditor terms renegotiated and in place.",
         c["dead_release"] + c["wip_release"] + c["rec_release"] + abs(c["oth_relief"])*0.90, "🟢"),
        ("Apr-26","Retail","Summer peak. Maintain all WC discipline. No new dead stock.",
         total_r * 0.85, "🟢"),
        ("May-26","MD","Pre-season FY27 planning — WC constraints built in from day 1.",
         total_r * 0.93, "🟢"),
        ("Jun-26","MD+CFO","FY26 close. All 6 levers delivered. WC fully optimised.",
         total_r, "🟢"),
    ]

    col_t, col_c = st.columns([1, 1])

    with col_t:
        rdf = pd.DataFrame(roadmap, columns=["Month","Owner","Action","Cumulative Release","Icon"])
        rdf["Cum. Release (PKR M)"] = rdf["Cumulative Release"].apply(lambda v: round(v/1e6,1))
        rdf["% of Target"]          = rdf["Cumulative Release"].apply(
            lambda v: f"{min(v/total_r*100,100):.0f}%" if total_r else "–")
        st.dataframe(rdf[["Icon","Month","Owner","Action","Cum. Release (PKR M)","% of Target"]],
                 hide_index=True, width="stretch", height=460)

    with col_c:
        st.markdown('<div class="sh">Cumulative Cash Release Trajectory</div>', unsafe_allow_html=True)
        cum_vals = [r[3]/1e6 for r in roadmap]
        fig_rd = go.Figure()
        fig_rd.add_trace(go.Scatter(x=months_list, y=cum_vals, mode="lines+markers",
                                     line=dict(color="#3fb950", width=3), marker=dict(size=8),
                                     fill="tozeroy", fillcolor="rgba(63,185,80,0.10)"))
        fig_rd.add_hline(y=total_r/1e6, line_dash="dash", line_color="#d29922",
                         annotation_text=f"  Target: {pkr(total_r)}",
                         annotation_font_color="#d29922")
        fig_rd.update_layout(**{**CHART, "height":360, "showlegend":False,
                                "xaxis":dict(gridcolor="#21262d", tickangle=-30),
                                "yaxis":dict(gridcolor="#21262d", title="PKR M")})
        st.plotly_chart(fig_rd, width="stretch")

        # Monthly split bar
        st.markdown('<div class="sh">Monthly Cash Release Breakdown</div>', unsafe_allow_html=True)
        monthly_vals = [cum_vals[0]] + [cum_vals[i] - cum_vals[i-1] for i in range(1, len(cum_vals))]
        fig_mb = go.Figure(go.Bar(x=months_list, y=monthly_vals,
                                   marker_color=["#f85149" if v < 0 else "#3fb950" for v in monthly_vals],
                                   text=[f"{v:.0f}M" for v in monthly_vals],
                                   textposition="outside", cliponaxis=False))
        fig_mb.update_layout(**{**CHART, "height":220, "showlegend":False,
                                "yaxis":dict(gridcolor="#21262d", title="PKR M"),
                                "xaxis":dict(gridcolor="#21262d", tickangle=-30, tickfont=dict(size=9))})
        st.plotly_chart(fig_mb, width="stretch")

    # ── 1-YEAR FINANCIAL PROJECTION: WITH vs WITHOUT PLAN ──────────────────────
    st.markdown("---")
    st.markdown("### 1-Year Financial Projection: With vs Without This Plan")
    st.caption("Without Plan = YTD run-rate annualised (no improvement). With Plan = all 6 levers fully executed.")

    # WITHOUT plan: annualise YTD actuals (8 months → 12)
    rev_base    = d["ytd_net_rev"]   * 12 / 8
    cogs_base   = d["ytd_cogs"]      * 12 / 8
    gp_base     = d["ytd_gp"]        * 12 / 8
    opex_base   = (d["ytd_stores_opex"] + d["ytd_corp_oh"]) * 12 / 8
    ebitda_base = d["ytd_ebitda"]    * 12 / 8

    # WITH plan: quantified improvements from each lever
    dead_recovery   = d["fg_winter_fcst"] * 0.55          # 55% cash recovery on dead stock clearance
    emb_saving      = c["net_sav"]                         # annual in-house EMB saving
    wc_int_saving   = c["wc_interest_improvement"]         # annual WC financing cost saving
    fg_carry_saving = c["fg_release"] * d["cost_of_capital"]  # freed FG capital at CoC
    rec_saving      = c["rec_release"] * d["cost_of_capital"] # freed receivables

    rev_plan    = rev_base + dead_recovery                 # dead stock proceeds add to top line
    cogs_plan   = cogs_base - emb_saving                   # EMB in-house cuts COGS
    gp_plan     = rev_plan - cogs_plan
    opex_plan   = opex_base                                # opex unchanged (no structural cut)
    ebitda_plan = gp_plan - opex_plan + wc_int_saving + fg_carry_saving + rec_saving
    ebitda_improvement = ebitda_plan - ebitda_base

    # Tables side by side
    col_wo, col_wi, col_delta = st.columns(3)

    with col_wo:
        st.markdown(f"""<div class="card">
<div style="font-size:13px;font-weight:700;color:#8b949e;margin-bottom:10px">WITHOUT PLAN<br><span style="font-size:11px;font-weight:400">YTD run-rate continued</span></div>
<table style="width:100%;font-size:14px;border-collapse:collapse">
<tr><td style="padding:5px 0;color:#c9d1d9">Net Revenue</td><td style="text-align:right;color:#e6edf3;font-weight:600">{pkr(rev_base)}</td></tr>
<tr><td style="padding:5px 0;color:#c9d1d9">COGS</td><td style="text-align:right;color:#f85149;font-weight:600">({pkr(cogs_base)})</td></tr>
<tr><td style="padding:5px 0;color:#c9d1d9;border-top:1px solid #30363d">Gross Profit</td><td style="text-align:right;color:#e6edf3;font-weight:700;border-top:1px solid #30363d">{pkr(gp_base)}</td></tr>
<tr><td style="padding:5px 0;color:#c9d1d9">GP%</td><td style="text-align:right;color:#d29922">{gp_base/rev_base*100:.1f}%</td></tr>
<tr><td style="padding:5px 0;color:#c9d1d9">Stores + Corp Opex</td><td style="text-align:right;color:#f85149">({pkr(opex_base)})</td></tr>
<tr><td style="padding:5px 0;color:#c9d1d9;border-top:1px solid #30363d">EBITDA</td><td style="text-align:right;font-weight:800;color:#f85149;border-top:1px solid #30363d">{pkr(ebitda_base)}</td></tr>
<tr><td style="padding:5px 0;color:#c9d1d9">Dead Stock</td><td style="text-align:right;color:#f85149">Still {pkr(d['fg_winter_fcst'])} depreciating</td></tr>
<tr><td style="padding:5px 0;color:#c9d1d9">WC Interest Cost</td><td style="text-align:right;color:#f85149">({pkr(c['wc_net_cost_fcst'])})/yr</td></tr>
</table>
</div>""", unsafe_allow_html=True)

    with col_wi:
        st.markdown(f"""<div class="card" style="border-color:#3fb950">
<div style="font-size:13px;font-weight:700;color:#3fb950;margin-bottom:10px">WITH PLAN<br><span style="font-size:11px;font-weight:400;color:#8b949e">All 6 levers executed</span></div>
<table style="width:100%;font-size:14px;border-collapse:collapse">
<tr><td style="padding:5px 0;color:#c9d1d9">Net Revenue</td><td style="text-align:right;color:#e6edf3;font-weight:600">{pkr(rev_plan)}</td></tr>
<tr><td style="padding:5px 0;color:#c9d1d9">COGS</td><td style="text-align:right;color:#f85149;font-weight:600">({pkr(cogs_plan)})</td></tr>
<tr><td style="padding:5px 0;color:#c9d1d9;border-top:1px solid #30363d">Gross Profit</td><td style="text-align:right;color:#3fb950;font-weight:700;border-top:1px solid #30363d">{pkr(gp_plan)}</td></tr>
<tr><td style="padding:5px 0;color:#c9d1d9">GP%</td><td style="text-align:right;color:#3fb950">{gp_plan/rev_plan*100:.1f}%</td></tr>
<tr><td style="padding:5px 0;color:#c9d1d9">Stores + Corp Opex</td><td style="text-align:right;color:#f85149">({pkr(opex_plan)})</td></tr>
<tr><td style="padding:5px 0;color:#c9d1d9;border-top:1px solid #30363d">EBITDA (incl. WC saving)</td><td style="text-align:right;font-weight:800;{'color:#3fb950' if ebitda_plan>=0 else 'color:#d29922'};border-top:1px solid #30363d">{pkr(ebitda_plan)}</td></tr>
<tr><td style="padding:5px 0;color:#c9d1d9">Dead Stock</td><td style="text-align:right;color:#3fb950">Cleared: +{pkr(dead_recovery)}</td></tr>
<tr><td style="padding:5px 0;color:#c9d1d9">WC Interest Cost</td><td style="text-align:right;color:#3fb950">({pkr(c['wc_net_cost_tgt'])})/yr</td></tr>
</table>
</div>""", unsafe_allow_html=True)

    with col_delta:
        st.markdown(f"""<div class="card" style="border-color:#58a6ff">
<div style="font-size:13px;font-weight:700;color:#58a6ff;margin-bottom:10px">IMPROVEMENT<br><span style="font-size:11px;font-weight:400;color:#8b949e">Plan vs No Plan</span></div>
<table style="width:100%;font-size:14px;border-collapse:collapse">
<tr><td style="padding:5px 0;color:#c9d1d9">Revenue uplift</td><td style="text-align:right;color:#3fb950;font-weight:600">+{pkr(rev_plan-rev_base)}</td></tr>
<tr><td style="padding:4px 0;font-size:12px;color:#8b949e;padding-left:12px">Dead stock recovery</td><td style="text-align:right;font-size:12px;color:#8b949e">+{pkr(dead_recovery)}</td></tr>
<tr><td style="padding:5px 0;color:#c9d1d9">COGS reduction</td><td style="text-align:right;color:#3fb950;font-weight:600">+{pkr(emb_saving)}</td></tr>
<tr><td style="padding:4px 0;font-size:12px;color:#8b949e;padding-left:12px">EMB in-house saving</td><td style="text-align:right;font-size:12px;color:#8b949e">+{pkr(emb_saving)}</td></tr>
<tr><td style="padding:5px 0;color:#c9d1d9">WC interest saving</td><td style="text-align:right;color:#3fb950;font-weight:600">+{pkr(wc_int_saving)}</td></tr>
<tr><td style="padding:5px 0;color:#c9d1d9">FG carry saving</td><td style="text-align:right;color:#3fb950;font-weight:600">+{pkr(fg_carry_saving)}</td></tr>
<tr><td style="padding:5px 0;color:#c9d1d9;border-top:1px solid #30363d;font-weight:700">EBITDA Improvement</td><td style="text-align:right;font-weight:800;color:#3fb950;border-top:1px solid #30363d">+{pkr(ebitda_improvement)}</td></tr>
<tr><td style="padding:5px 0;color:#c9d1d9">WC Cash Released</td><td style="text-align:right;color:#58a6ff;font-weight:700">+{pkr(c['total_wc_release'])}</td></tr>
</table>
</div>""", unsafe_allow_html=True)

    # Visual comparison bar chart
    st.markdown('<div class="sh">P&L Comparison — Without Plan vs With Plan</div>', unsafe_allow_html=True)
    pl_labels  = ["Net Revenue","Gross Profit","EBITDA"]
    base_vals  = [rev_base/1e6, gp_base/1e6, ebitda_base/1e6]
    plan_vals  = [rev_plan/1e6, gp_plan/1e6, ebitda_plan/1e6]
    fig_proj = go.Figure()
    fig_proj.add_trace(go.Bar(name="Without Plan", x=pl_labels, y=base_vals,
                               marker_color="#8b949e", opacity=0.85,
                               text=[f"{v:+.0f}M" for v in base_vals], textposition="outside"))
    fig_proj.add_trace(go.Bar(name="With Plan",    x=pl_labels, y=plan_vals,
                               marker_color="#3fb950", opacity=0.85,
                               text=[f"{v:+.0f}M" for v in plan_vals], textposition="outside"))
    fig_proj.add_hline(y=0, line_dash="dot", line_color="#8b949e")
    fig_proj.update_layout(**{**CHART, "barmode":"group", "height":320,
                              "yaxis":dict(gridcolor="#21262d", title="PKR M"),
                              "xaxis":dict(gridcolor="#21262d"),
                              "annotations":[dict(x=1.01, y=1, xref="paper", yref="paper",
                                  text=f"<b>EBITDA swing: +{pkr(ebitda_improvement)}</b>",
                                  showarrow=False, font=dict(size=12, color="#3fb950"),
                                  bgcolor="#161b22", bordercolor="#3fb950", borderwidth=1,
                                  xanchor="right")]})
    st.plotly_chart(fig_proj, use_container_width=True)

    st.markdown(f"""<div class="info">
<b>Key assumptions in the With Plan scenario:</b>
55% recovery on PKR {d['fg_winter_fcst']/1e6:.0f}M dead stock = <b>+{pkr(dead_recovery)}</b> revenue |
EMB in-house removes outsource cost = <b>+{pkr(emb_saving)}</b> COGS saving |
WC financing cost drops by <b>+{pkr(wc_int_saving)}</b>/yr at {d['cost_of_capital']*100:.0f}% CoC |
FG inventory reduction saves <b>+{pkr(fg_carry_saving)}</b>/yr carry cost.
</div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 4 — MACHINERY ROI  (number inputs, not sliders)
# ══════════════════════════════════════════════════════════════════════════════
elif "Machinery" in page:
    st.title("Machinery ROI — 28 Ricoma EMB Machines")
    st.caption("Enter values directly. All ROI metrics and charts update instantly.")

    d = st.session_state.d

    st.markdown('<div class="sh">Machine Assumptions — Edit Directly</div>', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("**Equipment**")
        d["num_machines"]      = int(st.number_input("Number of Machines",         value=int(d["num_machines"]),      step=1,   key="m_num"))
        d["machine_cost_usd"]  = int(st.number_input("Machine Cost (USD each)",     value=int(d["machine_cost_usd"]),  step=500, key="m_cost"))
        d["usd_pkr"]           = int(st.number_input("USD / PKR Rate",              value=int(d["usd_pkr"]),           step=1,   key="m_fx"))
        d["install_cost"]      = st.number_input("Install + Freight (PKR M)",       value=float(d["install_cost"]/1e6), step=0.1, key="m_inst") * 1e6
        d["machine_life_yrs"]  = int(st.number_input("Machine Life (Years)",        value=int(d["machine_life_yrs"]),  step=1,   key="m_life"))

    with col2:
        st.markdown("**Production**")
        d["pcs_per_mach_day"]  = int(st.number_input("Pcs per Machine per Day",     value=int(d["pcs_per_mach_day"]),  step=1,   key="m_pcs"))
        d["op_days"]           = int(st.number_input("Operating Days per Year",     value=int(d["op_days"]),           step=1,   key="m_days"))
        d["outsource_cost_pc"] = int(st.number_input("Outsource EMB Cost/pc (PKR)", value=int(d["outsource_cost_pc"]), step=5,   key="m_out"))
        d["inhouse_cost_pc"]   = int(st.number_input("In-House EMB Cost/pc (PKR)",  value=int(d["inhouse_cost_pc"]),   step=5,   key="m_in"))

    with col3:
        st.markdown("**Operating Costs**")
        d["operator_wage_mo"]  = int(st.number_input("Operator Monthly Wage (PKR)", value=int(d["operator_wage_mo"]),  step=1000,key="m_wage"))
        d["ops_per_mach"]      = int(st.number_input("Operators per Machine",       value=int(d["ops_per_mach"]),      step=1,   key="m_ops"))
        d["annual_power"]      = st.number_input("Annual Power Cost (PKR M)",       value=float(d["annual_power"]/1e6), step=0.1, key="m_pwr") * 1e6
        d["annual_maint"]      = st.number_input("Annual Maintenance (PKR M)",      value=float(d["annual_maint"]/1e6), step=0.1, key="m_mnt") * 1e6

    with col4:
        st.markdown("**WC Link**")
        d["wip_days_fcst"]     = st.number_input("WIP Days (Current)",              value=float(d["wip_days_fcst"]),   step=0.5, key="m_wip_f")
        d["wip_days_tgt"]      = st.number_input("WIP Days (Post In-House)",        value=float(d["wip_days_tgt"]),    step=0.5, key="m_wip_t")
        d["annual_cogs"]       = st.number_input("Annual COGS (PKR M)",             value=float(d["annual_cogs"]/1e6), step=10.0,key="m_cogs") * 1e6
        d["cost_of_capital"]   = st.number_input("Cost of Capital (%)",             value=float(d["cost_of_capital"]*100), step=0.5, key="m_coc") / 100

    st.session_state.d = d
    c = calc(d)

    st.markdown("---")

    # KPI row
    k1,k2,k3,k4,k5 = st.columns(5)
    k1.metric("Total CAPEX",            pkr(c["capex"]))
    k2.metric("Annual Capacity",        f"{c['capacity']:,.0f} pcs")
    k3.metric("Net EMB Saving/yr",      pkr(c["net_sav"]))
    k4.metric("Payback Period",         f"{c['payback']:.1f} yrs",
              delta="🟢 Good" if c["payback"]<2 else ("🟡 Acceptable" if c["payback"]<4 else "🔴 Long"))
    k5.metric("3-Year Net Return",      pkr(c["net_3yr"]),
              delta=f"ROI Yr1: {c['roi_yr1']*100:.0f}%")

    st.markdown("---")
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown('<div class="sh">Annual Benefits & Cost Breakdown</div>', unsafe_allow_html=True)
        items  = ["Gross EMB\nSaving","Operator\nCost","Power\nCost","Maintenance","Net EMB\nSaving","WC Interest\nBenefit","Total Annual\nBenefit"]
        vals   = [c["gross_sav"], -c["run_cost"]*0.9, -d["annual_power"], -d["annual_maint"],
                  c["net_sav"], c["annual_wc_benefit"], c["total_annual_benefit"]]
        clrs   = ["#3fb950","#f85149","#f85149","#f85149","#58a6ff","#3fb950","#bc8cff"]
        fig_b  = go.Figure(go.Bar(x=items, y=[v/1e6 for v in vals], marker_color=clrs,
                                   text=[f"PKR {v/1e6:.1f}M" for v in vals],
                                   textposition="outside", cliponaxis=False))
        fig_b.add_hline(y=0, line_dash="dot", line_color="#8b949e")
        fig_b.update_layout(**{**CHART, "height":300, "showlegend":False,
                               "yaxis":dict(gridcolor="#21262d", title="PKR M"),
                               "xaxis":dict(gridcolor="#21262d", tickangle=-10)})
        st.plotly_chart(fig_b, width="stretch")

        # Detailed numbers table
        st.markdown('<div class="sh">Detailed Calculation</div>', unsafe_allow_html=True)
        calc_rows = [
            ("CAPEX",                    pkr(c["capex"]),              f"{d['num_machines']} × USD {d['machine_cost_usd']:,} × PKR {d['usd_pkr']} + install"),
            ("Annual Capacity",          f"{c['capacity']:,.0f} pcs",  f"{d['pcs_per_mach_day']} pcs/mach × {d['num_machines']} mach × {d['op_days']} days"),
            ("Saving/Piece",             f"PKR {d['outsource_cost_pc']-d['inhouse_cost_pc']}",f"PKR {d['outsource_cost_pc']} outsource − PKR {d['inhouse_cost_pc']} in-house"),
            ("Gross EMB Saving",         pkr(c["gross_sav"]),          "Capacity × saving/piece"),
            ("Total Run Cost",           pkr(c["run_cost"]),           "Operators + power + maintenance"),
            ("Net EMB Saving",           pkr(c["net_sav"]),            "Gross − run cost"),
            ("Annual Depreciation",      pkr(c["annual_depr"]),        f"Straight-line over {d['machine_life_yrs']} yrs"),
            ("WIP Release (days cut)",   pkr(c["wip_release"]),        f"{d['wip_days_fcst']:.1f} → {d['wip_days_tgt']:.1f} days"),
            ("WC Interest Benefit",      pkr(c["annual_wc_benefit"]),  f"WC release × {d['cost_of_capital']*100:.0f}% CoC"),
            ("Total Annual Benefit",     pkr(c["total_annual_benefit"]),"EMB + WC interest"),
            ("Payback",                  f"{c['payback']:.1f} years",  "CAPEX ÷ total annual benefit"),
            ("3-Year Net Return",        pkr(c["net_3yr"]),            "3 × net EMB saving − CAPEX"),
        ]
        st.dataframe(pd.DataFrame(calc_rows, columns=["Metric","Value","Notes"]),
                 hide_index=True, width="stretch")

    with col_r:
        st.markdown('<div class="sh">Payback Curve</div>', unsafe_allow_html=True)
        years = list(range(0, 8))
        cum   = [0] + [c["net_sav"]*y/1e6 for y in range(1,8)]
        cap_l = [c["capex"]/1e6]*8
        fig_pb = go.Figure()
        fig_pb.add_trace(go.Scatter(x=years, y=cum, mode="lines+markers",
                                     name="Cumulative Benefit", line=dict(color="#3fb950", width=3)))
        fig_pb.add_trace(go.Scatter(x=years, y=cap_l, mode="lines",
                                     name="CAPEX", line=dict(color="#f85149", dash="dash", width=2)))
        if c["payback"] < 8:
            fig_pb.add_vline(x=c["payback"], line_dash="dot", line_color="#d29922",
                             annotation_text=f"  Payback: {c['payback']:.1f} yrs",
                             annotation_font_color="#d29922")
        fig_pb.update_layout(**{**CHART, "height":280,
                                "xaxis":dict(gridcolor="#21262d", title="Year"),
                                "yaxis":dict(gridcolor="#21262d", title="PKR M")})
        st.plotly_chart(fig_pb, width="stretch")

        st.markdown('<div class="sh">Sensitivity: Net Annual Saving (PKR M)</div>', unsafe_allow_html=True)
        sav_range = [40, 50, 60, 70, 80, 100, 120]
        pcs_range = [100_000, 200_000, 300_000, 336_000, 400_000, 500_000]
        z = [[round((pcs*s - c["run_cost"])/1e6, 1) for s in sav_range] for pcs in pcs_range]
        fig_ht = go.Figure(go.Heatmap(
            z=z, x=[f"PKR {s}" for s in sav_range], y=[f"{p//1000}K pcs" for p in pcs_range],
            colorscale="RdYlGn",
            text=[[f"{v:.1f}M" for v in row] for row in z], texttemplate="%{text}",
            colorbar=dict(title="PKR M", tickfont=dict(color="#e6edf3"), titlefont=dict(color="#e6edf3")),
        ))
        fig_ht.update_layout(**{**CHART, "height":310,
                                "xaxis":dict(title="Saving/Piece (PKR)"),
                                "yaxis":dict(title="Annual Pieces")})
        st.plotly_chart(fig_ht, width="stretch")
        st.caption(f"Base case: {c['capacity']//1000}K pcs × PKR {d['outsource_cost_pc']-d['inhouse_cost_pc']} = {pkr(c['net_sav'])}/yr")

# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 5 — CASH FLOW FORECAST  (monthly + weekly, head-wise)
# ══════════════════════════════════════════════════════════════════════════════
elif "Cash Flow" in page:
    d = st.session_state.d
    c = calc(d)

    st.title("Cash Flow Forecast — Head-Wise")
    st.caption("Forward cash requirements and releases by category, based on your current Command Centre inputs.")

    # ── KPIs ──────────────────────────────────────────────────────────────────
    monthly_burn = d["ytd_ebitda"] * 12 / 8 / 12
    k1,k2,k3,k4 = st.columns(4)
    k1.metric("Monthly Op. Cash Burn",   pkr(monthly_burn),      delta="Based on YTD run-rate", delta_color="inverse")
    k2.metric("Total WC Release (12M)",  pkr(c["total_wc_release"]))
    k3.metric("Cash & Bank (Current)",   pkr(d["cash_bank"]))
    runway_months = d["cash_bank"] / abs(monthly_burn) if monthly_burn < 0 else 99
    k4.metric("Cash Runway",             f"{runway_months:.1f} months",
              delta="at current burn rate", delta_color="inverse" if runway_months < 3 else "normal")

    st.markdown("---")

    tab_m, tab_w = st.tabs(["📅 Monthly (12 months)", "📆 Weekly (12 weeks)"])

    def style_df(df):
        """Colour positive green, negative red for cash columns."""
        def colour(val):
            try:
                v = float(val)
                if v > 0: return "color:#3fb950;font-weight:600"
                if v < 0: return "color:#f85149;font-weight:600"
            except: pass
            return ""
        cash_cols = [c for c in df.columns if "PKR M" in c]
        return df.style.applymap(colour, subset=cash_cols)

    with tab_m:
        st.markdown('<div class="sh">Monthly Cash Flow — Next 12 Months (PKR M)</div>', unsafe_allow_html=True)
        df_m = build_cashflow(d, c, periods=12, weekly=False)

        # Show operating and WC sections in sub-tabs
        sub_full, sub_ops, sub_wc = st.tabs(["Full View", "Operating Only", "WC Initiatives Only"])

        op_cols  = ["Month","Sales Receipts (PKR M)","COGS Payments (PKR M)","Gross Profit (PKR M)",
                    "Stores Opex (PKR M)","Corp Overhead (PKR M)","Operating EBITDA (PKR M)"]
        wc_cols  = ["Month","Dead Stock Proceeds (PKR M)","WIP Release (PKR M)","FG Release (PKR M)",
                    "Other Pay. Extension (PKR M)","MG Pay-Down (PKR M)","E-com Collection (PKR M)",
                    "Net Cash Flow (PKR M)","Cumulative (PKR M)"]

        with sub_full:
            st.dataframe(style_df(df_m), hide_index=True, use_container_width=True, height=480)
        with sub_ops:
            st.caption("Operating P&L cash flows — YTD run-rate annualised (12/8 months)")
            st.dataframe(style_df(df_m[op_cols]), hide_index=True, use_container_width=True)
        with sub_wc:
            st.caption("WC initiative cash releases/obligations on top of operating flows")
            st.dataframe(style_df(df_m[wc_cols]), hide_index=True, use_container_width=True)

        # Chart: operating vs WC stacked
        st.markdown('<div class="sh">Monthly Cash Flow — Operating vs WC Initiatives</div>', unsafe_allow_html=True)
        fig_cf = go.Figure()
        fig_cf.add_trace(go.Bar(name="Sales Receipts",       x=df_m["Month"], y=df_m["Sales Receipts (PKR M)"].tolist(),      marker_color="#3fb950", opacity=0.85))
        fig_cf.add_trace(go.Bar(name="COGS Payments",        x=df_m["Month"], y=df_m["COGS Payments (PKR M)"].tolist(),        marker_color="#f85149", opacity=0.85))
        fig_cf.add_trace(go.Bar(name="Stores Opex",          x=df_m["Month"], y=df_m["Stores Opex (PKR M)"].tolist(),          marker_color="#d29922", opacity=0.85))
        fig_cf.add_trace(go.Bar(name="Corp Overhead",        x=df_m["Month"], y=df_m["Corp Overhead (PKR M)"].tolist(),        marker_color="#bc8cff", opacity=0.85))
        fig_cf.add_trace(go.Bar(name="Dead Stock Proceeds",  x=df_m["Month"], y=df_m["Dead Stock Proceeds (PKR M)"].tolist(),  marker_color="#58a6ff", opacity=0.85))
        fig_cf.add_trace(go.Bar(name="WIP Release",          x=df_m["Month"], y=df_m["WIP Release (PKR M)"].tolist(),          marker_color="#388bfd", opacity=0.85))
        fig_cf.add_trace(go.Bar(name="FG + Payables + E-com",x=df_m["Month"],
                                y=[a+b+c_v+d_v for a,b,c_v,d_v in zip(
                                    df_m["FG Release (PKR M)"].tolist(),
                                    df_m["Other Pay. Extension (PKR M)"].tolist(),
                                    df_m["MG Pay-Down (PKR M)"].tolist(),
                                    df_m["E-com Collection (PKR M)"].tolist())],
                                marker_color="#f0883e", opacity=0.85))
        fig_cf.add_trace(go.Scatter(name="Net Cash Flow", x=df_m["Month"],
                                    y=df_m["Net Cash Flow (PKR M)"].tolist(),
                                    mode="lines+markers", line=dict(color="#ffffff", width=2),
                                    marker=dict(size=7)))
        fig_cf.add_hline(y=0, line_dash="dot", line_color="#8b949e")
        fig_cf.update_layout(**{**CHART, "barmode":"stack", "height":370,
                                "yaxis":dict(gridcolor="#21262d", title="PKR M"),
                                "xaxis":dict(gridcolor="#21262d", tickangle=-30)})
        st.plotly_chart(fig_cf, use_container_width=True)

        # Cumulative line
        st.markdown('<div class="sh">Cumulative Cash Position (Starting from Cash & Bank)</div>', unsafe_allow_html=True)
        cum_abs = [d["cash_bank"]/1e6 + v for v in df_m["Cumulative (PKR M)"].tolist()]
        fig_cum = go.Figure(go.Scatter(x=df_m["Month"], y=cum_abs, mode="lines+markers",
                                        line=dict(color="#3fb950", width=3),
                                        fill="tozeroy", fillcolor="rgba(63,185,80,0.10)"))
        fig_cum.add_hline(y=0, line_dash="dash", line_color="#f85149",
                          annotation_text="  Zero cash line", annotation_font_color="#f85149")
        fig_cum.add_hline(y=d["cash_bank"]/1e6, line_dash="dot", line_color="#8b949e",
                          annotation_text=f"  Today: {pkr(d['cash_bank'])}", annotation_font_color="#8b949e")
        fig_cum.update_layout(**{**CHART, "height":260, "showlegend":False,
                                 "yaxis":dict(gridcolor="#21262d", title="PKR M"),
                                 "xaxis":dict(gridcolor="#21262d", tickangle=-30)})
        st.plotly_chart(fig_cum, use_container_width=True)

    with tab_w:
        st.markdown('<div class="sh">Weekly Cash Flow — Next 12 Weeks (PKR M)</div>', unsafe_allow_html=True)
        df_w = build_cashflow(d, c, periods=12, weekly=True)

        sub_wf, sub_wo, sub_ww = st.tabs(["Full View","Operating Only","WC Initiatives Only"])
        wk_op  = ["Week","Sales Receipts (PKR M)","COGS Payments (PKR M)","Gross Profit (PKR M)",
                  "Stores Opex (PKR M)","Corp Overhead (PKR M)","Operating EBITDA (PKR M)"]
        wk_wc  = ["Week","Dead Stock Proceeds (PKR M)","WIP Release (PKR M)","FG Release (PKR M)",
                  "Other Pay. Extension (PKR M)","MG Pay-Down (PKR M)","E-com Collection (PKR M)",
                  "Net Cash Flow (PKR M)","Cumulative (PKR M)"]
        with sub_wf: st.dataframe(style_df(df_w), hide_index=True, use_container_width=True, height=480)
        with sub_wo: st.dataframe(style_df(df_w[wk_op]), hide_index=True, use_container_width=True)
        with sub_ww: st.dataframe(style_df(df_w[wk_wc]), hide_index=True, use_container_width=True)

        st.markdown('<div class="sh">Weekly Net Cash Flow</div>', unsafe_allow_html=True)
        fig_wk = go.Figure()
        fig_wk.add_trace(go.Bar(x=df_w["Week"], y=df_w["Net Cash Flow (PKR M)"].tolist(),
                                 marker_color=["#3fb950" if v>=0 else "#f85149"
                                               for v in df_w["Net Cash Flow (PKR M)"].tolist()],
                                 text=[f"{v:.1f}M" for v in df_w["Net Cash Flow (PKR M)"].tolist()],
                                 textposition="outside", cliponaxis=False))
        fig_wk.add_hline(y=0, line_dash="dot", line_color="#8b949e")
        fig_wk.update_layout(**{**CHART, "height":280, "showlegend":False,
                                "yaxis":dict(gridcolor="#21262d", title="PKR M"),
                                "xaxis":dict(gridcolor="#21262d", tickangle=-30, tickfont=dict(size=9))})
        st.plotly_chart(fig_wk, use_container_width=True)

        st.markdown('<div class="sh">Weekly Cash by Head (Stacked)</div>', unsafe_allow_html=True)
        fig_wh = go.Figure()
        wc_heads = [
            ("Sales Receipts",    "Sales Receipts (PKR M)",         "#3fb950"),
            ("COGS Payments",     "COGS Payments (PKR M)",          "#f85149"),
            ("Stores + Corp OH",  "Operating EBITDA (PKR M)",       "#d29922"),
            ("Dead Stock",        "Dead Stock Proceeds (PKR M)",    "#58a6ff"),
            ("WIP Release",       "WIP Release (PKR M)",            "#388bfd"),
            ("FG + Others",       "FG Release (PKR M)",             "#f0883e"),
            ("MG Pay-Down",       "MG Pay-Down (PKR M)",            "#bc8cff"),
            ("E-com",             "E-com Collection (PKR M)",       "#8b949e"),
        ]
        for name, col_name, clr in wc_heads:
            if col_name in df_w.columns:
                fig_wh.add_trace(go.Bar(name=name, x=df_w["Week"],
                                         y=df_w[col_name].tolist(), marker_color=clr, opacity=0.85))
        fig_wh.add_hline(y=0, line_dash="dot", line_color="#8b949e")
        fig_wh.update_layout(**{**CHART, "barmode":"stack", "height":320,
                                "yaxis":dict(gridcolor="#21262d", title="PKR M"),
                                "xaxis":dict(gridcolor="#21262d", tickangle=-30, tickfont=dict(size=9))})
        st.plotly_chart(fig_wh, use_container_width=True)

    # ── Assumptions note ──────────────────────────────────────────────────────
    ann_rev_disp  = d["ytd_net_rev"]  * 12 / 8
    ann_cogs_disp = d["ytd_cogs"]     * 12 / 8
    ann_op_disp   = (d["ytd_stores_opex"] + d["ytd_corp_oh"]) * 12 / 8
    st.markdown("---")
    st.markdown(f"""<div class="info">
<b>How this cash flow is built:</b><br>
<b>A. Operating Flows</b> (YTD actuals × 12/8 annualised, then ÷ periods):<br>
&nbsp;&nbsp;• Sales Receipts: {pkr(ann_rev_disp)}/yr → {pkr(ann_rev_disp/12)}/month<br>
&nbsp;&nbsp;• COGS Payments: ({pkr(ann_cogs_disp)}/yr) — cash to suppliers<br>
&nbsp;&nbsp;• Stores + Corp Opex: ({pkr(ann_op_disp)}/yr) — fixed operating outflows<br>
&nbsp;&nbsp;• Operating EBITDA = Receipts − COGS − Opex ({pkr(d['ytd_ebitda']*12/8)}/yr run-rate)<br><br>
<b>B. WC Initiative Flows</b> (one-time releases ramped over time):<br>
&nbsp;&nbsp;• Dead stock proceeds — front-loaded, most cash in months 1–4<br>
&nbsp;&nbsp;• WIP release — starts Month 3 when EMB machines installed<br>
&nbsp;&nbsp;• FG release — gradual as intake freeze reduces inventory<br>
&nbsp;&nbsp;• Other payables extension — ramps as vendor terms renegotiated<br>
&nbsp;&nbsp;• MG pay-down — fixed monthly outflow per agreed schedule<br>
&nbsp;&nbsp;• E-com collection — immediate, front-loaded<br><br>
Change any input in <b>Command Centre → Edit Assumptions</b> and all flows update automatically.
</div>""", unsafe_allow_html=True)
