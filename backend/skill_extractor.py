import re
from typing import Dict, List, Tuple
from collections import Counter

# Comprehensive skill/keyword dictionaries for FDE roles
AI_ML_KEYWORDS = {
    # Core AI/ML
    "machine learning", "deep learning", "neural networks", "nlp", "natural language processing",
    "computer vision", "reinforcement learning", "supervised learning", "unsupervised learning",
    "transformers", "attention mechanism", "embeddings", "vector databases", "rag",
    "retrieval augmented generation", "fine-tuning", "prompt engineering", "llm", "large language models",
    "generative ai", "gen ai", "gpt", "claude", "chatgpt", "openai", "anthropic",
    "ai models", "foundation models", "frontier models", "ai systems", "ai applications",

    # Agents & Advanced AI
    "ai agents", "agent development", "agentic", "autonomous agents", "multi-agent",
    "function calling", "tool use", "mcp", "mcp servers", "sub-agents", "agent skills",
    "chain of thought", "reasoning", "ai orchestration",

    # ML Frameworks
    "tensorflow", "pytorch", "keras", "scikit-learn", "sklearn", "hugging face", "huggingface",
    "langchain", "llamaindex", "llama index", "openai api", "anthropic api", "claude api",
    "semantic kernel", "autogen", "crewai",

    # MLOps & Deployment
    "mlops", "mlflow", "kubeflow", "sagemaker", "vertex ai", "azure ml", "databricks",
    "model deployment", "model serving", "feature store", "model monitoring",
    "ai deployment", "llm deployment", "production ai", "ai at scale",

    # Evaluation & Safety
    "evaluation frameworks", "evals", "model evaluation", "ai safety", "responsible ai",
    "red teaming", "prompt injection", "jailbreaking", "guardrails",

    # Data Science
    "pandas", "numpy", "scipy", "matplotlib", "seaborn", "jupyter", "data science",
    "statistical analysis", "a/b testing", "experimentation",
}

PROGRAMMING_SKILLS = {
    # Languages
    "python", "javascript", "typescript", "java", "go", "golang", "rust", "c++", "c#",
    "scala", "kotlin", "ruby", "php", "swift", "r", "sql",

    # Web Frameworks
    "react", "vue", "angular", "next.js", "nextjs", "node.js", "nodejs", "express",
    "fastapi", "flask", "django", "spring", "rails", "svelte",

    # APIs & Integration
    "rest", "restful", "graphql", "grpc", "websockets", "api design", "api development",
    "openapi", "swagger", "api integration", "sdk", "webhooks",

    # Data Structures
    "data structures", "algorithms", "system design", "software architecture",
    "microservices", "distributed systems", "event-driven",

    # Development Practices
    "full-stack", "full stack", "backend", "frontend", "production code",
    "code review", "testing", "unit testing", "integration testing",
    "git", "version control", "agile development",
}

CLOUD_DEVOPS = {
    # Cloud Platforms
    "aws", "amazon web services", "gcp", "google cloud", "azure", "microsoft azure",
    "cloud infrastructure", "cloud native", "multi-cloud", "hybrid cloud",

    # Cloud Services
    "ec2", "s3", "lambda", "ecs", "eks", "rds", "dynamodb", "cloudformation",
    "bigquery", "cloud functions", "cloud run", "gke", "serverless",
    "api gateway", "sqs", "sns", "kinesis", "eventbridge",

    # Containers & Orchestration
    "docker", "kubernetes", "k8s", "helm", "terraform", "ansible", "jenkins",
    "ci/cd", "github actions", "gitlab ci", "circleci", "argocd",
    "infrastructure as code", "iac", "devops",

    # Databases
    "postgresql", "postgres", "mysql", "mongodb", "redis", "elasticsearch",
    "pinecone", "weaviate", "chroma", "qdrant", "milvus", "sql", "nosql",
    "vector database", "graph database", "neo4j", "snowflake", "redshift",

    # Observability
    "monitoring", "logging", "observability", "datadog", "splunk", "grafana",
    "prometheus", "new relic", "cloudwatch",
}

SOFT_SKILLS = {
    # Communication
    "communication", "presentation", "public speaking", "technical writing",
    "documentation", "storytelling", "executive presence",

    # Customer Facing
    "customer-facing", "client-facing", "stakeholder management",
    "customer engagement", "customer success", "customer relationships",
    "discovery", "requirements gathering", "needs assessment",

    # Problem Solving
    "problem solving", "problem-solving", "analytical", "critical thinking",
    "troubleshooting", "debugging", "root cause analysis",

    # Collaboration
    "collaboration", "teamwork", "cross-functional", "agile", "scrum",
    "leadership", "mentoring", "coaching", "influence",

    # Traits
    "high agency", "autonomy", "self-starter", "entrepreneurial",
    "ambiguity", "fast-paced", "adaptable", "resourceful",
}

FDE_SPECIFIC = {
    # Role Terms
    "forward deployed", "forward-deployed", "forward deploy", "forward deployment",
    "field engineer", "solutions engineer",
    "solutions architect", "technical account manager", "customer engineer",
    "professional services", "consulting", "technical consulting",

    # Activities
    "implementation", "integration", "deployment", "onboarding",
    "proof of concept", "poc", "pilot", "demo", "demonstration",
    "prototype", "prototyping", "mvp", "technical discovery",
    "white glove", "hands-on", "embedded", "on-site",

    # Sales & Business
    "enterprise", "enterprise sales", "technical sales", "pre-sales", "post-sales",
    "enterprise customers", "strategic customers", "key accounts",
    "revenue", "expansion", "upsell", "land and expand",

    # Domain Knowledge
    "use case", "use cases", "workflow", "workflows", "business process",
    "domain expertise", "industry knowledge", "vertical",
    "financial services", "healthcare", "life sciences", "fintech",

    # Delivery
    "production", "production environment", "production workflows",
    "customer requirements", "technical requirements", "solution design",
    "architecture review", "code review", "best practices",
    "deployment patterns", "reference architecture", "playbook",
}

DATA_PIPELINES = {
    # Data Engineering
    "data engineering", "data pipelines", "etl", "elt", "data warehouse",
    "data lake", "data mesh", "data modeling", "dbt",

    # Streaming
    "kafka", "apache kafka", "spark", "apache spark", "flink", "airflow",
    "streaming", "real-time", "batch processing",

    # Analytics
    "analytics", "business intelligence", "bi", "dashboards", "reporting",
    "looker", "tableau", "power bi", "metabase",
}

ALL_SKILLS = {
    "ai_ml": AI_ML_KEYWORDS,
    "programming": PROGRAMMING_SKILLS,
    "cloud_devops": CLOUD_DEVOPS,
    "soft_skills": SOFT_SKILLS,
    "fde_specific": FDE_SPECIFIC,
    "data_pipelines": DATA_PIPELINES,
}


class SkillExtractor:
    def __init__(self):
        # Build a flat lookup for faster matching
        self.skill_to_category = {}
        for category, skills in ALL_SKILLS.items():
            for skill in skills:
                self.skill_to_category[skill.lower()] = category

        # Compile regex patterns for each skill
        self.patterns = {}
        for skill in self.skill_to_category.keys():
            # Word boundary pattern to match whole words
            pattern = r'\b' + re.escape(skill) + r'\b'
            self.patterns[skill] = re.compile(pattern, re.IGNORECASE)

    def extract_skills(self, text: str) -> Dict[str, List[str]]:
        """Extract skills from text and categorize them."""
        if not text:
            return {cat: [] for cat in ALL_SKILLS.keys()}

        text_lower = text.lower()
        found_skills = {cat: set() for cat in ALL_SKILLS.keys()}

        for skill, pattern in self.patterns.items():
            if pattern.search(text_lower):
                category = self.skill_to_category[skill]
                found_skills[category].add(skill)

        # Convert sets to sorted lists
        return {cat: sorted(list(skills)) for cat, skills in found_skills.items()}

    def extract_all_keywords(self, text: str) -> List[Tuple[str, str, int]]:
        """Extract all keywords with their categories and counts."""
        if not text:
            return []

        text_lower = text.lower()
        results = []

        for skill, pattern in self.patterns.items():
            matches = pattern.findall(text_lower)
            if matches:
                category = self.skill_to_category[skill]
                results.append((skill, category, len(matches)))

        return sorted(results, key=lambda x: (-x[2], x[0]))

    def get_skill_frequencies(self, jobs: List[str]) -> Dict[str, Dict[str, int]]:
        """Get frequency of each skill across multiple job descriptions."""
        category_counts = {cat: Counter() for cat in ALL_SKILLS.keys()}

        for job_text in jobs:
            skills = self.extract_skills(job_text)
            for category, skill_list in skills.items():
                for skill in skill_list:
                    category_counts[category][skill] += 1

        return {cat: dict(counts.most_common()) for cat, counts in category_counts.items()}


class JobSectionParser:
    """Parse job descriptions into structured sections."""

    SECTION_PATTERNS = {
        "responsibilities": [
            r"(?:what you'll do|responsibilities|your role|the role|you will|your day|key responsibilities|job duties|duties and responsibilities)[:\s]*",
            r"(?:in this role|as a .+?, you will)[:\s]*",
        ],
        "qualifications": [
            r"(?:requirements|qualifications|what we're looking for|who you are|you have|you bring|must have|required skills|minimum qualifications|basic qualifications)[:\s]*",
            r"(?:we're looking for|ideal candidate|you should have)[:\s]*",
        ],
        "nice_to_have": [
            r"(?:nice to have|bonus|preferred|plus|ideally|it's a plus|extra credit|preferred qualifications|desired skills)[:\s]*",
            r"(?:you might also have|additional skills|not required but)[:\s]*",
        ],
        "about_role": [
            r"(?:about the role|the opportunity|overview|about this position|position summary)[:\s]*",
        ],
        "about_company": [
            r"(?:about us|about the company|who we are|our company|company description|about .+? company)[:\s]*",
        ],
    }

    def __init__(self):
        self.compiled_patterns = {}
        for section, patterns in self.SECTION_PATTERNS.items():
            self.compiled_patterns[section] = [
                re.compile(p, re.IGNORECASE | re.MULTILINE)
                for p in patterns
            ]

    def parse_sections(self, text: str) -> Dict[str, str]:
        """Parse job description into sections."""
        if not text:
            return {}

        sections = {}
        text_lower = text.lower()

        # Find all section boundaries
        boundaries = []
        for section, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    boundaries.append((match.start(), match.end(), section))

        # Sort by position
        boundaries.sort(key=lambda x: x[0])

        # Extract content between boundaries
        for i, (start, end, section) in enumerate(boundaries):
            # Get end position (next boundary or end of text)
            next_start = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
            content = text[end:next_start].strip()

            # Clean up the content
            content = self._clean_section(content)

            if content and (section not in sections or len(content) > len(sections[section])):
                sections[section] = content

        return sections

    def _clean_section(self, text: str) -> str:
        """Clean up section text."""
        # Remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)

        # Remove common noise
        text = re.sub(r'^\s*[-•*]\s*', '', text, flags=re.MULTILINE)

        return text.strip()

    def extract_bullet_points(self, text: str) -> List[str]:
        """Extract bullet points from text."""
        if not text:
            return []

        # Match various bullet point formats
        bullet_pattern = r'(?:^|\n)\s*(?:[-•*▪◦]|\d+[.)]\s*|\([a-z]\))\s*(.+?)(?=\n\s*(?:[-•*▪◦]|\d+[.)]|\([a-z]\))|$)'
        matches = re.findall(bullet_pattern, text, re.MULTILINE | re.DOTALL)

        return [m.strip() for m in matches if m.strip()]


# Initialize global instances
skill_extractor = SkillExtractor()
section_parser = JobSectionParser()
