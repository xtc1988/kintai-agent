import pytest
from services.dummy_stamper import DummyStamper


@pytest.mark.asyncio
async def test_dummy_clock_in():
    stamper = DummyStamper()
    result = await stamper.clock_in()
    assert result.success is True
    assert result.timestamp != ""
    assert result.error is None


@pytest.mark.asyncio
async def test_dummy_clock_out():
    stamper = DummyStamper()
    result = await stamper.clock_out()
    assert result.success is True


@pytest.mark.asyncio
async def test_dummy_close():
    stamper = DummyStamper()
    await stamper.close()  # should not raise
