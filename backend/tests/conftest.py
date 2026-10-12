"""
Integration test fixtures. Uses mongomock-motor so the full test suite runs
against an in-memory Mongo-compatible database with NO real `mongod`
process required — convenient for CI and for anyone without MongoDB
installed locally. Swap `AsyncMongoMockClient` for a real
`motor.motor_asyncio.AsyncIOMotorClient` pointed at a real test database if
you'd rather test against genuine MongoDB semantics (recommended before
trusting the partial-unique-index behavior in Phase 2, since mongomock's
index enforcement is not a perfect match for real MongoDB).
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.db import mongo
from app.main import create_app


@pytest_asyncio.fixture
async def test_db():
    client = AsyncMongoMockClient()
    db = client["kabadiwala_connect_test"]
    mongo.set_db_for_testing(db)
    await mongo.create_indexes()
    yield db


@pytest_asyncio.fixture
async def client(test_db):
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def seeded_admin(test_db):
    from app.modules.auth.service import create_user_for_seeding

    return await create_user_for_seeding(username="admin", password="admin1234", role="GOVERNMENT_ADMIN")


@pytest_asyncio.fixture
async def seeded_recycler(test_db):
    from app.modules.auth.service import create_user_for_seeding

    return await create_user_for_seeding(username="RCY-001", password="recyclerpass1", role="RECYCLER")


@pytest_asyncio.fixture
async def seeded_ward(test_db):
    from app.modules.wards import service as wards_service

    admin_actor = {"user_id": "seed-admin", "role": "GOVERNMENT_ADMIN"}
    return await wards_service.create_ward(ward_id="WARD-1", name="Test Ward 1", actor=admin_actor)


@pytest_asyncio.fixture
async def other_ward(test_db):
    from app.modules.wards import service as wards_service

    admin_actor = {"user_id": "seed-admin", "role": "GOVERNMENT_ADMIN"}
    return await wards_service.create_ward(ward_id="WARD-2", name="Test Ward 2", actor=admin_actor)


@pytest_asyncio.fixture
async def seeded_home_user(seeded_ward):
    from app.modules.home_users import service as home_users_service

    result = await home_users_service.register(
        username="home-user-1",
        password="homepass123",
        full_name="Test Home User",
        address="123 Test Street",
        ward_id="WARD-1",
        household_lat=12.9716,
        household_lng=77.5946,
        upi_id=None,
    )
    return result["user"]


@pytest_asyncio.fixture
async def seeded_collector(seeded_ward):
    from app.modules.collectors import service as collectors_service

    admin_actor = {"user_id": "seed-admin", "role": "GOVERNMENT_ADMIN"}
    result = await collectors_service.create_collector(
        employee_id="EMP-001",
        password="collectorpass1",
        ward_id="WARD-1",
        rrr_id=None,
        assigned_area_radius_m=None,
        actor=admin_actor,
    )
    return result["user"]


@pytest_asyncio.fixture
async def pending_rrr_center(seeded_ward):
    from app.modules.rrr_centres import service as rrr_centres_service

    result = await rrr_centres_service.register(
        username="rrr-centre-1",
        password="rrrpass123",
        rrr_id="RRR-001",
        tender_id="TENDER-001",
        ward_id="WARD-1",
        licence_doc_ref=None,
    )
    return result["user"], result["profile"]


@pytest_asyncio.fixture
async def seeded_rrr_center(pending_rrr_center):
    from app.modules.rrr_centres import service as rrr_centres_service

    user, _profile = pending_rrr_center
    admin_actor = {"user_id": "seed-admin", "role": "GOVERNMENT_ADMIN"}
    await rrr_centres_service.approve(user_id=user["user_id"], actor=admin_actor)
    return user


@pytest_asyncio.fixture
async def collected_submission(seeded_home_user, seeded_collector):
    """Drives one real submission all the way to COLLECTED using the
    existing, already-tested Phase 2/4 services — the RRR-side tests build
    on top of a genuinely-reached COLLECTED item, not a hand-crafted doc."""
    from app.modules.ewaste import service as ewaste_service

    submit_result = await ewaste_service.create_submission(
        current_user=seeded_home_user,
        ward_id="WARD-1",
        photo_file_id="photo-1",
        home_lat=12.9716,
        home_lng=77.5946,
        home_ts=None,
        idempotency_key="fixture-submit-1",
    )
    handover_result = await ewaste_service.handover(
        current_user=seeded_collector,
        submission_id=submit_result["submission_id"],
        photo_file_id="handover-photo-1",
        collector_lat=12.97165,
        collector_lng=77.59465,
        collector_ts=None,
        idempotency_key="fixture-handover-1",
    )
    assert handover_result["status"] == "COLLECTED"
    return submit_result["submission_id"]


@pytest_asyncio.fixture
async def at_rrr_submission(seeded_rrr_center, collected_submission):
    """Drives the same real submission one step further, to AT_RRR, using
    the existing already-tested Phase 5 receive() service — Phase 8's
    classification tests build on a genuinely-reached AT_RRR item, not a
    hand-crafted doc. Returns submission_id."""
    from app.modules.ewaste import service as ewaste_service

    receive_result = await ewaste_service.receive(
        current_user=seeded_rrr_center, submission_id=collected_submission, idempotency_key="fixture-receive-1"
    )
    assert receive_result["status"] == "AT_RRR"
    return collected_submission


@pytest_asyncio.fixture
async def pending_recycler(test_db):
    from app.modules.recyclers import service as recyclers_service

    result = await recyclers_service.register(
        username="demo-recycler-1",
        password="recyclerpass123",
        company_name="Demo Recycling Co",
    )
    return result["user"], result["profile"]


@pytest_asyncio.fixture
async def seeded_approved_recycler(pending_recycler):
    from app.modules.recyclers import service as recyclers_service

    user, _profile = pending_recycler
    admin_actor = {"user_id": "seed-admin", "role": "GOVERNMENT_ADMIN"}
    await recyclers_service.approve(user_id=user["user_id"], actor=admin_actor)
    return user


@pytest_asyncio.fixture
async def listed_lot(seeded_rrr_center, seeded_collector):
    """Drives one real item all the way to a published, LISTED_FOR_BIDDING
    lot using the existing, already-tested Phase 2/4/5 services — bid
    tests build on a genuinely-reached listed lot, not a hand-crafted doc.
    Returns (lot_id, submission_id)."""
    from app.modules.ewaste import service as ewaste_service
    from app.modules.lots import service as lots_service
    from app.modules.home_users import service as home_users_service

    home_result = await home_users_service.register(
        username="listed-lot-home-user",
        password="homepass123",
        full_name="Listed Lot Home User",
        address="x",
        ward_id="WARD-1",
        household_lat=12.9716,
        household_lng=77.5946,
        upi_id=None,
    )
    submit_result = await ewaste_service.create_submission(
        current_user=home_result["user"],
        ward_id="WARD-1",
        photo_file_id="p",
        home_lat=12.9716,
        home_lng=77.5946,
        home_ts=None,
        idempotency_key="listed-lot-submit",
    )
    submission_id = submit_result["submission_id"]
    await ewaste_service.handover(
        current_user=seeded_collector,
        submission_id=submission_id,
        photo_file_id="p",
        collector_lat=12.97165,
        collector_lng=77.59465,
        collector_ts=None,
        idempotency_key="listed-lot-handover",
    )
    await ewaste_service.receive(
        current_user=seeded_rrr_center, submission_id=submission_id, idempotency_key="listed-lot-receive"
    )
    await ewaste_service.classify(
        current_user=seeded_rrr_center,
        submission_id=submission_id,
        category="e-waste-small-appliances",
        idempotency_key="listed-lot-classify",
    )
    create_result = await lots_service.create_lot(
        current_user=seeded_rrr_center,
        category="e-waste-small-appliances",
        submission_ids=[submission_id],
        idempotency_key="listed-lot-create",
    )
    lot_id = create_result["lot_id"]
    publish_result = await lots_service.publish_lot(
        current_user=seeded_rrr_center, lot_id=lot_id, idempotency_key="listed-lot-publish"
    )
    assert publish_result["status"] == "LISTED_FOR_BIDDING"
    return lot_id, submission_id


@pytest_asyncio.fixture
async def accepted_bid_lot(listed_lot, seeded_approved_recycler, seeded_rrr_center):
    """Drives a real lot from LISTED_FOR_BIDDING to BID_SELECTED using the
    existing, already-tested Phase 6 bids service — Phase 9's
    logistics/payment tests build on a genuinely-accepted bid, not a
    hand-crafted doc. Returns (lot_id, submission_id, bid_id, amount_str)."""
    from app.modules.bids import service as bids_service

    lot_id, submission_id = listed_lot
    place_result = await bids_service.place_bid(
        current_user=seeded_approved_recycler,
        lot_id=lot_id,
        amount_str="500.00",
        idempotency_key="accepted-bid-place",
    )
    bid_id = place_result["bid_id"]
    accept_result = await bids_service.accept_bid(
        current_user=seeded_rrr_center, bid_id=bid_id, idempotency_key="accepted-bid-accept"
    )
    assert accept_result["status"] == "ACCEPTED"
    return lot_id, submission_id, bid_id, "500.00"


@pytest_asyncio.fixture
async def logistics_booked_lot(accepted_bid_lot, seeded_approved_recycler):
    """Drives the accepted-bid lot one step further, to LOGISTICS_BOOKED,
    using the real Phase 9 logistics service. Returns the same 4-tuple as
    accepted_bid_lot."""
    from datetime import datetime, timezone

    from app.modules.logistics import service as logistics_service

    lot_id, submission_id, bid_id, amount_str = accepted_bid_lot
    result = await logistics_service.book_logistics(
        current_user=seeded_approved_recycler,
        lot_id=lot_id,
        slot_time=datetime.now(timezone.utc),
        idempotency_key="fixture-logistics-book",
    )
    assert result["status"] == "BOOKED"
    return lot_id, submission_id, bid_id, amount_str, result["booking_id"]


@pytest_asyncio.fixture
async def ready_for_collection_lot(logistics_booked_lot, seeded_approved_recycler):
    """Drives the lot one more step, to READY_FOR_COLLECTION — the only
    status payments/service.py accepts a payment against."""
    from app.modules.logistics import service as logistics_service

    lot_id, submission_id, bid_id, amount_str, booking_id = logistics_booked_lot
    result = await logistics_service.confirm_collection(
        current_user=seeded_approved_recycler, booking_id=booking_id, idempotency_key="fixture-logistics-confirm"
    )
    assert result["status"] == "COLLECTED"
    return lot_id, submission_id, bid_id, amount_str, booking_id


@pytest_asyncio.fixture
async def sold_lot(ready_for_collection_lot, seeded_approved_recycler):
    """Drives the lot to SOLD via a real payment — accepted_bid_lot's
    fixed "500.00" amount is a deterministic SUCCESS per
    app/modules/payments/gateway.py (see test_payment_gateway.py).
    Returns (lot_id, submission_id, bid_id, amount_str, booking_id)."""
    from app.modules.payments import service as payments_service

    lot_id, submission_id, bid_id, amount_str, booking_id = ready_for_collection_lot
    result = await payments_service.initiate_payment(
        current_user=seeded_approved_recycler, lot_id=lot_id, idempotency_key="fixture-payment-initiate"
    )
    assert result["status"] == "SUCCEEDED"
    return lot_id, submission_id, bid_id, amount_str, booking_id
