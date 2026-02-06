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
    "ai_ml": "AI & ML: LLMs, Claude, GPT, Gemini, LangChain, LlamaIndex, PyTorch, TensorFlow, scikit-learn, RAG, embeddings, vector databases, Pinecone, Weaviate, Chroma, NLP, computer vision, AI agents",
    "backend": "Backend: Python, Java, Go, Rust, Node.js, FastAPI, Django, Flask, Express, Spring Boot, pandas, numpy, sqlalchemy, boto3, APIs, REST, GraphQL, microservices",
    "frontend": "Frontend: React, Vue, Angular, Next.js, Svelte, TypeScript, JavaScript, Tailwind, Material-UI, Redux, Zustand, webpack, vite",
    "cloud": "Cloud & DevOps: AWS, GCP, Azure, S3, Lambda, EC2, ECS, EKS, BigQuery, Kubernetes, Docker, Terraform, GitHub Actions, GitLab CI, Datadog, Grafana",
    "databases": "Databases: PostgreSQL, MySQL, MongoDB, Redis, Elasticsearch, DynamoDB, Cassandra, Neo4j, Supabase, Firebase",
    "tools": "Dev Tools: Git, GitHub, GitLab, Jira, Confluence, Notion, Figma, Postman, Swagger, Linux, Bash, VS Code",
    "soft_skills": "Soft Skills: customer-facing, stakeholder management, presentation, communication, problem-solving, collaboration, leadership",
    "fde_specific": "FDE Specific: forward deployed, field engineering, POC, demos, enterprise deployment, implementation, integration, onboarding",
    "data_pipelines": "Data Engineering: Spark, Kafka, Airflow, dbt, Snowflake, BigQuery, Redshift, Databricks, ETL, streaming",
    "other": "Other: Industries, certifications, methodologies, platforms, security, protocols, and miscellaneous requirements",
}

EXTRACTION_PROMPT = """Extract specific tools, libraries, frameworks, and technologies from this job description.

Categories:
- ai_ml: LLMs & AI (claude, gpt-4, gemini, llama, mistral, openai api, anthropic api, langchain, llamaindex, huggingface, transformers, pytorch, tensorflow, scikit-learn, rag, vector databases, pinecone, weaviate, chroma, embeddings, fine-tuning, prompt engineering, ai agents, computer vision, nlp, opencv, spacy)
- backend: Languages, frameworks & libraries (python, java, go, rust, node.js, ruby, fastapi, django, flask, express, spring boot, gin, pandas, numpy, sqlalchemy, asyncio, celery, redis-py, boto3, requests, pydantic)
- frontend: UI frameworks & libraries (react, vue, angular, next.js, svelte, typescript, javascript, tailwind, material-ui, chakra-ui, redux, zustand, webpack, vite, jest, cypress, storybook)
- cloud: Cloud services & DevOps tools (aws, gcp, azure, s3, lambda, ec2, ecs, eks, rds, dynamodb, sqs, sns, bigquery, cloud run, gke, kubernetes, docker, terraform, pulumi, ansible, github actions, gitlab ci, jenkins, argocd, datadog, grafana, prometheus, splunk)
- databases: Databases & data stores (postgresql, mysql, mongodb, redis, elasticsearch, cassandra, neo4j, pinecone, supabase, firebase, dynamodb)
- tools: Dev tools & platforms (git, github, gitlab, jira, confluence, notion, figma, postman, insomnia, swagger, linux, bash, vim, vscode)
- soft_skills: People skills (customer-facing, stakeholder management, presentation, communication, problem-solving, collaboration, leadership, mentoring)
- fde_specific: FDE/Field terms (forward deployed, field engineering, poc, demos, enterprise deployment, implementation, integration, onboarding, technical consulting, solution architecture)
- data_pipelines: Data engineering (spark, kafka, airflow, dbt, snowflake, bigquery, redshift, databricks, fivetran, airbyte, etl, streaming, batch processing, data warehouse)
- other: Everything else - industries (healthcare, fintech, insurance, e-commerce, legal, government, defense), certifications (aws certified, pmp, cissp, soc2, hipaa, gdpr), methodologies (agile, scrum, kanban, lean, six sigma), platforms (salesforce, stripe, twilio, segment, hubspot, zendesk, shopify, workday), security (oauth, jwt, sso, saml, encryption, rbac), protocols (http, grpc, websocket, mqtt), and any other specific terms

Rules:
1. Extract SPECIFIC tools, libraries, frameworks, and services mentioned (not generic terms)
2. Normalize names: "JS" → "javascript", "K8s" → "kubernetes", "Postgres" → "postgresql", "AWS S3" → "s3"
3. Return lowercase
4. Include version-specific tools: "python 3.11" → "python", "react 18" → "react"
5. Extract specific cloud services: "AWS Lambda" → "lambda", "Google BigQuery" → "bigquery"
6. Max 15 skills per category
7. Skip generic words: "experience", "knowledge", "proficiency", "understanding"

Return ONLY valid JSON:
{"ai_ml": ["claude", "langchain", "pinecone"], "backend": ["python", "fastapi", "pandas"], "frontend": ["react", "typescript"], "cloud": ["aws", "s3", "lambda", "kubernetes"], "databases": ["postgresql", "redis"], "tools": ["git", "jira"], "soft_skills": ["customer-facing"], "fde_specific": ["poc", "enterprise deployment"], "data_pipelines": ["snowflake", "airflow"], "other": ["healthcare", "agile", "soc2", "stripe"]}

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
