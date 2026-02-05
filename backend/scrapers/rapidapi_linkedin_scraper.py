"""
RapidAPI LinkedIn Data API Scraper

Uses the rockapis LinkedIn Data API from RapidAPI to search for jobs.
https://rapidapi.com/rockapis-rockapis-default/api/linkedin-data-api

To use this scraper:
1. Sign up at https://rapidapi.com/
2. Subscribe to the LinkedIn Data API (has free tier)
3. Set RAPIDAPI_KEY environment variable with your API key
"""

import os
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

import httpx

from .base_scraper import BaseScraper, JobListing

logger = logging.getLogger(__name__)


class RapidAPILinkedInScraper(BaseScraper):
    """Scraper using RapidAPI's LinkedIn Data API."""

    def __init__(self):
        super().__init__()
        self.name = "rapidapi_linkedin"
        self.api_key = os.getenv("RAPIDAPI_KEY", "")
        self.api_host = "linkedin-data-api.p.rapidapi.com"
        self.base_url = f"https://{self.api_host}"
        self.rate_limit_delay = (1, 2)

    def is_available(self) -> bool:
        """Check if RapidAPI key is configured."""
        return bool(self.api_key)

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for RapidAPI requests."""
        return {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.api_host,
        }

    def search_jobs(
        self,
        query: str = "forward deployed engineer",
        location: str = "San Francisco Bay Area",
        days_ago: int = 30,
        max_results: int = 50,
    ) -> List[JobListing]:
        """Search for jobs using RapidAPI LinkedIn Data API."""
        if not self.is_available():
            logger.warning("RapidAPI key not configured. Set RAPIDAPI_KEY env var.")
            return []

        jobs: List[JobListing] = []

        try:
            # Search for jobs
            # The API endpoint may vary - common patterns:
            # /search-jobs, /jobs/search, /searchJobs
            endpoint = f"{self.base_url}/search-jobs"

            params = {
                "keywords": query,
                "locationId": "90000084",  # SF Bay Area geo ID from LinkedIn
                "datePosted": "pastMonth",  # or "pastWeek", "past24Hours"
                "start": 0,
                "count": min(max_results, 50),  # API may limit per request
            }

            logger.info(f"Searching RapidAPI LinkedIn for: {query} in {location}")
            self._rate_limit()

            with httpx.Client(timeout=30) as client:
                response = client.get(
                    endpoint,
                    headers=self._get_headers(),
                    params=params,
                )

                if response.status_code == 401:
                    logger.error("RapidAPI authentication failed. Check your API key.")
                    return []

                if response.status_code == 429:
                    logger.warning("RapidAPI rate limit exceeded.")
                    return []

                if response.status_code != 200:
                    logger.error(f"RapidAPI returned status {response.status_code}: {response.text[:200]}")
                    return []

                data = response.json()

                # Parse response - structure may vary by API
                job_list = data.get("data", data.get("jobs", data.get("results", [])))

                for job_data in job_list:
                    try:
                        job = self._parse_job(job_data)
                        if job and self._is_fde_role(job.title):
                            jobs.append(job)
                    except Exception as e:
                        logger.error(f"Error parsing job: {e}")
                        continue

        except Exception as e:
            logger.error(f"RapidAPI LinkedIn search failed: {e}")

        logger.info(f"Found {len(jobs)} FDE jobs from RapidAPI LinkedIn")
        return jobs[:max_results]

    def _parse_job(self, job_data: Dict) -> Optional[JobListing]:
        """Parse job data from RapidAPI response."""
        try:
            # Field names may vary by API version
            title = (
                job_data.get("title") or
                job_data.get("jobTitle") or
                job_data.get("position", "")
            )

            company = (
                job_data.get("company") or
                job_data.get("companyName") or
                job_data.get("company_name", "Unknown")
            )
            if isinstance(company, dict):
                company = company.get("name", "Unknown")

            location = (
                job_data.get("location") or
                job_data.get("jobLocation") or
                job_data.get("formattedLocation", "")
            )

            job_url = (
                job_data.get("url") or
                job_data.get("jobUrl") or
                job_data.get("link") or
                job_data.get("applyUrl", "")
            )

            # Build LinkedIn job URL if we have job ID
            job_id = job_data.get("id") or job_data.get("jobId") or job_data.get("entityUrn", "")
            if job_id and not job_url:
                if "urn:li:jobPosting:" in str(job_id):
                    job_id = str(job_id).split(":")[-1]
                job_url = f"https://www.linkedin.com/jobs/view/{job_id}"

            if not job_url:
                return None

            description = (
                job_data.get("description") or
                job_data.get("jobDescription") or
                job_data.get("descriptionText", "")
            )

            # Parse date
            date_posted = None
            posted_time = job_data.get("postedDate") or job_data.get("listedAt") or job_data.get("postedAt")
            if posted_time:
                try:
                    if isinstance(posted_time, (int, float)):
                        # Milliseconds timestamp
                        date_posted = datetime.fromtimestamp(posted_time / 1000)
                    elif isinstance(posted_time, str):
                        date_posted = self._parse_relative_date(posted_time)
                except:
                    pass

            return JobListing(
                title=title,
                company=company,
                location=self._normalize_location(location),
                job_url=job_url,
                apply_url=job_url,
                source="rapidapi_linkedin",
                raw_description=description,
                date_posted=date_posted,
            )

        except Exception as e:
            logger.error(f"Error parsing RapidAPI job data: {e}")
            return None

    def get_job_details(self, job_url: str) -> Optional[Dict]:
        """Get detailed job information."""
        if not self.is_available():
            return None

        try:
            # Extract job ID from URL
            job_id = None
            if "/jobs/view/" in job_url:
                job_id = job_url.split("/jobs/view/")[-1].split("/")[0].split("?")[0]

            if not job_id:
                return None

            endpoint = f"{self.base_url}/get-job-details"
            params = {"id": job_id}

            self._rate_limit()

            with httpx.Client(timeout=30) as client:
                response = client.get(
                    endpoint,
                    headers=self._get_headers(),
                    params=params,
                )

                if response.status_code != 200:
                    return None

                data = response.json()
                job_data = data.get("data", data)

                description = (
                    job_data.get("description") or
                    job_data.get("jobDescription") or
                    ""
                )

                return {
                    "raw_description": description,
                    "employment_type": job_data.get("employmentType"),
                    "salary_range": job_data.get("salary") or job_data.get("compensationDescription"),
                }

        except Exception as e:
            logger.error(f"Error getting job details: {e}")
            return None


# Singleton instance
rapidapi_linkedin_scraper = RapidAPILinkedInScraper()
