"""Streamlit tool for building the gold set.

The gold set is the ground truth the whole project is measured against, so
labelling must be blind to model output to avoid anchoring bias. This
package holds the annotation UI and the split logic; it deliberately has
no dependency on the extraction package.
"""

from __future__ import annotations
