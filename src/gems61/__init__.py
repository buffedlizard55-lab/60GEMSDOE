"""GEMS61: selection-instrument audit + thermally-conditioned knickpoint lane (session 60GEMSDOE-2).

Reuses the shared template verbatim -- ``gems52.metric`` (official metric), ``gems52.holdout``
(whole-segment hide-and-recover folds), ``gems52.evaluate_holdout`` (pooled evaluator),
``gems52.submission_writer`` and ``gems52.gates`` (fail-closed packaging/validation) -- and
``gems60.drains`` (priority-flood/D8/chi/ksn hydrology from the previous session's lane).
Nothing here re-implements a shared tool; only new *analysis* lives in this package.
"""
__all__ = ["dataio", "instruments"]
