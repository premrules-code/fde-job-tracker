from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean, Float, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Basic info
    title = Column(String(500), nullable=False)
    company = Column(String(255), nullable=False)
    location = Column(String(255))
    job_url = Column(String(1000), unique=True, nullable=False)
    apply_url = Column(String(1000))

    # Source info
    source = Column(String(50))  # linkedin, indeed, greenhouse, lever, ashby
    date_posted = Column(DateTime)
    date_scraped = Column(DateTime, default=datetime.utcnow)

    # Job description sections
    raw_description = Column(Text)
    responsibilities = Column(Text)
    qualifications = Column(Text)
    nice_to_have = Column(Text)
    about_role = Column(Text)
    about_company = Column(Text)

    # Extracted skills/keywords
    required_skills = Column(JSON)  # List of required skills
    bonus_skills = Column(JSON)  # List of nice-to-have skills
    technologies = Column(JSON)  # Specific tech stack mentioned
    ai_ml_keywords = Column(JSON)  # AI/ML specific terms

    # Metadata
    salary_range = Column(String(255))
    experience_level = Column(String(100))
    employment_type = Column(String(50))  # full-time, contract, etc.
    remote_status = Column(String(50))  # remote, hybrid, onsite

    # Scoring
    relevance_score = Column(Float)  # How relevant to FDE role
    is_active = Column(Boolean, default=True)


class SkillFrequency(Base):
    __tablename__ = "skill_frequencies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    skill = Column(String(255), unique=True, nullable=False)
    category = Column(String(100))  # programming, ai_ml, cloud, soft_skills, etc.
    frequency = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)


class ScraperLog(Base):
    __tablename__ = "scraper_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50))
    jobs_found = Column(Integer)
    jobs_added = Column(Integer)
    errors = Column(Text)
    run_time = Column(DateTime, default=datetime.utcnow)


# Database setup - Neon PostgreSQL
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Test connections before using them
    pool_recycle=300,    # Recycle connections every 5 minutes
    pool_size=5,
    max_overflow=10,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
