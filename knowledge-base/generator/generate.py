"""Generates the fictitious Alpenlogic AG knowledge base (PDF + DOCX).

Run:  .venv/bin/python generate.py
Output: ../documents/
Everything here is fictitious. Ground truth and deliberate traps: ../GROUND_TRUTH.md

The documents are intentionally noisy, like real ones: letterheads, reference numbers, page
numbering, legal boilerplate, history tables, unrelated sections. The facts listed in
GROUND_TRUTH.md are buried inside that noise. Do not change a fact here without updating it.
"""
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

OUT = Path(__file__).resolve().parent.parent / "documents"
OUT.mkdir(exist_ok=True)

NAME = "Alpenlogic AG"
ADDRESS = "Pfingstweidstrasse 31, 8005 Zurich, Switzerland"
UID = "CHE-123.456.789"
DISCLAIMER = "FICTITIOUS DOCUMENT - created for software testing purposes only. Not a real record."

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=16, spaceAfter=6, spaceBefore=4)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=11.5, spaceBefore=10, spaceAfter=3)
BODY = ParagraphStyle("B", parent=ss["BodyText"], fontSize=9.5, leading=13)
SMALL = ParagraphStyle("S", parent=BODY, fontSize=7.5, leading=9.5, textColor=colors.HexColor("#555555"))
CELL = ParagraphStyle("C", parent=BODY, fontSize=8.5, leading=11)
CELLB = ParagraphStyle("CB", parent=CELL, fontName="Helvetica-Bold")
RIGHT = ParagraphStyle("R", parent=BODY, alignment=2)


def P(text, style=BODY):
    return Paragraph(text, style)


def table(rows, widths, header=True, zebra=True, font=CELL, align_right_from=None):
    data = []
    for i, r in enumerate(rows):
        st = CELLB if (header and i == 0) else font
        data.append([c if not isinstance(c, str) else Paragraph(c, st) for c in r])
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#bbbbbb")),
             ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6e9ee")))
    if zebra:
        for i in range(1 if header else 0, len(rows)):
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f7f7f9")))
    t.setStyle(TableStyle(style))
    return t


def form_table(rows, widths=(55, 115)):
    """Label/value grid without header, like administrative forms."""
    data = [[Paragraph(k, CELLB), Paragraph(v, CELL)] for k, v in rows]
    t = Table(data, colWidths=[w * mm for w in widths])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#bbbbbb")),
                           ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


class NumberedCanvas(rl_canvas.Canvas):
    """Canvas that knows the total page count ("Page 2 of 5")."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self.setFont("Helvetica", 7.5)
            self.setFillColor(colors.HexColor("#555555"))
            self.drawRightString(190 * mm, 10 * mm, f"Page {self._pageNumber} of {total}")
            super().showPage()
        super().save()


def pdf(filename, issuer, ref, date, story, tagline="", confidential=""):
    """issuer = (name, [address lines]); drawn as letterhead on every page."""
    def deco(c, doc):
        c.saveState()
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(colors.HexColor("#1f3a5f"))
        c.drawString(20 * mm, 282 * mm, issuer[0])
        c.setFont("Helvetica", 7.5)
        c.setFillColor(colors.HexColor("#444444"))
        for i, line in enumerate(issuer[1]):
            c.drawString(20 * mm, (277.5 - 3.6 * i) * mm, line)
        c.drawRightString(190 * mm, 282 * mm, f"Ref.: {ref}")
        c.drawRightString(190 * mm, 278.4 * mm, date)
        if tagline:
            c.drawRightString(190 * mm, 274.8 * mm, tagline)
        if confidential:
            c.setFillColor(colors.HexColor("#a02020"))
            c.drawRightString(190 * mm, 271.2 * mm, confidential)
        c.setStrokeColor(colors.HexColor("#1f3a5f"))
        c.setLineWidth(0.8)
        c.line(20 * mm, 264 * mm, 190 * mm, 264 * mm)
        c.setStrokeColor(colors.HexColor("#bbbbbb"))
        c.setLineWidth(0.4)
        c.line(20 * mm, 14 * mm, 190 * mm, 14 * mm)
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.HexColor("#a02020"))
        c.drawString(20 * mm, 10 * mm, DISCLAIMER)
        c.restoreState()

    doc = BaseDocTemplate(str(OUT / filename), pagesize=A4, title=filename, author=issuer[0])
    frame = Frame(20 * mm, 18 * mm, 170 * mm, 242 * mm, id="f", leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=deco)])
    doc.build(story, canvasmaker=NumberedCanvas)


# ------------------------------------------------------------------ shared filler
DATA_PROTECTION = (
    "<b>Data protection.</b> Personal data are processed in accordance with the Swiss Federal Act on Data "
    "Protection (FADP). Data are used exclusively for the purposes described in this document and are not "
    "transmitted to third parties unless required by law. Requests for access or rectification may be addressed "
    "to the data protection contact named in our privacy notice.")
NO_LEGAL = ("This document is provided for information. It does not replace legal advice and creates no rights "
            "beyond those set out in the applicable legislation. Reproduction, even in part, is only permitted "
            "with the written consent of the issuer.")


# ------------------------------------------------------------------ PDFs
def commercial_register():
    reg = ("Commercial Register Office of the Canton of Zurich",
           ["Neumühlequai 10", "8090 Zurich", "Tel. +41 43 555 20 00 (Mon-Fri 08:00-12:00)", "www.hr.zh.example"])
    entries = [
        ["Entry no.", "Date", "Change", "Status"],
        ["1", "14.03.2016", "Incorporation of the company. Share capital CHF 100,000 (200 registered shares of CHF 500).", "<font color='#888888'>modified</font>"],
        ["2", "02.09.2016", "Entry of purpose clause and signing authorities.", "<font color='#888888'>modified</font>"],
        ["3", "21.06.2018", "Capital increase to CHF 500,000. Amendment of articles (art. 3). New share capital: CHF 500,000 divided into 1,000 registered shares of CHF 500 each, fully paid in.", "<b>current</b>"],
        ["4", "11.01.2021", "Change of address within Zurich. Former address: Hardstrasse 201, 8005 Zurich.", "<font color='#888888'>modified</font>"],
        ["5", "29.04.2022", "Appointment of Limmat Revision AG as auditor.", "<b>current</b>"],
        ["6", "18.10.2023", "Registered office address: Pfingstweidstrasse 31, 8005 Zurich.", "<b>current</b>"],
    ]
    persons = [
        ["Name", "Function", "Domicile", "Signature"],
        ["Keller, Marc", "Chairman of the board and CEO", "Zurich", "Sole signature"],
        ["Brunner, Sofia", "Member of the board and CTO", "Winterthur", "Collective signature of two"],
        ["Limmat Revision AG", "Auditor", "Zurich", "-"],
    ]
    pdf("01_commercial_register_extract.pdf", reg, "HR-ZH-2026-118842", "Issued: 20 October 2026", [
        P("Extract from the Commercial Register", H1),
        P("Certified extract - current entries and history", BODY),
        Spacer(1, 6),
        form_table([
            ("Company name", f"<b>{NAME}</b>"),
            ("UID", UID),
            ("CH-ID", "CH-020.3.045.118-7"),
            ("Legal form", "Company limited by shares (Aktiengesellschaft, AG)"),
            ("Registered office", "Zurich (ZH)"),
            ("Address", "Pfingstweidstrasse 31, 8005 Zurich"),
            ("Date of articles of association", "08.03.2016, last amended 21.06.2018"),
            ("Purpose", "Consulting, development and operation of digital transformation and artificial intelligence "
                        "solutions, as well as related training and cloud services. The company may establish "
                        "branches, acquire holdings and carry out all transactions serving its purpose."),
            ("Share capital", "CHF 500,000 (fully paid in)"),
            ("Shares", "1,000 registered shares of CHF 500 each"),
            ("Publication", "Swiss Official Gazette of Commerce (SOGC), see register history"),
        ]),
        P("Persons registered", H2),
        table(persons, (45, 55, 30, 40)),
        P("Register history", H2),
        table(entries, (14, 22, 112, 22)),
        PageBreak(),
        P("Information and legal notes", H1),
        P("1. This extract reproduces the register data on the day of issue. The Commercial Register Office "
          "certifies it only with the electronic seal printed on the last page. Entries marked <i>modified</i> are "
          "shown for information and are no longer valid."),
        P("2. The legal effect of entries is governed by Articles 929 ff. of the Swiss Code of Obligations and by "
          "the Commercial Register Ordinance. Public faith in the register (art. 933 CO) applies."),
        P("3. Bidders in public procurement procedures are generally required to provide an extract that is not "
          "older than three months."),
        P("Fees", H2),
        table([["Item", "Quantity", "Fee (CHF)"],
               ["Certified extract (electronic)", "1", "30.00"],
               ["History of entries", "1", "10.00"],
               ["VAT", "-", "not subject"],
               ["<b>Total</b>", "", "<b>40.00</b>"]], (100, 30, 40)),
        Spacer(1, 8),
        P("Payment reference: 00 00000 00000 11884 20261 02004. Payable within 30 days.", SMALL),
        P(NO_LEGAL, SMALL),
    ], tagline="Certified extract", confidential="")


def debt_enforcement():
    off = ("Debt Enforcement Office Zurich 5",
           ["Werdstrasse 75", "8036 Zurich", "Tel. +41 44 555 40 10", "Opening hours: Mon-Fri 08:00-11:30 / 13:30-16:30"])
    pdf("02_debt_enforcement_register_extract.pdf", off, "BA-Z5-2026-077319", "Issued: 22 October 2026", [
        P("Extract from the Debt Enforcement Register", H1),
        P("Procurement extract - legal entities"),
        Spacer(1, 6),
        form_table([
            ("Request no.", "BA-Z5-2026-077319"),
            ("Date of request", "22.10.2026"),
            ("Applicant", f"{NAME} (own request)"),
            ("Purpose", "Public procurement (proof of suitability)"),
            ("Debtor", f"{NAME}"),
            ("Address", ADDRESS),
            ("UID", UID),
            ("Registered office", "Zurich"),
        ]),
        P("Search result", H2),
        table([["Category", "Period", "Number of entries", "Total amount (CHF)"],
               ["Debt collection proceedings (pending)", "Last 5 years", "0", "0.00"],
               ["Debt collection proceedings (settled / withdrawn)", "Last 5 years", "0", "0.00"],
               ["Bankruptcy proceedings", "Last 5 years", "0", "0.00"],
               ["Seizures carried out", "Last 5 years", "0", "0.00"],
               ["Certificates of loss", "Last 5 years", "0", "0.00"],
               ["Realisation of pledged assets", "Last 5 years", "0", "0.00"]], (80, 30, 30, 30)),
        Spacer(1, 6),
        P("<b>Result: no entries recorded for the debtor identified above.</b>"),
        P("Legal basis and validity", H2),
        P("Third parties who demonstrate a legitimate interest may inspect the register (art. 8a DEBA). This "
          "extract is issued for the purposes of public procurement and is valid for three months from the "
          "date of issue. It only reflects proceedings registered at the Debt Enforcement Offices in the "
          "district of Zurich 5; entries in other districts must be requested separately."),
        P("Fees", H2),
        table([["Item", "Fee (CHF)"], ["Extract for legal entities", "17.00"], ["Administrative fee", "3.00"],
               ["<b>Total</b>", "<b>20.00</b>"]], (130, 40)),
        Spacer(1, 6),
        P(NO_LEGAL, SMALL),
    ], tagline="Official extract")


def insurance():
    ins = ("Limmat Versicherungen AG",
           ["Commercial Clients - Liability", "Bahnhofstrasse 90, 8001 Zurich", "Tel. +41 44 555 70 00", "claims@limmat-vers.example"])
    pdf("03_liability_insurance_certificate.pdf", ins, "RC-2025-448812", "Issued: 3 November 2025", [
        P("Certificate of Insurance", H1),
        P("Professional &amp; general liability insurance - business customers"),
        Spacer(1, 6),
        form_table([
            ("Policyholder", f"{NAME}<br/>{ADDRESS}"),
            ("Policy no.", "RC-2025-448812"),
            ("Customer no.", "CU-0044-8821"),
            ("Broker", "Seeblick Insurance Brokers GmbH, Zurich"),
            ("Insurance period", "01.11.2025 - 31.10.2026 (12:00)"),
            ("Premium", "CHF 14,860.00 per year (incl. 5% stamp duty), payable annually"),
            ("Business activity insured", "IT consulting, software development, AI solutions, operation of cloud platforms"),
        ]),
        P("Schedule of covers", H2),
        table([["Cover", "Limit per claim (CHF)", "Deductible (CHF)", "Notes"],
               ["Personal injury", "10,000,000", "1,000", "Incl. consequential losses"],
               ["Property damage", "10,000,000", "1,000", "Incl. data media, excl. data itself"],
               ["Financial loss (pure)", "5,000,000", "5,000", "Professional liability for consulting and development"],
               ["Cyber liability (third party)", "2,000,000", "10,000", "Separate sub-limit"],
               ["Legal expenses", "250,000", "-", "Contract and administrative proceedings"],
               ["Loss of documents entrusted", "100,000", "1,000", ""],
               ["Annual aggregate (all covers)", "20,000,000", "-", "Per insurance year"]],
              (50, 38, 30, 52)),
        Spacer(1, 6),
        P("Territorial scope: Switzerland and the Principality of Liechtenstein; worldwide for temporary "
          "assignments up to 90 days, excluding USA and Canada claims.", BODY),
        PageBreak(),
        P("Main exclusions (summary)", H2),
        P("The following are not insured, among others: intentional acts; fines and penalties; claims arising "
          "from asbestos, nuclear energy or war; infringement of patents; guarantees going beyond statutory "
          "liability; loss of or damage to property in the policyholder's custody; contractual penalties."),
        P("Obligations of the policyholder", H2),
        P("Claims must be notified within 14 days. The policyholder shall not acknowledge liability or make "
          "payments without the insurer's consent. Changes to the insured business activity or turnover "
          "above 20 % must be reported."),
        P("Insurance premiums by year", H2),
        table([["Year", "Premium (CHF)", "Claims paid (CHF)"], ["2023/24", "13,920.00", "0.00"],
               ["2024/25", "14,310.00", "0.00"], ["2025/26", "14,860.00", "0.00"]], (50, 60, 60)),
        Spacer(1, 6),
        P("This certificate confirms the cover in force during the insurance period stated above. It is "
          "issued at the policyholder's request and does not extend or modify the policy conditions "
          "(General Terms and Conditions edition 2022). Renewal is subject to separate agreement.", BODY),
        Spacer(1, 14),
        P("Limmat Versicherungen AG<br/><br/><i>Authorised signatories</i>: R. Meier, S. Vogel"),
        P(NO_LEGAL, SMALL),
    ], tagline="Valid with policy conditions")


def brochure():
    bro = ("Alpenlogic AG", ["Digital transformation &amp; applied AI", "Pfingstweidstrasse 31, 8005 Zurich", "www.alpenlogic.example"])

    def two_col(left, right):
        t = Table([[left, right]], colWidths=[82 * mm, 82 * mm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        return t

    pdf("04_company_brochure_2026.pdf", bro, "BRO-2026-EN-03", "Edition June 2026", [
        P("Making digital work. Making AI useful.", H1),
        P("<i>Company profile 2026</i>"),
        Spacer(1, 6),
        P("Alpenlogic AG supports public bodies and mid-sized companies in modernising their processes, data "
          "and services. We advise, we build, and we operate - with a team that has worked on more than 120 "
          "projects since 2016."),
        P("Our services", H2),
        two_col(
            [P("<b>Consulting</b><br/>Digital strategy, process analysis, target operating models, procurement "
               "support for IT tenders.<br/><br/><b>AI solutions</b><br/>Document intelligence, knowledge assistants, "
               "forecasting, evaluation and monitoring of AI systems.", CELL)],
            [P("<b>Software engineering</b><br/>Web platforms, integrations, APIs, legacy modernisation, "
               "quality assurance.<br/><br/><b>Cloud &amp; operations</b><br/>Managed services, monitoring, "
               "service desk, security patching, 24/7 on-call for critical systems.", CELL)]),
        P("Facts &amp; figures", H2),
        table([["Founded", "2016, Zurich"], ["Projects delivered", "120+"], ["Customer satisfaction (2025 survey)", "4.6 / 5"],
               ["Team (June 2026)", "28 people: 14 with higher professional training, 9 with professional training, 5 other staff and apprentices"],
               ["Languages", "German, French, English, Italian"],
               ["Site", "Single site: Pfingstweidstrasse 31, 8005 Zurich"]], (55, 115), header=False),
        PageBreak(),
        P("Selected references", H2),
        table([["Client (sector)", "Project", "Year"],
               ["Cantonal administration", "Digital counter and e-forms platform", "2024"],
               ["Regional hospital group", "Document classification with AI", "2025"],
               ["Municipal utility", "Smart-meter data platform", "2023"],
               ["Industrial SME", "Predictive maintenance pilot", "2025"],
               ["University institute", "Research data portal", "2022"]], (70, 80, 20)),
        P("Quality, security and recognition", H2),
        P("Our management systems are certified to <b>ISO 27001</b> (information security) and <b>ISO 9001</b> "
          "(quality). We are a member of the Swiss ICT association and a partner of several cloud providers. "
          "Awards: Swiss Digital Award finalist 2023; 'Great Place to Learn' label 2025."),
        P("Sustainability", H2),
        P("We use renewable electricity in our offices, offer public transport subsidies and compensate "
          "unavoidable business flights. Our team volunteers two days per year for local digital education projects."),
        P("Careers", H2),
        P("We are regularly looking for software engineers, data scientists and consultants. Apprenticeship "
          "positions (ICT specialist) start every August. Send your application to jobs@alpenlogic.example."),
        P("Contact", H2),
        table([["Role", "Name", "Phone", "E-mail"],
               ["Chief Executive Officer", "Marc Keller", "+41 44 555 01 20", "marc.keller@alpenlogic.example"],
               ["Chief Technology Officer", "Sofia Brunner", "+41 44 555 01 22", "sofia.brunner@alpenlogic.example"],
               ["General enquiries", "Reception", "+41 44 555 01 00", "info@alpenlogic.example"]], (45, 30, 35, 60)),
        Spacer(1, 8),
        P("Subscribe to our quarterly newsletter at www.alpenlogic.example/news. Figures as of June 2026 unless stated. "
          "Photos are illustrative.", SMALL),
    ], tagline="Company profile")


def iso_certs():
    cb = ("Swiss Cert Services AG", ["Certification body (accredited)", "Industriestrasse 12, 8400 Winterthur", "www.swisscert.example"])
    story = []
    for std, scope_title, num, valid, sc in [
        ("ISO/IEC 27001:2022", "Information security management system", "IS-ZH-77310", "12 March 2028",
         "Consulting, development and operation of AI and cloud solutions at the site Pfingstweidstrasse 31, "
         "8005 Zurich. Statement of applicability version 4.2 of 15 January 2025."),
        ("ISO 9001:2015", "Quality management system", "QM-ZH-55102", "12 March 2028",
         "Consulting, software development and managed operation of IT services at the site Pfingstweidstrasse 31, 8005 Zurich."),
    ]:
        story += [
            P("Certificate", H1),
            P(f"Certificate no. <b>{num}</b>"),
            Spacer(1, 4),
            P(f"The management system of <b>{NAME}</b>, {ADDRESS}, has been assessed and found to comply with "
              f"the requirements of <b>{std}</b> ({scope_title})."),
            Spacer(1, 4),
            table([["Item", "Detail"],
                   ["Scope", sc],
                   ["Initial certification", "13 March 2019"],
                   ["Current certification cycle", "13 March 2025 - 12 March 2028"],
                   ["Surveillance audits", "Annually, next due: March 2027"],
                   ["Valid until", f"<b>{valid}</b>"],
                   ["Accreditation", "SAS 0xx (fictitious)"]], (45, 125)),
            Spacer(1, 6),
            P("Conditions of certification", H2),
            P("The certificate remains valid subject to successful surveillance audits and to the use of the "
              "certification mark in accordance with the rules of the certification body. Any major change to "
              "the scope, organisation or location must be notified without delay. The certification body may "
              "suspend or withdraw the certificate if the requirements are no longer met."),
            P("Audit history", H2),
            table([["Date", "Type", "Result", "Auditor"],
                   ["Mar 2019", "Initial audit", "Passed", "T. Huber"],
                   ["Mar 2020", "Surveillance", "Passed, 2 minor findings", "T. Huber"],
                   ["Mar 2021", "Surveillance (remote)", "Passed", "K. Frei"],
                   ["Mar 2022", "Surveillance", "Passed, 1 minor finding", "K. Frei"],
                   ["Mar 2025", "Recertification", "Passed", "T. Huber"],
                   ["Mar 2026", "Surveillance", "Passed", "K. Frei"]], (30, 45, 60, 35)),
            PageBreak(),
        ]
    story = story[:-1]
    pdf("05_iso_certificates.pdf", cb, "CERT-2025-0312", "Certificates dated 13 March 2025", story, tagline="Certification of management systems")


def tax_attestation():
    tx = ("Cantonal Tax Office Zurich", ["Corporate Taxes - Section 4", "Steuerweg 12, 8090 Zurich", "Tel. +41 43 555 30 30", "Tue-Thu 09:00-12:00"])
    pdf("06_tax_attestation.pdf", tx, "ST-JP-2026-55120", "Zurich, 1 October 2026", [
        P(f"{NAME}<br/>Pfingstweidstrasse 31<br/>8005 Zurich", BODY),
        Spacer(1, 12),
        P("Attestation of tax compliance (legal entities)", H1),
        form_table([("Your reference", "Request of 24 September 2026"), ("Our reference", "ST-JP-2026-55120"),
                    ("Taxpayer no.", "2016.044.118.3"), ("UID", UID), ("Purpose", "Public procurement")]),
        Spacer(1, 8),
        P("Dear Sir or Madam,"),
        P("Further to your request, we confirm that, according to our records as of 30 September 2026, "
          "<b>Alpenlogic AG has paid in full all cantonal, municipal and direct federal taxes due, including back "
          "taxes</b>, up to and including tax period 2025. No outstanding amounts are recorded."),
        P("Overview of assessments", H2),
        table([["Tax period", "Assessment status", "Cantonal / municipal", "Direct federal"],
               ["2022", "Final", "Paid", "Paid"], ["2023", "Final", "Paid", "Paid"],
               ["2024", "Final", "Paid", "Paid"], ["2025", "Provisional", "Paid (advance)", "Paid (advance)"]], (30, 45, 50, 45)),
        Spacer(1, 6),
        P("This attestation covers cantonal, municipal and direct federal taxes only. It does not concern value "
          "added tax (VAT), withholding tax or other levies, which are administered by the Federal Tax "
          "Administration. Provisional assessments may be revised."),
        P("Legal remedies", H2),
        P("This attestation is not a decision within the meaning of the Tax Act and cannot be appealed. "
          "Complaints regarding assessments must be lodged against the assessment concerned within the "
          "statutory period."),
        Spacer(1, 10),
        P("Yours faithfully,<br/>Cantonal Tax Office Zurich<br/><i>Corporate Taxes - Section 4</i>"),
        Spacer(1, 8),
        P("Enclosure: none. Copy: none.", SMALL),
    ], tagline="Attestation")


def ahv_certificate():
    sv = ("Social Insurance Institution of the Canton of Zurich (SVA Zurich)",
          ["AHV compensation office 'Zurich Cantonal'", "Hardturmstrasse 120, 8005 Zurich", "Tel. +41 44 555 60 60", "Counter hours 08:30-16:00"])
    pdf("07_social_insurance_certificate.pdf", sv, "AK-ZH-2026-31207", "Zurich, 5 October 2026", [
        P("Certificate of contributions", H1),
        form_table([("Employer", NAME), ("Employer no.", "113.482.9"), ("UID", UID),
                    ("Address", ADDRESS), ("Affiliated since", "01.04.2016"), ("Purpose", "Public procurement")]),
        Spacer(1, 8),
        P("Subject: Confirmation of payment of social insurance contributions", H2),
        P("We confirm that the above employer is affiliated with our compensation office and that all contributions "
          "due up to 30 September 2026 for <b>AHV, IV, EO, FAK (family allowances) and ALV</b> have been paid in full, "
          "<b>including the employee shares deducted from wages</b>."),
        P("Contribution overview", H2),
        table([["Year", "Declared payroll (CHF)", "AHV/IV/EO (CHF)", "ALV (CHF)", "FAK (CHF)", "Status"],
               ["2023", "3,420,115", "362,532", "37,621", "58,142", "Settled"],
               ["2024", "3,688,740", "391,006", "40,576", "62,709", "Settled"],
               ["2025", "3,801,260", "402,934", "41,814", "64,621", "Settled"],
               ["2026 (to 30.09)", "2,904,380", "307,853", "31,948", "49,374", "Paid"]], (28, 38, 30, 24, 24, 26)),
        Spacer(1, 6),
        P("Not covered by this certificate: accident insurance (UVG), occupational pension (BVG), "
          "daily sickness allowance insurance and supplementary insurance, which are managed by third parties.", BODY),
        P("Notice", H2),
        P("The compensation office reserves the right to request supplementary contributions following an "
          "employer audit (art. 68 AHVA). The certificate is not a release. Contributions for the months "
          "October-December 2026 are not yet due."),
        Spacer(1, 10),
        P("SVA Zurich - AHV compensation office<br/><i>Employer contributions department</i>"),
        P(NO_LEGAL, SMALL),
    ], tagline="Certificate")


def pension_confirmation():
    pf = ("Sammelstiftung Limmat BVG", ["Collective pension foundation", "Seestrasse 200, 8002 Zurich", "Tel. +41 44 555 80 80", "service@limmat-bvg.example"])
    pdf("08_pension_fund_confirmation.pdf", pf, "LB-2026-A-9120", "Zurich, 6 October 2026", [
        P("Confirmation of affiliation and contributions", H1),
        form_table([("Employer", NAME), ("Contract no.", "VT-2016-0412"), ("UID", UID),
                    ("Insurance plan", "Plan 3 - basic plus supplementary (BVG+)"), ("Affiliation since", "01.04.2016")]),
        Spacer(1, 8),
        P("We confirm that the above company is affiliated with the Sammelstiftung Limmat BVG for occupational "
          "pension provision (BVG). <b>All contributions due until 30 September 2026 have been paid in full, "
          "including the employee shares deducted from wages.</b>"),
        P("Plan summary", H2),
        table([["Age band", "Savings contribution (% insured salary)", "Risk contribution (%)", "Total (%)"],
               ["25-34", "7.0", "1.8", "8.8"], ["35-44", "10.0", "1.8", "11.8"],
               ["45-54", "15.0", "1.8", "16.8"], ["55-65", "18.0", "1.8", "19.8"]], (30, 70, 40, 30)),
        Spacer(1, 6),
        table([["Key figure (2026)", "Value"], ["Conversion rate at age 65", "5.8 %"], ["Technical interest rate", "1.75 %"],
               ["Funding ratio (31.12.2025)", "112.4 %"], ["Number of affiliated employers", "412"]], (100, 70)),
        Spacer(1, 6),
        P("This confirmation concerns contribution payments only and does not certify the individual benefits of "
          "insured persons. It was issued at the employer's request."),
        Spacer(1, 10),
        P("Sammelstiftung Limmat BVG<br/><i>Employer services</i>"),
        P(NO_LEGAL, SMALL),
    ], tagline="Confirmation")


# ------------------------------------------------------------------ DOCX helpers
def _field(run, instr):
    for t, txt in (("begin", None), (None, instr), ("end", None)):
        if t:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), t)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = txt
        run._r.append(el)


def docx_base(title, header_text, footer_left):
    d = Document()
    sec = d.sections[0]
    hp = sec.header.paragraphs[0]
    hp.text = header_text
    hp.runs[0].font.size = Pt(8)
    hp.runs[0].font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
    fp = sec.footer.paragraphs[0]
    fp.text = f"{footer_left}\t\tPage "
    fp.runs[0].font.size = Pt(7.5)
    r = fp.add_run()
    r.font.size = Pt(7.5)
    _field(r, "PAGE")
    r2 = fp.add_run(" of ")
    r2.font.size = Pt(7.5)
    r3 = fp.add_run()
    r3.font.size = Pt(7.5)
    _field(r3, "NUMPAGES")
    fp2 = sec.footer.add_paragraph(DISCLAIMER)
    fp2.runs[0].font.size = Pt(7)
    fp2.runs[0].font.color.rgb = RGBColor(0xA0, 0x20, 0x20)
    d.add_heading(title, 0)
    return d


def dtable(d, rows, style="Light Grid Accent 1"):
    t = d.add_table(rows=len(rows), cols=len(rows[0]))
    t.style = style
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            t.cell(i, j).text = str(v)
            for p in t.cell(i, j).paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9)
                    r.font.bold = (i == 0)
    d.add_paragraph()
    return t


def para(d, text, bold_prefix=None):
    p = d.add_paragraph()
    if bold_prefix:
        p.add_run(bold_prefix).bold = True
    p.add_run(text)
    return p


def annual_report():
    d = docx_base("Alpenlogic AG - Annual Report 2024", "Alpenlogic AG | Annual Report 2024 | Confidential - for shareholders and authorities",
                  "Annual Report 2024")
    para(d, "Pfingstweidstrasse 31, 8005 Zurich - Approved by the Board of Directors on 28 March 2025 - General Meeting of 24 April 2025")
    d.add_heading("Contents", 1)
    for i, t in enumerate(["Letter to shareholders", "Business review", "Corporate governance", "Share capital and shareholders",
                           "People", "Financial statements", "Notes", "Outlook and risks"], 1):
        d.add_paragraph(f"{i}. {t}", style="List Number")
    d.add_page_break()

    d.add_heading("1. Letter to shareholders", 1)
    para(d, "2024 was a year of consolidation. Demand for AI-supported solutions grew, in particular in public "
            "administration and healthcare, and we invested in our delivery platform and in training. Revenue "
            "rose by 10.5 % and operating profit by 20.3 %. We thank our customers, our employees and our "
            "shareholders for their trust.")
    para(d, "Marc Keller, Chairman and CEO - Sofia Brunner, CTO")

    d.add_heading("2. Business review", 1)
    dtable(d, [["Business unit", "Revenue 2024 (CHF k)", "Share", "Comment"],
               ["Consulting", "2,310", "36 %", "Two framework contracts renewed"],
               ["AI solutions", "1,990", "31 %", "Strongest growth (+18 %)"],
               ["Software engineering", "1,410", "22 %", "Stable"],
               ["Cloud & operations", "710", "11 %", "New managed-service customers"]])
    para(d, "We delivered 24 projects in 2024, including a document-classification system for a regional hospital "
            "group and an e-forms platform for a cantonal administration. The customer satisfaction survey "
            "yielded an average score of 4.5 out of 5.")

    d.add_heading("3. Corporate governance", 1)
    dtable(d, [["Body", "Members", "Remarks"],
               ["Board of directors", "Marc Keller (Chairman), Sofia Brunner", "Two meetings per quarter"],
               ["Management", "Marc Keller (CEO), Sofia Brunner (CTO), Nadine Frei (CFO, no signing authority)", ""],
               ["Auditor", "Limmat Revision AG, Zurich", "Ordinary audit"]])

    d.add_heading("4. Share capital and shareholders", 1)
    para(d, "As at 31 December 2024 the share capital amounts to CHF 500,000, divided into 1,000 registered shares "
            "of CHF 500 each, fully paid in. The company holds no treasury shares. Following the capital increase of "
            "2018, no changes occurred.")
    dtable(d, [["Shareholder", "Share", "Nationality / seat"],
               ["Founders (Marc Keller and Sofia Brunner, jointly)", "60 %", "Swiss nationals, resident in Switzerland"],
               ["Helvetia Growth Fund (fictitious)", "25 %", "Zurich, Switzerland"],
               ["Employee participation foundation", "15 %", "Zurich, Switzerland"]])
    para(d, "No shareholder is of Russian nationality or established in the Russian Federation. No shareholder "
            "holds, directly or indirectly, shares on behalf of persons from the Russian Federation.")

    d.add_heading("5. People", 1)
    para(d, "At 31 December 2024 the company employed 31 people (29.2 full-time equivalents), including 3 apprentices.")
    dtable(d, [["Indicator", "2024", "2023"],
               ["Employees (headcount)", "31", "29"], ["Full-time equivalents", "29.2", "27.6"],
               ["Women in %", "35", "33"], ["Average age", "37.8", "37.1"], ["Staff turnover in %", "8.1", "10.3"],
               ["Training days per employee", "4.6", "4.1"]])

    d.add_heading("6. Financial statements", 1)
    d.add_heading("6.1 Income statement (CHF thousand)", 2)
    dtable(d, [["Item", "2024", "2023"], ["Revenue", "6,420", "5,810"], ["Personnel expenses", "-4,130", "-3,780"],
               ["Other operating expenses", "-1,310", "-1,240"], ["Depreciation", "-270", "-200"],
               ["Operating profit", "710", "590"], ["Financial result", "-12", "-9"], ["Income taxes", "-118", "-96"],
               ["Net profit", "580", "485"]])
    d.add_heading("6.2 Balance sheet (CHF thousand)", 2)
    dtable(d, [["Item", "31.12.2024", "31.12.2023"], ["Cash and equivalents", "1,640", "1,290"], ["Receivables", "1,420", "1,230"],
               ["Fixed assets", "910", "780"], ["Total assets", "3,970", "3,300"], ["Liabilities", "1,590", "1,350"],
               ["Equity", "2,380", "1,950"]])

    d.add_heading("7. Notes", 1)
    para(d, "The financial statements were prepared in accordance with the Swiss law on accounting (Art. 957 ff. CO). "
            "Fixed assets are depreciated on a straight-line basis over 3 to 5 years. Social security: the company "
            "is affiliated with the SVA Zurich as AHV compensation office (Röntgenstrasse 17, 8005 Zurich) and with "
            "Sammelstiftung Limmat BVG for occupational pension. Subsequent events: none.")
    d.add_heading("8. Outlook and risks", 1)
    para(d, "For 2025 we plan moderate growth and the recruitment of four additional specialists. Principal risks: "
            "dependency on a few framework contracts, shortage of skilled labour, evolving AI regulation, and "
            "cyber-security incidents.")
    d.save(OUT / "09_annual_report_2024.docx")


def policy_front(d, ref, owner):
    d.add_heading("Document control", 1)
    dtable(d, [["Item", "Value"], ["Document ref.", ref], ["Owner", owner], ["Approved by", "Executive board (M. Keller)"],
               ["Classification", "Internal"], ["Review cycle", "Annual"]])
    dtable(d, [["Version", "Date", "Author", "Change"], ["1.0", "02.02.2021", "N. Frei", "First version"],
               ["1.3", "10.01.2024", "N. Frei", "Added section on remote work"],
               ["2.0", "15.01.2026", "N. Frei", "Annual review, structure revised"]])


def hr_policy():
    d = docx_base("HR & Employment Compliance Policy", "Alpenlogic AG | HR-POL-002 | Internal", "HR-POL-002 v2.0")
    policy_front(d, "HR-POL-002", "People & Culture")
    d.add_heading("1. Purpose and scope", 1)
    para(d, "This policy describes the principles applied to all employees of Alpenlogic AG at its Zurich site "
            "and defines responsibilities for compliance with employment law.")
    d.add_heading("2. Working time, holidays and remote work", 1)
    dtable(d, [["Topic", "Rule"], ["Standard working week", "41 hours"], ["Annual holidays", "25 days (28 days from age 50)"],
               ["Remote work", "Up to 2 days per week, agreement with line manager"], ["Overtime", "Compensated in time; approval required"],
               ["Dress code", "Business casual"]])
    d.add_heading("3. Occupational health and safety", 1)
    para(d, "Alpenlogic AG complies with the applicable occupational health and safety regulations. A safety officer "
            "is appointed; workplace checks (ergonomics, fire protection) are carried out annually and documented. "
            "Incidents are reported to the safety officer within 24 hours.")
    d.add_heading("4. Collective and standard employment agreements", 1)
    para(d, "No collective employment agreement (CEA) declared generally binding applies to the company's IT consulting "
            "activities. Employment relationships follow the Swiss Code of Obligations and individual contracts "
            "consistent with customary conditions of the sector. No standard employment contract (NAV) is applicable "
            "to the activity.")
    d.add_heading("5. Wages and working conditions", 1)
    para(d, "Wages and working conditions meet the customary standards of the sector in Zurich. The company complies "
            "with notification and permit obligations under the BGSA when posting or hiring foreign personnel.")
    dtable(d, [["Salary band", "Typical role", "Annual range (CHF)"], ["B1", "Junior / apprentice", "30,000 - 65,000"],
               ["B2", "Engineer / consultant", "85,000 - 120,000"], ["B3", "Senior / lead", "120,000 - 155,000"]])
    d.add_heading("6. Equal treatment", 1)
    para(d, "The company applies the principle of non-discrimination and equal treatment of women and men, including "
            "equal pay, verified by an internal annual pay analysis. Complaints may be addressed confidentially to "
            "People & Culture or to an external counselling service.")
    d.add_heading("7. Training and apprenticeships", 1)
    para(d, "Each employee has a training budget of CHF 3,000 per year. Apprenticeships (ICT specialist) are offered "
            "in cooperation with the vocational school of Zurich.")
    d.add_heading("8. Environment", 1)
    para(d, "The company complies with Swiss environmental protection regulations applicable at its place of "
            "performance. Its offices use renewable electricity and a business-travel policy limits flights.")
    d.add_heading("9. Social insurance", 1)
    para(d, "The AHV compensation office is the SVA Zurich, Röntgenstrasse 17, 8005 Zurich. Occupational pension: "
            "Sammelstiftung Limmat BVG, Seestrasse 200, 8002 Zurich. Accident insurance (UVG) is managed through an "
            "external insurer; details are set out in the individual contracts.")
    d.add_heading("10. Data protection for employee data", 1)
    para(d, "Personnel files are stored on access-controlled systems and retained for ten years after termination, "
            "unless legal obligations require otherwise.")
    d.save(OUT / "10_hr_compliance_policy.docx")


def procurement_policy():
    d = docx_base("Procurement & Business Conduct Policy", "Alpenlogic AG | CMP-POL-005 | Internal", "CMP-POL-005 v1.4")
    policy_front(d, "CMP-POL-005", "Legal & Compliance")
    d.add_heading("1. Purpose", 1)
    para(d, "This policy sets out how Alpenlogic AG conducts business with customers, suppliers and public bodies, "
            "including participation in public procurement procedures.")
    d.add_heading("2. Gifts and hospitality", 1)
    dtable(d, [["Situation", "Rule"], ["Gifts from suppliers", "Up to CHF 100 per year; above that, approval required"],
               ["Invitations to events", "Business purpose must be documented"], ["Public officials", "No gifts or hospitality"]])
    d.add_heading("3. Fair competition", 1)
    para(d, "Alpenlogic AG does not enter into agreements and does not take measures that restrict competition. "
            "Staff are trained annually on competition law. No investigation is pending.")
    d.add_heading("4. Sanctions screening", 1)
    para(d, "The company is not on any list of sanctioned bidders, including the list under Art. 45 para. 3 IVöB "
            "(verified internally on 1 October 2026). Shareholders and beneficial owners have no connection to the "
            "Russian Federation within the meaning of Art. 29c of the Ordinance on Measures connected with the "
            "Situation in Ukraine.")
    d.add_heading("5. Subcontractors and suppliers", 1)
    para(d, "In agreements with subcontractors and suppliers, the company includes the obligations regarding working "
            "conditions, tax, social insurance and environmental protection required by public procurement law. "
            "Subcontractors above 10 % of the contract value are screened against sanctions lists.")
    dtable(d, [["Supplier category", "Due diligence", "Review"], ["Cloud providers", "Security questionnaire, ISO 27001", "Annual"],
               ["Freelancers", "Contract template, tax and social insurance proof", "At onboarding"],
               ["Hardware", "Framework agreement", "Every 2 years"]])
    d.add_heading("6. Conflicts of interest and whistleblowing", 1)
    para(d, "Conflicts of interest must be reported to Legal & Compliance. Concerns can be raised confidentially via "
            "compliance@alpenlogic.example; retaliation is prohibited.")
    d.save(OUT / "11_procurement_conduct_policy.docx")


if __name__ == "__main__":
    for fn in (commercial_register, debt_enforcement, insurance, brochure, iso_certs, tax_attestation,
               ahv_certificate, pension_confirmation, annual_report, hr_policy, procurement_policy):
        fn()
    print(sorted(p.name for p in OUT.iterdir()))
