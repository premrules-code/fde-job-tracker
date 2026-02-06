"""
SerpAPI Google Jobs Scraper

Uses SerpAPI to search Google Jobs for job listings.
https://serpapi.com/google-jobs-api

To use this scraper:
1. Sign up at https://serpapi.com/
2. Get your API key (has free tier - 100 searches/month)
3. Set SERPAPI_KEY environment variable
"""

import os
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import re

import httpx

from .base_scraper import BaseScraper, JobListing

logger = logging.getLogger(__name__)


class SerpAPIScraper(BaseScraper):
    """Scraper using SerpAPI's Google Jobs API."""

    def __init__(self):
        super().__init__()
        self.name = "serpapi_google"
        self.api_key = os.getenv("SERPAPI_KEY", "")
        self.base_url = "https://serpapi.com/search"
        self.rate_limit_delay = (0.5, 1)

    def is_available(self) -> bool:
        """Check if SerpAPI key is configured."""
        return bool(self.api_key)

    def search_jobs(
        self,
        query: str = "forward deployed engineer",
        location: str = "San Francisco Bay Area",
        days_ago: int = 30,
        max_results: int = 50,
    ) -> List[JobListing]:
        """Search Google Jobs via SerpAPI."""
        if not self.is_available():
            logger.warning("SerpAPI key not configured. Set SERPAPI_KEY env var.")
            return []

        jobs: List[JobListing] = []

        try:
            # Build SerpAPI request
            params = {
                "engine": "google_jobs",
                "q": query,
                "location": location,
                "api_key": self.api_key,
                "hl": "en",
                "gl": "us",
            }

            # Add date filter
            if days_ago <= 1:
                params["chips"] = "date_posted:today"
            elif days_ago <= 3:
                params["chips"] = "date_posted:3days"
            elif days_ago <= 7:
                params["chips"] = "date_posted:week"
            elif days_ago <= 30:
                params["chips"] = "date_posted:month"

            logger.info(f"Searching Google Jobs via SerpAPI for: {query} in {location}")

            with httpx.Client(timeout=30) as client:
                response = client.get(self.base_url, params=params)

                if response.status_code == 401:
                    logger.error("SerpAPI authentication failed. Check your API key.")
                    return []

                if response.status_code == 429:
                    logger.warning("SerpAPI rate limit exceeded.")
                    return []

                if response.status_code != 200:
                    logger.error(f"SerpAPI returned status {response.status_code}")
                    return []

                data = response.json()

                # Check for errors
                if "error" in data:
                    logger.error(f"SerpAPI error: {data['error']}")
                    return []

                # Parse jobs from response
                jobs_results = data.get("jobs_results", [])

                for job_data in jobs_results:
                    try:
                        job = self._parse_job(job_data)
                        if job and self._is_fde_role(job.title):
                            jobs.append(job)
                    except Exception as e:
                        logger.error(f"Error parsing SerpAPI job: {e}")
                        continue

                    if len(jobs) >= max_results:
                        break

                # Handle pagination if needed
                next_page_token = data.get("serpapi_pagination", {}).get("next_page_token")
                while next_page_token and len(jobs) < max_results:
                    self._rate_limit()
                    params["next_page_token"] = next_page_token

                    response = client.get(self.base_url, params=params)
                    if response.status_code != 200:
                        break

                    data = response.json()
                    jobs_results = data.get("jobs_results", [])

                    for job_data in jobs_results:
                        try:
                            job = self._parse_job(job_data)
                            if job and self._is_fde_role(job.title):
                                jobs.append(job)
                        except:
                            continue

                        if len(jobs) >= max_results:
                            break

                    next_page_token = data.get("serpapi_pagination", {}).get("next_page_token")

        except Exception as e:
            logger.error(f"SerpAPI search failed: {e}")

        logger.info(f"Found {len(jobs)} FDE jobs from Google Jobs via SerpAPI")
        return jobs[:max_results]

    def _parse_job(self, job_data: Dict) -> Optional[JobListing]:
        """Parse job data from SerpAPI Google Jobs response."""
        try:
            title = job_data.get("title", "")
            if not title:
                return None

            company = job_data.get("company_name", "Unknown")
            location = job_data.get("location", "")

            # Get job URL - SerpAPI provides apply links
            job_url = ""
            apply_options = job_data.get("apply_options", [])
            if apply_options:
                # Get first apply option URL
                job_url = apply_options[0].get("link", "")

            # Fallback to related links
            if not job_url:
                related_links = job_data.get("related_links", [])
                if related_links:
                    job_url = related_links[0].get("link", "")

            # Fallback to job_id based URL
            if not job_url:
                job_id = job_data.get("job_id", "")
                if job_id:
                    # Google Jobs doesn't have direct URLs, use search URL
                    job_url = f"https://www.google.com/search?q={title.replace(' ', '+')}+{company.replace(' ', '+')}&ibp=htl;jobs"

            if not job_url:
                return None

            # Get description
            description = job_data.get("description", "")

            # Parse date
            date_posted = None
            posted_at = job_data.get("detected_extensions", {}).get("posted_at", "")
            if posted_at:
                date_posted = self._parse_relative_date(posted_at)

            # Get employment type and salary
            extensions = job_data.get("detected_extensions", {})
            employment_type = extensions.get("schedule_type", "")
            salary = extensions.get("salary", "")

            return JobListing(
                title=title,
                company=company,
                location=self._normalize_location(location),
                job_url=job_url,
                apply_url=job_url,
                source="google_jobs",
                raw_description=description,
                date_posted=date_posted,
                employment_type=employment_type if employment_type else None,
                salary_range=salary if salary else None,
            )

        except Exception as e:
            logger.error(f"Error parsing SerpAPI job data: {e}")
            return None

    def get_job_details(self, job_url: str) -> Optional[Dict]:
        """Get job details - for Google Jobs, details are in search results."""
        # Google Jobs includes full description in search results
        # No additional fetch needed
        return None


# Singleton instance
serpapi_scraper = SerpAPIScraper()
