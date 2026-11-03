from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as UUID_PK
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "company"
    entity_id: Mapped[UUID] = mapped_column(ForeignKey("entity.id"), primary_key=True)


class Document(Base):
    __tablename__ = "document"
    id: Mapped[UUID] = mapped_column(UUID_PK, primary_key=True)
    subject_id: Mapped[UUID] = mapped_column(ForeignKey("company.entity_id"))
    sha256: Mapped[str] = mapped_column(Text, unique=True)
    version: Mapped[int] = mapped_column(Integer)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("subject_id", "version"),
        CheckConstraint("published_at <= acquired_at"),
    )


class CodeNameMixin:
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class EntityType(CodeNameMixin, Base):
    __tablename__ = "entity_type"
    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    description: Mapped[str | None] = mapped_column(Text)


class Entity(Base):
    __tablename__ = "entity"
    id: Mapped[UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid4)
    entity_type_id: Mapped[int] = mapped_column(ForeignKey("entity_type.id"), nullable=False)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        Index("idx_entity_type", "entity_type_id"),
        Index("idx_entity_name", "canonical_name"),
    )


class UnitDimension(CodeNameMixin, Base):
    __tablename__ = "unit_dimension"
    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)


class FinancialPeriodType(CodeNameMixin, Base):
    __tablename__ = "financial_period_type"
    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)


class FinancialPeriod(Base):
    __tablename__ = "financial_period"
    id: Mapped[UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid4)
    company_entity_id: Mapped[UUID] = mapped_column(ForeignKey("company.entity_id"), nullable=False)
    period_type_id: Mapped[int] = mapped_column(
        ForeignKey("financial_period_type.id"), nullable=False
    )
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    fiscal_year: Mapped[int | None] = mapped_column(Integer)
    fiscal_quarter: Mapped[int | None] = mapped_column(Integer)
    __table_args__ = (
        UniqueConstraint(
            "company_entity_id",
            "period_type_id",
            "period_start",
            "period_end",
            name="uq_financial_period_identity",
        ),
        CheckConstraint(
            "period_start IS NULL OR period_end >= period_start", name="valid_interval"
        ),
        CheckConstraint(
            "fiscal_quarter IS NULL OR fiscal_quarter BETWEEN 1 AND 4", name="quarter_range"
        ),
    )


class FinancialMetric(CodeNameMixin, Base):
    __tablename__ = "financial_metric"
    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    unit_dimension_id: Mapped[int | None] = mapped_column(ForeignKey("unit_dimension.id"))
    is_duration: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")


class FinancialFact(Base):
    __tablename__ = "financial_fact"
    id: Mapped[UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid4)
    financial_period_id: Mapped[UUID] = mapped_column(
        ForeignKey("financial_period.id"), nullable=False
    )
    financial_metric_id: Mapped[int] = mapped_column(
        ForeignKey("financial_metric.id"), nullable=False
    )
    value: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    unit_code: Mapped[str] = mapped_column(Text, nullable=False)
    taxonomy_concept: Mapped[str] = mapped_column(Text, nullable=False)
    accession_number: Mapped[str | None] = mapped_column(Text)
    filing_form: Mapped[str | None] = mapped_column(Text)
    sec_frame: Mapped[str | None] = mapped_column(Text)
    source_document_id: Mapped[UUID] = mapped_column(ForeignKey("document.id"), nullable=False)
    filed_at: Mapped[date | None] = mapped_column(Date)
    known_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    known_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_derived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    __table_args__ = (
        UniqueConstraint(
            "source_document_id",
            "accession_number",
            "financial_metric_id",
            "financial_period_id",
            "taxonomy_concept",
            name="uq_financial_fact_source_metric_period",
        ),
        CheckConstraint("known_to IS NULL OR known_to >= known_from", name="knowledge_interval"),
        Index("idx_financial_fact_metric_period", "financial_metric_id", "financial_period_id"),
    )


class Scenario(Base):
    __tablename__ = "scenario"
    id: Mapped[UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid4)
    subject_entity_id: Mapped[UUID] = mapped_column(ForeignKey("entity.id"), nullable=False)
    analyst_entity_id: Mapped[UUID] = mapped_column(ForeignKey("entity.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    information_cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    __table_args__ = (
        Index("idx_scenario_subject_cutoff", "subject_entity_id", "information_cutoff_at"),
    )


class ScenarioShock(Base):
    __tablename__ = "scenario_shock"
    id: Mapped[UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid4)
    scenario_id: Mapped[UUID] = mapped_column(ForeignKey("scenario.id"), nullable=False)
    shock_type: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    __table_args__ = (
        CheckConstraint(
            "shock_type IN ('PROJECT_DELAY_MONTHS', 'FINANCING_SPREAD_BPS', "
            "'CAPEX_PERCENT', 'REVENUE_PERCENT', 'DELIVERED_MW_CHANGE')",
            name="valid_type",
        ),
        UniqueConstraint("scenario_id", "shock_type"),
    )


class ScenarioOutput(Base):
    __tablename__ = "scenario_output"
    id: Mapped[UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid4)
    scenario_id: Mapped[UUID] = mapped_column(ForeignKey("scenario.id"), nullable=False)
    metric_code: Mapped[str] = mapped_column(Text, nullable=False)
    baseline_value: Mapped[Decimal | None] = mapped_column(Numeric)
    shocked_value: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    unit_code: Mapped[str] = mapped_column(Text, nullable=False)
    formula: Mapped[str] = mapped_column(Text, nullable=False)
    source_kind: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[UUID | None] = mapped_column(UUID_PK)
    __table_args__ = (UniqueConstraint("scenario_id", "metric_code"),)
