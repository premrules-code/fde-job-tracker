"""
Y Combinator Jobs Scraper

Scrapes job listings from Y Combinator's job board.
https://www.ycombinator.com/jobs

No API key required - public job board.
"""

import logging
import re
from typing import List, Dict, Optional
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, JobListing

logger = logging.getLogger(__name__)


class YCombinatorScraper(BaseScraper):
    """Scraper for Y Combinator job board."""

    def __init__(self):
        super().__init__()
        self.name = "ycombinator"
        self.base_url = "https://www.ycombinator.com"
        self.jobs_url = "https://www.ycombinator.com/jobs"
        self.rate_limit_delay = (1, 2)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    def search_jobs(
        self,
        query: str = "forward deployed engineer",
        location: str = "San Francisco Bay Area",
        days_ago: int = 30,
        max_results: int = 50,
    ) -> List[JobListing]:
        """Search Y Combinator jobs for FDE roles."""
        jobs: List[JobListing] = []

        try:
            # YC Jobs has a search/filter URL
            search_url = f"{self.jobs_url}/role/software-engineer"

            logger.info(f"Fetching Y Combinator jobs from: {search_url}")
            self._rate_limit()

            with httpx.Client(timeout=30, follow_redirects=True) as client:
                response = client.get(search_url, headers=self.headers)

                if response.status_code != 200:
                    logger.warning(f"YC Jobs returned status {response.status_code}")
                    return jobs

                soup = BeautifulSoup(response.text, "html.parser")

                # Find job listings - YC uses different selectors
                # Try multiple selector patterns
                job_cards = soup.find_all("a", class_=re.compile(r"JobCard|job-card|listing"))

                if not job_cards:
                    # Try finding job links in a list
                    job_cards = soup.find_all("div", class_=re.compile(r"job|listing|JobListing"))

                if not job_cards:
                    # Try finding all links that look like job postings
                    all_links = soup.find_all("a", href=re.compile(r"/companies/.*/jobs/"))
                    job_cards = all_links

                logger.info(f"Found {len(job_cards)} potential job cards on YC")

                for card in job_cards:
                    try:
                        job = self._parse_job_card(card, soup)
                        if job and self._is_fde_role(job.title):
                            jobs.append(job)
                    except Exception as e:
                        logger.error(f"Error parsing YC job card: {e}")
                        continue

                    if len(jobs) >= max_results:
                        break

            # Also try the API endpoint if available
            api_jobs = self._fetch_from_api(query, max_results - len(jobs))
            jobs.extend(api_jobs)

        except Exception as e:
            logger.error(f"Error fetching Y Combinator jobs: {e}")

        # Filter for FDE roles
        fde_jobs = [job for job in jobs if self._is_fde_role(job.title)]
        logger.info(f"Found {len(fde_jobs)} FDE jobs from Y Combinator")

        return fde_jobs[:max_results]

    def _fetch_from_api(self, query: str, max_results: int) -> List[JobListing]:
        """Try to fetch jobs from YC's API/JSON endpoint."""
        jobs: List[JobListing] = []

        try:
            # YC sometimes has a JSON endpoint
            api_url = "https://www.ycombinator.com/jobs/api"

            with httpx.Client(timeout=30) as client:
                response = client.get(
                    api_url,
                    headers={**self.headers, "Accept": "application/json"},
                )

                if response.status_code == 200:
                    try:
                        data = response.json()
                        job_list = data if isinstance(data, list) else data.get("jobs", [])

                        for job_data in job_list[:max_results]:
                            job = self._parse_api_job(job_data)
                            if job:
                                jobs.append(job)
                    except:
                        pass

        except Exception as e:
            logger.debug(f"YC API not available: {e}")

        return jobs

    def _parse_job_card(self, card, soup) -> Optional[JobListing]:
        """Parse a job card from YC jobs page."""
        try:
            # Get job URL
            if card.name == "a":
                href = card.get("href", "")
            else:
                link = card.find("a", href=True)
                href = link.get("href", "") if link else ""

            if not href:
                return None

            if not href.startswith("http"):
                job_url = self.base_url + href
            else:
                job_url = href

            # Get title
            title_elem = card.find("h2") or card.find("h3") or card.find(class_=re.compile(r"title|job-title"))
            if not title_elem:
                # Try to get text from the card itself
                title_elem = card.find("span") or card

            title = title_elem.get_text(strip=True) if title_elem else ""

            if not title:
                return None

            # Get company name
            company_elem = card.find(class_=re.compile(r"company|startup"))
            if not company_elem:
                # Try to extract from URL pattern /companies/[company]/jobs/
                match = re.search(r"/companies/([^/]+)/", href)
                company = match.group(1).replace("-", " ").title() if match else "YC Company"
            else:
                company = company_elem.get_text(strip=True)

            # Get location
            location_elem = card.find(class_=re.compile(r"location"))
            location = location_elem.get_text(strip=True) if location_elem else ""

            return JobListing(
                title=title,
                company=company,
                location=self._normalize_location(location),
                job_url=job_url,
                apply_url=job_url,
                source="ycombinator",
                date_posted=None,
            )

        except Exception as e:
            logger.error(f"Error parsing YC job card: {e}")
            return None

    def _parse_api_job(self, job_data: Dict) -> Optional[JobListing]:
        """Parse job data from YC API response."""
        try:
            title = job_data.get("title") or job_data.get("job_title", "")
            if not title:
                return None

            company = job_data.get("company") or job_data.get("company_name", "YC Company")
            if isinstance(company, dict):
                company = company.get("name", "YC Company")

            location = job_data.get("location") or job_data.get("locations", "")
            if isinstance(location, list):
                location = ", ".join(location)

            job_url = job_data.get("url") or job_data.get("job_url", "")
            if not job_url:
                slug = job_data.get("slug") or job_data.get("id", "")
                company_slug = job_data.get("company_slug", "")
                if slug and company_slug:
                    job_url = f"{self.base_url}/companies/{company_slug}/jobs/{slug}"

            if not job_url:
                return None

            return JobListing(
                title=title,
                company=company,
                location=self._normalize_location(location),
                job_url=job_url,
                apply_url=job_url,
                source="ycombinator",
                date_posted=None,
            )

        except Exception as e:
            logger.error(f"Error parsing YC API job: {e}")
            return None

    def get_job_details(self, job_url: str) -> Optional[Dict]:
        """Get full job details from YC job page."""
        try:
            self._rate_limit()

            with httpx.Client(timeout=30, follow_redirects=True) as client:
                response = client.get(job_url, headers=self.headers)

                if response.status_code != 200:
                    return None

                soup = BeautifulSoup(response.text, "html.parser")

                # Find job description
                description_elem = (
                    soup.find("div", class_=re.compile(r"description|job-description")) or
                    soup.find("div", class_=re.compile(r"content|prose")) or
                    soup.find("article")
                )

                description = ""
                if description_elem:
                    description = description_elem.get_text(separator="\n", strip=True)

                return {
                    "raw_description": description,
                }

        except Exception as e:
            logger.error(f"Error getting YC job details: {e}")
            return None


# Singleton instance
ycombinator_scraper = YCombinatorScraper()
