import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app import models

# Farver pr. sæson — bruges i templates
SAESON_FARVER = {
    "A": {"bg": "bg-red-500",    "text": "text-white", "label": "Sæson A"},
    "B": {"bg": "bg-orange-400", "text": "text-white", "label": "Sæson B"},
    "C": {"bg": "bg-yellow-400", "text": "text-gray-800", "label": "Sæson C"},
    "D": {"bg": "bg-green-400",  "text": "text-gray-800", "label": "Sæson D"},
    "E": {"bg": "bg-blue-300",   "text": "text-gray-800", "label": "Sæson E"},
}


def get_saeson_for_dato(dato: datetime.date, db: Session) -> Optional[str]:
    """Returnerer sæsonbogstav (A-E) for en given dato, eller None."""
    intervaller = db.query(models.SeasonInterval).all()
    for interval in intervaller:
        if interval.date_from <= dato <= interval.date_to:
            return interval.season.value
    return None


def generer_aarsoverblik(aar: int, db: Session) -> list[dict]:
    """
    Genererer en liste af måneder med uger for et givet år.
    Hver dag får sin sæsonfarve (eller grå hvis ingen sæson).
    """
    intervaller = db.query(models.SeasonInterval).order_by(
        models.SeasonInterval.date_from
    ).all()

    def saeson_for(dato: datetime.date) -> Optional[str]:
        for iv in intervaller:
            if iv.date_from <= dato <= iv.date_to:
                return iv.season.value
        return None

    maaneder = []
    for maaned_nr in range(1, 13):
        # Find alle dage i måneden
        foerste_dag = datetime.date(aar, maaned_nr, 1)
        if maaned_nr == 12:
            sidst_dag = datetime.date(aar, 12, 31)
        else:
            sidst_dag = datetime.date(aar, maaned_nr + 1, 1) - datetime.timedelta(days=1)

        dage = []
        dag = foerste_dag
        while dag <= sidst_dag:
            saeson = saeson_for(dag)
            farver = SAESON_FARVER.get(saeson, {"bg": "bg-gray-100", "text": "text-gray-400", "label": ""})
            dage.append({
                "dato": dag,
                "dag_nr": dag.day,
                "ugedag": dag.weekday(),  # 0=man, 6=søn
                "uge_nr": dag.isocalendar()[1],
                "saeson": saeson,
                "bg": farver["bg"],
                "text": farver["text"],
            })
            dag += datetime.timedelta(days=1)

        # Byg uge-struktur: liste af uger, hver med uge_nr + 7 slots (None = tom)
        uger = []
        for dag_dict in dage:
            if dag_dict["ugedag"] == 0 or not uger:
                uger.append({"uge_nr": dag_dict["uge_nr"], "dage": [None] * dag_dict["ugedag"] + [dag_dict]})
            else:
                uger[-1]["dage"].append(dag_dict)
        if uger and len(uger[-1]["dage"]) < 7:
            uger[-1]["dage"] += [None] * (7 - len(uger[-1]["dage"]))

        maaneder.append({
            "nr": maaned_nr,
            "navn": foerste_dag.strftime("%B").capitalize(),
            "uger": uger,
        })

    return maaneder
