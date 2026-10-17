"""Deterministic fictional sample-data generator for the NFPL project (Phase 7).

Produces flat JSON / CSV / NDJSON data files that conform to the NFPL
access-control schema. It performs no database work and depends only on the
Python standard library, so dataset generation and database insertion stay
decoupled.
"""

__all__ = ["builder", "benchmark", "reference", "writers", "cli"]
