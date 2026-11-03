from pathlib import Path
from uuid import NAMESPACE_DNS, uuid5

from sqlalchemy import create_engine, text

from packages.db.models import Base

engine = create_engine("postgresql+psycopg://postgres@/showcase?host=/var/run/postgresql")


def key(label):
    return uuid5(NAMESPACE_DNS, "synthetic.showcase.invalid/" + label)


SUBJECT = key("Reedglass Compute")
ANALYST = key("reviewer")
PERIOD = key("FY-2030")


def migrate():
    with engine.begin() as cx:
        cx.execute(text("SELECT pg_advisory_xact_lock(720103)"))
        if cx.scalar(text("SELECT to_regclass('public.frozen_input')")):
            return
        initialize(cx)


def initialize(cx):
    Base.metadata.create_all(cx, checkfirst=False)
    cx.exec_driver_sql(Path(__file__).with_name("migration.sql").read_text())
    cx.exec_driver_sql(
        "INSERT INTO entity_type(id,code,name) VALUES (1,'COMPANY','Company'),(2,'ANALYST','Analyst')"
    )
    cx.execute(
        text(
            "INSERT INTO entity(id,entity_type_id,canonical_name) VALUES (:s,1,'Reedglass Compute'),(:a,2,'Fixture reviewer')"
        ),
        {"s": SUBJECT, "a": ANALYST},
    )
    cx.execute(text("INSERT INTO company VALUES (:s)"), {"s": SUBJECT})
    cx.exec_driver_sql(
        "INSERT INTO financial_period_type(id,code,name) VALUES (1,'FY','Fiscal year')"
    )
    cx.execute(
        text(
            "INSERT INTO financial_period(id,company_entity_id,period_type_id,period_end) VALUES (:p,:s,1,'2030-12-31')"
        ),
        {"s": SUBJECT, "p": PERIOD},
    )
    cx.exec_driver_sql(
        "INSERT INTO financial_metric(id,code,name) VALUES (1,'CAPEX','Capital expenditure')"
    )


if __name__ == "__main__":
    migrate()
