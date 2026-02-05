import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
import logging
import re

from .base_scraper import BaseScraper, JobListing

logger = logging.getLogger(__name__)

# Companies known to use Greenhouse for FDE roles
GREENHOUSE_COMPANIES = {
    "anthropic": "anthropic",
    "openai": "openai",
    "scale": "scaleai",
    "palantir": "palantir",
    "databricks": "databricks",
    "anyscale": "anyscale",
    "vapi": "vapi",
    "reducto": "reducto",
    "dust": "dust-tt",
    "lancedb": "lancedb",
    "galileo": "galileo-ai",
}


class GreenhouseScraper(BaseScraper):
    """Scraper for Greenhouse job boards."""

    def __init__(self):
        super().__init__()
        self.name = "greenhouse"
        self.base_url = "https://boards.greenhouse.io"
        self.api_url = "https://boards-api.greenhouse.io/v1/boards"
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
        """Search Greenhouse boards for FDE jobs."""
        jobs = []

        for company_name, board_token in GREENHOUSE_COMPANIES.items():
            try:
                company_jobs = self._search_company_board(
                    company_name, board_token, query, location
                )
                jobs.extend(company_jobs)

                if len(jobs) >= max_results:
                    break

            except Exception as e:
                logger.error(f"Error searching {company_name} Greenhouse board: {e}")
                continue

        logger.info(f"Found {len(jobs)} jobs on Greenhouse boards")
        return jobs[:max_results]

    def _search_company_board(
        self,
        company_name: str,
        board_token: str,
        query: str,
        location: str,
    ) -> List[JobListing]:
        """Search a specific company's Greenhouse board."""
        jobs = []

        # Use Greenhouse API
        api_url = f"{self.api_url}/{board_token}/jobs"

        try:
            self._rate_limit()
            response = requests.get(api_url, headers=self.headers, timeout=30)

            if response.status_code != 200:
                logger.warning(f"Greenhouse API returned {response.status_code} for {board_token}")
                return jobs

            data = response.json()
            job_list = data.get("jobs", [])

            for job_data in job_list:
                try:
                    job = self._parse_job_data(job_data, company_name, board_token)
                    if job and self._matches_search(job, query, location):
                        jobs.append(job)
                except Exception as e:
                    logger.error(f"Error parsing Greenhouse job: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error fetching Greenhouse jobs for {board_token}: {e}")

        return jobs

    def _parse_job_data(
        self, job_data: Dict, company_name: str, board_token: str
    ) -> Optional[JobListing]:
        """Parse job data from Greenhouse API."""
        try:
            job_id = job_data.get("id")
            title = job_data.get("title", "")

            # Get location
            location_data = job_data.get("location", {})
            location = location_data.get("name", "") if isinstance(location_data, dict) else str(location_data)

            # Build URLs
            job_url = f"{self.base_url}/{board_token}/jobs/{job_id}"
            apply_url = f"{job_url}#app"

            # Get updated date (Greenhouse uses updated_at)
            updated_at = job_data.get("updated_at")
            date_posted = None
            if updated_at:
                try:
                    date_posted = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                except:
                    pass

            return JobListing(
                title=title,
                company=company_name.title(),
                location=self._normalize_location(location),
                job_url=job_url,
                apply_url=apply_url,
                source=self.name,
                date_posted=date_posted,
            )

        except Exception as e:
            logger.error(f"Error parsing Greenhouse job data: {e}")
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
            # Check if job location is in SF Bay Area
            sf_terms = ["san francisco", "sf", "bay area", "palo alto", "mountain view"]
            job_loc_lower = job.location.lower()
            location_match = any(term in job_loc_lower for term in sf_terms)

        return (title_match or fde_match) and location_match

    def get_job_details(self, job_url: str) -> Optional[Dict]:
        """Get full job details from Greenhouse job page."""
        try:
            # Extract board token and job ID from URL
            # Format: https://boards.greenhouse.io/{board_token}/jobs/{job_id}
            match = re.search(r'boards\.greenhouse\.io/([^/]+)/jobs/(\d+)', job_url)
            if not match:
                return self._scrape_job_page(job_url)

            board_token = match.group(1)
            job_id = match.group(2)

            # Use API to get job details
            api_url = f"{self.api_url}/{board_token}/jobs/{job_id}"

            self._rate_limit()
            response = requests.get(api_url, headers=self.headers, timeout=30)

            if response.status_code != 200:
                return self._scrape_job_page(job_url)

            data = response.json()

            # Get job content (HTML description)
            content = data.get("content", "")
            # Convert HTML to text
            if content:
                soup = BeautifulSoup(content, "html.parser")
                raw_description = soup.get_text(separator="\n", strip=True)
            else:
                raw_description = ""

            return {
                "raw_description": raw_description,
                "employment_type": None,
            }

        except Exception as e:
            logger.error(f"Error getting Greenhouse job details: {e}")
            return None

    def _scrape_job_page(self, job_url: str) -> Optional[Dict]:
        """Fallback: scrape job page directly."""
        try:
            self._rate_limit()
            response = requests.get(job_url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html",
            }, timeout=30)

            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            # Find job description
            content_elem = soup.find("div", id="content") or soup.find("div", class_=re.compile(r"content|job-description"))

            if content_elem:
                raw_description = content_elem.get_text(separator="\n", strip=True)
            else:
                raw_description = ""

            return {
                "raw_description": raw_description,
                "employment_type": None,
            }

        except Exception as e:
            logger.error(f"Error scraping Greenhouse job page: {e}")
            return None
