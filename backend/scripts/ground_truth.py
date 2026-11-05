"""What a fill of the Annex 4 must give (knowledge-base/GROUND_TRUTH.md), checked field by field.

Used by `record_llm.py` to judge each recording at once, and by the replay test of the recorded
answers. Free-text fields with no single right wording (business purpose, activities, coverage
details) are not checked. Values are compared on their letters and digits only, case ignored
("CHF 500'000" matches "500,000").
"""

import re
from dataclasses import dataclass

from app.modules.filling.rules import AnswerType

AUTO, MISSING, OUTDATED, CONFLICT, DECLARATION, MANUAL = (
    AnswerType.AUTO,
    AnswerType.MISSING,
    AnswerType.OUTDATED,
    AnswerType.CONFLICT,
    AnswerType.DECLARATION,
    AnswerType.MANUAL,
)


@dataclass(frozen=True)
class Expected:
    types: frozenset[AnswerType]
    # Each item must be in the value; an item "a|b" is met by either.
    contains: tuple[str, ...] = ()


def expect(*types: AnswerType, contains: tuple[str, ...] = ()) -> Expected:
    return Expected(frozenset(types), contains)


YES = expect(DECLARATION, contains=("yes",))
NO = expect(DECLARATION, contains=("no",))
EMPTY = expect(MISSING)
# A declaration whose rule does not apply to the bidder: empty for the user, or "yes".
YES_OR_EMPTY = expect(DECLARATION, MISSING, contains=("yes",))

ANNEX_4: dict[str, Expected] = {
    "tender_no_type_of_work": expect(AUTO, contains=("ZH-2026-0412",)),
    "exact_company_name": expect(AUTO, contains=("Alpenlogic AG",)),
    "street_postcode_city_country": expect(AUTO, contains=("Pfingstweidstrasse 31", "8005")),
    "telephone_e_mail": expect(AUTO, contains=("+41 44 555 01", "alpenlogic.example")),
    "responsible_person_contact_person": expect(AUTO, contains=("Marc Keller",)),
    "uid": expect(AUTO, contains=("CHE-123.456.789",)),
    "legal_form": expect(AUTO, contains=("limited by shares",)),
    "registered_office": expect(AUTO, contains=("Zurich",)),
    "company_has_had_this_legal_form_since": expect(
        AUTO, contains=("14.03.2016|14 March 2016|2016-03-14",)
    ),
    # Only in the 2024 annual report: proposed, to check (over a year old).
    "ownership_structure_incl_own_shareholdings": expect(
        AUTO, OUTDATED, contains=("60", "25", "15")
    ),
    "share_capital": expect(AUTO, contains=("500000",)),
    "certificates": expect(AUTO, contains=("27001", "9001")),
    "with_higher_professional_training": expect(AUTO, OUTDATED, CONFLICT, contains=("14",)),
    "with_professional_training": expect(AUTO, OUTDATED, CONFLICT, contains=("9",)),
    "auxiliary_staff": EMPTY,
    # Only the 2024 figure exists: empty, or proposed to check.
    "apprentices": expect(MISSING, OUTDATED),
    "insurance_company": expect(AUTO, OUTDATED, contains=("Limmat Versicherungen AG",)),
    "personal_injury": expect(OUTDATED, contains=("10000000",)),
    "property_damage": expect(OUTDATED, contains=("10000000",)),
    "financial_loss": expect(OUTDATED, contains=("5000000",)),
    "competent_tax_office_exact_address": expect(
        AUTO, contains=("Cantonal Tax Office", "Steuerweg 12")
    ),
    "ahv_compensation_office_exact_address": expect(CONFLICT, contains=("Hardturmstrasse 120",)),
    "for_foreign_bidders_details_of_the_pension_scheme_exact_addr": EMPTY,
    "bvg_pension_fund_exact_address_and_details": expect(
        AUTO, contains=("Sammelstiftung Limmat BVG", "Seestrasse 200")
    ),
    "for_foreign_bidders_details_of_the_pension_scheme_exact_addr_2": EMPTY,
    "do_you_comply_with_the_applicable_occupational_health_and_sa": YES,
    "do_you_comply_with_the_collective_employment_agreement_that_": YES_OR_EMPTY,
    "do_you_comply_with_the_standard_employment_contract_that_app": YES_OR_EMPTY,
    "do_you_comply_with_the_customary_wage_and_working_conditions": YES,
    "only_for_services_to_be_performed_abroad_for_the_services_to": EMPTY,
    "do_you_comply_with_the_principle_of_non_discrimination_in_pa": YES,
    "have_you_paid_in_full_the_taxes_due_at_your_place_of_busines": YES,
    "have_you_paid_in_full_the_vat_or_sales_tax_due": EMPTY,
    "have_you_paid_in_full_the_social_security_contributions_due_": YES,
    "have_you_paid_in_full_the_contributions_due_under_generally_": YES_OR_EMPTY,
    "are_you_subject_to_debt_enforcement_or_bankruptcy_proceeding": NO,
    "have_any_seizures_been_carried_out_against_you_in_the_past_t": NO,
    "have_you_entered_into_any_agreements_or_taken_other_measures": NO,
    "do_you_confirm_that_you_are_not_on_the_list_of_sanctioned_bi": YES,
    "do_you_comply_with_the_swiss_regulations_on_environmental_pr": YES,
    "only_for_services_to_be_performed_abroad_do_you_comply_with_": EMPTY,
    "do_you_confirm_that_you_have_included_or_will_include_the_ab": YES,
    "remarks": EMPTY,
    "place_and_date": expect(MANUAL),
}


def check(
    expected: dict[str, Expected], answers: dict[str, tuple[AnswerType, str | None]]
) -> dict[str, str | None]:
    """For each expected field (by key): None when the answer matches, else what is wrong.
    `answers` maps a field key to its answer's type and value."""
    return {key: _problem(want, answers.get(key)) for key, want in expected.items()}


def _problem(want: Expected, got: tuple[AnswerType, str | None] | None) -> str | None:
    if got is None:
        return "no answer"
    answer_type, value = got
    if answer_type not in want.types:
        names = " or ".join(sorted(want.types))
        return f"type {answer_type}, expected {names}"
    if answer_type == MISSING:
        return None
    for item in want.contains:
        if not any(_letters(option) in _letters(value or "") for option in item.split("|")):
            return f"{value!r} lacks {item.split('|')[0]!r}"
    return None


def _letters(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.casefold())
