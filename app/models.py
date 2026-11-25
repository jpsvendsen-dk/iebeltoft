from sqlalchemy import Column, Integer, String, Date, Numeric, Enum, DateTime, Text, ForeignKey, Boolean, false, UniqueConstraint, Index
from sqlalchemy.sql import func
from app.database import Base
import enum


class SeasonEnum(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


class BookingStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"


class SeasonInterval(Base):
    """Definerer hvilke datoer der tilhører hvilken sæson."""
    __tablename__ = "season_intervals"

    id = Column(Integer, primary_key=True)
    date_from = Column(Date, nullable=False)
    date_to = Column(Date, nullable=False)
    season = Column(Enum(SeasonEnum), nullable=False)
    label = Column(String(100))  # fx "Sommer 2025"


class SeasonPrice(Base):
    """Ugepris for hver sæson."""
    __tablename__ = "season_prices"

    season = Column(Enum(SeasonEnum), primary_key=True)
    price_per_week = Column(Numeric(10, 2), nullable=False)
    min_nights = Column(Integer, default=7)


class Settings(Base):
    """Systemindstillinger — singleton (id=1)."""
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, default=1)
    admin_email = Column(String(200))
    electricity_price_kwh = Column(Numeric(8, 2), default=2.65)
    water_price_m3 = Column(Numeric(8, 2), default=65.00)
    saturday_only = Column(Integer, default=1)  # 1 = kun lørdag-til-lørdag


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, server_default=func.now())

    guest_name = Column(String(200), nullable=False)
    guest_email = Column(String(200), nullable=False)
    guest_phone = Column(String(50))
    guest_address = Column(String(200))
    guest_zip = Column(String(10))
    guest_city = Column(String(100))
    guest_remarks = Column(Text)  # Gæstens egne bemærkninger

    check_in = Column(Date, nullable=False)
    check_out = Column(Date, nullable=False)

    total_price = Column(Numeric(10, 2))
    status = Column(Enum(BookingStatus), default=BookingStatus.pending)

    stripe_payment_id = Column(String(200))
    notes = Column(Text)  # Admin-noter


class CalendarVisitor(Base):
    __tablename__ = "calendar_visitors"
    id = Column(Integer, primary_key=True)
    email = Column(String(254), unique=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    early_access = Column(Boolean, nullable=False, default=False, server_default=false())
    progress_version = Column(Integer, nullable=False, default=0, server_default="0")


class CalendarLoginLink(Base):
    __tablename__ = "calendar_login_links"
    token_hash = Column(String(64), primary_key=True)
    email = Column(String(254), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    used_at = Column(DateTime)


class CalendarLoginSession(Base):
    __tablename__ = "calendar_login_sessions"
    token_hash = Column(String(64), primary_key=True)
    visitor_id = Column(Integer, ForeignKey("calendar_visitors.id"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)


class CalendarOpenedDoor(Base):
    __tablename__ = "calendar_opened_doors"
    visitor_id = Column(Integer, ForeignKey("calendar_visitors.id"), primary_key=True)
    year = Column(Integer, primary_key=True)
    day = Column(Integer, primary_key=True)


class CalendarLoginRate(Base):
    __tablename__ = "calendar_login_rates"
    bucket = Column(String(64), primary_key=True)
    count = Column(Integer, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)


class CalendarDoorEvent(Base):
    __tablename__ = "calendar_door_events"
    __table_args__ = (
        UniqueConstraint("visitor_id", "event_id", name="uq_calendar_visitor_event"),
        Index("ix_calendar_event_history", "year", "clicked_at", "id"),
        Index("ix_calendar_visitor_history", "visitor_id", "year", "clicked_at"),
    )
    id = Column(Integer, primary_key=True)
    visitor_id = Column(Integer, ForeignKey("calendar_visitors.id"), nullable=False)
    event_id = Column(String(36), nullable=False)
    year = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False)
    clicked_at = Column(DateTime, nullable=False)
    result = Column(String(16), nullable=False)  # opened, reopened, locked
    progress_version = Column(Integer, nullable=False, default=0, server_default="0")
    ip_address = Column(String(45))
    device_type = Column(String(120))
    user_agent = Column(String(512))


class CalendarLoginEvent(Base):
    __tablename__ = "calendar_login_events"
    id = Column(Integer, primary_key=True)
    visitor_id = Column(Integer, ForeignKey("calendar_visitors.id"), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    logged_at = Column(DateTime, nullable=False, index=True)
    ip_address = Column(String(45))
    device_type = Column(String(120))
    user_agent = Column(String(512))


class CalendarSnakeProfile(Base):
    __tablename__ = "calendar_snake_profiles"
    __table_args__ = (UniqueConstraint("year", "name_key", name="uq_snake_player_name"),)
    visitor_id = Column(Integer, ForeignKey("calendar_visitors.id"), primary_key=True)
    year = Column(Integer, primary_key=True)
    display_name = Column(String(20))
    name_key = Column(String(60))
    is_public = Column(Boolean, nullable=False, default=False, server_default=false())
    best_score = Column(Integer, nullable=False, default=0, server_default="0")
    achieved_at = Column(DateTime)


class CalendarSnakeRound(Base):
    __tablename__ = "calendar_snake_rounds"
    id = Column(String(36), primary_key=True)
    visitor_id = Column(Integer, ForeignKey("calendar_visitors.id"), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    seed = Column(Integer, nullable=False)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime)
    score = Column(Integer)
    submission_hash = Column(String(64))
