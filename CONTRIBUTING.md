# Contributing

1. **Read the brief** in `README.md` §0 before changing anything. It is re-read every session.
2. **Stay in the lane.** The lane is the single method paragraph; a raster whose
   rank-correlation with any registry raster exceeds 0.90, or whose dots fall within 3 px
   of one registry raster's dots for more than 70 % of them, has drifted: log it as a
   duplicate and stop.
3. **Label every number** HOLDOUT-DTI (evaluator version, withheld positives, 95 % CI) or
   ORGANIZER-CONFIRMED (submission-page receipt). A projection is never written as a score.
   Negative results are deliverables and must be published with their numbers.
4. **Reuse, don't fork.** Fix a shared tool once and report the fix; never keep a private
   copy of `metric.py` / `holdout.py`.
5. **Budget.** Stop after 3 experiments or 2 hours. Promotion to a competition slot is a
   separate selector step.
6. Run `PYTHONPATH=src python -m pytest tests -q` and `python scripts/build_site.py`
   before opening a pull request.
