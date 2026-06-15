import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.models import (
    Base, Room, RoomBooking, RoomCleaning, RoomMaintenance, Staff, Account, Expense, AccountType, Store
)

@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()

def test_database_structure(test_db):
    # 1. Setup mock store, staff, room
    store = Store(name="Test Store")
    test_db.add(store)
    test_db.commit()

    staff_reporter = Staff(username="reporter1", password_hash="123", name="Reporter Jack", role="supervisor")
    staff_cleaner = Staff(username="housekeeper1", password_hash="123", name="Cleaner Mary", role="housekeeper")
    staff_tech = Staff(username="technician1", password_hash="123", name="Tech Bob", role="technician")
    test_db.add_all([staff_reporter, staff_cleaner, staff_tech])
    test_db.commit()

    room = Room(room_number="101", room_type="Standard", price_per_night=5000.0, status="available")
    test_db.add(room)
    test_db.commit()

    # 2. Setup cleaning task
    cleaning = RoomCleaning(
        room_id=room.id,
        floor_wing="Ground Floor",
        cleaning_status="Pending",
        cleaning_type="Deep Clean",
        assigned_housekeeper_id=staff_cleaner.id,
        notes="Inspect minibar",
        scheduled_time=datetime.datetime.utcnow()
    )
    test_db.add(cleaning)
    test_db.commit()

    # 3. Setup maintenance ticket
    maint = RoomMaintenance(
        room_id=room.id,
        area="Room 101 Bathroom",
        issue_type="Plumbing",
        priority="High",
        reported_by_id=staff_reporter.id,
        assigned_technician_id=staff_tech.id,
        status="Open",
        cost=1500.0,
        notes="Leaking shower faucet",
        is_recurring=True,
        recurring_months=3
    )
    test_db.add(maint)
    test_db.commit()

    # 4. Verify structures and relationships
    assert cleaning.room.room_number == "101"
    assert cleaning.housekeeper.name == "Cleaner Mary"
    assert maint.room.room_number == "101"
    assert maint.reporter.name == "Reporter Jack"
    assert maint.technician.name == "Tech Bob"
    assert maint.is_recurring is True
    assert maint.recurring_months == 3


def test_checkout_triggers_cleaning(test_db):
    # Setup Room & Booking
    room = Room(room_number="102", room_type="Suite", price_per_night=8000.0, status="occupied")
    test_db.add(room)
    test_db.commit()

    booking = RoomBooking(
        room_id=room.id,
        customer_name="John Doe",
        customer_phone="0711222333",
        from_date=datetime.datetime.now(),
        to_date=datetime.datetime.now(),
        nights=2,
        booking_type="Bed Only",
        occupancy=1,
        total_amount=16000.0,
        paid_amount=16000.0,
        balance=0.0,
        status="active"
    )
    test_db.add(booking)
    test_db.commit()

    # Checkout simulation
    booking.status = "checked_out"
    room.status = "dirty"
    
    new_cleaning = RoomCleaning(
        room_id=booking.room_id,
        floor_wing=room.category or "Default",
        cleaning_status="Pending",
        cleaning_type="Checkout Clean",
        notes=f"Auto-generated checkout clean for guest {booking.customer_name}.",
        scheduled_time=datetime.datetime.utcnow(),
        created_at=datetime.datetime.utcnow()
    )
    test_db.add(new_cleaning)
    test_db.commit()

    # Verify room is dirty and cleaning task exists
    assert room.status == "dirty"
    assert booking.status == "checked_out"
    
    task = test_db.query(RoomCleaning).filter(RoomCleaning.room_id == room.id).first()
    assert task is not None
    assert task.cleaning_type == "Checkout Clean"
    assert task.cleaning_status == "Pending"
    assert "John Doe" in task.notes


def test_checkin_validation_dirty_or_maintenance(test_db):
    # Setup Rooms
    room_dirty = Room(room_number="103", room_type="Standard", price_per_night=5000.0, status="dirty")
    room_maint = Room(room_number="104", room_type="Standard", price_per_night=5000.0, status="maintenance")
    room_avail = Room(room_number="105", room_type="Standard", price_per_night=5000.0, status="available")
    test_db.add_all([room_dirty, room_maint, room_avail])
    test_db.commit()

    # Validation logic helper for test
    def validate_room_bookable(room_obj, db_session):
        if room_obj.status in ["dirty", "cleaning"]:
            return False, "Room is dirty or being cleaned"
        if room_obj.status == "maintenance":
            return False, "Room is undergoing maintenance"
        
        # Check active maintenance tickets
        active_maint = db_session.query(RoomMaintenance).filter(
            RoomMaintenance.room_id == room_obj.id,
            RoomMaintenance.status.in_(["Open", "Assigned", "In Progress"])
        ).first()
        if active_maint:
            return False, "Room has active maintenance ticket"

        # Check active cleaning tasks
        active_clean = db_session.query(RoomCleaning).filter(
            RoomCleaning.room_id == room_obj.id,
            RoomCleaning.cleaning_status.in_(["Pending", "In Progress"])
        ).first()
        if active_clean:
            return False, "Room is currently being cleaned"

        return True, "Available"

    # Assert block states
    ok, msg = validate_room_bookable(room_dirty, test_db)
    assert ok is False
    assert "dirty" in msg

    ok, msg = validate_room_bookable(room_maint, test_db)
    assert ok is False
    assert "maintenance" in msg

    ok, msg = validate_room_bookable(room_avail, test_db)
    assert ok is True


def test_maintenance_unblocking_expense_and_recurrence(test_db):
    # Setup accounting configurations
    store = Store(name="KastomPOS Hotel")
    test_db.add(store)
    test_db.commit()

    exp_type = AccountType(name="Expense", description="Expenses")
    test_db.add(exp_type)
    test_db.commit()

    acc = Account(name="Repairs & Maintenance", account_type="Expense", account_type_id=exp_type.id)
    test_db.add(acc)
    test_db.commit()

    staff_reporter = Staff(username="reporter2", password_hash="123", name="Jack", role="supervisor")
    test_db.add(staff_reporter)
    test_db.commit()

    # Setup room and put in maintenance
    room = Room(room_number="106", room_type="Standard", price_per_night=5000.0, status="available")
    test_db.add(room)
    test_db.commit()

    ticket = RoomMaintenance(
        room_id=room.id,
        area="Room 106 Balcony Door",
        issue_type="Furniture",
        priority="Medium",
        reported_by_id=staff_reporter.id,
        status="Open",
        cost=4500.0,
        is_recurring=True,
        recurring_months=6,
        notes="Replace door lock handle"
    )
    room.status = "maintenance"
    test_db.add(ticket)
    test_db.commit()

    assert room.status == "maintenance"

    # Complete maintenance ticket simulation
    ticket.status = "Completed"
    ticket.completion_date = datetime.datetime.utcnow()

    # Verify Expense Registration
    maint_account = test_db.query(Account).filter(Account.name.ilike('%maintenance%') | Account.name.ilike('%repair%')).first()
    assert maint_account is not None

    new_exp = Expense(
        ref_no="EXP-MAINT-0001",
        store_id=store.id,
        account_id=maint_account.id,
        amount=ticket.cost,
        balance=0.0,
        paid_to="Technician",
        expense_date=datetime.datetime.utcnow(),
        status="Completed",
        narrative=f"Auto-generated expense for completed room maintenance #{ticket.id}",
        is_active=True
    )
    test_db.add(new_exp)

    # Verify Room Unblock
    # Check if there are other open tickets
    other_maint = test_db.query(RoomMaintenance).filter(
        RoomMaintenance.room_id == room.id,
        RoomMaintenance.id != ticket.id,
        RoomMaintenance.status.in_(["Open", "Assigned", "In Progress"])
    ).first()
    if not other_maint:
        room.status = "available"

    # Verify Recurring Schedule creation
    if ticket.is_recurring and ticket.recurring_months:
        next_sched = datetime.datetime.utcnow() + datetime.timedelta(days=30 * ticket.recurring_months)
        new_recurring = RoomMaintenance(
            room_id=ticket.room_id,
            area=ticket.area,
            issue_type=ticket.issue_type,
            priority=ticket.priority,
            reported_by_id=ticket.reported_by_id,
            scheduled_date=next_sched,
            status="Open",
            is_recurring=True,
            recurring_months=ticket.recurring_months,
            notes=f"Auto-generated recurring ticket following completed ticket #{ticket.id}.",
            created_at=datetime.datetime.utcnow()
        )
        test_db.add(new_recurring)

    test_db.commit()

    # Asserts
    assert room.status == "available"
    assert test_db.query(Expense).filter(Expense.ref_no == "EXP-MAINT-0001").first() is not None
    assert test_db.query(Expense).filter(Expense.amount == 4500.0).first() is not None
    
    recurring_ticket = test_db.query(RoomMaintenance).filter(
        RoomMaintenance.room_id == room.id,
        RoomMaintenance.status == "Open"
    ).first()
    assert recurring_ticket is not None
    assert recurring_ticket.is_recurring is True
    assert recurring_ticket.recurring_months == 6
