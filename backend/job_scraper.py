import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from models import Job, SkillFrequency, ScraperLog, SessionLocal, init_db
from skill_extractor import skill_extractor, section_parser
from llm_skill_extractor import llm_skill_extractor
from scrapers import (
    IndeedScraper,
    LinkedInScraper,
    GreenhouseScraper,
    LeverScraper,
    WellfoundScraper,
    JobListing,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FDEJobScraper:
    """Main orchestrator for scraping FDE jobs from multiple sources."""

    # Search queries - focused on FDE roles only
    SEARCH_QUERIES = [
        "forward deployed engineer",
    ]

    def __init__(self):
        self.scrapers = [
            IndeedScraper(),
            LinkedInScraper(),
            GreenhouseScraper(),
            LeverScraper(),
            WellfoundScraper(),
        ]
        init_db()

    def run_daily_scrape(
        self,
        location: str = "San Francisco Bay Area",
        days_ago: int = 30,
        max_results_per_source: int = 50,
    ) -> Dict:
        """Run a full scrape across all sources."""
        logger.info(f"Starting daily scrape for FDE jobs in {location}")

        all_jobs: List[JobListing] = []
        scraper_results = {}

        # Run scrapers in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}

            for scraper in self.scrapers:
                for query in self.SEARCH_QUERIES[:2]:  # Limit queries per scraper
                    future = executor.submit(
                        self._run_scraper,
                        scraper,
                        query,
                        location,
                        days_ago,
                        max_results_per_source,
                    )
                    futures[future] = (scraper.name, query)

            for future in as_completed(futures):
                scraper_name, query = futures[future]
                try:
                    jobs = future.result()
                    all_jobs.extend(jobs)

                    if scraper_name not in scraper_results:
                        scraper_results[scraper_name] = {"found": 0, "errors": []}
                    scraper_results[scraper_name]["found"] += len(jobs)

                except Exception as e:
                    logger.error(f"Error in {scraper_name} for query '{query}': {e}")
                    if scraper_name not in scraper_results:
                        scraper_results[scraper_name] = {"found": 0, "errors": []}
                    scraper_results[scraper_name]["errors"].append(str(e))

        # Deduplicate jobs by URL
        unique_jobs = self._deduplicate_jobs(all_jobs)
        logger.info(f"Found {len(unique_jobs)} unique jobs from {len(all_jobs)} total")

        # Process and save jobs
        saved_count = self._process_and_save_jobs(unique_jobs)

        # Update skill frequencies
        self._update_skill_frequencies()

        # Log scraper run
        self._log_scraper_run(scraper_results, saved_count)

        return {
            "total_found": len(all_jobs),
            "unique_jobs": len(unique_jobs),
            "saved_jobs": saved_count,
            "scraper_results": scraper_results,
        }

    def _run_scraper(
        self,
        scraper,
        query: str,
        location: str,
        days_ago: int,
        max_results: int,
    ) -> List[JobListing]:
        """Run a single scraper with error handling."""
        try:
            jobs = scraper.search_jobs(
                query=query,
                location=location,
                days_ago=days_ago,
                max_results=max_results,
            )
            return jobs
        except Exception as e:
            logger.error(f"Scraper {scraper.name} failed: {e}")
            return []

    def _deduplicate_jobs(self, jobs: List[JobListing]) -> List[JobListing]:
        """Remove duplicate jobs based on URL."""
        seen_urls = set()
        unique = []

        for job in jobs:
            # Normalize URL for comparison
            url = job.job_url.lower().rstrip("/")
            if url not in seen_urls:
                seen_urls.add(url)
                unique.append(job)

        return unique

    def _process_and_save_jobs(self, jobs: List[JobListing]) -> int:
        """Process jobs (extract skills, sections) and save to database."""
        db = SessionLocal()
        saved_count = 0

        try:
            for i, job_listing in enumerate(jobs):
                try:
                    # Check if job already exists
                    existing = db.query(Job).filter(Job.job_url == job_listing.job_url).first()
                    if existing:
                        continue

                    # Fetch full job details (description)
                    logger.info(f"Fetching details for job {i+1}/{len(jobs)}: {job_listing.title}")
                    details = self._get_job_details(job_listing)

                    # Get description from details or listing
                    raw_desc = ""
                    if details and details.get("raw_description"):
                        raw_desc = details.get("raw_description", "")
                    elif hasattr(job_listing, 'description') and job_listing.description:
                        raw_desc = job_listing.description

                    # Extract skills and sections
                    # Use LLM extraction if available, otherwise fall back to regex
                    if raw_desc and llm_skill_extractor.is_available():
                        skills = llm_skill_extractor.extract_skills(raw_desc)
                        logger.info(f"Using LLM skill extraction")
                    else:
                        skills = skill_extractor.extract_skills(raw_desc) if raw_desc else {}
                    sections = section_parser.parse_sections(raw_desc) if raw_desc else {}

                    # Create job record
                    job = Job(
                        title=job_listing.title,
                        company=job_listing.company,
                        location=job_listing.location,
                        job_url=job_listing.job_url,
                        apply_url=job_listing.apply_url or (details.get("apply_url") if details else None),
                        source=job_listing.source,
                        date_posted=job_listing.date_posted,
                        date_scraped=datetime.utcnow(),
                        raw_description=raw_desc,
                        responsibilities=sections.get("responsibilities"),
                        qualifications=sections.get("qualifications"),
                        nice_to_have=sections.get("nice_to_have"),
                        about_role=sections.get("about_role"),
                        about_company=sections.get("about_company"),
                        required_skills=skills.get("programming", []) + skills.get("cloud_devops", []),
                        bonus_skills=skills.get("soft_skills", []),
                        technologies=skills.get("cloud_devops", []),
                        ai_ml_keywords=skills.get("ai_ml", []),
                        salary_range=job_listing.salary_range or (details.get("salary_range") if details else None),
                        employment_type=job_listing.employment_type or (details.get("employment_type") if details else None),
                        relevance_score=self._calculate_relevance(job_listing.title, skills),
                        is_active=True,
                    )

                    db.add(job)
                    saved_count += 1

                    # Commit in batches of 10
                    if saved_count % 10 == 0:
                        db.commit()
                        logger.info(f"Saved {saved_count} jobs so far...")

                except Exception as e:
                    logger.error(f"Error processing job {job_listing.job_url}: {e}")
                    continue

            db.commit()
            logger.info(f"Saved {saved_count} new jobs to database")

        except Exception as e:
            logger.error(f"Error saving jobs: {e}")
            db.rollback()
        finally:
            db.close()

        return saved_count

    def _get_job_details(self, job_listing: JobListing) -> Optional[Dict]:
        """Get full job details from the appropriate scraper."""
        for scraper in self.scrapers:
            if scraper.name == job_listing.source:
                return scraper.get_job_details(job_listing.job_url)
        return None

    def _calculate_relevance(self, title: str, skills: Dict) -> float:
        """Calculate a relevance score for FDE role."""
        score = 0.0

        # Title keywords
        title_lower = title.lower()
        if "forward deploy" in title_lower or "fde" in title_lower:
            score += 0.5
        elif "solutions engineer" in title_lower:
            score += 0.4
        elif "field engineer" in title_lower or "implementation" in title_lower:
            score += 0.3
        elif "customer engineer" in title_lower:
            score += 0.25

        # AI/ML skills boost
        ai_ml_count = len(skills.get("ai_ml", []))
        score += min(ai_ml_count * 0.05, 0.25)

        # Programming skills
        prog_count = len(skills.get("programming", []))
        score += min(prog_count * 0.02, 0.15)

        # Cloud/DevOps
        cloud_count = len(skills.get("cloud_devops", []))
        score += min(cloud_count * 0.02, 0.1)

        return min(score, 1.0)

    def _update_skill_frequencies(self):
        """Update skill frequency table based on all active jobs."""
        db = SessionLocal()

        try:
            # Get all active jobs
            jobs = db.query(Job).filter(Job.is_active == True).all()
            descriptions = [job.raw_description for job in jobs if job.raw_description]

            # Calculate frequencies
            frequencies = skill_extractor.get_skill_frequencies(descriptions)

            # Update database
            for category, skill_counts in frequencies.items():
                for skill, count in skill_counts.items():
                    existing = db.query(SkillFrequency).filter(SkillFrequency.skill == skill).first()

                    if existing:
                        existing.frequency = count
                        existing.category = category
                        existing.last_updated = datetime.utcnow()
                    else:
                        new_skill = SkillFrequency(
                            skill=skill,
                            category=category,
                            frequency=count,
                            last_updated=datetime.utcnow(),
                        )
                        db.add(new_skill)

            db.commit()
            logger.info("Updated skill frequencies")

        except Exception as e:
            logger.error(f"Error updating skill frequencies: {e}")
            db.rollback()
        finally:
            db.close()

    def _log_scraper_run(self, results: Dict, saved_count: int):
        """Log the scraper run results."""
        db = SessionLocal()

        try:
            for source, data in results.items():
                log = ScraperLog(
                    source=source,
                    jobs_found=data["found"],
                    jobs_added=saved_count // len(results),  # Approximate
                    errors="\n".join(data["errors"]) if data["errors"] else None,
                    run_time=datetime.utcnow(),
                )
                db.add(log)

            db.commit()

        except Exception as e:
            logger.error(f"Error logging scraper run: {e}")
            db.rollback()
        finally:
            db.close()


# Singleton instance
job_scraper = FDEJobScraper()


if __name__ == "__main__":
    # Run a test scrape
    results = job_scraper.run_daily_scrape(days_ago=7, max_results_per_source=10)
    print(f"Scrape results: {results}")
