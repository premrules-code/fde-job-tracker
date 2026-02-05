from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
from pathlib import Path
import logging

from models import Job, SkillFrequency, ScraperLog, get_db, init_db, SessionLocal
from job_scraper import job_scraper
from jobspy_scraper import run_jobspy_scrape
from scrapers import rss_scraper
from skill_extractor import skill_extractor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FDE Job Tracker API",
    description="API for tracking Forward Deployed Engineer job postings",
    version="1.0.0",
)

# Serve static frontend files
STATIC_DIR = Path(__file__).parent / "static"
logger.info(f"Static directory path: {STATIC_DIR}, exists: {STATIC_DIR.exists()}")
if STATIC_DIR.exists():
    logger.info(f"Static directory contents: {list(STATIC_DIR.iterdir())}")
    if (STATIC_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")
        logger.info("Mounted /assets")

# CORS middleware for React frontend
import os
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:5174,http://localhost:5175,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:5175").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for API responses
class JobResponse(BaseModel):
    id: int
    title: str
    company: str
    location: Optional[str]
    job_url: str
    apply_url: Optional[str]
    source: Optional[str]
    date_posted: Optional[datetime]
    date_scraped: Optional[datetime]
    raw_description: Optional[str]
    responsibilities: Optional[str]
    qualifications: Optional[str]
    nice_to_have: Optional[str]
    about_role: Optional[str]
    about_company: Optional[str]
    required_skills: Optional[List[str]]
    bonus_skills: Optional[List[str]]
    technologies: Optional[List[str]]
    ai_ml_keywords: Optional[List[str]]
    salary_range: Optional[str]
    employment_type: Optional[str]
    remote_status: Optional[str]
    relevance_score: Optional[float]

    class Config:
        from_attributes = True


class SkillFrequencyResponse(BaseModel):
    skill: str
    category: str
    frequency: int

    class Config:
        from_attributes = True


class DailySummary(BaseModel):
    date: str
    total_jobs: int
    new_jobs: int
    jobs_by_source: dict
    jobs_by_company: dict
    top_skills: List[dict]


class HeatmapData(BaseModel):
    category: str
    skills: List[dict]


class ScrapeResponse(BaseModel):
    status: str
    message: str
    results: Optional[dict] = None


# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()
    logger.info("Database initialized")


# API Endpoints

@app.get("/")
async def root():
    """Serve frontend or API info."""
    if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
        return FileResponse(STATIC_DIR / "index.html")
    return {"message": "FDE Job Tracker API", "version": "1.0.0"}


@app.get("/api/jobs", response_model=List[JobResponse])
async def get_jobs(
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None, description="Search in title, company, or description"),
    source: Optional[str] = Query(None, description="Filter by source (indeed, linkedin, etc.)"),
    company: Optional[str] = Query(None, description="Filter by company name"),
    days: Optional[int] = Query(30, description="Jobs posted in last N days"),
    min_relevance: Optional[float] = Query(None, description="Minimum relevance score"),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    """Get all jobs with optional filters."""
    query = db.query(Job).filter(Job.is_active == True)

    # Apply filters
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Job.title.ilike(search_term)) |
            (Job.company.ilike(search_term)) |
            (Job.raw_description.ilike(search_term))
        )

    if source:
        query = query.filter(Job.source == source)

    if company:
        query = query.filter(Job.company.ilike(f"%{company}%"))

    if days:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        query = query.filter(Job.date_scraped >= cutoff_date)

    if min_relevance:
        query = query.filter(Job.relevance_score >= min_relevance)

    # Order by relevance and date
    query = query.order_by(desc(Job.date_posted), desc(Job.relevance_score))

    jobs = query.offset(offset).limit(limit).all()
    return jobs


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: Session = Depends(get_db)):
    """Get a specific job by ID."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/skills/frequencies", response_model=List[SkillFrequencyResponse])
async def get_skill_frequencies(
    db: Session = Depends(get_db),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, le=200),
):
    """Get skill frequencies for heatmap."""
    query = db.query(SkillFrequency)

    if category:
        query = query.filter(SkillFrequency.category == category)

    skills = query.order_by(desc(SkillFrequency.frequency)).limit(limit).all()
    return skills


@app.get("/api/skills/heatmap")
async def get_skills_heatmap(db: Session = Depends(get_db)) -> List[HeatmapData]:
    """Get skills organized by category for heatmap visualization."""
    categories = ["ai", "ml", "backend", "frontend", "cloud", "data", "fde", "industry"]

    result = []
    for category in categories:
        skills = (
            db.query(SkillFrequency)
            .filter(SkillFrequency.category == category)
            .order_by(desc(SkillFrequency.frequency))
            .limit(20)
            .all()
        )

        result.append(HeatmapData(
            category=category,
            skills=[{"skill": s.skill, "frequency": s.frequency} for s in skills]
        ))

    return result


@app.get("/api/summary/daily")
async def get_daily_summary(
    db: Session = Depends(get_db),
    days: int = Query(7, description="Number of days to summarize"),
) -> List[DailySummary]:
    """Get daily job posting summary."""
    summaries = []

    for i in range(days):
        date = datetime.utcnow().date() - timedelta(days=i)
        start = datetime.combine(date, datetime.min.time())
        end = datetime.combine(date, datetime.max.time())

        # Jobs scraped on this day
        day_jobs = (
            db.query(Job)
            .filter(Job.date_scraped >= start, Job.date_scraped <= end)
            .all()
        )

        # Jobs by source
        jobs_by_source = {}
        jobs_by_company = {}

        for job in day_jobs:
            source = job.source or "unknown"
            jobs_by_source[source] = jobs_by_source.get(source, 0) + 1

            company = job.company or "unknown"
            jobs_by_company[company] = jobs_by_company.get(company, 0) + 1

        # Top skills from these jobs
        all_skills = []
        for job in day_jobs:
            if job.ai_ml_keywords:
                all_skills.extend(job.ai_ml_keywords)
            if job.required_skills:
                all_skills.extend(job.required_skills)

        skill_counts = {}
        for skill in all_skills:
            skill_counts[skill] = skill_counts.get(skill, 0) + 1

        top_skills = sorted(
            [{"skill": k, "count": v} for k, v in skill_counts.items()],
            key=lambda x: x["count"],
            reverse=True
        )[:10]

        summaries.append(DailySummary(
            date=date.isoformat(),
            total_jobs=db.query(Job).filter(Job.date_scraped <= end).count(),
            new_jobs=len(day_jobs),
            jobs_by_source=jobs_by_source,
            jobs_by_company=jobs_by_company,
            top_skills=top_skills,
        ))

    return summaries


@app.get("/api/companies")
async def get_companies(db: Session = Depends(get_db)):
    """Get list of all companies with job counts."""
    companies = (
        db.query(Job.company, func.count(Job.id).label("count"))
        .filter(Job.is_active == True)
        .group_by(Job.company)
        .order_by(desc("count"))
        .all()
    )

    return [{"company": c[0], "count": c[1]} for c in companies]


@app.get("/api/sources")
async def get_sources(db: Session = Depends(get_db)):
    """Get list of all sources with job counts."""
    sources = (
        db.query(Job.source, func.count(Job.id).label("count"))
        .filter(Job.is_active == True)
        .group_by(Job.source)
        .order_by(desc("count"))
        .all()
    )

    return [{"source": s[0], "count": s[1]} for s in sources]


# Scrape progress tracking
scrape_progress = {
    "status": "idle",
    "step": "",
    "progress": 0,
    "total": 0,
    "jobs_found": 0,
    "jobs_added": 0,
    "current_job": "",
}

@app.get("/api/scrape/progress")
async def get_scrape_progress():
    """Get current scrape progress."""
    return scrape_progress

@app.post("/api/scrape", response_model=ScrapeResponse)
async def trigger_scrape(
    background_tasks: BackgroundTasks,
    days: int = Query(30, description="Scrape jobs from last N days"),
    location: str = Query("San Francisco Bay Area", description="Location to search"),
):
    """Trigger a scrape job using jobspy (Indeed + LinkedIn)."""
    global scrape_progress

    if scrape_progress["status"] == "running":
        return ScrapeResponse(
            status="running",
            message="Scrape already in progress",
            results=scrape_progress,
        )

    # Reset progress
    scrape_progress = {
        "status": "running",
        "step": "Starting scrape...",
        "progress": 0,
        "total": 0,
        "jobs_found": 0,
        "jobs_added": 0,
        "current_job": "",
    }

    # Run scrape in background
    background_tasks.add_task(run_scrape_with_progress, location, days)

    return ScrapeResponse(
        status="started",
        message="Scrape started in background. Poll /api/scrape/progress for updates.",
        results=scrape_progress,
    )

def run_scrape_with_progress(location: str, days: int):
    """Run scrape with progress updates."""
    global scrape_progress
    try:
        logger.info(f"Starting scrape for {location}, last {days} days...")
        scrape_progress["step"] = "Fetching jobs from LinkedIn & Indeed..."

        results = run_jobspy_scrape(location=location, days=days, progress_callback=update_progress)

        scrape_progress = {
            "status": "completed",
            "step": "Done!",
            "progress": 100,
            "total": 100,
            "jobs_found": results.get("jobs_found", 0),
            "jobs_added": results.get("jobs_added", 0),
            "current_job": "",
        }
        logger.info(f"Scrape completed: {results}")
    except Exception as e:
        logger.error(f"Scrape failed: {e}")
        scrape_progress = {
            "status": "failed",
            "step": f"Error: {str(e)}",
            "progress": 0,
            "total": 0,
            "jobs_found": 0,
            "jobs_added": 0,
            "current_job": "",
        }

def update_progress(step: str, progress: int, total: int, current_job: str = "", jobs_added: int = 0):
    """Callback to update scrape progress."""
    global scrape_progress
    scrape_progress["step"] = step
    scrape_progress["progress"] = progress
    scrape_progress["total"] = total
    scrape_progress["current_job"] = current_job
    scrape_progress["jobs_added"] = jobs_added


@app.get("/api/scrape/status")
async def get_scrape_status(db: Session = Depends(get_db)):
    """Get status of recent scrape jobs."""
    logs = (
        db.query(ScraperLog)
        .order_by(desc(ScraperLog.run_time))
        .limit(10)
        .all()
    )

    return [
        {
            "source": log.source,
            "jobs_found": log.jobs_found,
            "jobs_added": log.jobs_added,
            "errors": log.errors,
            "run_time": log.run_time.isoformat() if log.run_time else None,
        }
        for log in logs
    ]


@app.get("/api/search")
async def search_jobs(
    q: str = Query(..., description="Search query"),
    db: Session = Depends(get_db),
    limit: int = Query(50, le=200),
):
    """Full-text search across all job fields (for command palette)."""
    search_term = f"%{q}%"

    jobs = (
        db.query(Job)
        .filter(
            Job.is_active == True,
            (Job.title.ilike(search_term)) |
            (Job.company.ilike(search_term)) |
            (Job.raw_description.ilike(search_term)) |
            (Job.responsibilities.ilike(search_term)) |
            (Job.qualifications.ilike(search_term)) |
            (Job.nice_to_have.ilike(search_term))
        )
        .order_by(desc(Job.relevance_score))
        .limit(limit)
        .all()
    )

    return [JobResponse.model_validate(job) for job in jobs]


# RSS Feed Scraping Endpoints

class RSSFeedRequest(BaseModel):
    feed_url: str
    source_name: Optional[str] = "linkedin_rss"


@app.get("/api/rss/feeds")
async def get_rss_feeds():
    """Get list of configured RSS feeds."""
    return {
        "rss_app_feeds": rss_scraper.rss_app_feeds,
        "custom_feeds": rss_scraper.custom_feeds,
    }


@app.post("/api/rss/feeds")
async def add_rss_feed(feed: RSSFeedRequest):
    """Add a new RSS.app feed URL (e.g., from rss.app for LinkedIn jobs)."""
    rss_scraper.add_rss_app_feed(feed.feed_url, feed.source_name)
    return {
        "status": "success",
        "message": f"Added RSS feed: {feed.feed_url}",
        "total_feeds": len(rss_scraper.rss_app_feeds),
    }


@app.post("/api/rss/scrape")
async def trigger_rss_scrape(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    days: int = Query(30, description="Scrape jobs from last N days"),
    location: str = Query("San Francisco", description="Location to search"),
):
    """Trigger a scrape using RSS feeds (Indeed RSS + RSS.app feeds)."""
    global scrape_progress

    if scrape_progress["status"] == "running":
        return ScrapeResponse(
            status="running",
            message="Scrape already in progress",
            results=scrape_progress,
        )

    # Reset progress
    scrape_progress = {
        "status": "running",
        "step": "Starting RSS scrape...",
        "progress": 0,
        "total": 100,
        "jobs_found": 0,
        "jobs_added": 0,
        "current_job": "",
    }

    background_tasks.add_task(run_rss_scrape_with_progress, location, days)

    return ScrapeResponse(
        status="started",
        message="RSS scrape started in background. Poll /api/scrape/progress for updates.",
        results=scrape_progress,
    )


def run_rss_scrape_with_progress(location: str, days: int):
    """Run RSS scrape with progress updates."""
    global scrape_progress
    db = SessionLocal()

    try:
        logger.info(f"Starting RSS scrape for {location}, last {days} days...")
        scrape_progress["step"] = "Fetching jobs from RSS feeds..."

        # Get jobs from RSS scraper
        jobs = rss_scraper.search_jobs(
            query="forward deployed engineer",
            location=location,
            days_ago=days,
            max_results=50,
        )

        scrape_progress["jobs_found"] = len(jobs)
        scrape_progress["progress"] = 30

        jobs_added = 0
        total_jobs = len(jobs)

        for idx, job_listing in enumerate(jobs):
            try:
                # Check if job already exists
                existing = db.query(Job).filter(Job.job_url == job_listing.job_url).first()
                if existing:
                    continue

                # Extract skills from description
                skills = {}
                if job_listing.raw_description:
                    skills = skill_extractor.extract_skills(job_listing.raw_description)

                # Create job record
                job = Job(
                    title=job_listing.title,
                    company=job_listing.company,
                    location=job_listing.location,
                    job_url=job_listing.job_url,
                    apply_url=job_listing.apply_url,
                    source=job_listing.source,
                    date_posted=job_listing.date_posted,
                    date_scraped=datetime.utcnow(),
                    raw_description=job_listing.raw_description,
                    required_skills=skills.get("backend", []) + skills.get("frontend", []),
                    technologies=skills.get("cloud", []),
                    ai_ml_keywords=skills.get("ai", []) + skills.get("ml", []),
                    relevance_score=0.9 if "forward deploy" in job_listing.title.lower() else 0.7,
                    is_active=True,
                )

                db.add(job)
                jobs_added += 1

                # Update progress
                progress_pct = 30 + int((idx + 1) / total_jobs * 60) if total_jobs > 0 else 90
                scrape_progress["step"] = f"Processing jobs ({idx + 1}/{total_jobs})..."
                scrape_progress["progress"] = progress_pct
                scrape_progress["current_job"] = f"{job_listing.title[:30]} @ {job_listing.company}"
                scrape_progress["jobs_added"] = jobs_added

            except Exception as e:
                logger.error(f"Error processing RSS job: {e}")
                continue

        db.commit()

        scrape_progress = {
            "status": "completed",
            "step": "Done!",
            "progress": 100,
            "total": 100,
            "jobs_found": len(jobs),
            "jobs_added": jobs_added,
            "current_job": "",
        }
        logger.info(f"RSS scrape completed: {jobs_added} jobs added")

    except Exception as e:
        logger.error(f"RSS scrape failed: {e}")
        scrape_progress = {
            "status": "failed",
            "step": f"Error: {str(e)}",
            "progress": 0,
            "total": 0,
            "jobs_found": 0,
            "jobs_added": 0,
            "current_job": "",
        }
    finally:
        db.close()


# Serve frontend for all non-API routes
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """Serve React frontend for all non-API routes."""
    if STATIC_DIR.exists():
        # Try to serve the requested file
        file_path = STATIC_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        # Fallback to index.html for SPA routing
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
    return {"message": "FDE Job Tracker API", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
