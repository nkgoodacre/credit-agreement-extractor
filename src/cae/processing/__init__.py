"""HTML-to-text conversion and section splitting.

Credit agreements are long and highly structured (articles, numbered
sections, a definitions article of quoted terms). Extraction quality
depends on preserving that structure and on being able to trace any quote
back to a character offset in the source, so this layer is kept separate
from both acquisition and the LLM calls.
"""

from __future__ import annotations
