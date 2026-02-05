"""
RSS Feed Scraper for job postings.

Supports:
- RSS.app feeds (for LinkedIn, etc.)
- Indeed RSS feeds
- Custom job RSS feeds
- Any RSS/Atom feed with job postings

To create a LinkedIn RSS feed via RSS.app:
1. Go to https://rss.app/
2. Create a new feed from LinkedIn Jobs URL like:
   https://www.linkedin.com/jobs/search/?keywords=forward%20deployed%20engineer&location=San%20Francisco
3. Copy the RSS.app feed URL and add it to RSS_APP_FEEDS below or via environment variable
"""

import os
import logging
import re
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import quote_plus

import feedparser
import httpx

from .base_scraper import BaseScraper, JobListing

logger = logging.getLogger(__name__)


class RSSFeedScraper(BaseScraper):
    """Scraper for RSS job feeds including RSS.app generated feeds."""

    def __init__(self):
        super().__init__()
        self.name = "rss"
        self.rate_limit_delay = (1, 2)

        # RSS.app feeds for LinkedIn jobs (user can add their own)
        # Format: List of RSS.app feed URLs
        self.rss_app_feeds: List[Dict] = []

        # LinkedIn job search URL to convert via RSS.app:
        # https://www.linkedin.com/jobs/search-results/?keywords=forward%20deploy&origin=JOBS_HOME_KEYWORD_HISTORY&f_TPR=r2592000&distance=50.0&geoId=90000084
        # (Forward Deploy jobs in SF Bay Area, 50 mile radius, last 30 days)

        # Load RSS.app feeds from environment variable (comma-separated)
        # Set RSS_APP_FEEDS env var with your RSS.app feed URL
        rss_app_env = os.getenv("RSS_APP_FEEDS", "")
        if rss_app_env:
            for feed_url in rss_app_env.split(","):
                feed_url = feed_url.strip()
                if feed_url:
                    self.rss_app_feeds.append({
                        "url": feed_url,
                        "source": "linkedin_rss",
                        "name": "LinkedIn via RSS.app"
                    })

        # Pre-configured RSS feed URLs for FDE jobs
        self.feed_sources = {
            "indeed": {
                "url_template": "https://www.indeed.com/rss?q={query}&l={location}&sort=date&fromage={days}",
                "name": "Indeed RSS",
            },
        }

        # Custom RSS feeds can be added here
        self.custom_feeds: List[str] = []

    def add_custom_feed(self, feed_url: str):
        """Add a custom RSS feed URL."""
        if feed_url not in self.custom_feeds:
            self.custom_feeds.append(feed_url)
            logger.info(f"Added custom RSS feed: {feed_url}")

    def add_rss_app_feed(self, feed_url: str, source_name: str = "linkedin_rss"):
        """Add an RSS.app feed URL (e.g., for LinkedIn jobs)."""
        self.rss_app_feeds.append({
            "url": feed_url,
            "source": source_name,
            "name": f"{source_name} via RSS.app"
        })
        logger.info(f"Added RSS.app feed: {feed_url}")

    def search_jobs(
        self,
        query: str = "forward deployed engineer",
        location: str = "San Francisco",
        days_ago: int = 30,
        max_results: int = 50,
    ) -> List[JobListing]:
        """Search for jobs across all configured RSS feeds."""
        all_jobs: List[JobListing] = []

        # Search RSS.app feeds first (LinkedIn, etc.)
        for feed_config in self.rss_app_feeds:
            try:
                rss_app_jobs = self._fetch_rss_app_feed(feed_config, max_results)
                all_jobs.extend(rss_app_jobs)
                logger.info(f"Found {len(rss_app_jobs)} jobs from {feed_config['name']}")
            except Exception as e:
                logger.error(f"Error fetching RSS.app feed {feed_config['url']}: {e}")

        # Search Indeed RSS
        indeed_jobs = self._fetch_indeed_rss(query, location, days_ago, max_results)
        all_jobs.extend(indeed_jobs)
        logger.info(f"Found {len(indeed_jobs)} jobs from Indeed RSS")

        # Search custom feeds
        for feed_url in self.custom_feeds:
            try:
                custom_jobs = self._fetch_generic_rss(feed_url, max_results)
                all_jobs.extend(custom_jobs)
                logger.info(f"Found {len(custom_jobs)} jobs from custom feed: {feed_url}")
            except Exception as e:
                logger.error(f"Error fetching custom feed {feed_url}: {e}")

        # Filter for FDE roles only
        fde_jobs = [job for job in all_jobs if self._is_fde_role(job.title)]
        logger.info(f"Filtered to {len(fde_jobs)} FDE-related jobs from {len(all_jobs)} total")

        return fde_jobs[:max_results]

    def _fetch_rss_app_feed(self, feed_config: Dict, max_results: int) -> List[JobListing]:
        """Fetch jobs from an RSS.app generated feed (LinkedIn, etc.)."""
        jobs: List[JobListing] = []
        feed_url = feed_config["url"]
        source_name = feed_config.get("source", "rss_app")

        try:
            logger.info(f"Fetching RSS.app feed: {feed_url}")

            # RSS.app feeds may require User-Agent header
            feed = feedparser.parse(
                feed_url,
                request_headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                }
            )

            if feed.bozo:
                logger.warning(f"Feed parsing warning: {feed.bozo_exception}")

            for entry in feed.entries[:max_results]:
                try:
                    job = self._parse_rss_app_entry(entry, source_name)
                    if job:
                        jobs.append(job)
                except Exception as e:
                    logger.error(f"Error parsing RSS.app entry: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error fetching RSS.app feed: {e}")

        return jobs

    def _parse_rss_app_entry(self, entry: Dict, source_name: str) -> Optional[JobListing]:
        """Parse an RSS.app feed entry (typically from LinkedIn) into a JobListing."""
        try:
            title = entry.get("title", "")
            if not title:
                return None

            job_url = entry.get("link", "")
            if not job_url:
                return None

            # Get description/summary
            description = entry.get("summary", "") or entry.get("description", "")

            # Try to extract company from title or description
            # LinkedIn job titles often include company info
            company = "Unknown"

            # Check for author field (sometimes RSS.app captures this)
            if entry.get("author"):
                company = entry.get("author")

            # Try to extract from description
            company_match = re.search(r'(?:at|@)\s+([A-Za-z0-9\s&]+?)(?:\s*[-|]|\s*$)', title)
            if company_match:
                company = company_match.group(1).strip()

            # Extract location from description if available
            location = ""
            location_match = re.search(
                r'(?:Location|Remote|Hybrid|On-site)[:\s]+([^<\n]+)',
                description,
                re.IGNORECASE
            )
            if location_match:
                location = location_match.group(1).strip()

            # Parse date
            date_posted = None
            if entry.get("published_parsed"):
                date_posted = datetime(*entry.published_parsed[:6])
            elif entry.get("updated_parsed"):
                date_posted = datetime(*entry.updated_parsed[:6])

            return JobListing(
                title=title,
                company=company,
                location=self._normalize_location(location),
                job_url=job_url,
                source=source_name,
                raw_description=self._clean_html(description),
                date_posted=date_posted,
            )

        except Exception as e:
            logger.error(f"Error parsing RSS.app entry: {e}")
            return None

    def _fetch_indeed_rss(
        self,
        query: str,
        location: str,
        days_ago: int,
        max_results: int,
    ) -> List[JobListing]:
        """Fetch jobs from Indeed RSS feed."""
        jobs: List[JobListing] = []

        try:
            # Build Indeed RSS URL
            encoded_query = quote_plus(query)
            encoded_location = quote_plus(location)
            feed_url = f"https://www.indeed.com/rss?q={encoded_query}&l={encoded_location}&sort=date&fromage={days_ago}"

            logger.info(f"Fetching Indeed RSS: {feed_url}")

            # Fetch and parse feed
            feed = feedparser.parse(feed_url)

            if feed.bozo:
                logger.warning(f"Feed parsing warning: {feed.bozo_exception}")

            for entry in feed.entries[:max_results]:
                try:
                    job = self._parse_indeed_entry(entry)
                    if job:
                        jobs.append(job)
                except Exception as e:
                    logger.error(f"Error parsing Indeed entry: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error fetching Indeed RSS: {e}")

        return jobs

    def _parse_indeed_entry(self, entry: Dict) -> Optional[JobListing]:
        """Parse an Indeed RSS feed entry into a JobListing."""
        try:
            title = entry.get("title", "")
            if not title:
                return None

            # Indeed RSS format: "Job Title - Company - Location"
            # Or sometimes just "Job Title"
            parts = title.split(" - ")

            job_title = parts[0].strip() if parts else title
            company = parts[1].strip() if len(parts) > 1 else "Unknown"
            location = parts[2].strip() if len(parts) > 2 else ""

            # Get job URL
            job_url = entry.get("link", "")
            if not job_url:
                return None

            # Get description
            description = entry.get("summary", "") or entry.get("description", "")

            # Parse date
            date_posted = None
            if entry.get("published_parsed"):
                date_posted = datetime(*entry.published_parsed[:6])
            elif entry.get("updated_parsed"):
                date_posted = datetime(*entry.updated_parsed[:6])

            return JobListing(
                title=job_title,
                company=company,
                location=self._normalize_location(location),
                job_url=job_url,
                source="indeed_rss",
                raw_description=self._clean_html(description),
                date_posted=date_posted,
            )

        except Exception as e:
            logger.error(f"Error parsing Indeed entry: {e}")
            return None

    def _fetch_generic_rss(self, feed_url: str, max_results: int) -> List[JobListing]:
        """Fetch jobs from a generic RSS feed."""
        jobs: List[JobListing] = []

        try:
            logger.info(f"Fetching RSS feed: {feed_url}")

            feed = feedparser.parse(feed_url)

            if feed.bozo:
                logger.warning(f"Feed parsing warning: {feed.bozo_exception}")

            feed_title = feed.feed.get("title", "Unknown Feed")

            for entry in feed.entries[:max_results]:
                try:
                    job = self._parse_generic_entry(entry, feed_title)
                    if job:
                        jobs.append(job)
                except Exception as e:
                    logger.error(f"Error parsing entry: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error fetching RSS feed {feed_url}: {e}")

        return jobs

    def _parse_generic_entry(self, entry: Dict, source_name: str) -> Optional[JobListing]:
        """Parse a generic RSS feed entry into a JobListing."""
        try:
            title = entry.get("title", "")
            if not title:
                return None

            job_url = entry.get("link", "")
            if not job_url:
                return None

            # Try to extract company from various fields
            company = (
                entry.get("author", "")
                or entry.get("dc_creator", "")
                or entry.get("source", {}).get("title", "")
                or "Unknown"
            )

            # Get description
            description = entry.get("summary", "") or entry.get("description", "") or entry.get("content", [{}])[0].get("value", "")

            # Try to extract location from title or description
            location = self._extract_location(title + " " + description)

            # Parse date
            date_posted = None
            if entry.get("published_parsed"):
                date_posted = datetime(*entry.published_parsed[:6])
            elif entry.get("updated_parsed"):
                date_posted = datetime(*entry.updated_parsed[:6])

            return JobListing(
                title=title,
                company=company,
                location=self._normalize_location(location),
                job_url=job_url,
                source=f"rss_{source_name.lower().replace(' ', '_')}",
                raw_description=self._clean_html(description),
                date_posted=date_posted,
            )

        except Exception as e:
            logger.error(f"Error parsing generic entry: {e}")
            return None

    def _extract_location(self, text: str) -> str:
        """Try to extract location from text."""
        # Common US city patterns
        location_patterns = [
            r"San Francisco[,\s]+CA",
            r"New York[,\s]+NY",
            r"Seattle[,\s]+WA",
            r"Austin[,\s]+TX",
            r"Boston[,\s]+MA",
            r"Los Angeles[,\s]+CA",
            r"Remote",
            r"Hybrid",
        ]

        for pattern in location_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)

        return ""

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text."""
        if not text:
            return ""
        # Simple HTML tag removal
        clean = re.sub(r'<[^>]+>', '', text)
        # Clean up whitespace
        clean = re.sub(r'\s+', ' ', clean)
        return clean.strip()

    def get_job_details(self, job_url: str) -> Optional[Dict]:
        """Get full job details by fetching the job page."""
        try:
            self._rate_limit()

            with httpx.Client(timeout=30, follow_redirects=True) as client:
                response = client.get(
                    job_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                    }
                )
                response.raise_for_status()

                # Extract description from page (simplified)
                html = response.text
                description = self._extract_description_from_html(html)

                return {
                    "raw_description": description,
                }

        except Exception as e:
            logger.error(f"Error fetching job details from {job_url}: {e}")
            return None

    def _extract_description_from_html(self, html: str) -> str:
        """Extract job description from HTML page."""
        # Try common job description patterns
        patterns = [
            r'<div[^>]*class="[^"]*job-description[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*id="[^"]*description[^"]*"[^>]*>(.*?)</div>',
            r'<section[^>]*class="[^"]*description[^"]*"[^>]*>(.*?)</section>',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                return self._clean_html(match.group(1))

        return ""


# Singleton instance
rss_scraper = RSSFeedScraper()
