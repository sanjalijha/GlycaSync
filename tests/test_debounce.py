import asyncio

import pytest

from app.integrations.debounce import DebounceBuffer, IngressPart


@pytest.mark.asyncio
async def test_multipart_messages_merge_into_one_payload():
    flushed = []
    buffer = DebounceBuffer(window_seconds=0.2, on_flush=flushed.append)
    await buffer.add(IngressPart(phone_number="+91999", image_url="/tmp/a.png"))
    await asyncio.sleep(0.05)
    await buffer.add(IngressPart(phone_number="+91999", text="thoda ghabrahat"))
    await asyncio.sleep(0.4)
    assert len(flushed) == 1
    assert flushed[0].parts == 2
    assert flushed[0].image_url == "/tmp/a.png"
    assert "ghabrahat" in flushed[0].text


@pytest.mark.asyncio
async def test_each_patient_flushes_independently():
    flushed = []
    buffer = DebounceBuffer(window_seconds=0.1, on_flush=flushed.append)
    await buffer.add(IngressPart(phone_number="+91111", text="sugar 110"))
    await buffer.add(IngressPart(phone_number="+91222", text="sugar 240"))
    await asyncio.sleep(0.3)
    assert {p.phone_number for p in flushed} == {"+91111", "+91222"}


@pytest.mark.asyncio
async def test_late_message_extends_the_window():
    flushed = []
    buffer = DebounceBuffer(window_seconds=0.2, on_flush=flushed.append)
    await buffer.add(IngressPart(phone_number="+91999", text="one"))
    await asyncio.sleep(0.15)
    await buffer.add(IngressPart(phone_number="+91999", text="two"))
    await asyncio.sleep(0.1)
    assert flushed == []
    await asyncio.sleep(0.2)
    assert len(flushed) == 1


@pytest.mark.asyncio
async def test_manual_flush_drains_buffer():
    buffer = DebounceBuffer(window_seconds=60)
    await buffer.add(IngressPart(phone_number="+91999", text="urgent"))
    assert buffer.pending_count() == 1
    payload = await buffer.flush("+91999")
    assert payload.text == "urgent"
    assert buffer.pending_count() == 0
    assert await buffer.flush("+91999") is None


@pytest.mark.asyncio
async def test_async_callback_is_awaited():
    seen = []

    async def handler(payload):
        await asyncio.sleep(0)
        seen.append(payload)

    buffer = DebounceBuffer(window_seconds=0.1, on_flush=handler)
    await buffer.add(IngressPart(phone_number="+91999", text="hi"))
    await asyncio.sleep(0.3)
    assert len(seen) == 1
