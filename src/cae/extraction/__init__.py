"""LLM calls, context selection, validation, retries and grounding.

This is the model boundary. Everything that makes the model call
trustworthy -- choosing which sections to send, validating the response,
retrying with the validation error, checking each evidence quote against
the source text, caching, and recording cost and latency -- is treated as
a first-class concern here rather than bolted onto a bare API call.
"""

from __future__ import annotations
