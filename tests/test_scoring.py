from core.scoring import compute_score, sanitize_name


def test_score_formula():
    s = compute_score(seconds=30.0, moves=40, multiplier=1.5, radar_uses=1, hint_uses=2)
    assert s.base == 10000 - 50 * 30 - 20 * 40          # 7700
    assert s.scaled == 7700 * 1.5                       # 11550
    assert s.final == 11550 - 500 - 600                 # 10450


def test_base_floors_at_zero_and_final_can_go_negative():
    s = compute_score(seconds=500.0, moves=0, multiplier=3.0, radar_uses=3, hint_uses=1)
    assert s.base == 0 and s.scaled == 0
    assert s.final == -1800


def test_seconds_rounded_to_displayed_precision():
    s = compute_score(seconds=12.34, moves=10, multiplier=1.0, radar_uses=0, hint_uses=0)
    assert s.seconds == 12.3
    assert s.final == 10000 - 615 - 200


def test_half_points_round_in_final():
    s = compute_score(seconds=0.1, moves=0, multiplier=1.5, radar_uses=0, hint_uses=0)
    assert s.scaled == 9995 * 1.5            # 14992.5
    assert s.final == 14993                 # half rounds up


def test_sanitize_name():
    assert sanitize_name("Abdullah_#1 !") == "Abdullah1 "
    assert sanitize_name("A" * 20) == "A" * 12
