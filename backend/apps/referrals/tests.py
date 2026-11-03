import pytest

from .services import fee_for_rent


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("rent", "expected"),
    [(14_999, 1_500), (15_000, 2_500), (29_999, 2_500),
     (30_000, 4_000), (60_000, 4_000), (60_001, 6_000)],
)
def test_seeded_fee_rules_keep_the_agreed_monthly_rent_bands(rent, expected):
    assert fee_for_rent(rent) == expected
