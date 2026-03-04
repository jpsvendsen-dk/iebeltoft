import datetime
from sqlalchemy.orm import Session
from app import models
from app.services.saeson import SAESON_FARVER
from app.utils import DANSKE_MAANEDER

# Lysere versioner af sæsonfarver til gæste-kalender
GAESTE_FARVER = {
    "A": {"bg": "bg-red-100",    "hover": "hover:bg-red-200",    "text": "text-red-900"},
    "B": {"bg": "bg-orange-100", "hover": "hover:bg-orange-200", "text": "text-orange-900"},
    "C": {"bg": "bg-yellow-100", "hover": "hover:bg-yellow-200", "text": "text-yellow-900"},
    "D": {"bg": "bg-green-100",  "hover": "hover:bg-green-200",  "text": "text-green-900"},
    "E": {"bg": "bg-blue-100",   "hover": "hover:bg-blue-200",   "text": "text-blue-900"},
}


def hent_optagne_datoer(db: Session) -> set:
    """Returnerer et sæt af alle optagne datoer (bekræftede + afventende bookinger)."""
    i_dag = datetime.date.today()
    bookinger = db.query(models.Booking).filter(
        models.Booking.check_out > i_dag,
        models.Booking.status.in_([
            models.BookingStatus.confirmed,
            models.BookingStatus.pending,
        ])
    ).all()

    optagne = set()
    for b in bookinger:
        dag = b.check_in
        while dag < b.check_out:
            optagne.add(dag)
            dag += datetime.timedelta(days=1)
    return optagne


def generer_gaeste_kalender(db: Session, maaneder_frem: int = 14) -> list[dict]:
    """
    Genererer kalenderdata til gæste-visningen.
    Viser nuværende og kommende måneder med tilgængelighed og sæsonfarver.
    """
    i_dag = datetime.date.today()
    optagne = hent_optagne_datoer(db)

    intervaller = db.query(models.SeasonInterval).order_by(
        models.SeasonInterval.date_from
    ).all()

    def saeson_for(dato: datetime.date):
        for iv in intervaller:
            if iv.date_from <= dato <= iv.date_to:
                return iv.season.value
        return None

    maaneder = []
    for m in range(maaneder_frem):
        aar = i_dag.year + (i_dag.month - 1 + m) // 12
        maaned_nr = (i_dag.month - 1 + m) % 12 + 1

        foerste_dag = datetime.date(aar, maaned_nr, 1)
        if maaned_nr == 12:
            sidst_dag = datetime.date(aar, 12, 31)
        else:
            sidst_dag = datetime.date(aar, maaned_nr + 1, 1) - datetime.timedelta(days=1)

        dage = []
        dag = foerste_dag
        while dag <= sidst_dag:
            saeson = saeson_for(dag)

            if dag < i_dag:
                status = "fortid"
            elif dag in optagne:
                status = "optaget"
            elif saeson is None:
                status = "optaget"  # Ingen sæson defineret = ikke mulig at booke
            else:
                status = "ledig"

            farver = GAESTE_FARVER.get(saeson, {
                "bg": "bg-white", "hover": "hover:bg-gray-50", "text": "text-gray-700"
            })

            dage.append({
                "dato_str": dag.isoformat(),
                "dag_nr": dag.day,
                "ugedag": dag.weekday(),
                "saeson": saeson or "",
                "status": status,
                "bg": farver["bg"],
                "hover": farver["hover"],
                "text": farver["text"],
            })
            dag += datetime.timedelta(days=1)

        maaneder.append({
            "nr": maaned_nr,
            "aar": aar,
            "navn": DANSKE_MAANEDER[maaned_nr],
            "dage": dage,
            "start_ugedag": foerste_dag.weekday(),
        })

    return maaneder


def tjek_overlap(check_in: datetime.date, check_out: datetime.date, db: Session,
                 undtag_booking_id: int = None) -> bool:
    """Returnerer True hvis der er overlap med eksisterende bookinger."""
    q = db.query(models.Booking).filter(
        models.Booking.status != models.BookingStatus.cancelled,
        models.Booking.check_in < check_out,
        models.Booking.check_out > check_in,
    )
    if undtag_booking_id:
        q = q.filter(models.Booking.id != undtag_booking_id)
    return q.count() > 0
