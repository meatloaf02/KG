"""
Entity lexicons for mention extraction (NOR-107, NOR-109).

Contains dictionaries mapping surface forms to normalized entity IDs
for products, capabilities, and risk topics.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class EntityMatch:
    """A matched entity in text."""

    entity_id: str
    entity_type: str  # "capability", "product", "risk"
    name: str
    normalized_name: str
    category: Optional[str]
    match_text: str
    start_char: int
    end_char: int
    confidence: float = 1.0


# =============================================================================
# AI/ML Capability Lexicon (NOR-107)
# =============================================================================

# Map surface forms -> (entity_id, canonical_name, category)
AI_CAPABILITY_LEXICON = {
    # Artificial Intelligence (broad)
    "artificial intelligence": ("ai", "Artificial Intelligence", "artificial_intelligence"),
    "ai": ("ai", "Artificial Intelligence", "artificial_intelligence"),
    "a.i.": ("ai", "Artificial Intelligence", "artificial_intelligence"),
    "ai-powered": ("ai", "Artificial Intelligence", "artificial_intelligence"),
    "ai-driven": ("ai", "Artificial Intelligence", "artificial_intelligence"),
    "ai-enabled": ("ai", "Artificial Intelligence", "artificial_intelligence"),
    "ai-based": ("ai", "Artificial Intelligence", "artificial_intelligence"),

    # Machine Learning
    "machine learning": ("ml", "Machine Learning", "machine_learning"),
    "ml": ("ml", "Machine Learning", "machine_learning"),
    "ml-powered": ("ml", "Machine Learning", "machine_learning"),
    "ml-based": ("ml", "Machine Learning", "machine_learning"),
    "machine-learning": ("ml", "Machine Learning", "machine_learning"),

    # Deep Learning
    "deep learning": ("deep-learning", "Deep Learning", "machine_learning"),
    "deep-learning": ("deep-learning", "Deep Learning", "machine_learning"),
    "neural network": ("deep-learning", "Deep Learning", "machine_learning"),
    "neural networks": ("deep-learning", "Deep Learning", "machine_learning"),

    # Natural Language Processing
    "natural language processing": ("nlp", "Natural Language Processing", "artificial_intelligence"),
    "nlp": ("nlp", "Natural Language Processing", "artificial_intelligence"),
    "natural language understanding": ("nlp", "Natural Language Processing", "artificial_intelligence"),
    "nlu": ("nlp", "Natural Language Processing", "artificial_intelligence"),
    "text analytics": ("nlp", "Natural Language Processing", "artificial_intelligence"),
    "sentiment analysis": ("nlp", "Natural Language Processing", "artificial_intelligence"),

    # Generative AI / LLMs
    "generative ai": ("generative-ai", "Generative AI", "artificial_intelligence"),
    "generative artificial intelligence": ("generative-ai", "Generative AI", "artificial_intelligence"),
    "gen ai": ("generative-ai", "Generative AI", "artificial_intelligence"),
    "genai": ("generative-ai", "Generative AI", "artificial_intelligence"),
    "large language model": ("llm", "Large Language Model", "artificial_intelligence"),
    "large language models": ("llm", "Large Language Model", "artificial_intelligence"),
    "llm": ("llm", "Large Language Model", "artificial_intelligence"),
    "llms": ("llm", "Large Language Model", "artificial_intelligence"),
    "gpt": ("llm", "Large Language Model", "artificial_intelligence"),
    "chatgpt": ("llm", "Large Language Model", "artificial_intelligence"),
    "foundation model": ("llm", "Large Language Model", "artificial_intelligence"),
    "foundation models": ("llm", "Large Language Model", "artificial_intelligence"),

    # Predictive Analytics
    "predictive analytics": ("predictive-analytics", "Predictive Analytics", "analytics"),
    "predictive analysis": ("predictive-analytics", "Predictive Analytics", "analytics"),
    "predictive modeling": ("predictive-analytics", "Predictive Analytics", "analytics"),
    "predictive models": ("predictive-analytics", "Predictive Analytics", "analytics"),
    "forecasting": ("predictive-analytics", "Predictive Analytics", "analytics"),

    # Automation
    "automation": ("automation", "Automation", "automation"),
    "automated": ("automation", "Automation", "automation"),
    "automate": ("automation", "Automation", "automation"),
    "robotic process automation": ("automation", "Automation", "automation"),
    "rpa": ("automation", "Automation", "automation"),
    "intelligent automation": ("automation", "Automation", "automation"),
    "workflow automation": ("automation", "Automation", "automation"),

    # Computer Vision
    "computer vision": ("computer-vision", "Computer Vision", "artificial_intelligence"),
    "image recognition": ("computer-vision", "Computer Vision", "artificial_intelligence"),
    "object detection": ("computer-vision", "Computer Vision", "artificial_intelligence"),

    # Recommendation Systems
    "recommendation engine": ("recommendations", "Recommendations", "machine_learning"),
    "recommendation system": ("recommendations", "Recommendations", "machine_learning"),
    "recommendations": ("recommendations", "Recommendations", "machine_learning"),
    "personalization": ("recommendations", "Recommendations", "machine_learning"),
    "personalized": ("recommendations", "Recommendations", "machine_learning"),

    # Anomaly Detection
    "anomaly detection": ("anomaly-detection", "Anomaly Detection", "machine_learning"),
    "fraud detection": ("anomaly-detection", "Anomaly Detection", "machine_learning"),
    "outlier detection": ("anomaly-detection", "Anomaly Detection", "machine_learning"),

    # Chatbots / Conversational AI
    "chatbot": ("conversational-ai", "Conversational AI", "artificial_intelligence"),
    "chatbots": ("conversational-ai", "Conversational AI", "artificial_intelligence"),
    "virtual assistant": ("conversational-ai", "Conversational AI", "artificial_intelligence"),
    "conversational ai": ("conversational-ai", "Conversational AI", "artificial_intelligence"),
    "voice assistant": ("conversational-ai", "Conversational AI", "artificial_intelligence"),
}

# =============================================================================
# Workday Product Lexicon (NOR-109)
# =============================================================================

# Map surface forms -> (entity_id, canonical_name, description)
PRODUCT_LEXICON = {
    # HCM
    "workday hcm": ("workday-hcm", "Workday Human Capital Management", "HR suite"),
    "workday human capital management": ("workday-hcm", "Workday Human Capital Management", "HR suite"),
    "human capital management": ("workday-hcm", "Workday Human Capital Management", "HR suite"),
    "hcm": ("workday-hcm", "Workday Human Capital Management", "HR suite"),

    # Financials
    "workday financials": ("workday-financials", "Workday Financial Management", "Financial suite"),
    "workday financial management": ("workday-financials", "Workday Financial Management", "Financial suite"),
    "financial management": ("workday-financials", "Workday Financial Management", "Financial suite"),

    # Payroll
    "workday payroll": ("workday-payroll", "Workday Payroll", "Payroll"),
    "payroll": ("workday-payroll", "Workday Payroll", "Payroll"),

    # Planning / Adaptive
    "workday adaptive planning": ("workday-planning", "Workday Adaptive Planning", "Planning"),
    "adaptive planning": ("workday-planning", "Workday Adaptive Planning", "Planning"),
    "workday planning": ("workday-planning", "Workday Adaptive Planning", "Planning"),
    "adaptive insights": ("workday-planning", "Workday Adaptive Planning", "Planning"),

    # Recruiting
    "workday recruiting": ("workday-recruiting", "Workday Recruiting", "Talent acquisition"),
    "recruiting": ("workday-recruiting", "Workday Recruiting", "Talent acquisition"),
    "talent acquisition": ("workday-recruiting", "Workday Recruiting", "Talent acquisition"),

    # Learning
    "workday learning": ("workday-learning", "Workday Learning", "LMS"),
    "learning management": ("workday-learning", "Workday Learning", "LMS"),

    # Prism Analytics
    "workday prism analytics": ("workday-prism", "Workday Prism Analytics", "Analytics"),
    "prism analytics": ("workday-prism", "Workday Prism Analytics", "Analytics"),
    "prism": ("workday-prism", "Workday Prism Analytics", "Analytics"),

    # Peakon
    "workday peakon": ("workday-peakon", "Workday Peakon Employee Voice", "Engagement"),
    "peakon": ("workday-peakon", "Workday Peakon Employee Voice", "Engagement"),
    "employee voice": ("workday-peakon", "Workday Peakon Employee Voice", "Engagement"),
    "peakon employee voice": ("workday-peakon", "Workday Peakon Employee Voice", "Engagement"),

    # VNDLY
    "vndly": ("workday-vndly", "Workday VNDLY", "Vendor management"),
    "workday vndly": ("workday-vndly", "Workday VNDLY", "Vendor management"),

    # Extend
    "workday extend": ("workday-extend", "Workday Extend", "Platform"),
    "extend": ("workday-extend", "Workday Extend", "Platform"),

    # Scout RFP (acquired)
    "scout rfp": ("workday-scout", "Workday Strategic Sourcing", "Sourcing"),
    "workday strategic sourcing": ("workday-scout", "Workday Strategic Sourcing", "Sourcing"),

    # Spend Management
    "workday spend management": ("workday-spend", "Workday Spend Management", "Procurement"),
    "spend management": ("workday-spend", "Workday Spend Management", "Procurement"),

    # Talent Management
    "workday talent management": ("workday-talent", "Workday Talent Management", "Talent"),
    "talent management": ("workday-talent", "Workday Talent Management", "Talent"),
    "talent optimization": ("workday-talent", "Workday Talent Management", "Talent"),

    # Time Tracking
    "workday time tracking": ("workday-time", "Workday Time Tracking", "Time"),
    "time tracking": ("workday-time", "Workday Time Tracking", "Time"),

    # Expenses
    "workday expenses": ("workday-expenses", "Workday Expenses", "Expenses"),
    "expense management": ("workday-expenses", "Workday Expenses", "Expenses"),
}

# =============================================================================
# Risk Topic Lexicon (NOR-108)
# =============================================================================

# Map surface forms -> (entity_id, canonical_name, category)
RISK_LEXICON = {
    # Cybersecurity
    "cybersecurity": ("cybersecurity-risk", "Cybersecurity Risk", "cybersecurity"),
    "cyber security": ("cybersecurity-risk", "Cybersecurity Risk", "cybersecurity"),
    "cyber attack": ("cybersecurity-risk", "Cybersecurity Risk", "cybersecurity"),
    "cyberattack": ("cybersecurity-risk", "Cybersecurity Risk", "cybersecurity"),
    "cyber threat": ("cybersecurity-risk", "Cybersecurity Risk", "cybersecurity"),
    "security breach": ("cybersecurity-risk", "Cybersecurity Risk", "cybersecurity"),
    "security incident": ("cybersecurity-risk", "Cybersecurity Risk", "cybersecurity"),
    "ransomware": ("cybersecurity-risk", "Cybersecurity Risk", "cybersecurity"),
    "malware": ("cybersecurity-risk", "Cybersecurity Risk", "cybersecurity"),
    "phishing": ("cybersecurity-risk", "Cybersecurity Risk", "cybersecurity"),

    # Data Breach
    "data breach": ("data-breach", "Data Breach", "cybersecurity"),
    "data breaches": ("data-breach", "Data Breach", "cybersecurity"),
    "unauthorized access": ("data-breach", "Data Breach", "cybersecurity"),
    "data theft": ("data-breach", "Data Breach", "cybersecurity"),
    "data loss": ("data-breach", "Data Breach", "cybersecurity"),
    "personal data": ("data-breach", "Data Breach", "cybersecurity"),
    "personally identifiable information": ("data-breach", "Data Breach", "cybersecurity"),
    "pii": ("data-breach", "Data Breach", "cybersecurity"),

    # Regulatory Compliance
    "regulatory compliance": ("regulatory-compliance", "Regulatory Compliance", "regulatory"),
    "compliance requirements": ("regulatory-compliance", "Regulatory Compliance", "regulatory"),
    "regulatory requirements": ("regulatory-compliance", "Regulatory Compliance", "regulatory"),
    "gdpr": ("regulatory-compliance", "Regulatory Compliance", "regulatory"),
    "ccpa": ("regulatory-compliance", "Regulatory Compliance", "regulatory"),
    "sox": ("regulatory-compliance", "Regulatory Compliance", "regulatory"),
    "sarbanes-oxley": ("regulatory-compliance", "Regulatory Compliance", "regulatory"),
    "hipaa": ("regulatory-compliance", "Regulatory Compliance", "regulatory"),
    "regulatory changes": ("regulatory-compliance", "Regulatory Compliance", "regulatory"),
    "compliance risk": ("regulatory-compliance", "Regulatory Compliance", "regulatory"),

    # Competition
    "competition": ("competition-risk", "Competition Risk", "competition"),
    "competitive pressure": ("competition-risk", "Competition Risk", "competition"),
    "competitive landscape": ("competition-risk", "Competition Risk", "competition"),
    "competitors": ("competition-risk", "Competition Risk", "competition"),
    "market competition": ("competition-risk", "Competition Risk", "competition"),
    "competitive threat": ("competition-risk", "Competition Risk", "competition"),

    # AI Ethics
    "ai ethics": ("ai-ethics", "AI Ethics and Bias", "technology"),
    "algorithmic bias": ("ai-ethics", "AI Ethics and Bias", "technology"),
    "ai bias": ("ai-ethics", "AI Ethics and Bias", "technology"),
    "model bias": ("ai-ethics", "AI Ethics and Bias", "technology"),
    "fairness": ("ai-ethics", "AI Ethics and Bias", "technology"),
    "responsible ai": ("ai-ethics", "AI Ethics and Bias", "technology"),
    "ethical ai": ("ai-ethics", "AI Ethics and Bias", "technology"),
    "ai governance": ("ai-ethics", "AI Ethics and Bias", "technology"),

    # System Outage / Reliability
    "system outage": ("system-reliability", "System Reliability Risk", "operational"),
    "service disruption": ("system-reliability", "System Reliability Risk", "operational"),
    "downtime": ("system-reliability", "System Reliability Risk", "operational"),
    "system failure": ("system-reliability", "System Reliability Risk", "operational"),
    "service availability": ("system-reliability", "System Reliability Risk", "operational"),
    "business continuity": ("system-reliability", "System Reliability Risk", "operational"),
    "disaster recovery": ("system-reliability", "System Reliability Risk", "operational"),

    # Economic / Market
    "economic downturn": ("economic-risk", "Economic Risk", "market"),
    "recession": ("economic-risk", "Economic Risk", "market"),
    "market volatility": ("economic-risk", "Economic Risk", "market"),
    "economic uncertainty": ("economic-risk", "Economic Risk", "market"),
    "macroeconomic": ("economic-risk", "Economic Risk", "market"),

    # Talent / Workforce
    "talent retention": ("talent-risk", "Talent Risk", "talent"),
    "employee retention": ("talent-risk", "Talent Risk", "talent"),
    "talent acquisition": ("talent-risk", "Talent Risk", "talent"),
    "labor shortage": ("talent-risk", "Talent Risk", "talent"),
    "workforce": ("talent-risk", "Talent Risk", "talent"),
    "key personnel": ("talent-risk", "Talent Risk", "talent"),

    # Integration / Technology
    "integration risk": ("integration-risk", "Integration Risk", "technology"),
    "system integration": ("integration-risk", "Integration Risk", "technology"),
    "technology integration": ("integration-risk", "Integration Risk", "technology"),
    "legacy systems": ("integration-risk", "Integration Risk", "technology"),
    "technical debt": ("integration-risk", "Integration Risk", "technology"),
}


def get_all_lexicons() -> dict[str, dict]:
    """Return all lexicons for entity matching."""
    return {
        "capability": AI_CAPABILITY_LEXICON,
        "product": PRODUCT_LEXICON,
        "risk": RISK_LEXICON,
    }


def get_entity_ids_by_type(entity_type: str) -> set[str]:
    """Get all unique entity IDs for a given type."""
    lexicons = get_all_lexicons()
    if entity_type not in lexicons:
        return set()

    return {v[0] for v in lexicons[entity_type].values()}
