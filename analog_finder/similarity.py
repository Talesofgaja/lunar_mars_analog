"""Similarity metrics, each returning a score in [0, 1] (1 = identical).

To add a metric: write a function that takes (candidate_section, reference_section, cfg)
and returns a float or None, then register it in score_against_reference().
"""
import math
import numpy as np
from .descriptors import SLOPE_BIN_WIDTH_DEG

EPS = 1e-6


def _log_ratio_similarity(a, b):
    """Similarity of two positive magnitudes on a log scale (ratio of 2 gives ~0.5)."""
    return math.exp(-abs(math.log((a + EPS) / (b + EPS))))


def morphometric_similarity(cand, ref, scales):
    """Average of slope-distribution, roughness and relief similarities."""
    p = np.asarray(cand["slope_hist"])
    q = np.asarray(ref["slope_hist"])
    # Earth Mover's (Wasserstein-1) distance between slope distributions, in degrees.
    w1_deg = float(np.sum(np.abs(np.cumsum(p) - np.cumsum(q))) * SLOPE_BIN_WIDTH_DEG)
    parts = [
        math.exp(-w1_deg / scales["slope_w1_deg"]),
        _log_ratio_similarity(cand["roughness_m"], ref["roughness_m"]),
        _log_ratio_similarity(cand["relief_m"], ref["relief_m"]),
    ]
    return float(np.mean(parts))


def keyed_similarity(cand, ref, scales):
    """Mean of exp(-|a-b|/scale) over keys present in both descriptors."""
    terms = []
    for key, scale in scales.items():
        a, b = cand.get(key), ref.get(key)
        if a is None or b is None:
            continue
        terms.append(math.exp(-abs(a - b) / scale))
    return float(np.mean(terms)) if terms else None


def score_against_reference(cand_desc, ref_desc, cfg):
    """Per-criterion scores for one candidate against one reference. Missing criteria are omitted."""
    scores = {}
    if cand_desc.get("morphometric") and ref_desc.get("morphometric"):
        scores["morphometric"] = morphometric_similarity(
            cand_desc["morphometric"], ref_desc["morphometric"], cfg["morph_scales"])
    if cand_desc.get("spectral") and ref_desc.get("spectral"):
        scores["spectral"] = keyed_similarity(
            cand_desc["spectral"], ref_desc["spectral"], cfg["spectral_scales"])
    if cand_desc.get("climate") and ref_desc.get("climate"):
        scores["climate"] = keyed_similarity(
            cand_desc["climate"], ref_desc["climate"], cfg["climate_scales"])
    return {k: v for k, v in scores.items() if v is not None}


def composite(scores, weights):
    """Weighted mean over the criteria that are available.

    Weights are renormalised over available criteria, so a reference without
    climate data (e.g. the Moon) is compared on morphometry and spectra only.
    """
    avail = {k: v for k, v in scores.items() if k in weights}
    if not avail:
        return None
    return sum(weights[k] * v for k, v in avail.items()) / sum(weights[k] for k in avail)


def best_reference(cand_desc, refs, cfg):
    """Return the reference with the highest composite score, or None."""
    best = None
    for ref in refs:
        scores = score_against_reference(cand_desc, ref["descriptor"], cfg)
        comp = composite(scores, cfg["weights"])
        if comp is None:
            continue
        if best is None or comp > best["composite"]:
            best = {"reference": ref["name"], "body": ref["body"],
                    "composite": comp, "scores": scores}
    return best
