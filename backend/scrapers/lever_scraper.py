import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
import logging
import re

from .base_scraper import BaseScraper, JobListing

logger = logging.getLogger(__name__)

# Companies known to use Lever for FDE roles
LEVER_COMPANIES = {
    "salesforce": "salesforce",
    "postman": "postman",
    "gigaml": "gigaml",
    "further-ai": "furtherai",
    "simple-ai": "simpleai",
    "bland-ai": "bland",
    "first-resonance": "firstresonance",
    "civilgrid": "civilgrid",
    "orb": "withorb",
    "krew": "krew",
    "variance": "variance",
    "serval": "serval",
}


class LeverScraper(BaseScraper):
    """Scraper for Lever job boards."""

    def __init__(self):
        super().__init__()
        self.name = "lever"
        self.base_url = "https://jobs.lever.co"
        self.api_url = "https://api.lever.co/v0/postings"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        }

    def search_jobs(
        self,
        query: str = "forward deployed engineer",
        location: str = "San Francisco Bay Area",
        days_ago: int = 30,
        max_results: int = 100,
    ) -> List[JobListing]:
        """Search Lever boards for FDE jobs."""
        jobs = []

        for company_name, board_slug in LEVER_COMPANIES.items():
            try:
                company_jobs = self._search_company_board(
                    company_name, board_slug, query, location
                )
                jobs.extend(company_jobs)

                if len(jobs) >= max_results:
                    break

            except Exception as e:
                logger.error(f"Error searching {company_name} Lever board: {e}")
                continue

        logger.info(f"Found {len(jobs)} jobs on Lever boards")
        return jobs[:max_results]

    def _search_company_board(
        self,
        company_name: str,
        board_slug: str,
        query: str,
        location: str,
    ) -> List[JobListing]:
        """Search a specific company's Lever board."""
        jobs = []

        # Use Lever API
        api_url = f"{self.api_url}/{board_slug}"

        try:
            self._rate_limit()
            response = requests.get(api_url, headers=self.headers, timeout=30)

            if response.status_code != 200:
                logger.warning(f"Lever API returned {response.status_code} for {board_slug}")
                return jobs

            job_list = response.json()

            for job_data in job_list:
                try:
                    job = self._parse_job_data(job_data, company_name)
                    if job and self._matches_search(job, query, location):
                        jobs.append(job)
                except Exception as e:
                    logger.error(f"Error parsing Lever job: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error fetching Lever jobs for {board_slug}: {e}")

        return jobs

    def _parse_job_data(self, job_data: Dict, company_name: str) -> Optional[JobListing]:
        """Parse job data from Lever API."""
        try:
            title = job_data.get("text", "")

            # Get location from categories
            categories = job_data.get("categories", {})
            location = categories.get("location", "")
            if isinstance(location, list):
                location = ", ".join(location)

            # Get URLs
            job_url = job_data.get("hostedUrl", "")
            apply_url = job_data.get("applyUrl", job_url)

            # Get creation date
            created_at = job_data.get("createdAt")
            date_posted = None
            if created_at:
                try:
                    # Lever uses milliseconds timestamp
                    date_posted = datetime.fromtimestamp(created_at / 1000)
                except:
                    pass

            # Get employment type from categories
            commitment = categories.get("commitment", "")

            return JobListing(
                title=title,
                company=company_name.replace("-", " ").title(),
                location=self._normalize_location(location),
                job_url=job_url,
                apply_url=apply_url,
                source=self.name,
                date_posted=date_posted,
                employment_type=commitment if commitment else None,
            )

        except Exception as e:
            logger.error(f"Error parsing Lever job data: {e}")
            return None

    def _matches_search(self, job: JobListing, query: str, location: str) -> bool:
        """Check if job matches search criteria."""
        query_lower = query.lower()
        query_terms = query_lower.split()

        # Check title matches any query term
        title_lower = job.title.lower()
        title_match = any(term in title_lower for term in query_terms)

        # Also match FDE-related titles
        fde_match = self._is_fde_role(job.title)

        # Check location
        location_match = True
        if location:
            sf_terms = ["san francisco", "sf", "bay area", "palo alto", "mountain view", "remote"]
            job_loc_lower = job.location.lower()
            location_match = any(term in job_loc_lower for term in sf_terms)

        return (title_match or fde_match) and location_match

    def get_job_details(self, job_url: str) -> Optional[Dict]:
        """Get full job details from Lever job page."""
        try:
            self._rate_limit()
            response = requests.get(job_url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html",
            }, timeout=30)

            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            # Find job description sections
            content_sections = soup.find_all("div", class_=re.compile(r"section|content"))

            raw_description = ""
            for section in content_sections:
                # Skip navigation and header sections
                if section.find("nav") or section.find("header"):
                    continue
                text = section.get_text(separator="\n", strip=True)
                if len(text) > 100:  # Only include substantial sections
                    raw_description += text + "\n\n"

            if not raw_description:
                # Fallback: get main content
                main_content = soup.find("div", class_=re.compile(r"posting|job-description"))
                if main_content:
                    raw_description = main_content.get_text(separator="\n", strip=True)

            return {
                "raw_description": raw_description.strip(),
                "employment_type": None,
            }

        except Exception as e:
            logger.error(f"Error getting Lever job details: {e}")
            return None
