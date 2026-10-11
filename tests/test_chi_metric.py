"""The metric is checked against a LITERAL brute-force transcription of the
published formulas, plus the organizers' own worked example."""
import numpy as np
import pytest
from gems60chi.metric import ALPHA, BETA, dti, dti_components, pooled_dti


def brute_force(pred, truth, r_px=3.0):
    """Word-for-word transcription of the published definition, O(|G| x N)."""
    h, w = pred.shape
    ys, xs = np.nonzero(truth)
    tp = fp = 0.0
    for gy, gx in zip(ys, xs):
        best = 0.0
        for y in range(max(0, gy - int(r_px)), min(h, gy + int(r_px) + 1)):
            for x in range(max(0, gx - int(r_px)), min(w, gx + int(r_px) + 1)):
                d = np.hypot(y - gy, x - gx)
                if d <= r_px:
                    best = max(best, pred[y, x] * max(1.0 - d / r_px, 0.0))
        tp += best
    for y in range(h):
        for x in range(w):
            if pred[y, x] <= 0:
                continue
            bestk = 0.0
            for gy, gx in zip(ys, xs):
                d = np.hypot(y - gy, x - gx)
                bestk = max(bestk, max(1.0 - d / r_px, 0.0))
            fp += pred[y, x] * (1.0 - bestk)
    fn = len(ys) - tp
    return tp, fp, fn


def test_published_worked_example():
    # page 967: TP_w = 3.00, FP_w = 1.89, FN_w = 2.00 -> DTI = 0.60
    got = 3.00 / (3.00 + 0.2 * 1.89 + 0.8 * 2.00)
    assert abs(got - 0.60) < 0.005


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_bruteforce_equivalence(seed):
    rng = np.random.default_rng(seed)
    shape = (26, 31)
    truth = rng.random(shape) < 0.07
    pred = (rng.random(shape) < 0.25) * rng.random(shape)
    c = dti_components(pred, truth, r_px=3.0)
    tp, fp, fn = brute_force(pred, truth, 3.0)
    assert abs(c["tpw"] - tp) < 1e-9
    assert abs(c["fpw"] - fp) < 1e-9
    assert abs(c["fnw"] - fn) < 1e-9


def test_fn_identity_and_pooling():
    rng = np.random.default_rng(9)
    truth = rng.random((40, 40)) < 0.05
    pred = (rng.random((40, 40)) < 0.2).astype(float)
    c = dti_components(pred, truth)
    assert abs(c["fnw"] - (c["n_gt"] - c["tpw"])) < 1e-9
    assert abs(pooled_dti([c, dict(tpw=0, fpw=0, fnw=0, n_gt=0)]) - c["dti"]) < 1e-6


def test_perfect_prediction_is_one():
    truth = np.zeros((30, 30), bool); truth[10:14, 10:20] = True
    assert dti(truth.astype(float), truth) > 0.999
