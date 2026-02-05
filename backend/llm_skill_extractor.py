import os
import json
import logging
from typing import Dict, List
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

logger = logging.getLogger(__name__)

# Load .env file from backend directory
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# Get API key from environment
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

SKILL_CATEGORIES = {
    "ai": "AI technologies: LLMs, GPT, Claude, ChatGPT, Gemini, AI agents, agentic systems, RAG, prompt engineering, fine-tuning, embeddings, vector databases, LangChain, AI safety, AI deployment",
    "ml": "Machine Learning: ML frameworks (PyTorch, TensorFlow, scikit-learn), ML models, deep learning, neural networks, NLP, computer vision, MLOps, model training, model evaluation, data science",
    "backend": "Backend development: Python, Java, Go, Node.js, APIs, REST, GraphQL, databases (PostgreSQL, MongoDB, Redis), microservices, system design, distributed systems",
    "frontend": "Frontend development: React, Vue, Angular, TypeScript, JavaScript, Next.js, UI/UX, web development, mobile development",
    "cloud": "Cloud & Infrastructure: AWS, GCP, Azure, Kubernetes, Docker, CI/CD, Terraform, serverless, DevOps, infrastructure, deployment, monitoring, scalability",
    "data": "Data & ETL: data pipelines, ETL, ELT, data engineering, Spark, Kafka, Airflow, dbt, data warehouse, Snowflake, BigQuery, Redshift, data modeling, analytics, BI, Tableau, Looker, data integration",
    "fde": "Field/FDE skills: customer-facing, enterprise deployment, POC, demos, technical consulting, solution architecture, implementation, integration, stakeholder management, communication, presentation, discovery, requirements gathering",
    "industry": "Industry domains: healthcare, fintech, financial services, insurance, life sciences, manufacturing, retail, e-commerce, logistics, legal, government, public sector, defense, energy, telecom, media, gaming, education, real estate",
}

EXTRACTION_PROMPT = """Extract technical skills from this Forward Deployed Engineer job description.

Categories (be specific and accurate):
- ai: AI/LLM technologies (Claude, GPT, ChatGPT, AI agents, RAG, prompt engineering, LangChain, embeddings, vector DBs)
- ml: Machine Learning (PyTorch, TensorFlow, scikit-learn, deep learning, NLP, computer vision, MLOps)
- backend: Backend development (Python, Java, Go, Node.js, APIs, REST, GraphQL, PostgreSQL, MongoDB, Redis)
- frontend: Frontend development (React, Vue, Angular, TypeScript, JavaScript, Next.js)
- cloud: Cloud & DevOps (AWS, GCP, Azure, Kubernetes, Docker, CI/CD, Terraform, serverless)
- data: Data & ETL (data pipelines, ETL, Spark, Kafka, Airflow, dbt, Snowflake, BigQuery, data warehouse, analytics, Tableau)
- fde: FDE/Field skills (customer-facing, enterprise deployment, POC, demos, consulting, solution architecture, stakeholder management)
- industry: Industry domains mentioned (healthcare, fintech, financial services, insurance, life sciences, manufacturing, retail, government, defense)

Rules:
1. Extract SPECIFIC technologies, frameworks, tools, and industry domains
2. Normalize names: "JS" -> "JavaScript", "K8s" -> "Kubernetes", "Postgres" -> "PostgreSQL"
3. Put each skill in ONE category only (most relevant)
4. Keep skill names concise (1-3 words max)
5. For industry: extract specific verticals/domains the company works in or requires experience with
6. Don't include generic words like "experience", "skills", "ability"

Return ONLY valid JSON:
{
  "ai": ["Claude", "GPT-4", "RAG", "prompt engineering"],
  "ml": ["PyTorch", "NLP"],
  "backend": ["Python", "PostgreSQL", "REST APIs"],
  "frontend": ["React", "TypeScript"],
  "cloud": ["AWS", "Kubernetes", "Docker"],
  "data": ["Snowflake", "ETL", "data pipelines"],
  "fde": ["enterprise deployment", "POC", "stakeholder management"],
  "industry": ["healthcare", "fintech", "financial services"]
}

Job Description:
"""


class LLMSkillExtractor:
    def __init__(self):
        self.client = None
        if ANTHROPIC_API_KEY:
            self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
            logger.info("LLM Skill Extractor initialized with Anthropic API")
        else:
            logger.warning("ANTHROPIC_API_KEY not set - LLM extraction disabled")

    def extract_skills(self, text: str) -> Dict[str, List[str]]:
        """Extract skills from text using Claude."""
        if not self.client or not text:
            return {cat: [] for cat in SKILL_CATEGORIES.keys()}

        try:
            # Truncate very long descriptions
            text = text[:8000] if len(text) > 8000 else text

            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": EXTRACTION_PROMPT + text
                    }
                ]
            )

            # Parse JSON response
            content = response.content[0].text.strip()

            # Handle potential markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

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

            return normalized

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return {cat: [] for cat in SKILL_CATEGORIES.keys()}
        except Exception as e:
            logger.error(f"LLM skill extraction failed: {e}")
            return {cat: [] for cat in SKILL_CATEGORIES.keys()}

    def is_available(self) -> bool:
        """Check if LLM extraction is available."""
        return self.client is not None


# Singleton instance
llm_skill_extractor = LLMSkillExtractor()


if __name__ == "__main__":
    # Test the extractor
    sample = """
    We're looking for a Forward Deployed Engineer to work with our enterprise customers.

    Requirements:
    - 5+ years of Python and TypeScript experience
    - Experience with LLMs, RAG, and prompt engineering
    - AWS or GCP cloud experience
    - Kubernetes and Docker
    - Strong customer communication skills
    - Experience with enterprise software deployment
    - Bonus: Experience with LangChain, vector databases like Pinecone
    """

    if llm_skill_extractor.is_available():
        skills = llm_skill_extractor.extract_skills(sample)
        print(json.dumps(skills, indent=2))
    else:
        print("Set ANTHROPIC_API_KEY to test LLM extraction")
