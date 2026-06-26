import numpy as np

from app.pipeline.tracker import FaceObs, FaceTracker, iou

DIM = 8
REF = np.zeros(DIM, dtype=np.float32)
REF[0] = 1.0


def emb(sim: float, axis: int = 1) -> np.ndarray:
    """Vector unitario con dot(REF, .) == sim y el resto sobre un eje dado."""
    v = np.zeros(DIM, dtype=np.float32)
    v[0] = sim
    v[axis] = float(np.sqrt(max(0.0, 1.0 - sim * sim)))
    return v


def obs(sim, bbox=(0, 0, 10, 10), quality=20.0, axis=1):
    e = emb(sim, axis)
    return FaceObs(bbox=bbox, embedding=e, quality=quality, sim_ref=float(REF @ e))


def tracker(**kw):
    kw.setdefault("threshold", 0.30)
    kw.setdefault("secondary_threshold", 0.22)
    return FaceTracker(REF, **kw)


# -- IoU ---------------------------------------------------------------------
def test_iou_identical():
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0


def test_iou_disjoint():
    assert iou((0, 0, 10, 10), (100, 100, 110, 110)) == 0.0


def test_iou_half_overlap():
    # Mitad de solapamiento en X -> inter 50, union 150.
    assert abs(iou((0, 0, 10, 10), (5, 0, 15, 10)) - (50 / 150)) < 1e-6


# -- tracking básico ---------------------------------------------------------
def test_single_identity_one_track():
    t = tracker()
    t.update(0.0, 0, [obs(0.6)])
    t.update(0.5, 1, [obs(0.6)])
    closed = t.finalize()
    assert len(closed) == 1
    assert closed[0].is_match
    assert len(closed[0].points) == 2


def test_two_identities_two_tracks():
    t = tracker()
    # Identidad A (eje 1, cerca de REF) y B (eje 2, ortogonal, lejos), sin solape.
    a = obs(0.6, bbox=(0, 0, 10, 10), axis=1)
    b = obs(0.0, bbox=(100, 100, 110, 110), axis=2)
    t.update(0.0, 0, [a, b])
    t.update(0.5, 1, [obs(0.6, bbox=(0, 0, 10, 10), axis=1),
                      obs(0.0, bbox=(100, 100, 110, 110), axis=2)])
    closed = t.finalize()
    assert len(closed) == 2
    matches = [c for c in closed if c.is_match]
    assert len(matches) == 1  # sólo A matchea la referencia


def test_association_by_appearance_without_overlap():
    # Misma identidad pero la caja se movió (IoU=0): debe asociar por apariencia.
    t = tracker()
    t.update(0.0, 0, [obs(0.6, bbox=(0, 0, 10, 10))])
    t.update(0.5, 1, [obs(0.6, bbox=(200, 200, 210, 210))])
    closed = t.finalize()
    assert len(closed) == 1
    assert len(closed[0].points) == 2


# -- agregación temporal -----------------------------------------------------
def test_aggregation_confirms_when_no_single_frame_passes():
    # Dos frames con sim 0.29 (<0.30) y ruido opuesto; misma caja (asocia por IoU).
    # El promedio cancela el ruido y concentra la identidad -> agregado supera umbral.
    t = tracker()
    f1 = FaceObs((0, 0, 10, 10), emb(0.29, axis=1), 20.0, 0.29)
    f2 = FaceObs((0, 0, 10, 10), emb(0.29, axis=2), 20.0, 0.29)
    t.update(0.0, 0, [f1])
    t.update(0.5, 1, [f2])
    closed = t.finalize()
    assert len(closed) == 1
    assert closed[0].best_sim < 0.30
    assert closed[0].aggregated_sim >= 0.30
    assert closed[0].is_match


def test_quality_weighting_favors_high_quality_frame():
    # Frame de alta calidad con sim alta domina el embedding agregado.
    t = tracker()
    t.update(0.0, 0, [FaceObs((0, 0, 10, 10), emb(0.7, 1), 100.0, 0.7)])
    t.update(0.5, 1, [FaceObs((0, 0, 10, 10), emb(0.1, 1), 1.0, 0.1)])
    closed = t.finalize()
    assert closed[0].aggregated_sim > 0.6


# -- umbral secundario / recuperación ---------------------------------------
def test_secondary_recovers_degraded_frames_of_matched_track():
    t = tracker(threshold=0.30, secondary_threshold=0.22)
    # Mismo track: un frame fuerte y dos débiles (uno sobre, otro bajo el secundario).
    t.update(0.0, 0, [obs(0.55, bbox=(0, 0, 10, 10))])
    t.update(0.5, 1, [obs(0.25, bbox=(0, 0, 10, 10))])
    t.update(1.0, 2, [obs(0.18, bbox=(0, 0, 10, 10))])
    closed = t.finalize()
    assert len(closed) == 1
    pts = closed[0].match_points(0.22)
    sims = sorted(round(p.sim_ref, 2) for p in pts)
    assert sims == [0.25, 0.55]  # 0.18 queda excluido


def test_no_match_track_yields_no_points():
    t = tracker()
    t.update(0.0, 0, [obs(0.15, axis=2)])
    t.update(0.5, 1, [obs(0.15, axis=2)])
    closed = t.finalize()
    assert len(closed) == 1
    assert not closed[0].is_match
    assert closed[0].match_points(0.22) == []


# -- cierre por hueco temporal ----------------------------------------------
def test_stale_track_closes_after_gap():
    t = tracker(max_gap_seconds=2.0)
    t.update(0.0, 0, [obs(0.6)])
    # Pasaron 5s sin actualizar el track -> se cierra al llegar el próximo frame.
    closed_now = t.update(5.0, 10, [obs(0.6)])
    assert len(closed_now) == 1
    assert closed_now[0].points[0].timestamp == 0.0
    remaining = t.finalize()
    assert len(remaining) == 1
    assert remaining[0].points[0].timestamp == 5.0


def test_best_frame_tracks_highest_sim():
    t = tracker()
    t.update(0.0, 0, [FaceObs((0, 0, 10, 10), emb(0.3, 1), 20.0, 0.3, frame="A")])
    t.update(0.5, 1, [FaceObs((0, 0, 10, 10), emb(0.8, 1), 20.0, 0.8, frame="B")])
    closed = t.finalize()
    assert closed[0].best_frame == "B"
    assert closed[0].best_timestamp == 0.5
