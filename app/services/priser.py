import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from app import models
from app.services.saeson import get_saeson_for_dato


def beregn_pris(check_in: datetime.date, check_out: datetime.date, db: Session) -> dict:
    """
    Beregner totalprisen for et ophold.
    Returner dict med:
      - total: Decimal
      - nætter: int
      - linjer: liste af {saeson, nætter, ugepris, delbeløb}
      - fejl: str eller None (fx manglende pris for en sæson)
    """
    nætter = (check_out - check_in).days
    if nætter <= 0:
        return {"total": Decimal(0), "nætter": 0, "linjer": [], "fejl": "Ugyldige datoer"}

    # Hent alle priser én gang
    alle_priser = {p.season.value: p for p in db.query(models.SeasonPrice).all()}

    # Gennemgå alle nætter og gruppér efter sæson
    saeson_naetter: dict[str, int] = {}
    dato = check_in
    while dato < check_out:
        saeson = get_saeson_for_dato(dato, db)
        if saeson is None:
            saeson = "?"
        saeson_naetter[saeson] = saeson_naetter.get(saeson, 0) + 1
        dato += datetime.timedelta(days=1)

    # Byg prislinjer
    linjer = []
    total = Decimal(0)
    fejl = None

    for saeson, antal in sorted(saeson_naetter.items()):
        if saeson == "?":
            fejl = "Nogle datoer mangler sæsondefinition — prisen er ufuldstændig."
            linjer.append({
                "saeson": "?",
                "nætter": antal,
                "ugepris": None,
                "delbeløb": None,
            })
            continue

        pris = alle_priser.get(saeson)
        if pris is None:
            fejl = f"Sæson {saeson} mangler en ugepris — kontakt udlejer."
            linjer.append({
                "saeson": saeson,
                "nætter": antal,
                "ugepris": None,
                "delbeløb": None,
            })
            continue

        ugepris = Decimal(str(pris.price_per_week))
        natpris = ugepris / 7
        delbeløb = (natpris * antal).quantize(Decimal("0.01"))
        total += delbeløb

        linjer.append({
            "saeson": saeson,
            "nætter": antal,
            "ugepris": ugepris,
            "delbeløb": delbeløb,
        })

    return {
        "total": total,
        "nætter": nætter,
        "linjer": linjer,
        "fejl": fejl,
    }
