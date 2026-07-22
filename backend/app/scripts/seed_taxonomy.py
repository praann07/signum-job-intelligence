"""Seed the skill taxonomy with a broad, curated real-world skill list.

Run:  python -m app.scripts.seed_taxonomy
Idempotent: existing skills are skipped.
"""

from __future__ import annotations

from app.infrastructure.database.models import SkillTaxonomy
from app.infrastructure.database.session import async_session_factory

# (skill, category, [aliases])
SEED: list[tuple[str, str, list[str]]] = [
    # Languages / Frameworks
    ("Rust", "language", ["rust lang", "rustlang"]),
    ("Kotlin", "language", []),
    ("Java", "language", ["java se", "java ee"]),
    ("C++", "language", ["cpp", "cplusplus"]),
    ("C#", "language", ["csharp", "c sharp"]),
    ("PHP", "language", []),
    ("Ruby", "language", []),
    ("Scala", "language", []),
    ("Go", "language", ["golang"]),
    ("Swift", "language", []),
    ("JavaScript", "language", ["js", "ecmascript"]),
    ("TypeScript", "language", ["ts"]),
    ("Python", "language", ["py"]),
    ("Vue.js", "framework", ["vue", "vuejs"]),
    ("Svelte", "framework", []),
    ("Angular", "framework", []),
    ("Django", "framework", []),
    ("Flask", "framework", []),
    ("FastAPI", "framework", []),
    ("Spring Boot", "framework", ["spring", "springboot"]),
    (".NET", "framework", ["dotnet", "dot net"]),
    ("Node.js", "framework", ["node", "nodejs"]),
    ("Express.js", "framework", ["express", "expressjs"]),
    ("Solidity", "language", []),
    # Data / ML
    ("PyTorch", "framework", ["torch"]),
    ("TensorFlow", "framework", ["tf"]),
    ("scikit-learn", "tool", ["sklearn", "scikit learn"]),
    ("pandas", "tool", []),
    ("NumPy", "tool", ["numpy"]),
    ("Hugging Face", "tool", ["huggingface", "hf"]),
    ("spaCy", "tool", ["spacy"]),
    ("NLTK", "tool", []),
    ("MLOps", "concept", ["ml ops", "ml-ops"]),
    ("LLM Ops", "concept", ["llmops"]),
    ("vector databases", "concept", ["vector db", "vectordb"]),
    ("Pinecone", "tool", []),
    ("Weaviate", "tool", []),
    ("FAISS", "tool", []),
    ("prompt engineering", "concept", ["prompt eng"]),
    ("fine-tuning", "concept", ["finetuning", "fine tuning"]),
    ("Airbyte", "tool", []),
    ("dbt", "tool", []),
    ("Snowflake", "database", []),
    ("BigQuery", "database", ["big query"]),
    ("Databricks", "tool", []),
    ("Apache Kafka", "tool", ["kafka"]),
    ("Apache Flink", "tool", ["flink"]),
    ("Hadoop", "tool", []),
    ("Tableau", "tool", []),
    ("Power BI", "tool", ["powerbi"]),
    ("Looker", "tool", []),
    ("MATLAB", "tool", []),
    ("R", "language", []),
    # Cloud / DevOps / Infra
    ("Ansible", "tool", []),
    ("Jenkins", "tool", []),
    ("GitHub Actions", "tool", ["github actions"]),
    ("GitLab CI", "tool", ["gitlab ci", "gitlab-ci"]),
    ("CircleCI", "tool", []),
    ("Helm", "tool", []),
    ("Prometheus", "tool", []),
    ("Grafana", "tool", []),
    ("Istio", "tool", []),
    ("Nginx", "tool", ["nginx"]),
    ("ELK stack", "tool", ["elk", "elasticsearch logstash kibana"]),
    ("Datadog", "tool", []),
    ("New Relic", "tool", []),
    ("Vault", "tool", ["hashicorp vault"]),
    ("OpenTofu", "tool", ["opentofu"]),
    ("CloudFormation", "tool", []),
    ("Pulumi", "tool", []),
    ("serverless", "concept", []),
    ("edge computing", "concept", ["edge"]),
    ("AWS", "cloud", ["amazon web services"]),
    ("Azure", "cloud", []),
    ("GCP", "cloud", ["google cloud"]),
    # Databases
    ("MySQL", "database", []),
    ("MongoDB", "database", ["mongo"]),
    ("Cassandra", "database", []),
    ("DynamoDB", "database", ["dynamodb"]),
    ("Elasticsearch", "database", ["elastic search"]),
    ("Neo4j", "database", []),
    ("ClickHouse", "database", []),
    ("DuckDB", "database", ["duckdb"]),
    ("TimescaleDB", "database", ["timescaledb"]),
    ("CockroachDB", "database", ["cockroachdb"]),
    ("SQLite", "database", ["sqlite"]),
    ("PostgreSQL", "database", ["postgres", "postgresql"]),
    ("Redis", "database", []),
    ("SQL", "language", ["sql"]),
    # Mobile / Frontend
    ("SwiftUI", "framework", []),
    ("Jetpack Compose", "framework", ["jetpack compose"]),
    ("React Native", "framework", ["react-native", "reactnative"]),
    ("Ionic", "framework", []),
    ("Figma", "tool", []),
    ("Sketch", "tool", []),
    ("Webflow", "tool", []),
    ("accessibility", "concept", ["a11y", "accessibility"]),
    ("design systems", "concept", ["design system"]),
    ("WebGL", "framework", []),
    ("React", "framework", []),
    ("Tailwind", "framework", ["tailwindcss", "tailwind css"]),
    ("HTML", "language", ["html"]),
    ("CSS", "language", ["css"]),
    ("GraphQL", "framework", []),
    ("Next.js", "framework", ["nextjs"]),
    ("REST", "concept", ["rest api", "restful"]),
    # Security
    ("penetration testing", "concept", ["pentest", "pen testing"]),
    ("SOC 2", "concept", ["soc2", "soc 2"]),
    ("ISO 27001", "concept", ["iso27001"]),
    ("IAM", "concept", ["identity and access management"]),
    ("SIEM", "tool", []),
    ("zero trust", "concept", ["zerotrust", "zero-trust"]),
    ("incident response", "concept", []),
    ("threat modeling", "concept", []),
    ("OWASP", "concept", []),
    ("SAST", "tool", []),
    ("DAST", "tool", []),
    ("Zero Trust", "concept", ["zero trust"]),
    # Business / Ops
    ("project management", "concept", ["pm"]),
    ("Scrum", "concept", []),
    ("Agile", "concept", []),
    ("Jira", "tool", []),
    ("Confluence", "tool", []),
    ("Asana", "tool", []),
    ("Notion", "tool", []),
    ("Salesforce", "tool", []),
    ("HubSpot", "tool", []),
    ("SAP", "tool", []),
    ("Oracle ERP", "tool", ["oracle"]),
    ("GDPR", "concept", []),
    # Marketing / Growth
    ("SEO", "concept", []),
    ("SEM", "concept", []),
    ("Google Ads", "tool", ["google adwords"]),
    ("Meta Ads", "tool", ["facebook ads"]),
    ("growth hacking", "concept", []),
    ("Mailchimp", "tool", []),
    ("A/B testing", "concept", ["ab testing"]),
    ("conversion rate optimization", "concept", ["cro"]),
    # Emerging / Niche
    ("blockchain", "concept", []),
    ("Web3", "concept", ["web 3"]),
    ("smart contracts", "concept", []),
    ("AR/VR", "concept", ["arvr", "ar vr"]),
    ("Unity", "tool", []),
    ("Unreal Engine", "tool", ["unreal"]),
    ("robotics", "concept", []),
    ("IoT", "concept", ["internet of things"]),
    ("embedded systems", "concept", ["embedded"]),
    ("quantum computing", "concept", ["quantum"]),
    ("bioinformatics", "concept", ["bioinformatics", "bio informatics"]),
    ("CI/CD", "concept", ["ci cd", "cicd"]),
    ("Docker", "tool", []),
    ("Kubernetes", "tool", ["k8s"]),
    ("Terraform", "tool", []),
    ("Linux", "tool", []),
    ("Git", "tool", []),
    ("LLM", "concept", ["llm", "large language model"]),
    ("LangChain", "framework", []),
    ("RAG", "concept", ["retrieval augmented generation"]),
    ("Airflow", "tool", []),
    ("Spark", "tool", ["apache spark"]),
    ("Flutter", "framework", []),
    ("Android", "framework", []),
    ("iOS", "framework", []),
    ("UI/UX", "concept", ["ui ux", "uiux"]),
    ("CRM", "tool", []),
]

CATEGORY_FIX = {
    "language": "language",
    "framework": "framework",
    "tool": "tool",
    "cloud": "cloud",
    "database": "database",
    "concept": "concept",
    "platform": "platform",
}


async def seed() -> None:
    added = 0
    async with async_session_factory() as session:
        # ponytail: load existing once to make the insert idempotent.
        from sqlalchemy import select

        existing = set(r[0] for r in (await session.execute(select(SkillTaxonomy.skill))).all())
        for skill, cat, aliases in SEED:
            if skill in existing:
                continue
            # normalize category to an allowed enum value
            cat = CATEGORY_FIX.get(cat, "tool")
            session.add(
                SkillTaxonomy(
                    skill=skill,
                    category=cat,
                    aliases=aliases,
                    is_active=True,
                    added_by="seed",
                )
            )
            added += 1
        await session.commit()
    print(f"seeded {added} new skills ({len(SEED) - added} already present)")


if __name__ == "__main__":
    import asyncio

    asyncio.run(seed())
