"""The 6 golden drift cases as code fixtures + expected signals.

Shared by test_classifier.py and scripts/metrics.py so the numbers in the pitch
come from the same source of truth as the tests.

`expected` uses coarse signal flags that the deterministic heuristic can be held
to. `vlm_only` marks cases whose precise classification requires the real VLM
(structural reasoning); the heuristic is not asserted strictly on those.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GoldenCase:
    pr_number: int
    title: str
    code: str
    expected: dict = field(default_factory=dict)
    vlm_only: bool = False


_ALIGNED_BODY = """
  <svg data-node="icon" />
  <div data-node="content">
    <h3 data-node="title">Payment failed</h3>
    <p data-node="description">Your last transaction could not be processed.</p>
  </div>
"""

CASE_1 = GoldenCase(
    pr_number=1,
    title="Hardcoded #ef4444 instead of var(--color-danger)",
    code=f"""
<div data-node="card" style={{{{ background: 'var(--color-surface)', padding: 'var(--spacing-md)' }}}}>
  {_ALIGNED_BODY}
  <button data-node="btn-primary" style={{{{ background: '#ef4444' }}}}>Retry</button>
</div>
""",
    expected={"violation": True, "noise": False, "evolution": False},
)

CASE_2 = GoldenCase(
    pr_number=2,
    title="15px padding instead of 16px (spacing-md)",
    code=f"""
<div data-node="card" style={{{{ background: 'var(--color-surface)', padding: '15px' }}}}>
  {_ALIGNED_BODY}
  <button data-node="btn-primary" style={{{{ background: 'var(--color-danger)' }}}}>Retry</button>
</div>
""",
    expected={"violation": True, "noise": False, "evolution": False},
)

CASE_3 = GoldenCase(
    pr_number=3,
    title="Wrapper div added for scroll/flexbox handling",
    code=f"""
<div className="scroll-wrapper" style={{{{ overflow: 'auto' }}}}>
  <div data-node="card" style={{{{ background: 'var(--color-surface)', padding: 'var(--spacing-md)' }}}}>
    {_ALIGNED_BODY}
    <button data-node="btn-primary" style={{{{ background: 'var(--color-danger)' }}}}>Retry</button>
  </div>
</div>
""",
    expected={"violation": False, "noise": True, "evolution": False},
)

CASE_4 = GoldenCase(
    pr_number=4,
    title="Component rebuilt from scratch mimicking the StatusCard",
    code="""
<div data-node="card" style={{ display: 'flex', background: 'var(--color-surface)' }}>
  <span data-node="icon">!</span>
  <div data-node="content">
    <div data-node="title" style={{ fontWeight: 'bold' }}>Payment failed</div>
    <div data-node="description">Your last transaction could not be processed.</div>
  </div>
  <a data-node="btn-primary" role="button" style={{ background: 'var(--color-danger)' }}>Retry</a>
</div>
""",
    expected={"violation": True, "noise": False, "evolution": False},
    vlm_only=True,
)

CASE_5 = GoldenCase(
    pr_number=5,
    title="New secondary button absent from Figma",
    code=f"""
<div data-node="card" style={{{{ background: 'var(--color-surface)', padding: 'var(--spacing-md)' }}}}>
  {_ALIGNED_BODY}
  <button data-node="btn-primary" style={{{{ background: 'var(--color-danger)' }}}}>Retry</button>
  <button data-node="btn-secondary" style={{{{ background: 'transparent' }}}}>Dismiss</button>
</div>
""",
    expected={"violation": False, "noise": False, "evolution": True},
)

CASE_6 = GoldenCase(
    pr_number=6,
    title="Cases 1 + 3 combined in the same file",
    code=f"""
<div className="scroll-wrapper" style={{{{ overflow: 'auto' }}}}>
  <div data-node="card" style={{{{ background: 'var(--color-surface)', padding: 'var(--spacing-md)' }}}}>
    {_ALIGNED_BODY}
    <button data-node="btn-primary" style={{{{ background: '#ef4444' }}}}>Retry</button>
  </div>
</div>
""",
    expected={"violation": True, "noise": True, "evolution": False},
)

CASES = [CASE_1, CASE_2, CASE_3, CASE_4, CASE_5, CASE_6]
