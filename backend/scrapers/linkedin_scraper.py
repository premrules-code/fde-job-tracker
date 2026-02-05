import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import urllib.parse
import logging
import re

from .base_scraper import BaseScraper, JobListing

logger = logging.getLogger(__name__)


class LinkedInScraper(BaseScraper):
    """Scraper for LinkedIn job listings (public/guest view)."""

    def __init__(self):
        super().__init__()
        self.name = "linkedin"
        self.base_url = "https://www.linkedin.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        # LinkedIn location geoId for SF Bay Area
        self.sf_geo_id = "90000084"  # San Francisco Bay Area

    def search_jobs(
        self,
        query: str = "forward deployed engineer",
        location: str = "San Francisco Bay Area",
        days_ago: int = 30,
        max_results: int = 100,
    ) -> List[JobListing]:
        """Search LinkedIn for FDE jobs using public API."""
        jobs = []

        # LinkedIn time filter mapping
        time_filter = "r2592000"  # Last 30 days (in seconds)
        if days_ago <= 1:
            time_filter = "r86400"
        elif days_ago <= 7:
            time_filter = "r604800"

        # Build search URL for public job search
        params = {
            "keywords": query,
            "location": location,
            "geoId": self.sf_geo_id,
            "f_TPR": time_filter,
            "position": 1,
            "pageNum": 0,
        }

        search_url = f"{self.base_url}/jobs/search?" + urllib.parse.urlencode(params)
        logger.info(f"Searching LinkedIn: {search_url}")

        try:
            page = 0
            while len(jobs) < max_results:
                # LinkedIn uses start parameter
                paginated_url = search_url + f"&start={page * 25}"

                self._rate_limit()
                response = requests.get(paginated_url, headers=self.headers, timeout=30)

                if response.status_code != 200:
                    logger.warning(f"LinkedIn returned status {response.status_code}")
                    break

                soup = BeautifulSoup(response.text, "html.parser")

                # Find job cards in public view
                job_cards = soup.find_all("div", class_=re.compile(r"base-card|job-search-card"))

                if not job_cards:
                    # Try alternate selector for guest view
                    job_cards = soup.find_all("li", class_=re.compile(r"jobs-search-results__list-item"))

                if not job_cards:
                    logger.info("No more job cards found")
                    break

                for card in job_cards:
                    try:
                        job = self._parse_job_card(card)
                        if job:
                            jobs.append(job)
                    except Exception as e:
                        logger.error(f"Error parsing LinkedIn job card: {e}")
                        continue

                page += 1
                if page > 4:  # Safety limit for LinkedIn
                    break

        except Exception as e:
            logger.error(f"Error searching LinkedIn: {e}")

        logger.info(f"Found {len(jobs)} jobs on LinkedIn")
        return jobs

    def _parse_job_card(self, card) -> Optional[JobListing]:
        """Parse a job card from LinkedIn search results."""
        try:
            # Find title and link
            title_elem = card.find("a", class_=re.compile(r"base-card__full-link|job-card-container__link"))
            if not title_elem:
                title_elem = card.find("a", class_=re.compile(r"job-search-card"))

            if not title_elem:
                return None

            title_span = card.find("span", class_=re.compile(r"base-search-card__title"))
            title = title_span.get_text(strip=True) if title_span else title_elem.get_text(strip=True)

            # Get job URL
            href = title_elem.get("href", "")
            if "?" in href:
                job_url = href.split("?")[0]  # Remove tracking params
            else:
                job_url = href

            # Find company
            company_elem = card.find("a", class_=re.compile(r"base-search-card__subtitle")) or card.find("h4", class_=re.compile(r"base-search-card__subtitle"))
            company = company_elem.get_text(strip=True) if company_elem else "Unknown"

            # Find location
            location_elem = card.find("span", class_=re.compile(r"job-search-card__location"))
            location = location_elem.get_text(strip=True) if location_elem else ""

            # Find date
            date_elem = card.find("time", class_=re.compile(r"job-search-card__listdate"))
            date_posted = None
            if date_elem:
                datetime_attr = date_elem.get("datetime")
                if datetime_attr:
                    try:
                        date_posted = datetime.fromisoformat(datetime_attr.replace("Z", "+00:00"))
                    except:
                        date_posted = self._parse_relative_date(date_elem.get_text(strip=True))
                else:
                    date_posted = self._parse_relative_date(date_elem.get_text(strip=True))

            return JobListing(
                title=title,
                company=company,
                location=self._normalize_location(location),
                job_url=job_url,
                apply_url=job_url,  # LinkedIn apply is on the job page
                source=self.name,
                date_posted=date_posted,
            )

        except Exception as e:
            logger.error(f"Error parsing LinkedIn job card: {e}")
            return None

    def get_job_details(self, job_url: str) -> Optional[Dict]:
        """Get full job details from LinkedIn job page."""
        try:
            self._rate_limit()
            response = requests.get(job_url, headers=self.headers, timeout=30)

            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            # Find job description (public view)
            description_elem = soup.find("div", class_=re.compile(r"show-more-less-html__markup|description__text"))

            if description_elem:
                raw_description = description_elem.get_text(separator="\n", strip=True)
            else:
                # Try script tag with job posting data
                scripts = soup.find_all("script", type="application/ld+json")
                for script in scripts:
                    try:
                        import json
                        data = json.loads(script.string)
                        if "description" in data:
                            raw_description = data["description"]
                            break
                    except:
                        continue
                else:
                    raw_description = ""

            # Find employment type
            employment_type = None
            criteria_list = soup.find_all("li", class_=re.compile(r"description__job-criteria-item"))
            for item in criteria_list:
                header = item.find("h3")
                if header and "Employment type" in header.get_text():
                    value = item.find("span", class_=re.compile(r"description__job-criteria-text"))
                    if value:
                        employment_type = value.get_text(strip=True).lower()
                        break

            return {
                "raw_description": raw_description,
                "employment_type": employment_type,
            }

        except Exception as e:
            logger.error(f"Error getting LinkedIn job details: {e}")
            return None
