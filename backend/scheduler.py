"""
Daily scheduler for automatic job scraping.
Run this as a separate process or integrate with your hosting platform's scheduler.
"""
import logging
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from job_scraper import job_scraper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def daily_scrape_job():
    """Run the daily scrape job."""
    logger.info(f"Starting scheduled scrape at {datetime.now()}")

    try:
        results = job_scraper.run_daily_scrape(
            location="San Francisco Bay Area",
            days_ago=7,  # Look at last 7 days for daily runs
            max_results_per_source=50,
        )
        logger.info(f"Scheduled scrape completed: {results}")

    except Exception as e:
        logger.error(f"Scheduled scrape failed: {e}")


def main():
    """Main entry point for the scheduler."""
    scheduler = BlockingScheduler()

    # Run daily at 6 AM UTC (10 PM PST)
    scheduler.add_job(
        daily_scrape_job,
        CronTrigger(hour=6, minute=0),
        id='daily_scrape',
        name='Daily FDE Job Scrape',
        replace_existing=True,
    )

    logger.info("Scheduler started. Daily scrape scheduled for 6 AM UTC.")
    logger.info("Press Ctrl+C to exit.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
