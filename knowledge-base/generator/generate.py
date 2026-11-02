"""Generates the fictitious Alpenlogic AG knowledge base (PDF + DOCX).

Run:  .venv/bin/python generate.py
Output: ../documents/
Everything here is fictitious. Ground truth and deliberate traps: ../GROUND_TRUTH.md
"""
from pathlib import Path

from docx import Document
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path(__file__).resolve().parent.parent / "documents"
OUT.mkdir(exist_ok=True)

NAME = "Alpenlogic AG"
ADDRESS = "Pfingstweidstrasse 31, 8005 Zurich, Switzerland"
UID = "CHE-123.456.789"
DISCLAIMER = "Fictitious document created for software testing purposes only."

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=18, spaceAfter=8)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=13, spaceBefore=10, spaceAfter=4)
BODY = ParagraphStyle("B", parent=ss["BodyText"], fontSize=10, leading=14)
CELL = ParagraphStyle("C", parent=BODY, fontSize=9.5, leading=12)


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.grey)
    canvas.drawString(20 * mm, 10 * mm, DISCLAIMER)
    canvas.drawRightString(190 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def pdf(filename, story):
    doc = SimpleDocTemplate(str(OUT / filename), pagesize=A4, leftMargin=20 * mm,
                            rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=20 * mm,
                            title=filename, author="Fictitious issuer")
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)


def kv(rows, widths=(55 * mm, 115 * mm)):
    data = [[Paragraph(f"<b>{k}</b>", CELL), Paragraph(v, CELL)] for k, v in rows]
    t = Table(data, colWidths=widths)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def P(text, style=BODY):
    return Paragraph(text, style)


# ---------------------------------------------------------------- PDFs
def commercial_register():
    pdf("01_commercial_register_extract.pdf", [
        P("Commercial Register of the Canton of Zurich", H1),
        P("Extract (certified), issued on 20 October 2026"),
        Spacer(1, 6),
        kv([
            ("Company name", NAME),
            ("UID", UID),
            ("Legal form", "Company limited by shares (Aktiengesellschaft, AG)"),
            ("Registered office", "Zurich (ZH)"),
            ("Business address", ADDRESS),
            ("Date of incorporation", "14 March 2016 (entry in the commercial register)"),
            ("Share capital", "CHF 500,000 (fully paid in), divided into 1,000 registered shares of CHF 500 each"),
            ("Purpose", "Consulting, development and operation of digital transformation and artificial "
                        "intelligence solutions, as well as related training and cloud services. The company may "
                        "establish branches, acquire holdings and carry out all transactions serving its purpose."),
            ("Board of directors", "Marc Keller, Chairman (sole signature); Sofia Brunner, Member (collective signature of two)"),
            ("Management", "Marc Keller, CEO (sole signature); Sofia Brunner, CTO (collective signature of two)"),
            ("Auditor", "Limmat Revision AG, Zurich"),
        ]),
        Spacer(1, 10),
        P("This extract reflects the register status on the day of issue and has no legal effect without "
          "the certification stamp of the Commercial Register Office."),
    ])


def debt_enforcement():
    pdf("02_debt_enforcement_register_extract.pdf", [
        P("Debt Enforcement Office Zurich 5", H1),
        P("Extract from the debt enforcement register, issued on 22 October 2026"),
        Spacer(1, 6),
        kv([
            ("Debtor", f"{NAME}, {ADDRESS}"),
            ("UID", UID),
            ("Period covered", "Last five years (22 October 2021 to 22 October 2026)"),
            ("Pending debt collection proceedings", "None"),
            ("Bankruptcy proceedings", "None"),
            ("Seizures (attachments) carried out", "None"),
            ("Certificates of loss (actes de défaut de biens)", "None"),
        ]),
        Spacer(1, 10),
        P("<b>Result: no entries.</b> This extract is valid for the purposes of public procurement for three months."),
    ])


def insurance():
    pdf("03_liability_insurance_certificate.pdf", [
        P("Limmat Versicherungen AG", H1),
        P("Certificate of Professional and General Liability Insurance"),
        Spacer(1, 6),
        kv([
            ("Policyholder", f"{NAME}, {ADDRESS}"),
            ("Insurer", "Limmat Versicherungen AG, Bahnhofstrasse 90, 8001 Zurich"),
            ("Policy number", "RC-2025-448812"),
            ("Insurance period", "1 November 2025 to 31 October 2026"),
            ("Cover", "Professional and general liability for IT consulting, software development and cloud operation"),
            ("Sum insured per claim - personal injury", "CHF 10,000,000"),
            ("Sum insured per claim - property damage", "CHF 10,000,000"),
            ("Sum insured per claim - financial loss", "CHF 5,000,000"),
            ("Annual aggregate", "CHF 20,000,000"),
        ]),
        Spacer(1, 10),
        P("This certificate confirms the cover in force during the insurance period stated above. "
          "Renewal terms are agreed separately."),
    ])


def brochure():
    pdf("04_company_brochure_2026.pdf", [
        P("Alpenlogic AG - Company Profile 2026", H1),
        P("<i>Digital transformation and applied AI for Swiss organisations.</i>"),
        P("Who we are", H2),
        P("Founded in Zurich in 2016, Alpenlogic AG helps public bodies and mid-sized companies modernise their "
          "processes and put artificial intelligence to productive use. We combine strategy consulting, "
          "software engineering and managed operation of cloud platforms."),
        P("What we do", H2),
        P("<b>Main activity:</b> digital transformation consulting and development of AI technical solutions.<br/>"
          "<b>Secondary activities:</b> operation and support of cloud platforms (managed services) and professional training."),
        P("Our team", H2),
        kv([
            ("Total headcount (June 2026)", "28 people"),
            ("Higher professional training", "14 (university degree or higher vocational diploma)"),
            ("Professional training", "9 (federal VET diploma)"),
            ("Other staff and apprentices", "5"),
            ("Location", "Pfingstweidstrasse 31, 8005 Zurich (head office, single site)"),
        ]),
        P("Quality and security", H2),
        P("Alpenlogic AG is certified to <b>ISO 27001</b> (information security) and <b>ISO 9001</b> (quality management). "
          "Certificates are renewed after annual surveillance audits."),
        P("Contact", H2),
        P("Marc Keller, CEO - phone +41 44 555 01 20 - e-mail marc.keller@alpenlogic.example<br/>"
          "General enquiries: info@alpenlogic.example"),
    ])


def iso_certs():
    story = []
    for std, scope, num, valid in [
        ("ISO/IEC 27001:2022", "Information security management system", "IS-ZH-77310", "12 March 2028"),
        ("ISO 9001:2015", "Quality management system", "QM-ZH-55102", "12 March 2028"),
    ]:
        story += [
            P("Certificate of Conformity", H1),
            P(f"This is to certify that the management system of <b>{NAME}</b>, {ADDRESS}, conforms to the "
              f"requirements of <b>{std}</b>."),
            Spacer(1, 6),
            kv([
                ("Standard", std), ("Scope", f"{scope} for consulting, development and operation of AI and cloud solutions"),
                ("Certificate no.", num), ("Certification body", "Swiss Cert Services AG (fictitious)"),
                ("Initial certification", "13 March 2019"), ("Valid until", valid),
            ]),
            PageBreak(),
        ]
    pdf("05_iso_certificates.pdf", story[:-1])


def tax_attestation():
    pdf("06_tax_attestation.pdf", [
        P("Cantonal Tax Office Zurich", H1),
        P("Attestation of tax compliance, issued on 1 October 2026"),
        Spacer(1, 6),
        kv([
            ("Taxpayer", f"{NAME}, UID {UID}"),
            ("Competent tax office", "Cantonal Tax Office Zurich, Corporate Taxes, Steuerweg 12, 8090 Zurich"),
        ]),
        Spacer(1, 8),
        P("The Cantonal Tax Office confirms that, as of 30 September 2026, the taxpayer has paid in full all "
          "<b>cantonal, municipal and direct federal taxes</b> due, including back taxes, up to and including tax period 2025. "
          "No outstanding amounts are recorded."),
        P("This attestation does not cover value added tax (VAT), which is administered by the Federal Tax Administration."),
    ])


def ahv_certificate():
    pdf("07_social_insurance_certificate.pdf", [
        P("Social Insurance Institution of the Canton of Zurich (SVA Zurich)", H1),
        P("AHV compensation office - certificate of contributions, issued on 5 October 2026"),
        Spacer(1, 6),
        kv([
            ("Affiliated employer", f"{NAME}, UID {UID}"),
            ("AHV compensation office", "Social Insurance Institution of the Canton of Zurich, Hardturmstrasse 120, 8005 Zurich"),
            ("Contributions covered", "AHV, IV, EO, FAK (family allowances) and ALV"),
            ("Status", "All contributions due up to 30 September 2026 have been paid in full, including the employee "
                       "shares deducted from wages."),
        ]),
    ])


def pension_confirmation():
    pdf("08_pension_fund_confirmation.pdf", [
        P("Sammelstiftung Limmat BVG", H1),
        P("Confirmation of affiliation and contribution payments (occupational pension, BVG), 6 October 2026"),
        Spacer(1, 6),
        kv([
            ("Employer", f"{NAME}, UID {UID}"),
            ("Pension fund", "Sammelstiftung Limmat BVG, Seestrasse 200, 8002 Zurich"),
            ("Affiliation", "Since 1 April 2016, mandatory and supplementary occupational pension (BVG)"),
            ("Status", "All contributions due until 30 September 2026 have been paid in full, including the employee "
                       "shares deducted from wages."),
        ]),
    ])


# ---------------------------------------------------------------- DOCX
def docx_base(title):
    d = Document()
    d.add_heading(title, 0)
    sec = d.sections[0]
    sec.footer.paragraphs[0].text = DISCLAIMER
    return d


def annual_report():
    d = docx_base("Alpenlogic AG - Annual Report 2024")
    d.add_heading("1. Company overview", 1)
    d.add_paragraph(f"{NAME} is a company limited by shares (AG) incorporated in Zurich in 2016. Its main "
                    "activity is consulting and software development for digital transformation and AI.")
    d.add_heading("2. Share capital and shareholders", 1)
    d.add_paragraph("As at 31 December 2024 the share capital amounts to CHF 500,000, divided into 1,000 registered "
                    "shares of CHF 500 each, fully paid in. The company holds no treasury shares.")
    t = d.add_table(rows=1, cols=3)
    t.style = "Light Grid"
    for c, h in zip(t.rows[0].cells, ("Shareholder", "Share", "Nationality / seat")):
        c.text = h
    for row in [("Founders (Marc Keller and Sofia Brunner, jointly)", "60%", "Swiss nationals, resident in Switzerland"),
                ("Helvetia Growth Fund (fictitious)", "25%", "Zurich, Switzerland"),
                ("Employee participation foundation", "15%", "Zurich, Switzerland")]:
        cells = t.add_row().cells
        for c, v in zip(cells, row):
            c.text = v
    d.add_paragraph("No shareholder is of Russian nationality or established in the Russian Federation.")
    d.add_heading("3. People", 1)
    d.add_paragraph("At 31 December 2024 the company employed 31 people (29.2 full-time equivalents), "
                    "including 3 apprentices.")
    d.add_heading("4. Financial summary (CHF thousand)", 1)
    t = d.add_table(rows=1, cols=3)
    t.style = "Light Grid"
    for c, h in zip(t.rows[0].cells, ("Item", "2024", "2023")):
        c.text = h
    for row in [("Revenue", "6,420", "5,810"), ("Operating profit", "710", "590"), ("Equity", "2,380", "1,950")]:
        cells = t.add_row().cells
        for c, v in zip(cells, row):
            c.text = v
    d.add_heading("5. Social security", 1)
    d.add_paragraph("The company is affiliated with the SVA Zurich as AHV compensation office "
                    "(Röntgenstrasse 17, 8005 Zurich) and with Sammelstiftung Limmat BVG for occupational pension.")
    d.save(OUT / "09_annual_report_2024.docx")


def hr_policy():
    d = docx_base("Alpenlogic AG - HR & Employment Compliance Policy (2026)")
    sections = [
        ("1. Occupational health and safety", "Alpenlogic AG complies with the applicable occupational health and "
         "safety regulations. A safety officer is appointed and annual workplace checks are documented."),
        ("2. Collective and standard employment agreements", "No collective employment agreement (CEA) declared "
         "generally binding applies to the company's IT consulting activities. Employment relationships follow "
         "the Swiss Code of Obligations and individual contracts consistent with customary conditions of the sector. "
         "No standard employment contract (NAV) is applicable to the activity."),
        ("3. Wages and working conditions", "Wages and working conditions meet the customary standards of the sector "
         "in Zurich. The company complies with notification and permit obligations under the BGSA when "
         "posting or hiring foreign personnel."),
        ("4. Equal treatment", "The company applies the principle of non-discrimination and equal treatment of "
         "women and men, including equal pay, verified by an internal annual pay analysis."),
        ("5. Environment", "The company complies with Swiss environmental protection regulations applicable at its "
         "place of performance. Its offices use renewable electricity and a business-travel policy limits flights."),
        ("6. Social insurance", "The AHV compensation office is the SVA Zurich, Röntgenstrasse 17, 8005 Zurich. "
         "Occupational pension: Sammelstiftung Limmat BVG, Seestrasse 200, 8002 Zurich."),
    ]
    for h, text in sections:
        d.add_heading(h, 1)
        d.add_paragraph(text)
    d.save(OUT / "10_hr_compliance_policy.docx")


def procurement_policy():
    d = docx_base("Alpenlogic AG - Procurement & Business Conduct Policy (2026)")
    sections = [
        ("1. Fair competition", "Alpenlogic AG does not enter into agreements and does not take measures that "
         "restrict competition. Staff are trained annually on competition law. No investigation is pending."),
        ("2. Sanctions screening", "The company is not on any list of sanctioned bidders, including the list under "
         "Art. 45 para. 3 IVöB (verified internally on 1 October 2026). Shareholders and beneficial owners have no "
         "connection to the Russian Federation within the meaning of Art. 29c of the Ordinance on Measures "
         "connected with the Situation in Ukraine."),
        ("3. Subcontractors", "In agreements with subcontractors and suppliers, the company includes the obligations "
         "regarding working conditions, tax, social insurance and environmental protection required by public "
         "procurement law. Subcontractors above 10% of the contract value are screened against sanctions lists."),
    ]
    for h, text in sections:
        d.add_heading(h, 1)
        d.add_paragraph(text)
    d.save(OUT / "11_procurement_conduct_policy.docx")


if __name__ == "__main__":
    for fn in (commercial_register, debt_enforcement, insurance, brochure, iso_certs, tax_attestation,
               ahv_certificate, pension_confirmation, annual_report, hr_policy, procurement_policy):
        fn()
    print(sorted(p.name for p in OUT.iterdir()))
