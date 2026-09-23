"""Unit tests for the pure filtering predicates in cae.edgar.filters."""

from __future__ import annotations

from datetime import date

from cae.edgar.filters import (
    CUTOFF_DATE,
    MIN_CONTENT_BYTES,
    is_after_cutoff,
    is_downloadable_type,
    is_excluded_document_type,
    is_exhibit_10,
    is_large_enough,
    is_target_form,
    looks_like_credit_agreement,
)


def test_target_forms() -> None:
    assert is_target_form("8-K")
    assert is_target_form("10-Q")
    assert is_target_form("10-K")
    assert not is_target_form("S-1")
    assert not is_target_form("10-K/A")


def test_cutoff_date_is_inclusive() -> None:
    assert is_after_cutoff(CUTOFF_DATE)
    assert is_after_cutoff(date(2022, 6, 1))
    assert not is_after_cutoff(date(2021, 12, 31))


def test_exhibit_10_prefix() -> None:
    assert is_exhibit_10("EX-10.1")
    assert is_exhibit_10("EX-10.24")
    assert is_exhibit_10("ex-10.1")  # case-insensitive
    assert not is_exhibit_10("EX-99.1")
    assert not is_exhibit_10("EX-4.6")
    assert not is_exhibit_10("8-K")


def test_downloadable_type() -> None:
    assert is_downloadable_type("agreement.htm")
    assert is_downloadable_type("agreement.HTML")
    assert is_downloadable_type("agreement.txt")
    assert not is_downloadable_type("agreement.pdf")
    assert not is_downloadable_type("noextension")


def test_excluded_title_variants_amendment_waiver_joinder() -> None:
    assert is_excluded_document_type("AMENDMENT NO. 9")
    assert is_excluded_document_type("Amendment No 14 to Credit Agreement")
    assert is_excluded_document_type("WAIVER AND CONSENT")
    assert is_excluded_document_type(
        "JOINDER AND SECOND AMENDMENT TO CREDIT AGREEMENT BY AND AMONG T3 COMMUNICATIONS..."
    )


def test_excluded_ignores_generic_or_missing_title() -> None:
    assert not is_excluded_document_type("EX-10.1")
    assert not is_excluded_document_type(None)
    assert not is_excluded_document_type("")


def test_amended_and_restated_is_not_excluded() -> None:
    """A full replacement agreement, not a partial amendment -- see
    docs/DECISIONS.md, Phase 1."""
    assert not is_excluded_document_type("AMENDED AND RESTATED CREDIT AGREEMENT")
    assert not is_excluded_document_type(
        "THIRD AMENDED AND RESTATED CREDIT AGREEMENT DATED JANUARY 5, 2022"
    )


def test_excluded_checks_document_content_not_just_title() -> None:
    """The real-world case that motivated this check: file_description was
    just "EX-10.1" but the document opened with "SECOND AMENDMENT..."."""
    content = "<HTML><BODY>SECOND AMENDMENT TO REVOLVING CREDIT AGREEMENT ..."
    assert is_excluded_document_type(content)


def test_excluded_ancillary_document_types_found_in_a_real_run() -> None:
    """Each of these is real (trimmed) content from a `cae fetch` run
    before this check existed -- see docs/DECISIONS.md, Phase 1."""
    assert is_excluded_document_type(
        "EX-10.5 Document Execution Version LIMITED GUARANTEE This Limited "
        "Guarantee, dated as of March 12, 2025..."
    )
    assert is_excluded_document_type(
        "EX-10.66 Document EXECUTION COPY GUARANTY GUARANTY (this "
        "'Guaranty'), dated as of January 18, 2024..."
    )
    assert is_excluded_document_type(
        "Exhibit 10.2 Final Security Agreement SECURITY AGREEMENT This "
        "SECURITY AGREEMENT is made effective as of March 27, 2023..."
    )
    assert is_excluded_document_type(
        "Exhibit 10(j)(i) LENDER CONFIRMATION Confirmation Date: July 8, 2024..."
    )
    assert is_excluded_document_type(
        "Exhibit 10.3 Execution Version Limited Consent to Uncommitted "
        "Credit Agreement This Limited Consent..."
    )
    assert is_excluded_document_type(
        "Exhibit 10.2 Execution Version SUCCESSOR AGENCY AGREEMENT This "
        "SUCCESSOR AGENCY AGREEMENT is dated as of February 14, 2023..."
    )
    assert is_excluded_document_type(
        "Exhibit 10.4 EXECUTION VERSION INCREMENTAL COMMITMENT AND "
        "ASSUMPTION AGREEMENT dated as of April 1, 2022, relating to the "
        "SENIOR SECURED REVOLVING CREDIT AGREEMENT..."
    )
    assert is_excluded_document_type(
        "Exhibit 10.1 HTML Editor Exhibit 10.1 NEW LENDER AGREEMENT This New Lender Agreement..."
    )
    assert is_excluded_document_type(
        "Exhibit 10.1 Execution Version FIRST INCREMENTAL ASSUMPTION AGREEMENT..."
    )
    assert is_excluded_document_type(
        "Exhibit 10.2 September 12, 2023 DZS Inc. 5700 Tennyson Parkway, "
        "Suite 400 Plano, Texas 75024 Attention: Misty Kawecki Re: Credit "
        "Agreement, dated as of February 9, 2022 (as amended, the "
        "'Credit Agreement'), among DZS Inc... Capitalized terms used in "
        "this letter agreement (this 'Agreement')..."
    )
    assert is_excluded_document_type(
        "REFINANCING FACILITY AGREEMENT NO. 2 EXECUTION VERSION REFINANCING "
        "FACILITY AGREEMENT NO. 2 dated as of May 16, 2024 (this "
        "'Agreement'), to the AMENDED AND RESTATED CREDIT AGREEMENT dated "
        "as of March 11, 2022 (as amended, restated, supplemented or "
        "otherwise modified from time to time, the 'Credit Agreement', "
        "and the Credit Agreement as amended hereby, the 'Amended Credit "
        "Agreement')..."
    )


def test_excluded_amending_gerund_not_just_amendment_noun() -> None:
    """ "Amending" (gerund) slipped past the original "\\bamendments?\\b"
    pattern -- found reviewing all 300 documents from a real run, not a
    random sample (see docs/DECISIONS.md, Phase 1, fourth wave)."""
    assert is_excluded_document_type(
        "AMENDING AGREEMENT NO. 3 THIS AMENDING AGREEMENT NO. 3 (this..."
    )
    assert is_excluded_document_type(
        "THIRD AMENDING AGREEMENT TO THE CREDIT AGREEMENT, DATED APRIL 27, 2023..."
    )
    # Still must not exclude the real thing.
    assert not is_excluded_document_type("AMENDED AND RESTATED CREDIT AGREEMENT")


def test_excluded_fourth_wave_facility_modification_family() -> None:
    """Every one of these is real title-area text from the fourth wave of
    false positives -- found by reviewing all 300 documents from a real
    `cae fetch --limit 300` run, not a random 20-document sample (see
    docs/DECISIONS.md, Phase 1)."""
    assert is_excluded_document_type("COMMITMENT INCREASE AGREEMENT April 21, 2023...")
    assert is_excluded_document_type("COMMITMENT INCREASE SUPPLEMENT June 30, 2025...")
    assert is_excluded_document_type(
        "INCREASE AGREEMENT TO CREDIT AGREEMENT THIS INCREASE AGREEMENT..."
    )
    assert is_excluded_document_type("Commitment Amount Increase Request April 2, 2024...")
    assert is_excluded_document_type("Accordion Increase June 29, 2026 To Bank of Montreal...")
    assert is_excluded_document_type(
        "AUGMENTING LENDER SUPPLEMENT AUGMENTING LENDER SUPPLEMENT, dated..."
    )
    assert is_excluded_document_type(
        "ADDITIONAL LENDER SUPPLEMENT ADDITIONAL LENDER SUPPLEMENT, dated..."
    )
    assert is_excluded_document_type("REAFFIRMATION AGREEMENT This Reaffirmation Agreement...")
    assert is_excluded_document_type("SUSPENSION OF RIGHTS AGREEMENT To JPMorgan Chase Bank...")
    assert is_excluded_document_type("SEVENTH MODIFICATION AGREEMENT dated...")
    assert is_excluded_document_type("TECHNICAL MODIFICATION Dated...")
    assert is_excluded_document_type("FIRST INCREMENTAL TERM LOAN AGREEMENT dated...")
    assert is_excluded_document_type("SECOND INCREMENTAL TRANCHE B TERM LOAN AGREEMENT...")
    assert is_excluded_document_type("EXTENSION REQUEST Dated May 7, 2026 To BMO Bank N.A....")
    assert is_excluded_document_type("EXTENSION NO. 1 TO ...")
    assert is_excluded_document_type("Board Observer Agreement This agreement...")


def test_size_floor() -> None:
    assert not is_large_enough(0)
    assert not is_large_enough(MIN_CONTENT_BYTES - 1)
    assert is_large_enough(MIN_CONTENT_BYTES)
    assert is_large_enough(1_000_000)


def test_looks_like_credit_agreement() -> None:
    assert looks_like_credit_agreement("SENIOR SECURED REVOLVING CREDIT AGREEMENT")
    assert looks_like_credit_agreement(
        "EX-10.2 CREDIT AGREEMENT CREDIT AGREEMENT Made as of June 3rd, 2022 Among..."
    )
    assert not looks_like_credit_agreement(None)
    assert not looks_like_credit_agreement("")


def test_looks_like_credit_agreement_alone_is_not_a_sufficient_filter() -> None:
    """A real guaranty mentions "the Credit Agreement" (the one it backs)
    within its own title area, so a positive-only "mentions credit
    agreement somewhere" check would wrongly accept it -- this is exactly
    why `is_excluded_document_type` (a negative check on the document's
    own declared type) is the primary filter in `fetch`, and this
    function is only a secondary one (see docs/DECISIONS.md, Phase 1).
    """
    guaranty_text = (
        "GUARANTY GUARANTY (this Guaranty), dated as of January 18, 2024, by "
        "B. RILEY FINANCIAL, INC. (the Guarantor), in favor of AXOS BANK, in "
        "its capacity as administrative agent for the Secured Parties (as "
        "defined in the Credit Agreement)..."
    )
    assert looks_like_credit_agreement(guaranty_text)  # the trap
    assert is_excluded_document_type(guaranty_text)  # caught here instead
