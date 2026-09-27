from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.point import PointExpirationPolicy, PointTransactionType
from app.services.point import UserPointService


@pytest.mark.asyncio
async def test_monthly_grant_uses_configured_amount():
    """The monthly grant must honor MONTHLY_GRANT_AMOUNT instead of a hard-coded default."""
    configured_amount = 250

    db = MagicMock()
    # No existing monthly grant for the current month.
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=existing_result)

    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()

    service = UserPointService(db=db, redis=redis)
    service.create_point_allocation = AsyncMock()

    # Simulate an operator overriding the grant amount via settings.
    fake_settings = SimpleNamespace(MONTHLY_GRANT_AMOUNT=configured_amount)
    assert not hasattr(fake_settings, "MONTHLY_POINTS")

    with patch("app.services.point.get_settings", return_value=fake_settings):
        await service.grant_monthly_points("user-123")

    service.create_point_allocation.assert_awaited_once()
    kwargs = service.create_point_allocation.await_args.kwargs
    assert kwargs["amount"] == configured_amount
    assert kwargs["allocation_type"] is PointTransactionType.MONTHLY_GRANT
    assert kwargs["expiration_policy"] is PointExpirationPolicy.END_OF_THIS_MONTH
