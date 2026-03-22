import json
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Date, ForeignKey, Index
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, default="")
    website = Column(String(500), default="")
    linkedin_url = Column(String(500), default="")
    logo_url = Column(String(500), default="")

    # Location
    hq_city = Column(String(100), default="")
    hq_country = Column(String(100), default="", index=True)

    # Classification
    founded_year = Column(Integer)
    category = Column(String(100), default="", index=True)
    sub_category = Column(String(100), default="")
    stage = Column(String(50), default="", index=True)  # Seed, A, B, C, D, Growth

    # Funding summary
    total_raised_usd = Column(Float, default=0)
    last_round_date = Column(Date)
    last_round_size_usd = Column(Float)
    last_round_type = Column(String(50), default="")

    # Employee data
    employee_count = Column(Integer)
    employee_count_updated = Column(DateTime)
    employee_growth_6m = Column(Float)  # % growth over 6 months

    # Revenue / metrics
    revenue_estimate_usd = Column(Float)
    revenue_source = Column(String(100), default="")
    key_metrics_json = Column(Text, default="{}")  # JSON: {customers, AUM, TPV, etc.}

    # Scoring
    quality_score = Column(Float, default=0)  # 0-100
    growth_signal = Column(Float, default=0)  # 0-100

    # Next raise prediction
    next_raise_estimate = Column(String(50), default="")  # e.g., "Q3 2026"
    next_raise_confidence = Column(String(20), default="")  # Low, Medium, High

    # External IDs
    crunchbase_url = Column(String(500), default="")
    companies_house_id = Column(String(50), default="")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_scraped_at = Column(DateTime)

    # Relationships
    funding_rounds = relationship("FundingRound", back_populates="company", cascade="all, delete-orphan",
                                  order_by="FundingRound.announced_date.desc()")
    news_articles = relationship("NewsArticle", back_populates="company", cascade="all, delete-orphan",
                                 order_by="NewsArticle.published_date.desc()")
    employee_snapshots = relationship("EmployeeSnapshot", back_populates="company", cascade="all, delete-orphan",
                                      order_by="EmployeeSnapshot.snapshot_date.desc()")

    @property
    def key_metrics(self):
        try:
            return json.loads(self.key_metrics_json) if self.key_metrics_json else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    @key_metrics.setter
    def key_metrics(self, value):
        self.key_metrics_json = json.dumps(value)

    @property
    def total_raised_display(self):
        if not self.total_raised_usd:
            return "Undisclosed"
        if self.total_raised_usd >= 1_000_000_000:
            return f"${self.total_raised_usd / 1_000_000_000:.1f}B"
        if self.total_raised_usd >= 1_000_000:
            return f"${self.total_raised_usd / 1_000_000:.0f}M"
        return f"${self.total_raised_usd / 1_000:.0f}K"

    @property
    def last_round_display(self):
        if not self.last_round_size_usd:
            return self.last_round_type or "Unknown"
        size = self.last_round_size_usd
        if size >= 1_000_000_000:
            amt = f"${size / 1_000_000_000:.1f}B"
        elif size >= 1_000_000:
            amt = f"${size / 1_000_000:.0f}M"
        else:
            amt = f"${size / 1_000:.0f}K"
        parts = []
        if self.last_round_type:
            parts.append(self.last_round_type)
        parts.append(amt)
        if self.last_round_date:
            parts.append(self.last_round_date.strftime("%b %Y"))
        return " · ".join(parts)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "website": self.website,
            "linkedin_url": self.linkedin_url,
            "logo_url": self.logo_url,
            "hq_city": self.hq_city,
            "hq_country": self.hq_country,
            "founded_year": self.founded_year,
            "category": self.category,
            "sub_category": self.sub_category,
            "stage": self.stage,
            "total_raised_usd": self.total_raised_usd,
            "total_raised_display": self.total_raised_display,
            "last_round_date": self.last_round_date.isoformat() if self.last_round_date else None,
            "last_round_size_usd": self.last_round_size_usd,
            "last_round_type": self.last_round_type,
            "last_round_display": self.last_round_display,
            "employee_count": self.employee_count,
            "employee_growth_6m": self.employee_growth_6m,
            "revenue_estimate_usd": self.revenue_estimate_usd,
            "quality_score": self.quality_score,
            "growth_signal": self.growth_signal,
            "next_raise_estimate": self.next_raise_estimate,
            "next_raise_confidence": self.next_raise_confidence,
            "crunchbase_url": self.crunchbase_url,
            "companies_house_id": self.companies_house_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    __table_args__ = (
        Index("ix_companies_quality", "quality_score"),
        Index("ix_companies_country_category", "hq_country", "category"),
    )


class FundingRound(Base):
    __tablename__ = "funding_rounds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    round_type = Column(String(50), default="")  # Seed, Series A, etc.
    announced_date = Column(Date)
    amount_usd = Column(Float)
    currency_original = Column(String(10), default="USD")
    amount_original = Column(Float)
    lead_investors_json = Column(Text, default="[]")
    all_investors_json = Column(Text, default="[]")
    source_url = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="funding_rounds")

    @property
    def lead_investors(self):
        try:
            return json.loads(self.lead_investors_json) if self.lead_investors_json else []
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def all_investors(self):
        try:
            return json.loads(self.all_investors_json) if self.all_investors_json else []
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def amount_display(self):
        if not self.amount_usd:
            return "Undisclosed"
        if self.amount_usd >= 1_000_000_000:
            return f"${self.amount_usd / 1_000_000_000:.1f}B"
        if self.amount_usd >= 1_000_000:
            return f"${self.amount_usd / 1_000_000:.1f}M"
        return f"${self.amount_usd / 1_000:.0f}K"

    def to_dict(self):
        return {
            "id": self.id,
            "round_type": self.round_type,
            "announced_date": self.announced_date.isoformat() if self.announced_date else None,
            "amount_usd": self.amount_usd,
            "amount_display": self.amount_display,
            "lead_investors": self.lead_investors,
            "all_investors": self.all_investors,
            "source_url": self.source_url,
        }


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    url = Column(String(1000), nullable=False)
    published_date = Column(Date)
    source_name = Column(String(200), default="")
    snippet = Column(Text, default="")
    sentiment = Column(String(20), default="neutral")  # positive, neutral, negative
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="news_articles")

    def to_dict(self):
        return {
            "id": self.id,
            "company_id": self.company_id,
            "title": self.title,
            "url": self.url,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "source_name": self.source_name,
            "snippet": self.snippet,
            "sentiment": self.sentiment,
        }


class EmployeeSnapshot(Base):
    __tablename__ = "employee_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    employee_count = Column(Integer, nullable=False)
    snapshot_date = Column(Date, nullable=False)
    source = Column(String(50), default="estimate")  # linkedin, companies_house, estimate
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="employee_snapshots")


class ScanLog(Base):
    __tablename__ = "scan_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_name = Column(String(100), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    companies_updated = Column(Integer, default=0)
    articles_added = Column(Integer, default=0)
    status = Column(String(20), default="running")  # running, completed, failed
    error_msg = Column(Text, default="")
