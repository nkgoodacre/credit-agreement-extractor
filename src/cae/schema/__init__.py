"""Pydantic models for the extraction target.

The schema is the contract between the LLM and the evaluation harness:
every extracted value is paired with a verbatim evidence quote, and the
validators encode the plausibility rules a reviewer would apply by hand.
It lives in its own package so it can be imported by extraction,
evaluation and the labelling tool without pulling in their dependencies.
"""

from __future__ import annotations
