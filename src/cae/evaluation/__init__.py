"""Field-level metrics and run reports.

Compares extractions against the hand-labelled gold set with
field-type-aware matching rules, and reports accuracy, hallucination rate,
omission rate and grounding rate with Wilson confidence intervals. Kept
separate from extraction so that scoring can never influence a run.
"""

from __future__ import annotations
