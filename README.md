# FDE Job Tracker

A comprehensive job tracking application for Forward Deployed Engineer (FDE) roles in the San Francisco Bay Area. This tool scrapes job postings from multiple sources, extracts key skills and requirements, and provides a modern UI with skills heatmaps to help you understand what to study and focus on.

## Features

### Job Scraping
- **Multiple Job Boards**: LinkedIn, Indeed, Greenhouse, Lever, Wellfound (AngelList)
- **Target Companies**: Anthropic, OpenAI, Scale AI, Palantir, Salesforce, Databricks, Vapi, GigaML, Reducto, and more
- **Daily Automation**: Configurable scheduler for automatic daily scraping
- **Smart Deduplication**: Prevents duplicate job entries

### Job Parsing & Analysis
- **Section Extraction**: Automatically extracts responsibilities, qualifications, nice-to-have, and about sections
- **Skill Detection**: Identifies AI/ML keywords, programming languages, cloud technologies, soft skills
- **Relevance Scoring**: Ranks jobs by how closely they match FDE role criteria

### Modern UI
- **Job Cards**: Each job has an "Apply ↗" button that opens the actual posting directly
- **Skills Heatmap**: Visual representation of most-requested skills to help prioritize learning
- **Daily Summary**: Track new postings by company and source
- **Command Palette (⌘K)**: Full-text search across all job postings including raw descriptions
- **Expandable JD**: View full raw job descriptions with requirements and bonus sections

## Tech Stack

### Backend
- **FastAPI**: High-performance Python API framework
- **SQLite**: Lightweight database for job storage
- **BeautifulSoup/Requests**: Web scraping
- **APScheduler**: Daily job scheduling

### Frontend
- **React + TypeScript**: Modern UI framework
- **TanStack Query**: Data fetching and caching
- **Tailwind CSS**: Utility-first styling
- **cmdk**: Command palette implementation
- **Lucide Icons**: Beautiful icons

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- npm or yarn

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database and start server
python main.py
```

The API will be available at `http://localhost:8000`

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The UI will be available at `http://localhost:5173`

## Usage

### Running a Manual Scrape

1. Click the "Scrape Jobs" button in the UI, or
2. Send a POST request to `http://localhost:8000/api/scrape`

### Setting Up Daily Scraping

Run the scheduler in a separate terminal:

```bash
cd backend
python scheduler.py
```

This will scrape jobs daily at 6 AM UTC (10 PM PST).

### Using the Command Palette

Press `⌘K` (Mac) or `Ctrl+K` (Windows/Linux) to open the search palette. You can search by:
- Job title
- Company name
- Skills (e.g., "python", "langchain", "kubernetes")
- Any text in the job description

### Understanding the Skills Heatmap

The heatmap shows the frequency of skills mentioned across all job postings:
- **AI/ML**: LLMs, transformers, RAG, fine-tuning, etc.
- **Programming**: Python, JavaScript, Go, etc.
- **Cloud/DevOps**: AWS, GCP, Docker, Kubernetes, etc.
- **Soft Skills**: Communication, presentation, customer-facing, etc.
- **FDE Specific**: Forward deployed, solutions engineer, POC, etc.

Click any skill to filter jobs that mention it.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/jobs` | GET | List jobs with filters |
| `/api/jobs/{id}` | GET | Get job details |
| `/api/search?q=` | GET | Full-text search |
| `/api/skills/heatmap` | GET | Skills frequency data |
| `/api/summary/daily` | GET | Daily posting summary |
| `/api/companies` | GET | Companies with job counts |
| `/api/sources` | GET | Sources with job counts |
| `/api/scrape` | POST | Trigger manual scrape |

## Adding New Companies

Edit `backend/scrapers/greenhouse_scraper.py` or `backend/scrapers/lever_scraper.py` to add company board tokens:

```python
GREENHOUSE_COMPANIES = {
    "your-company": "board-token",  # from boards.greenhouse.io/board-token
}
```

## Project Structure

```
fde-job-tracker/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── models.py            # Database models
│   ├── job_scraper.py       # Main scraper orchestrator
│   ├── skill_extractor.py   # NLP skill extraction
│   ├── scheduler.py         # Daily scrape scheduler
│   ├── requirements.txt     # Python dependencies
│   └── scrapers/
│       ├── base_scraper.py      # Base scraper class
│       ├── indeed_scraper.py    # Indeed scraper
│       ├── linkedin_scraper.py  # LinkedIn scraper
│       ├── greenhouse_scraper.py # Greenhouse scraper
│       ├── lever_scraper.py     # Lever scraper
│       └── wellfound_scraper.py # Wellfound scraper
├── frontend/
│   ├── src/
│   │   ├── App.tsx          # Main application
│   │   ├── api.ts           # API client
│   │   └── components/
│   │       ├── JobCard.tsx      # Job listing card
│   │       ├── SkillHeatmap.tsx # Skills visualization
│   │       ├── DailySummary.tsx # Daily stats
│   │       ├── CommandPalette.tsx # ⌘K search
│   │       └── Filters.tsx      # Filter sidebar
│   └── package.json
└── README.md
```

## Notes

- Some job boards may rate-limit or block scrapers. The scrapers include random delays and proper headers to minimize this.
- LinkedIn and Indeed public pages have limited data compared to authenticated APIs.
- Greenhouse and Lever APIs are more reliable for company-specific scraping.
- The skill extraction is keyword-based; consider adding ML-based extraction for better accuracy.

## License

MIT
