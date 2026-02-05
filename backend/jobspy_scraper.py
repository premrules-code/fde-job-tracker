import os
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict
import pandas as pd
from dotenv import load_dotenv

from jobspy import scrape_jobs
from models import Job, SkillFrequency, ScraperLog, SessionLocal

# Load environment
load_dotenv(Path(__file__).parent / ".env")

logger = logging.getLogger(__name__)

# Try to import LLM extractor
try:
    from llm_skill_extractor import LLMSkillExtractor
    extractor = LLMSkillExtractor()
except:
    extractor = None

from skill_extractor import skill_extractor, section_parser


def run_jobspy_scrape(location: str = "San Francisco Bay Area", days: int = 30) -> Dict:
    """Run a scrape using jobspy library."""

    db = SessionLocal()
    results = {
        "status": "running",
        "jobs_found": 0,
        "jobs_added": 0,
        "jobs_skipped": 0,
        "errors": [],
        "sources": {}
    }

    try:
        logger.info(f"Starting jobspy scrape for '{location}'...")

        # Scrape from multiple sources
        jobs_df = scrape_jobs(
            site_name=["indeed", "linkedin"],
            search_term="forward deployed engineer",
            location=location,
            results_wanted=50,
            hours_old=days * 24,
            country_indeed='USA'
        )

        results["jobs_found"] = len(jobs_df)
        logger.info(f"Found {len(jobs_df)} total jobs")

        # Filter for FDE roles only
        fde_keywords = ['forward deploy', 'fde', 'forward-deploy']
        fde_jobs = jobs_df[jobs_df['title'].str.lower().str.contains('|'.join(fde_keywords), na=False)]

        logger.info(f"Filtered to {len(fde_jobs)} FDE jobs")

        # Process each job
        for _, row in fde_jobs.iterrows():
            try:
                job_url = str(row.get('job_url', ''))
                if not job_url or job_url == 'nan':
                    continue

                # Check for existing
                existing = db.query(Job).filter(Job.job_url == job_url).first()
                if existing:
                    results["jobs_skipped"] += 1
                    continue

                # Extract data
                title = str(row.get('title', ''))
                company = str(row.get('company', 'Unknown'))
                job_location = str(row.get('location', ''))
                source = str(row.get('site', 'unknown'))

                # Handle description
                description = row.get('description', '')
                if pd.isna(description):
                    description = ''
                else:
                    description = str(description)

                # Extract skills
                skills = {}
                sections = {}
                if description and len(description) > 50:
                    if extractor and extractor.is_available():
                        try:
                            skills = extractor.extract_skills(description)
                        except:
                            skills = skill_extractor.extract_skills(description)
                    else:
                        skills = skill_extractor.extract_skills(description)

                    try:
                        sections = section_parser.parse_sections(description)
                    except:
                        pass

                # Handle salary
                salary = None
                if pd.notna(row.get('min_amount')) and pd.notna(row.get('max_amount')):
                    salary = f"${int(row.get('min_amount')):,}-${int(row.get('max_amount')):,}"

                # Handle date
                date_posted = row.get('date_posted')
                if pd.isna(date_posted):
                    date_posted = datetime.now(timezone.utc)

                # Create job
                job = Job(
                    title=title,
                    company=company,
                    location=job_location,
                    job_url=job_url,
                    apply_url=job_url,
                    source=source,
                    date_posted=date_posted,
                    date_scraped=datetime.now(timezone.utc),
                    raw_description=description,
                    responsibilities=sections.get("responsibilities"),
                    qualifications=sections.get("qualifications"),
                    nice_to_have=sections.get("nice_to_have"),
                    required_skills=skills.get("backend", []) + skills.get("frontend", []),
                    technologies=skills.get("cloud", []),
                    ai_ml_keywords=skills.get("ai", []) + skills.get("ml", []),
                    salary_range=salary,
                    relevance_score=0.9,
                    is_active=True,
                )

                db.add(job)
                results["jobs_added"] += 1

                # Track by source
                if source not in results["sources"]:
                    results["sources"][source] = 0
                results["sources"][source] += 1

                logger.info(f"Added: {title[:40]} @ {company}")

            except Exception as e:
                logger.error(f"Error processing job: {e}")
                results["errors"].append(str(e))

        db.commit()

        # Log scrape results
        for source, count in results["sources"].items():
            log = ScraperLog(
                source=source,
                jobs_found=results["jobs_found"],
                jobs_added=count,
                errors=None,
                run_time=datetime.now(timezone.utc),
            )
            db.add(log)
        db.commit()

        results["status"] = "completed"
        logger.info(f"Scrape completed: {results['jobs_added']} jobs added")

    except Exception as e:
        logger.error(f"Scrape failed: {e}")
        results["status"] = "failed"
        results["errors"].append(str(e))

    finally:
        db.close()

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = run_jobspy_scrape()
    print(f"\nResults: {results}")
