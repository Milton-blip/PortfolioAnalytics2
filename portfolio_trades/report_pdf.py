from fpdf import FPDF
from .fonts import ensure_unicode_font

def _fmt_currency(x):
    x = float(x)
    s = f"${abs(x):,.2f}"
    return f"({s})" if x < 0 else s

def _fmt_number(x):
    return f"{float(x):,.1f}"

def render_pdf(tx, acc_sum, by_status, vol_pct_tag: int, outfile: str):
    font_path = ensure_unicode_font()
    pdf = FPDF(orientation="P", unit="mm", format="Letter")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.add_font("Unicode", "", font_path)
    pdf.set_font("Unicode", size=12)

    title = f"Transaction List - Target {vol_pct_tag}% Vol (Real Terms)"
    pdf.cell(0, 8, title, ln=1)

    cols = [("Identifier",32,"L"),("Sleeve",24,"L"),("Action",14,"C"),
            ("Shares_Delta",20,"R"),("Price",20,"R"),("AverageCost",20,"R"),
            ("Delta_$",24,"R"),("CapGain_$",24,"R")]

    def right_cell(w,h,t,b=0): pdf.cell(w,h,t,border=b,align="R")

    def header():
        pdf.set_font("Unicode", size=10)
        for (h,w,a) in cols: pdf.cell(w,7,h,border=1,align=a)
        pdf.ln(7)

    def row(r):
        pdf.set_font("Unicode", size=9)
        vals = [
            r["Identifier"], r["Sleeve"], r["Action"],
            _fmt_number(r["Shares_Delta"]), _fmt_currency(r["Price"]), _fmt_currency(r["AverageCost"]),
            _fmt_currency(r["Delta_Dollars"]), _fmt_currency(r["CapGain_Dollars"])
        ]
        for (hdr,w,a),v in zip(cols, vals):
            right_cell(w,7,str(v),1) if a=="R" else pdf.cell(w,7,str(v),1,align=a)
        pdf.ln(7)

    def kv(label, value):
        pdf.set_font("Unicode", size=10)
        pdf.cell(65,6,label,0,0,"L"); right_cell(40,6,value,0); pdf.ln(6)

    for (acct, tax), g in tx.sort_values(["Account","Action","Sleeve","Identifier"]).groupby(["Account","TaxStatus"]):
        pdf.ln(2); pdf.set_font("Unicode", size=11)
        pdf.cell(0,7,f"Account: {acct}", ln=1)
        pdf.set_font("Unicode", size=10)
        pdf.cell(0,6,f"Tax Status: {tax}", ln=1)
        header()
        for _, r in g.iterrows(): row(r)
        s = acc_sum[(acc_sum["Account"]==acct) & (acc_sum["TaxStatus"]==tax)].iloc[0]
        pdf.ln(2)
        kv("Total Buys",                _fmt_currency(s["Total_Buys"]))
        kv("Total Sells",               _fmt_currency(s["Total_Sells"]))
        kv("Net Realized Capital Gain", _fmt_currency(s["Net_CapGain"]))
        kv("Est Cap Gains Tax",         _fmt_currency(s["Est_Tax"]))
        pdf.ln(2)

    pdf.ln(4); pdf.set_font("Unicode", size=11)
    pdf.cell(0,7,"Tax Status Summary", ln=1)

    ts_cols = [("Tax Status",40,"L"),("Total Buys",35,"R"),("Total Sells",35,"R"),
               ("Net CapGain",35,"R"),("Est Tax",35,"R")]
    for h,w,a in ts_cols: pdf.cell(w,7,h,1,align=a)
    pdf.ln(7); pdf.set_font("Unicode", size=9)
    for _, r in by_status.iterrows():
        vals = [r["TaxStatus"], _fmt_currency(r["Total_Buys"]), _fmt_currency(r["Total_Sells"]),
                _fmt_currency(r["Net_CapGain"]), _fmt_currency(r["Est_Tax"])]
        for (h,w,a),v in zip(ts_cols, vals):
            right_cell(w,7,str(v),1) if a=="R" else pdf.cell(w,7,str(v),1,align=a)
        pdf.ln(7)

    pdf.output(outfile)