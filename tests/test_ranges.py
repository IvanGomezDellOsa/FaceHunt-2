from app.pipeline.ranges import MatchPoint, build_ranges


def mp(ts, score=0.5, idx=0):
    return MatchPoint(timestamp=ts, score=score, frame_index=idx)


def test_empty():
    assert build_ranges([], merge_gap=2.0) == []


def test_single_match():
    ranges = build_ranges([mp(10)], merge_gap=2.0)
    assert len(ranges) == 1
    r = ranges[0]
    assert r.start == 10 and r.end == 10 and r.count == 1


def test_consecutive_merge_within_gap():
    pts = [mp(0), mp(1), mp(2), mp(3)]
    ranges = build_ranges(pts, merge_gap=2.0)
    assert len(ranges) == 1
    assert ranges[0].start == 0 and ranges[0].end == 3 and ranges[0].count == 4


def test_split_when_gap_exceeded():
    pts = [mp(0), mp(1), mp(10), mp(11)]
    ranges = build_ranges(pts, merge_gap=2.0)
    assert len(ranges) == 2
    assert ranges[0].end == 1
    assert ranges[1].start == 10 and ranges[1].end == 11


def test_best_timestamp_is_highest_score():
    pts = [mp(0, 0.4), mp(1, 0.9), mp(2, 0.5)]
    ranges = build_ranges(pts, merge_gap=2.0)
    assert ranges[0].best_timestamp == 1
    assert ranges[0].best_score == 0.9


def test_tie_breaks_to_earliest():
    pts = [mp(5, 0.8), mp(6, 0.8)]
    ranges = build_ranges(pts, merge_gap=2.0)
    assert ranges[0].best_timestamp == 5


def test_unordered_input_is_sorted():
    pts = [mp(11), mp(0), mp(10), mp(1)]
    ranges = build_ranges(pts, merge_gap=2.0)
    assert len(ranges) == 2
    assert ranges[0].start == 0
    assert ranges[1].start == 10


def test_zero_gap_keeps_only_exact_consecutive():
    # Con gap 0, sólo timestamps idénticos se agrupan.
    pts = [mp(0), mp(1), mp(1)]
    ranges = build_ranges(pts, merge_gap=0.0)
    assert len(ranges) == 2
    assert ranges[1].count == 2
