import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import urllib.parse
import logging
import re

from .base_scraper import BaseScraper, JobListing

logger = logging.getLogger(__name__)


class IndeedScraper(BaseScraper):
    """Scraper for Indeed job listings."""

    def __init__(self):
        super().__init__()
        self.name = "indeed"
        self.base_url = "https://www.indeed.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

    def search_jobs(
        self,
        query: str = "forward deployed engineer",
        location: str = "San Francisco Bay Area",
        days_ago: int = 30,
        max_results: int = 100,
    ) -> List[JobListing]:
        """Search Indeed for FDE jobs."""
        jobs = []

        # Build search URL
        params = {
            "q": query,
            "l": location,
            "fromage": days_ago,  # Jobs posted in last N days
            "sort": "date",
        }

        search_url = f"{self.base_url}/jobs?" + urllib.parse.urlencode(params)
        logger.info(f"Searching Indeed: {search_url}")

        try:
            page = 0
            while len(jobs) < max_results:
                paginated_url = search_url + f"&start={page * 10}"

                self._rate_limit()
                response = requests.get(paginated_url, headers=self.headers, timeout=30)

                if response.status_code != 200:
                    logger.warning(f"Indeed returned status {response.status_code}")
                    break

                soup = BeautifulSoup(response.text, "html.parser")

                # Find job cards
                job_cards = soup.find_all("div", class_=re.compile(r"job_seen_beacon|jobsearch-ResultsList"))

                if not job_cards:
                    # Try alternate selectors
                    job_cards = soup.find_all("a", class_=re.compile(r"jcs-JobTitle"))

                if not job_cards:
                    logger.info("No more job cards found")
                    break

                for card in job_cards:
                    try:
                        job = self._parse_job_card(card)
                        if job:
                            jobs.append(job)
                    except Exception as e:
                        logger.error(f"Error parsing job card: {e}")
                        continue

                page += 1
                if page > 10:  # Safety limit
                    break

        except Exception as e:
            logger.error(f"Error searching Indeed: {e}")

        logger.info(f"Found {len(jobs)} jobs on Indeed")
        return jobs

    def _parse_job_card(self, card) -> Optional[JobListing]:
        """Parse a job card from Indeed search results."""
        try:
            # Find title and link
            title_elem = card.find("a", class_=re.compile(r"jcs-JobTitle")) or card.find("h2", class_=re.compile(r"jobTitle"))
            if not title_elem:
                title_elem = card.find("a", {"data-jk": True})

            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)

            # Get job URL
            href = title_elem.get("href", "")
            if href.startswith("/"):
                job_url = self.base_url + href
            else:
                job_url = href

            # Extract job key for direct apply link
            job_key = title_elem.get("data-jk", "")
            if job_key:
                apply_url = f"{self.base_url}/viewjob?jk={job_key}"
            else:
                apply_url = job_url

            # Find company
            company_elem = card.find("span", class_=re.compile(r"companyName|company")) or card.find("span", {"data-testid": "company-name"})
            company = company_elem.get_text(strip=True) if company_elem else "Unknown"

            # Find location
            location_elem = card.find("div", class_=re.compile(r"companyLocation")) or card.find("span", {"data-testid": "text-location"})
            location = location_elem.get_text(strip=True) if location_elem else ""

            # Find date
            date_elem = card.find("span", class_=re.compile(r"date"))
            date_posted = None
            if date_elem:
                date_posted = self._parse_relative_date(date_elem.get_text(strip=True))

            # Find salary if available
            salary_elem = card.find("div", class_=re.compile(r"salary|compensation"))
            salary = salary_elem.get_text(strip=True) if salary_elem else None

            return JobListing(
                title=title,
                company=company,
                location=self._normalize_location(location),
                job_url=job_url,
                apply_url=apply_url,
                source=self.name,
                date_posted=date_posted,
                salary_range=salary,
            )

        except Exception as e:
            logger.error(f"Error parsing Indeed job card: {e}")
            return None

    def get_job_details(self, job_url: str) -> Optional[Dict]:
        """Get full job details from Indeed job page."""
        try:
            self._rate_limit()
            response = requests.get(job_url, headers=self.headers, timeout=30)

            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            # Find job description
            description_elem = soup.find("div", id="jobDescriptionText") or soup.find("div", class_=re.compile(r"jobsearch-jobDescriptionText"))

            if description_elem:
                raw_description = description_elem.get_text(separator="\n", strip=True)
            else:
                raw_description = ""

            # Try to find employment type
            employment_type = None
            job_type_elem = soup.find("div", class_=re.compile(r"jobsearch-JobMetadataHeader"))
            if job_type_elem:
                text = job_type_elem.get_text(strip=True).lower()
                if "full-time" in text:
                    employment_type = "full-time"
                elif "part-time" in text:
                    employment_type = "part-time"
                elif "contract" in text:
                    employment_type = "contract"

            return {
                "raw_description": raw_description,
                "employment_type": employment_type,
            }

        except Exception as e:
            logger.error(f"Error getting Indeed job details: {e}")
            return None
