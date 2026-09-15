"""Data acquisition from SEC EDGAR.

Isolated from the rest of the pipeline because EDGAR access has its own
constraints -- a required descriptive ``User-Agent``, a request-rate limit,
and undocumented response shapes that must be probed rather than assumed.
Keeping all of that here means the processing and extraction layers only
ever see local files.
"""

from __future__ import annotations
