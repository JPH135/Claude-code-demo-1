import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///fintech_scanner.db")
    SQLALCHEMY_DATABASE_URI = DATABASE_URL

    # API Keys (all optional - app works without them)
    CRUNCHBASE_API_KEY = os.getenv("CRUNCHBASE_API_KEY", "")
    COMPANIES_HOUSE_API_KEY = os.getenv("COMPANIES_HOUSE_API_KEY", "")
    NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")

    # Scheduler
    SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
    SCHEDULER_HOUR = int(os.getenv("SCHEDULER_HOUR", "2"))

    # Scraper settings
    REQUEST_TIMEOUT = 15
    RATE_LIMIT_DELAY = 1.5  # seconds between requests
    LINKEDIN_CACHE_DAYS = 7
    NEWS_MAX_AGE_DAYS = 90

    # Scoring weights
    TIER1_INVESTORS = [
        "Sequoia Capital", "Andreessen Horowitz", "a16z", "Accel",
        "Index Ventures", "Balderton Capital", "Atomico", "General Catalyst",
        "Tiger Global", "Coatue", "SoftBank", "Insight Partners",
        "Lightspeed Venture Partners", "Ribbit Capital", "QED Investors",
        "Dragoneer", "Addition", "DST Global", "GIC", "Temasek",
        "Northzone", "Creandum", "Cherry Ventures", "HV Capital",
        "Molten Ventures", "Passion Capital", "LocalGlobe", "Seedcamp",
    ]

    # Fintech categories
    CATEGORIES = [
        "Payments", "Lending", "Insurtech", "Wealthtech", "Regtech",
        "Banking-as-a-Service", "Crypto & DeFi", "B2B Fintech",
        "Embedded Finance", "Open Banking", "Neobank", "Capital Markets",
        "Accounting & Finance", "Financial Infrastructure", "Personal Finance",
    ]

    COUNTRIES = [
        "United Kingdom", "Germany", "France", "Netherlands", "Sweden",
        "Spain", "Italy", "Ireland", "Switzerland", "Finland",
        "Denmark", "Norway", "Belgium", "Austria", "Portugal",
        "Poland", "Czech Republic", "Estonia", "Lithuania", "Latvia",
    ]
