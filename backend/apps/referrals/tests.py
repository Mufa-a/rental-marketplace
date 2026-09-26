import pytest

from .services import fee_for_rent


@pytest.mark.parametrize(
    ("rent", "expected"),
    [(14_999, 1_500), (15_000, 2_500), (29_999, 2_500),
     (30_000, 4_000), (60_000, 4_000), (60_001, 6_000)],
)
def test_referral_fee_uses_agreed_monthly_rent_bands(rent, expected):
    assert fee_for_rent(rent) == expected
