from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging
import time
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JobListing:
    """Standardized job listing data structure."""

    def __init__(
        self,
        title: str,
        company: str,
        location: str,
        job_url: str,
        source: str,
        raw_description: str = "",
        apply_url: str = None,
        date_posted: datetime = None,
        salary_range: str = None,
        employment_type: str = None,
        remote_status: str = None,
    ):
        self.title = title
        self.company = company
        self.location = location
        self.job_url = job_url
        self.apply_url = apply_url or job_url
        self.source = source
        self.raw_description = raw_description
        self.date_posted = date_posted
        self.salary_range = salary_range
        self.employment_type = employment_type
        self.remote_status = remote_status

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "job_url": self.job_url,
            "apply_url": self.apply_url,
            "source": self.source,
            "raw_description": self.raw_description,
            "date_posted": self.date_posted,
            "salary_range": self.salary_range,
            "employment_type": self.employment_type,
            "remote_status": self.remote_status,
        }


class BaseScraper(ABC):
    """Base class for all job board scrapers."""

    def __init__(self):
        self.name = "base"
        self.base_url = ""
        self.rate_limit_delay = (2, 5)  # Random delay between requests

    @abstractmethod
    def search_jobs(
        self,
        query: str,
        location: str,
        days_ago: int = 30,
        max_results: int = 100,
    ) -> List[JobListing]:
        """Search for jobs matching query and location."""
        pass

    @abstractmethod
    def get_job_details(self, job_url: str) -> Optional[Dict]:
        """Get full job details from a job posting URL."""
        pass

    def _rate_limit(self):
        """Apply rate limiting between requests."""
        delay = random.uniform(*self.rate_limit_delay)
        time.sleep(delay)

    def _parse_relative_date(self, date_str: str) -> Optional[datetime]:
        """Parse relative date strings like '3 days ago', 'Posted today', etc."""
        if not date_str:
            return None

        date_str = date_str.lower().strip()
        now = datetime.now()

        if "today" in date_str or "just posted" in date_str or "just now" in date_str:
            return now
        elif "yesterday" in date_str:
            return now - timedelta(days=1)

        # Try to extract number of days/weeks/months
        import re

        # Days ago
        days_match = re.search(r'(\d+)\s*(?:day|d)\s*(?:ago)?', date_str)
        if days_match:
            return now - timedelta(days=int(days_match.group(1)))

        # Weeks ago
        weeks_match = re.search(r'(\d+)\s*(?:week|w)\s*(?:ago)?', date_str)
        if weeks_match:
            return now - timedelta(weeks=int(weeks_match.group(1)))

        # Months ago
        months_match = re.search(r'(\d+)\s*(?:month|mo)\s*(?:ago)?', date_str)
        if months_match:
            return now - timedelta(days=int(months_match.group(1)) * 30)

        # Hours ago
        hours_match = re.search(r'(\d+)\s*(?:hour|hr|h)\s*(?:ago)?', date_str)
        if hours_match:
            return now - timedelta(hours=int(hours_match.group(1)))

        return None

    def _is_fde_role(self, title: str) -> bool:
        """Check if job title matches FDE-related roles (strict: only Forward Deployed Engineer)."""
        title_lower = title.lower()
        # Strict filter: Only Forward Deployed Engineer roles
        fde_keywords = [
            "forward deploy",
            "forward-deploy",
            "fde",
        ]
        return any(kw in title_lower for kw in fde_keywords)

    def _normalize_location(self, location: str) -> str:
        """Normalize location strings."""
        if not location:
            return ""

        # Common SF Bay Area variations
        sf_variations = [
            "san francisco", "sf", "bay area", "silicon valley",
            "palo alto", "mountain view", "sunnyvale", "san jose",
            "oakland", "berkeley", "redwood city", "menlo park",
            "south san francisco", "san mateo", "fremont",
        ]

        location_lower = location.lower()
        for variation in sf_variations:
            if variation in location_lower:
                return "San Francisco Bay Area"

        return location
