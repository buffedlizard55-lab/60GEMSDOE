"""Build the lane's evidence surface: chi-space channel steepness, knickpoint strength, and the
strike-coherence gate across independent first-order drainages.

Chain of computation (each step named after the paper it implements):

  filled  = Priority-Flood + epsilon            Barnes et al. (2014)
  rec     = steepest-descent D8                 O'Callaghan & Mark (1984)
  acc     = D8 flow accumulation (m^2)
  chi     = integral (A0/A)^theta dx            Perron & Royden (2013)
  profile = per first-order-basin (chi, z), downstream -> upstream
  breaks  = piecewise segmentation of (chi, z)  Gailleton et al. (2019)
  ksn     = d z / d chi on each segment         Perron & Royden (2013); Kirby & Whipple (2012)
  cohere  = number of INDEPENDENT first-order drainages whose strongest knickpoints share a strike
            within a rotated corridor of half-width ``corridor_px``  (the lane's own requirement)

Confounds masked, each named with the mechanism it removes (Wobus et al. 2006):
  playa / closed-basin base levels : cells that the depression filler had to raise, plus cells whose
      local relief is below ``flat_relief_m``.  These are places where the channel profile is
      truncated by a depositional base level rather than by rock uplift.
  seismic striping                 : rows whose robust cross-band statistic is an outlier.  The
      repository measured 129 flagged rows / 86,947 stripe pixels inside the footprint
      (docs/results/tensor_lane_results.json of 55GEMSDOE); the rows are re-detected here from the
      supplied feature cube so the mask does not depend on a quoted list.
  lithology and climate            : NOT masked -- no free gridded product is reachable from this
      environment.  Their covariance with the score is MEASURED and reported instead, and the
      limitation is carried in the run card.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi

from . import drains as D

BIG = np.ones((3, 3), dtype=int)


def detect_striped_rows(row_means: np.ndarray, z_thresh: float = 4.0) -> dict:
    """Rows that are cross-band outliers in the per-row mean, i.e. the acquisition-striping artefact.

    ``row_means`` is (n_bands, height) of the footprint row-mean of each supplied feature band, so
    the caller can stream the 933 MB cube instead of holding it.  For every band the row-mean is
    robustly standardised (median / MAD); a row is flagged when it is an outlier in at least two
    bands, which stops a genuine geological gradient carried by one band from becoming a mask.
    """
    rm = np.asarray(row_means, dtype=np.float64)
    n_bands, h = rm.shape
    votes = np.zeros(h, dtype=np.int32)
    per_band = []
    for b in range(n_bands):
        s = rm[b]
        ok = np.isfinite(s)
        if not ok.any():
            per_band.append(0)
            continue
        med = np.nanmedian(s[ok])
        mad = np.nanmedian(np.abs(s[ok] - med))
        if not np.isfinite(mad) or mad <= 0:
            per_band.append(0)
            continue
        z = (s - med) / (1.4826 * mad)
        flag = np.isfinite(z) & (np.abs(z) >= z_thresh)
        votes += flag.astype(np.int32)
        per_band.append(int(flag.sum()))
    rows = votes >= 2
    return {"rows_flagged": int(rows.sum()), "rows_total": int(h),
            "per_band_flagged_rows": per_band, "z_thresh": z_thresh,
            "rule": "flagged when |robust z of the footprint row-mean| >= z_thresh in >= 2 bands",
            "rows": rows}


def local_relief(z: np.ndarray, footprint: np.ndarray, size: int = 15) -> np.ndarray:
    """max - min of z in a (size, size) window, computed as separable grey morphology."""
    a = np.where(footprint & np.isfinite(z), z, np.nan)
    v = np.nan_to_num(a, nan=np.nanmin(a))
    mx = ndi.maximum_filter(v, size=size)
    mn = ndi.minimum_filter(v, size=size)
    rel = (mx - mn).astype(np.float32)
    rel[~np.isfinite(z)] = np.nan
    return rel


def structure_tensor_azimuth(z: np.ndarray, sigma: float = 3.0) -> tuple[np.ndarray, np.ndarray]:
    """Local lineament azimuth (deg in [0,180)) and its coherence, from the elevation structure
    tensor.  The major axis of the tensor is the ridge/valley AXIS, which is the orientation a
    fault trace would share; its eigenvalue ratio is the coherence (0 = isotropic, 1 = perfect line)."""
    med = float(np.nanmedian(z))
    # guard against a caller that handed us a finite nodata sentinel instead of NaN
    huge = ~np.isfinite(z) | (np.abs(z) > 1e30)
    v = np.where(huge, med, z).astype(np.float32)
    gy, gx = np.gradient(v)
    jxx = ndi.gaussian_filter(gx * gx, sigma)
    jyy = ndi.gaussian_filter(gy * gy, sigma)
    jxy = ndi.gaussian_filter(gx * gy, sigma)
    tr = jxx + jyy
    det = jxx * jyy - jxy * jxy
    disc = np.sqrt(np.maximum(tr * tr / 4.0 - det, 0.0))
    l1 = tr / 2.0 + disc
    l2 = tr / 2.0 - disc
    # orientation of the MAJOR axis of the tensor (perpendicular to the dominant gradient)
    theta = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy)
    az = (np.degrees(theta) + 90.0) % 180.0
    coh = ((l1 - l2) / (l1 + l2 + 1e-9)).astype(np.float32)
    return az.astype(np.float32), coh


def build(dem: np.ndarray, footprint: np.ndarray, *, cell_m: float = 100.0, theta: float = 0.45,
          area0: float = 1.0, ac_m2: float = 1.0e6, knick_window: int = 4, knick_ratio: float = 1.6,
          min_drop_m: float = 20.0, corridor_px: int = 12, azimuth_bins: int = 18,
          row_means: np.ndarray | None = None, stripe_px_out: bool = True) -> dict:
    """Compute every lane field.  Returns a dict of float32 fields plus a diagnostics block."""
    finite = footprint & np.isfinite(dem)
    filled = D.fill_depressions(dem, finite, eps=1e-3)
    rec = D.d8_receivers(filled)
    flat_filled = filled.ravel()
    order_asc = np.argsort(flat_filled, kind="stable")
    order_desc = order_asc[::-1].copy()
    cell_area = cell_m * cell_m
    acc = D.accumulate_area(rec.ravel(), order_desc, cell_area).reshape(dem.shape)
    chan = D.channel_mask(acc, ac_m2)
    n_up = D.count_upstream_channels(rec.ravel(), chan.ravel(), order_asc)
    basin, cells, offs = D.first_order_basins(rec.ravel(), chan.ravel(), n_up, dem.shape[1])
    chi = D.chi_field(rec.ravel(), acc.ravel(), order_asc, theta, area0, cell_m).reshape(dem.shape)
    slope = D.slope_horn(filled, cell_m)

    n_links = int(offs.size - 1)
    knick_strength = np.zeros(dem.shape, dtype=np.float32)     # max break magnitude per cell
    ksn_seg = np.zeros(dem.shape, dtype=np.float32)            # |d z / d chi| of the host segment
    knick_cells: list[tuple[int, float, float]] = []           # (flat index, strength, azimuth)
    az_field, coh_field = structure_tensor_azimuth(filled)
    n_breaks = 0
    n_breaks_material = 0
    seg_slopes_all = []
    for b in range(n_links):
        idx = cells[offs[b]:offs[b + 1]]
        if idx.size < 3 * knick_window + 2:
            continue
        # cells are stored upstream-first; the profile is read downstream -> upstream
        ii = idx[::-1]
        z = flat_filled[ii]
        c = chi.ravel()[ii]
        r = D.segment_profile(c, z, window=knick_window, ratio=knick_ratio, min_drop_m=min_drop_m)
        n_breaks += int(r["positions"].size)
        if r["positions"].size:
            n_breaks_material += int(r["positions"].size)
            seg_slopes_all.extend(np.abs(r["slopes"]).tolist())
        # attribute the host-segment gradient to every channel cell of that segment
        edges = np.concatenate([[0], r["positions"], [ii.size - 1]])
        for a, bb in zip(edges[:-1], edges[1:]):
            if bb - a < 2:
                continue
            dc = c[a:bb + 1] - c[a:bb + 1].mean()
            den = float((dc * dc).sum())
            g = float(((dc * (z[a:bb + 1] - z[a:bb + 1].mean())).sum()) / den) if den > 1e-12 else 0.0
            ksn_seg.ravel()[ii[a:bb + 1]] = abs(g)
        for j, p in enumerate(r["positions"]):
            cell = int(ii[p])
            s = float(r["breaks"][j]) if j < r["breaks"].size else 0.0
            knick_strength.ravel()[cell] = max(knick_strength.ravel()[cell], s)
            knick_cells.append((cell, s, float(az_field.ravel()[cell])))

    # ---- thin to ONE knickpoint per first-order drainage (independence is what the lane needs) ---
    best_by_link: dict[int, tuple[int, float, float]] = {}
    for cell, s, az in knick_cells:
        link = int(basin.ravel()[cell])
        if link < 0:
            continue
        cur = best_by_link.get(link)
        if cur is None or s > cur[1]:
            best_by_link[link] = (cell, s, az)
    thinned = np.zeros(dem.shape, dtype=np.float32)
    az_of_dot = np.zeros(dem.shape, dtype=np.float32)
    for cell, s, az in best_by_link.values():
        thinned.ravel()[cell] = s
        az_of_dot.ravel()[cell] = az

    # ---- strike coherence: independent drainages within a corridor sharing a common strike ------
    coherence = np.zeros(dem.shape, dtype=np.float32)
    bin_edges = np.arange(azimuth_bins + 1) * (180.0 / azimuth_bins)
    per_bin_n = []
    st = ndi.generate_binary_structure(2, 1)
    for bi in range(azimuth_bins):
        lo, hi = bin_edges[bi], bin_edges[bi + 1]
        sel = (thinned > 0) & (az_of_dot >= lo) & (az_of_dot < hi)
        n = int(sel.sum())
        per_bin_n.append(n)
        if n == 0:
            continue
        cnt = ndi.uniform_filter(sel.astype(np.float32), size=2 * corridor_px + 1) * (
            (2 * corridor_px + 1) ** 2)
        coherence = np.maximum(coherence, cnt.astype(np.float32))
    coherence = np.rint(coherence)

    # ---- routing sanity diagnostics (a DEM with no real network must not be silently trusted) ----
    inner = np.zeros_like(finite)
    inner[1:-1, 1:-1] = True
    raised_frac = float(((filled - np.where(finite, dem, np.nan)) > 1e-9).sum()
                        / max(int((finite & inner).sum()), 1))
    dist = D.flow_distance(rec.ravel(), order_asc, cell_m)
    chan_flat = chan.ravel()
    sel = chan_flat & (dist > 5.0 * cell_m) & (acc.ravel() > 0)
    hack_b = float("nan")
    if int(sel.sum()) > 500:
        la = np.log10(np.maximum(acc.ravel()[sel], 1.0))
        ll = np.log10(np.maximum(dist[sel], cell_m))
        hack_b = float(np.polyfit(ll, la, 1)[0])          # A ~ L**b, b ~ 1.7 for real networks

    # ---- confound masks -------------------------------------------------------------------------
    raised = (filled > np.where(finite, dem, np.nan) + 0.5) & finite
    rel = local_relief(filled, finite, size=15)
    playa = raised | (rel < 5.0)
    stripe = None
    if row_means is not None:
        stripe = detect_striped_rows(row_means)
        stripe["stripe_pixels_in_footprint"] = int((stripe["rows"][:, None] & finite).sum())
    return {
        "filled": filled.astype(np.float32), "acc": acc.astype(np.float32),
        "chi": chi.astype(np.float32), "slope": slope.astype(np.float32),
        "channel": chan, "basin": basin.reshape(dem.shape),
        "knick_strength": knick_strength, "ksn_seg": ksn_seg,
        "knick_thinned": thinned, "coherence": coherence,
        "playa_or_closed_basin": playa, "stripe": stripe,
        "azimuth": az_field, "azimuth_coherence": coh_field,
        "stats": {
            "n_links": n_links, "n_channel_px": int(chan.sum()),
            "n_knickpoints": len(knick_cells), "n_knickpoints_material": n_breaks_material,
            "n_links_with_knick": int(len(best_by_link)),
            "per_azimuth_bin_counts": per_bin_n,
            "median_segment_slope": float(np.median(seg_slopes_all)) if seg_slopes_all else None,
            "chanel_threshold_m2": ac_m2, "theta": theta,
            "playa_px": int(playa.sum()),
            "acc_max_px": float(acc.max() / (cell_m * cell_m)),
            "acc_median_channel_px": float(np.median(acc.ravel()[chan_flat]) / (cell_m * cell_m)),
            "filled_raised_fraction": raised_frac,
            "hack_exponent_A_vs_L": hack_b,
            "flow_distance_max_km": float(dist.max() / 1000.0),
        },
    }


def strike_trace_support(knick: np.ndarray, footprint: np.ndarray, *, n_az_bins: int = 36,
                         offset_tol_px: float = 3.0, wedge_deg: float = 3.0, gap_px: float = 24.0,
                         min_support: int = 3, max_len_px: float = 200.0, paint_radius: int = 1,
                         basin: np.ndarray | None = None, max_traces: int = 400) -> dict:
    """Detector for the lane's actual object: a FAULT TRACE made of collinear knickpoints.

    Mechanism.  A fault the catalogue does not contain still forces every channel that crosses it
    into a steep reach (Kirby & Whipple 2012), and because a fault is a *line* those knickpoints sit
    on a common strike (Gailleton et al. 2019 use the same collinearity, in profile space).  The
    evidence for a trace is therefore the number of INDEPENDENT first-order drainages supporting it,
    not the strength of any single knickpoint -- exactly what the lane's stop rule demands
    ("aligned across several independent drainages along a common strike").

    Implementation (three stages, all deterministic):
      1. for each of ``n_az_bins`` strikes, knickpoints are retreived in along-strike order and
         chained greedily; a chain grows while the next point is within ``gap_px`` along the strike
         and within ``offset_tol_px + tan(wedge_deg)*(v - v_first)`` of the running mean offset.
         The wedge term is the discretisation allowance for an azimuth bin half-width, so a genuine
         trace is not lost merely because it sits between two bins;
      2. candidates are kept when they hold >= ``min_support`` points from >= ``min_support``
         DIFFERENT first-order basins, are shorter than ``max_len_px``, and then thinned by
         non-maximum suppression ordered by (support desc, offset residual asc): one fault cannot be
         claimed twice, and the best-fitting strike wins the points;
      3. each accepted trace is REFIT by principal axis on its inlier pixels (sub-bin azimuth), and
         painted from end to end with paint_radius.
    (A fixed-bin Hough transform was tried first and rejected by its own positive control: with a
    2 px rho bin it only accepts points collinear to one bin, which real knickpoint sets are not.)

    Returns dict(support, weight, traces, n_traces, support_px, stats).
    """
    h, w = knick.shape
    support = np.zeros((h, w), dtype=np.float32)
    weight = np.zeros((h, w), dtype=np.float32)
    traces: list[dict] = []
    ys, xs = np.nonzero((knick > 0) & footprint)
    n_pts = ys.size
    if n_pts < min_support:
        return {"support": support, "weight": weight, "traces": traces, "n_traces": 0,
                "support_px": 0, "stats": {"n_knickpoints": int(n_pts), "n_candidates": 0}}
    s = knick[ys, xs].astype(np.float64)
    uid = np.arange(n_pts, dtype=np.int64) if basin is None else basin[ys, xs].astype(np.int64)
    wedge = float(np.tan(np.deg2rad(wedge_deg)))
    cand: list[tuple[int, float, tuple]] = []
    for bi in range(n_az_bins):
        th = (bi + 0.5) * np.pi / n_az_bins
        ct, st = np.cos(th), np.sin(th)
        u = xs * ct + ys * st
        v = -xs * st + ys * ct
        order = np.argsort(v, kind="stable")
        for oi in range(n_pts):
            i = order[oi]
            chain = [i]
            u_sum, v_first, v_last = u[i], v[i], v[i]
            for oj in range(oi + 1, n_pts):
                j = order[oj]
                if v[j] - v_last > gap_px or v[j] - v_first > max_len_px:
                    break
                tol = offset_tol_px + wedge * (v[j] - v_first)
                if abs(u[j] - u_sum / len(chain)) <= tol:
                    chain.append(j)
                    u_sum += u[j]
                    v_last = v[j]
            if len(chain) < min_support:
                continue
            if np.unique(uid[chain]).size < min_support:
                continue
            vc = v[chain]
            resid = float(np.abs(u[chain] - u[chain].mean()).max())
            cand.append((len(chain), -resid, (th, u[chain].mean(), float(vc.min()),
                                              float(vc.max()), tuple(chain))))
    # non-maximum suppression by (support desc, residual asc), points consumed once
    cand.sort(key=lambda c: (-c[0], -c[1]))
    consumed = np.zeros(n_pts, dtype=bool)
    n_cand_accepted = 0
    for n_sup, neg_resid, (th, u0, v_lo, v_hi, chain) in cand:
        if len(traces) >= max_traces or n_cand_accepted >= max_traces:
            break
        idx = np.fromiter(chain, dtype=np.int64, count=len(chain))
        if consumed[idx].any():
            continue
        # refit the strike (principal axis) on the inlier pixels, in (x=col, y=row) coordinates
        pxin, pyin = xs[idx].astype(np.float64), ys[idx].astype(np.float64)
        mx, my = pxin.mean(), pyin.mean()
        cxx = float(((pxin - mx) ** 2).mean())
        cyy = float(((pyin - my) ** 2).mean())
        cxy = float(((pxin - mx) * (pyin - my)).mean())
        az_fit = 0.5 * np.arctan2(2.0 * cxy, cxx - cyy)
        dx_, dy_ = np.cos(az_fit), np.sin(az_fit)
        # re-project the inliers onto the fitted axis: the trace runs between their extremes
        tproj = (pxin - mx) * dx_ + (pyin - my) * dy_
        t0, t1 = float(tproj.min()), float(tproj.max())
        if t1 - t0 > max_len_px:
            continue
        steps = np.arange(int(t1 - t0) + 1, dtype=np.float64) + t0
        pxp = mx + steps * dx_
        pyp = my + steps * dy_
        pxi = np.rint(pxp).astype(np.int64)
        pyi = np.rint(pyp).astype(np.int64)
        ok = (pxi >= 0) & (pxi < w) & (pyi >= 0) & (pyi < h)
        if not ok.any():
            continue
        consumed[idx] = True
        n_cand_accepted += 1
        strength = float(np.mean(s[idx]))
        cnt = float(len(idx))
        idxs = []
        for oy in range(-paint_radius, paint_radius + 1):
            for ox in range(-paint_radius, paint_radius + 1):
                yy = np.clip(pyi[ok] + oy, 0, h - 1)
                xx = np.clip(pxi[ok] + ox, 0, w - 1)
                idxs.append(yy * w + xx)
        flat = np.concatenate(idxs)
        np.maximum.at(support.ravel(), flat, cnt)
        np.maximum.at(weight.ravel(), flat, cnt * strength)
        traces.append({"azimuth_bin_deg": float(np.degrees(th) % 180.0),
                       "azimuth_fit_deg": float(np.degrees(az_fit) % 180.0),
                       "support": int(len(idx)), "n_drainages": int(np.unique(uid[idx]).size),
                       "length_px": float(t1 - t0), "mean_knick_strength": strength,
                       "max_offset_residual_px": float(-neg_resid),
                       "midpoint_yx": [float(my), float(mx)]})
    support[~footprint] = 0.0
    weight[~footprint] = 0.0
    sup = support[support > 0]
    lens = [tr["length_px"] for tr in traces]
    return {"support": support, "weight": weight, "traces": traces, "n_traces": len(traces),
            "support_px": int((support > 0).sum()),
            "stats": {"n_knickpoints": int(n_pts), "n_candidates": len(cand),
                      "support_px_ge_min": int((support >= min_support).sum()),
                      "max_support": float(sup.max()) if sup.size else 0.0,
                      "trace_px_total": int(support.astype(np.int64).clip(0).sum()),
                      "median_trace_length_px": float(np.median(lens)) if lens else 0.0,
                      "median_drainages_per_trace": float(np.median(
                          [tr["n_drainages"] for tr in traces])) if traces else 0.0,
                      "azimuth_deg_hist_10": [int(x) for x in np.histogram(
                          [tr["azimuth_fit_deg"] for tr in traces],
                          bins=np.arange(0, 181, 10))[0]] if traces else [0] * 18}}


def score_from_traces(trace: dict, footprint: np.ndarray, min_drainages: int = 3) -> np.ndarray:
    """Emission score = trace weight where the trace has >= min_drainages supporting drainages."""
    sc = np.where(footprint & (trace["support"] >= float(min_drainages)),
                  trace["weight"], 0.0).astype(np.float32)
    return sc


def score_field(fields: dict, footprint: np.ndarray, min_drainages: int = 3,
                weight: str = "strength", **trace_kw) -> np.ndarray:
    """Convenience wrapper: build the strike traces from ``fields`` and return the emission score.

    There is deliberately no term that rewards proximity to the supplied catalogue: the board
    scores faults the catalogue does not contain (competition page 967).
    """
    tr = strike_trace_support(fields["knick_thinned"], footprint, min_support=int(min_drainages),
                              basin=fields.get("basin"), **trace_kw)
    return score_from_traces(tr, footprint, min_drainages)
