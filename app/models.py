from sqlalchemy import Column, Integer, String, Date, Numeric, Enum, DateTime, Text
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
