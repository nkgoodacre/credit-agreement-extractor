"""Filtering rules for candidate EDGAR documents.

Encodes the exclusion rules from the build spec (target forms, cutoff
date, amendments/waivers/joinders, HTML-only) as small, independently
testable predicates, so `fetch` can attach a precise, human-readable
reason to every document it skips rather than a bare pass/fail.
"""

from __future__ import annotations

import re
from datetime import date

TARGET_FORMS = frozenset({"8-K", "10-Q", "10-K"})

# Post-LIBOR: pricing in agreements filed from here on is SOFR-based.
CUTOFF_DATE = date(2022, 1, 1)

DOWNLOADABLE_SUFFIXES = frozenset({"htm", "html", "txt"})

EXHIBIT_10_PREFIX = "EX-10"

# How much of a document's own declared title/heading to look at. Filed
# agreements reliably state their own type in this range (empirically:
# within the first ~110 visible characters in every sample checked -- see
# docs/DECISIONS.md, Phase 1); keeping the window short is deliberate, to
# avoid false-positive matches on common words (e.g. "consent",
# "guarantee") that show up incidentally later in a document's recitals
# or definitions rather than in its own title.
_TITLE_WINDOW_CHARS = 500
_TAG_RE = re.compile(r"<[^>]+>")


def _visible_prefix(html_or_text: str, chars: int = _TITLE_WINDOW_CHARS) -> str:
    """Strip HTML tags and collapse whitespace, then return the first
    `chars` characters of the resulting visible text."""
    stripped = _TAG_RE.sub(" ", html_or_text)
    return re.sub(r"\s+", " ", stripped).strip()[:chars]


# Document types that are related to a credit agreement but are not one:
# partial amendments/waivers/joinders, and ancillary documents (guaranty,
# security agreement, lender confirmation, consent, ...) that a full-text
# search for "credit agreement" + "administrative agent" also surfaces
# because they reference an underlying credit agreement without being it.
#
# "amendment"/"amendments", not "amended": "Amended and Restated Credit
# Agreement" is a full replacement document, not a partial amendment, and
# must NOT match -- different word, no substring overlap. A bare
# "\bamendment\b" (rather than requiring "Amendment No. N") is deliberate:
# a real downloaded document was titled "SECOND AMENDMENT TO REVOLVING
# CREDIT AGREEMENT" with no "No." at all, and still needed to be excluded.
#
# The ancillary-document patterns (guaranty, security agreement,
# confirmation, consent, ...) were added after a real `cae fetch --limit
# 15` run downloaded a "LIMITED GUARANTEE", a "GUARANTY", a "SECURITY
# AGREEMENT", a "LENDER CONFIRMATION" and a "Limited Consent to
# Uncommitted Credit Agreement" -- the last of which shows why a purely
# positive "mentions 'credit agreement'" check is not enough; these are
# excluded by their own declared type instead (see docs/DECISIONS.md,
# Phase 1, for the full list of real documents this was checked against).
_EXCLUDED_DOCUMENT_TYPE_PATTERNS = (
    # "amend(ment|ing)", not "amended" -- see the note above this tuple.
    # Originally just "\bamendments?\b"; broadened after "AMENDING
    # AGREEMENT NO. 3" / "THIRD AMENDING AGREEMENT" (the gerund, not the
    # noun) was found slipping through in a full-corpus review of a real
    # 300-document run (see docs/DECISIONS.md, Phase 1, fourth wave).
    re.compile(r"\bamend(?:ments?|ing)\b", re.IGNORECASE),
    re.compile(r"\bwaiver\b", re.IGNORECASE),
    re.compile(r"\bjoinder\b", re.IGNORECASE),
    re.compile(r"\bguaranty\b", re.IGNORECASE),
    re.compile(r"\bguarantee\b", re.IGNORECASE),
    re.compile(r"\bsecurity\s+agreement\b", re.IGNORECASE),
    re.compile(r"\bpledge\s+agreement\b", re.IGNORECASE),
    re.compile(r"\bconfirmation\b", re.IGNORECASE),
    re.compile(r"\bconsent\b", re.IGNORECASE),
    re.compile(r"\bsubordination\s+agreement\b", re.IGNORECASE),
    re.compile(r"\bintercreditor\s+agreement\b", re.IGNORECASE),
    re.compile(r"\bnotice\s+of\s+(?:events?\s+of\s+)?default\b", re.IGNORECASE),
    # Found the same way as the ones above: a "SUCCESSOR AGENCY AGREEMENT"
    # (replacing the administrative agent on an existing facility) surfaced
    # in a real run and slipped through the original list.
    re.compile(r"\bagency\s+agreement\b", re.IGNORECASE),
    re.compile(r"\bassignment\s+and\s+assumption\b", re.IGNORECASE),
    re.compile(r"\bresignation\b", re.IGNORECASE),
    re.compile(r"\bfee\s+letter\b", re.IGNORECASE),
    # A second wave found by the same method (a 20-document random spot
    # check on a real 40-document run): documents that add or modify a
    # lender on an *existing* facility, not the base agreement --
    # "Incremental Commitment and Assumption Agreement", "First
    # Incremental Assumption Agreement", "New Lender Agreement".
    re.compile(r"\bincremental\s+commitment\b", re.IGNORECASE),
    re.compile(r"\bassumption\s+agreement\b", re.IGNORECASE),
    re.compile(r"\bnew\s+lender\s+agreement\b", re.IGNORECASE),
    # A third wave, same method: a plain, informal "letter agreement" (no
    # capitalised title at all -- just a dated letter opening "Re: Credit
    # Agreement...") and a "REFINANCING FACILITY AGREEMENT NO. 2" that
    # never uses the word "amendment" but explicitly modifies an earlier,
    # separately-dated credit agreement ("...to the ... CREDIT AGREEMENT
    # dated as of March 11, 2022..., the Credit Agreement as amended
    # hereby..."). The second is caught on substance ("as amended
    # hereby"/"amended thereby"), not a document-type label, because
    # enumerating every possible label for "this modifies an existing
    # facility" is a losing game -- see docs/DECISIONS.md, Phase 1.
    re.compile(r"\bletter\s+agreement\b", re.IGNORECASE),
    re.compile(r"\bas\s+amended\s+(?:hereby|thereby)\b", re.IGNORECASE),
    re.compile(r"\brefinancing\s+facility\s+agreement\b", re.IGNORECASE),
    # Fourth wave: found by reviewing the title area of all 300 documents
    # in a real full-scale run (not just a 20-document sample), grepped
    # for suspicious words and manually checked. All from the same
    # family: documents that increase, extend, modify or partially
    # restate an *existing* facility without being the base agreement --
    # "Commitment Increase Agreement/Supplement/Request", "Accordion
    # Increase", "Augmenting/Additional Lender Supplement",
    # "Reaffirmation Agreement", "Suspension of Rights Agreement",
    # "[N]th Modification Agreement", "Technical Modification",
    # "Incremental Term Loan/Tranche [B] ... Agreement", "Extension
    # Request/Agreement/No. N", "Board Observer Agreement". A genuine
    # candidate for using an "accordion" as a labelling-guide concept is
    # explicitly out of scope per the build spec's own Phase 4 guidance
    # (accordion is excluded from total commitments) -- consistent with
    # excluding the increase mechanics here too (see docs/DECISIONS.md,
    # Phase 1).
    re.compile(r"\bcommitment\s+increase\b", re.IGNORECASE),
    re.compile(r"\bincrease\s+supplement\b", re.IGNORECASE),
    re.compile(r"\bincrease\s+agreement\b", re.IGNORECASE),
    re.compile(r"\bincrease\s+request\b", re.IGNORECASE),
    re.compile(r"\baccordion\b", re.IGNORECASE),
    re.compile(r"\baugmenting\s+lender\b", re.IGNORECASE),
    re.compile(r"\badditional\s+lender\s+supplement\b", re.IGNORECASE),
    re.compile(r"\breaffirmation\b", re.IGNORECASE),
    re.compile(r"\bsuspension\s+of\s+rights\b", re.IGNORECASE),
    re.compile(r"\bmodification\s+agreement\b", re.IGNORECASE),
    re.compile(r"\btechnical\s+modification\b", re.IGNORECASE),
    re.compile(r"\bincremental\s+t(?:erm\s+loan|ranche)\b", re.IGNORECASE),
    re.compile(r"\bextension\s+(?:request|no\.?\s*\d+)\b", re.IGNORECASE),
    re.compile(r"\bboard\s+observer\s+agreement\b", re.IGNORECASE),
)

# A conservative, low floor, not a primary filter: catches a stray tiny
# document (a one-page letter) that happens to dodge every keyword above.
# Deliberately NOT set near the observed boundary in one real run (the
# smallest genuine credit agreement seen was ~190KB, the largest
# false-positive ~181KB -- too close a margin from a single sample to
# trust as a real threshold; a smaller company's genuinely short
# bilateral facility could plausibly fall in that range). Every false
# positive found in Phase 1 was under 90KB; 20,000 bytes stays far below
# that with room to spare (see docs/DECISIONS.md, Phase 1).
MIN_CONTENT_BYTES = 20_000


def is_target_form(form: str) -> bool:
    """True for 8-K, 10-Q and 10-K -- the forms credit agreements are
    typically filed as an exhibit to."""
    return form in TARGET_FORMS


def is_after_cutoff(filing_date: date, cutoff: date = CUTOFF_DATE) -> bool:
    return filing_date >= cutoff


def is_exhibit_10(file_type: str) -> bool:
    """True for Exhibit 10.x filings, where credit agreements are filed.
    Excludes the filing's own cover document (file_type == form, e.g.
    "8-K") and unrelated exhibit types (EX-99, EX-4, ...) that can also
    match the full-text search terms without being the agreement itself.
    """
    return file_type.upper().startswith(EXHIBIT_10_PREFIX)


def is_downloadable_type(filename: str) -> bool:
    """HTML/plain-text only; PDFs are skipped per the build spec."""
    if "." not in filename:
        return False
    suffix = filename.rsplit(".", 1)[-1].lower()
    return suffix in DOWNLOADABLE_SUFFIXES


def is_large_enough(content_length_bytes: int) -> bool:
    """A conservative floor, not a primary filter -- see the note on
    `MIN_CONTENT_BYTES`."""
    return content_length_bytes >= MIN_CONTENT_BYTES


def looks_like_credit_agreement(text: str | None) -> bool:
    """True if `text` -- a search-index title or a downloaded document's
    own content -- names itself a credit agreement in its title area.
    A secondary, positive check alongside `is_excluded_document_type`'s
    negative one: catches ancillary document types not in that list.
    """
    if not text:
        return False
    return bool(re.search(r"credit\s+agreement", _visible_prefix(text), re.IGNORECASE))


def is_excluded_document_type(text: str | None) -> bool:
    """True if `text` -- a search-index title or a downloaded document's
    own content -- declares itself, in its title area, to be a partial
    amendment/waiver/joinder or an ancillary document (guaranty, security
    agreement, confirmation, consent, ...) rather than a full credit
    agreement. `file_description` alone is not a reliable signal for this
    (see docs/DECISIONS.md, Phase 1): this same check is meant to be
    applied again to downloaded content, not just the search-index title.
    """
    if not text:
        return False
    title_area = _visible_prefix(text)
    return any(pattern.search(title_area) for pattern in _EXCLUDED_DOCUMENT_TYPE_PATTERNS)
