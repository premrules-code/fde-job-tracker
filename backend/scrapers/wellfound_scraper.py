import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
import urllib.parse
import logging
import re

from .base_scraper import BaseScraper, JobListing

logger = logging.getLogger(__name__)


class WellfoundScraper(BaseScraper):
    """Scraper for Wellfound (formerly AngelList) job listings."""

    def __init__(self):
        super().__init__()
        self.name = "wellfound"
        self.base_url = "https://wellfound.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    def search_jobs(
        self,
        query: str = "forward deployed engineer",
        location: str = "San Francisco Bay Area",
        days_ago: int = 30,
        max_results: int = 100,
    ) -> List[JobListing]:
        """Search Wellfound for FDE jobs."""
        jobs = []

        # Build search URL for engineering roles
        # Wellfound uses different URL structure
        search_queries = [
            "forward-deployed-engineer",
            "solutions-engineer",
            "field-engineer",
            "implementation-engineer",
        ]

        for search_term in search_queries:
            try:
                search_url = f"{self.base_url}/role/{search_term}"
                params = {
                    "locationSlug": "san-francisco-bay-area",
                }
                full_url = search_url + "?" + urllib.parse.urlencode(params)

                logger.info(f"Searching Wellfound: {full_url}")

                self._rate_limit()
                response = requests.get(full_url, headers=self.headers, timeout=30)

                if response.status_code != 200:
                    logger.warning(f"Wellfound returned status {response.status_code}")
                    continue

                soup = BeautifulSoup(response.text, "html.parser")

                # Find job cards
                job_cards = soup.find_all("div", class_=re.compile(r"styles_jobCard|job-card"))

                if not job_cards:
                    # Try alternate selector
                    job_cards = soup.find_all("a", class_=re.compile(r"styles_component.*JobListing"))

                for card in job_cards:
                    try:
                        job = self._parse_job_card(card)
                        if job:
                            jobs.append(job)
                    except Exception as e:
                        logger.error(f"Error parsing Wellfound job card: {e}")
                        continue

                if len(jobs) >= max_results:
                    break

            except Exception as e:
                logger.error(f"Error searching Wellfound for {search_term}: {e}")
                continue

        # Deduplicate by URL
        seen_urls = set()
        unique_jobs = []
        for job in jobs:
            if job.job_url not in seen_urls:
                seen_urls.add(job.job_url)
                unique_jobs.append(job)

        logger.info(f"Found {len(unique_jobs)} jobs on Wellfound")
        return unique_jobs[:max_results]

    def _parse_job_card(self, card) -> Optional[JobListing]:
        """Parse a job card from Wellfound search results."""
        try:
            # Find job link
            link_elem = card.find("a", href=True)
            if not link_elem:
                link_elem = card if card.name == "a" else None

            if not link_elem:
                return None

            href = link_elem.get("href", "")
            if not href.startswith("http"):
                job_url = self.base_url + href
            else:
                job_url = href

            # Find title
            title_elem = card.find("h2") or card.find("div", class_=re.compile(r"title|jobTitle"))
            if not title_elem:
                title_elem = card.find("span", class_=re.compile(r"styles_title"))

            title = title_elem.get_text(strip=True) if title_elem else "Unknown Title"

            # Find company
            company_elem = card.find("a", class_=re.compile(r"company|startup")) or card.find("span", class_=re.compile(r"company"))
            company = company_elem.get_text(strip=True) if company_elem else "Unknown Company"

            # Find location
            location_elem = card.find("span", class_=re.compile(r"location"))
            location = location_elem.get_text(strip=True) if location_elem else ""

            # Find salary
            salary_elem = card.find("span", class_=re.compile(r"salary|compensation"))
            salary = salary_elem.get_text(strip=True) if salary_elem else None

            return JobListing(
                title=title,
                company=company,
                location=self._normalize_location(location),
                job_url=job_url,
                apply_url=job_url,
                source=self.name,
                date_posted=None,  # Wellfound doesn't always show date
                salary_range=salary,
            )

        except Exception as e:
            logger.error(f"Error parsing Wellfound job card: {e}")
            return None

    def get_job_details(self, job_url: str) -> Optional[Dict]:
        """Get full job details from Wellfound job page."""
        try:
            self._rate_limit()
            response = requests.get(job_url, headers=self.headers, timeout=30)

            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            # Find job description
            description_elem = soup.find("div", class_=re.compile(r"description|job-description|content"))

            if description_elem:
                raw_description = description_elem.get_text(separator="\n", strip=True)
            else:
                # Try to find in main content
                main = soup.find("main") or soup.find("article")
                if main:
                    raw_description = main.get_text(separator="\n", strip=True)
                else:
                    raw_description = ""

            return {
                "raw_description": raw_description,
                "employment_type": None,
            }

        except Exception as e:
            logger.error(f"Error getting Wellfound job details: {e}")
            return None
