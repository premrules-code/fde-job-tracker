import os
import json
import logging
import hashlib
from typing import Dict, List, Optional
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env file from backend directory
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# Get API keys from environment
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Simple in-memory cache for skill extraction results
_skill_cache: Dict[str, Dict[str, List[str]]] = {}
MAX_CACHE_SIZE = 500

# Initialize clients
gemini_client = None
anthropic_client = None

# Try to initialize Gemini (primary - cheaper)
if GOOGLE_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GOOGLE_API_KEY)
        gemini_client = genai.GenerativeModel("gemini-2.0-flash")
        logger.info("Gemini Flash initialized (primary LLM)")
    except Exception as e:
        logger.warning(f"Failed to initialize Gemini: {e}")

# Try to initialize Anthropic (fallback)
if ANTHROPIC_API_KEY:
    try:
        from anthropic import Anthropic
        anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
        logger.info("Claude Haiku initialized (fallback LLM)")
    except Exception as e:
        logger.warning(f"Failed to initialize Anthropic: {e}")

SKILL_CATEGORIES = {
    "ai_ml": "AI & Machine Learning: LLMs (Claude, GPT, ChatGPT, Gemini), AI agents, agentic systems, RAG, prompt engineering, fine-tuning, embeddings, vector databases (Pinecone, Weaviate, Chroma), LangChain, LlamaIndex, AI safety, ML frameworks (PyTorch, TensorFlow, scikit-learn), deep learning, neural networks, NLP, computer vision, MLOps, transformers, hugging face",
    "backend": "Backend development: Python, Java, Go, Golang, Rust, Node.js, Ruby, PHP, FastAPI, Flask, Django, Spring Boot, Express, APIs, REST, GraphQL, gRPC, databases (PostgreSQL, MySQL, MongoDB, Redis), microservices, system design, distributed systems, message queues, Kafka",
    "frontend": "Frontend development: JavaScript, TypeScript, React, Vue, Angular, Next.js, Svelte, HTML, CSS, Tailwind, UI/UX, web development, mobile development, React Native, responsive design",
    "cloud": "Cloud & DevOps: AWS (EC2, S3, Lambda, ECS, EKS), GCP (BigQuery, Cloud Run, GKE), Azure, Kubernetes, Docker, CI/CD, GitHub Actions, Terraform, Ansible, serverless, infrastructure as code, monitoring, Datadog, observability",
    "soft_skills": "Soft skills & FDE traits: customer-facing, enterprise deployment, POC, demos, technical consulting, solution architecture, implementation, integration, stakeholder management, communication, presentation, discovery, requirements gathering, problem-solving, collaboration, leadership",
    "fde_specific": "FDE/Field specific: forward deployed, field engineering, professional services, technical account management, customer success, onboarding, white glove, hands-on deployment, production workflows",
    "data_pipelines": "Data Engineering: data pipelines, ETL, ELT, Spark, Kafka, Airflow, dbt, data warehouse, Snowflake, BigQuery, Redshift, data modeling, analytics, Tableau, Looker, streaming, batch processing",
}

EXTRACTION_PROMPT = """Extract skills and technologies from this Forward Deployed Engineer job description.

Categories:
- ai_ml: AI & ML technologies (Claude, GPT, LLMs, AI agents, RAG, prompt engineering, LangChain, PyTorch, TensorFlow, NLP, computer vision, MLOps, embeddings, vector databases)
- backend: Backend languages & frameworks (Python, Java, Go, Rust, Node.js, FastAPI, Django, Flask, Spring, APIs, REST, GraphQL, PostgreSQL, MongoDB, Redis, microservices)
- frontend: Frontend technologies (JavaScript, TypeScript, React, Vue, Angular, Next.js, Svelte, Tailwind, CSS, HTML)
- cloud: Cloud & DevOps (AWS, GCP, Azure, Kubernetes, Docker, CI/CD, Terraform, serverless, GitHub Actions, monitoring)
- soft_skills: Communication & collaboration (customer-facing, stakeholder management, presentation, problem-solving, leadership, teamwork)
- fde_specific: FDE-specific terms (forward deployed, field engineering, POC, demos, enterprise deployment, implementation, integration, onboarding)
- data_pipelines: Data engineering (ETL, data pipelines, Spark, Kafka, Airflow, dbt, Snowflake, BigQuery, data warehouse, analytics)

Rules:
1. Extract SPECIFIC technologies, tools, and frameworks mentioned
2. Normalize: "JS" → "javascript", "K8s" → "kubernetes", "Postgres" → "postgresql"
3. Return lowercase skill names
4. Put each skill in ONE category (most relevant)
5. Max 10 skills per category
6. Skip generic terms like "experience", "skills", "proficiency"

Return ONLY valid JSON (no markdown, no explanation):
{"ai_ml": ["claude", "gpt-4", "rag", "langchain"], "backend": ["python", "postgresql", "fastapi"], "frontend": ["react", "typescript"], "cloud": ["aws", "kubernetes", "docker"], "soft_skills": ["customer-facing", "stakeholder management"], "fde_specific": ["enterprise deployment", "poc"], "data_pipelines": ["snowflake", "airflow"]}

Job Description:
"""


class LLMSkillExtractor:
    def __init__(self, use_cache: bool = True):
        self.use_cache = use_cache
        self.extraction_count = 0
        self.gemini_count = 0
        self.claude_count = 0
        self.active_model = None

        # Determine which model to use (Gemini preferred for cost)
        if gemini_client:
            self.active_model = "gemini"
            logger.info("LLM Skill Extractor using Gemini Flash (primary)")
        elif anthropic_client:
            self.active_model = "claude"
            logger.info("LLM Skill Extractor using Claude Haiku (fallback)")
        else:
            logger.warning("No LLM API keys set - extraction disabled")

    def _get_cache_key(self, text: str) -> str:
        """Generate a cache key from text."""
        return hashlib.md5(text[:2000].encode()).hexdigest()

    def _get_from_cache(self, text: str) -> Optional[Dict[str, List[str]]]:
        """Get cached result if available."""
        if not self.use_cache:
            return None
        key = self._get_cache_key(text)
        return _skill_cache.get(key)

    def _save_to_cache(self, text: str, skills: Dict[str, List[str]]):
        """Save result to cache."""
        if not self.use_cache:
            return
        # Limit cache size
        if len(_skill_cache) >= MAX_CACHE_SIZE:
            # Remove oldest entries (first 100)
            keys_to_remove = list(_skill_cache.keys())[:100]
            for key in keys_to_remove:
                del _skill_cache[key]
        key = self._get_cache_key(text)
        _skill_cache[key] = skills

    def _extract_with_gemini(self, text: str) -> str:
        """Extract skills using Gemini Flash."""
        response = gemini_client.generate_content(
            EXTRACTION_PROMPT + text,
            generation_config={
                "temperature": 0.1,
                "max_output_tokens": 512,
            }
        )
        self.gemini_count += 1
        return response.text

    def _extract_with_claude(self, text: str) -> str:
        """Extract skills using Claude Haiku."""
        response = anthropic_client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=512,
            messages=[{"role": "user", "content": EXTRACTION_PROMPT + text}]
        )
        self.claude_count += 1
        return response.content[0].text

    def extract_skills(self, text: str) -> Dict[str, List[str]]:
        """Extract skills from text using Gemini Flash (primary) or Claude Haiku (fallback).

        Args:
            text: Job description text
        """
        if not self.active_model or not text:
            return {cat: [] for cat in SKILL_CATEGORIES.keys()}

        # Check cache first
        cached = self._get_from_cache(text)
        if cached:
            logger.debug("Using cached skill extraction")
            return cached

        try:
            # Truncate very long descriptions
            text = text[:6000] if len(text) > 6000 else text

            # Try Gemini first, fall back to Claude
            content = None
            try:
                if self.active_model == "gemini" and gemini_client:
                    content = self._extract_with_gemini(text)
                elif anthropic_client:
                    content = self._extract_with_claude(text)
            except Exception as e:
                logger.warning(f"Primary model failed: {e}, trying fallback...")
                # Try fallback
                if self.active_model == "gemini" and anthropic_client:
                    content = self._extract_with_claude(text)
                elif self.active_model == "claude" and gemini_client:
                    content = self._extract_with_gemini(text)

            if not content:
                return {cat: [] for cat in SKILL_CATEGORIES.keys()}

            self.extraction_count += 1

            # Parse JSON response
            content = content.strip()

            # Handle potential markdown code blocks
            if content.startswith("```"):
                lines = content.split("\n")
                # Remove first and last lines (``` markers)
                content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                content = content.strip()

            # Try to find JSON in the response
            if not content.startswith("{"):
                # Look for JSON object in the response
                start = content.find("{")
                end = content.rfind("}") + 1
                if start != -1 and end > start:
                    content = content[start:end]

            skills = json.loads(content)

            # Normalize: lowercase and deduplicate
            normalized = {}
            for category in SKILL_CATEGORIES.keys():
                if category in skills and isinstance(skills[category], list):
                    # Lowercase and deduplicate while preserving order
                    seen = set()
                    normalized[category] = []
                    for s in skills[category]:
                        s_lower = s.lower().strip()
                        if s_lower and s_lower not in seen:
                            seen.add(s_lower)
                            normalized[category].append(s_lower)
                else:
                    normalized[category] = []

            # Cache the result
            self._save_to_cache(text, normalized)

            logger.info(f"LLM extracted skills: {sum(len(v) for v in normalized.values())} total")
            return normalized

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}, content: {content[:200]}")
            return {cat: [] for cat in SKILL_CATEGORIES.keys()}
        except Exception as e:
            logger.error(f"LLM skill extraction failed: {e}")
            return {cat: [] for cat in SKILL_CATEGORIES.keys()}

    def is_available(self) -> bool:
        """Check if LLM extraction is available."""
        return self.active_model is not None

    def get_stats(self) -> Dict:
        """Get extraction statistics."""
        return {
            "available": self.is_available(),
            "active_model": self.active_model or "none",
            "gemini_available": gemini_client is not None,
            "claude_available": anthropic_client is not None,
            "cache_size": len(_skill_cache),
            "extractions_performed": self.extraction_count,
            "gemini_extractions": self.gemini_count,
            "claude_extractions": self.claude_count,
        }


# Singleton instance
llm_skill_extractor = LLMSkillExtractor()


def extract_skills_for_job(text: str, use_llm: bool = True) -> Dict[str, List[str]]:
    """
    Extract skills from job description, using LLM if available.

    Returns a dict with keys that match what scrapers expect:
    - ai_ml: AI/ML keywords
    - backend: Backend skills
    - frontend: Frontend skills
    - cloud: Cloud/DevOps skills
    - soft_skills: Soft skills
    - fde_specific: FDE-specific terms
    - data_pipelines: Data engineering skills

    Falls back to regex-based extraction if LLM is unavailable.
    """
    if use_llm and llm_skill_extractor.is_available():
        return llm_skill_extractor.extract_skills(text)
    else:
        # Fallback to regex-based extraction
        from skill_extractor import skill_extractor
        return skill_extractor.extract_skills(text)


if __name__ == "__main__":
    # Test the extractor
    sample = """
    We're looking for a Forward Deployed Engineer to work with our enterprise customers
    in the healthcare and financial services industries.

    Requirements:
    - 5+ years of Python and TypeScript experience
    - Experience with React, Next.js for frontend development
    - Experience with LLMs, RAG, and prompt engineering
    - Familiarity with Claude, GPT-4, or similar large language models
    - AWS or GCP cloud experience
    - Kubernetes and Docker containerization
    - Strong customer communication skills
    - Experience with enterprise software deployment and POC delivery
    - Bonus: Experience with LangChain, vector databases like Pinecone
    - Experience with data pipelines, Snowflake, or BigQuery
    """

    print("Testing LLM Skill Extractor...")
    stats = llm_skill_extractor.get_stats()
    print(f"Available: {stats['available']}")
    print(f"Active Model: {stats['active_model']}")
    print(f"Gemini Available: {stats['gemini_available']}")
    print(f"Claude Available: {stats['claude_available']}")

    if llm_skill_extractor.is_available():
        print(f"\nExtracting skills with {stats['active_model'].upper()}...")
        skills = llm_skill_extractor.extract_skills(sample)
        print("\nExtracted Skills:")
        for category, skill_list in skills.items():
            if skill_list:
                print(f"  {category}: {', '.join(skill_list)}")

        print(f"\nUpdated Stats: {llm_skill_extractor.get_stats()}")
    else:
        print("\nSet GOOGLE_API_KEY (preferred) or ANTHROPIC_API_KEY to enable LLM extraction")
