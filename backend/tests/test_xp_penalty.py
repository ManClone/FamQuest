from app.weekly_consequences import xp_penalty


def test_penalty_clamped_to_balance():
    result = xp_penalty(3, 5)
    assert result.deducted_xp == 3
    assert result.remaining_xp == 0
    assert result.unapplied_xp == 2


def test_penalty_does_not_change_other_amounts():
    result = xp_penalty(20, 5)
    assert result.remaining_xp == 15
    assert result.unapplied_xp == 0
