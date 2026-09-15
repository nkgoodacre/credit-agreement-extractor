"""Credit Agreement Extractor (``cae``).

An LLM pipeline that extracts structured terms from US syndicated credit
agreements filed on SEC EDGAR, then validates, grounds and evaluates those
extractions field by field. The package is organised so that the system
around the model -- acquisition, processing, schema, validation, grounding
and evaluation -- is where the code lives, not just the model call.
"""

from __future__ import annotations

__version__ = "0.1.0"
