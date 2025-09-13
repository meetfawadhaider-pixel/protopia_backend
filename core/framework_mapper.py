import re

# Define sample traits/keywords per framework
framework_keywords = {
    "Big Five Personality Traits": {
        "openness": ["creative", "open-minded", "explore", "ideas"],
        "conscientiousness": ["responsible", "organize", "plan", "goal"],
        "extraversion": ["talk", "social", "team", "lead"],
        "agreeableness": ["cooperate", "friendly", "help", "support"],
        "neuroticism": ["stress", "anxiety", "nervous", "worried"],
    },
    "Emotional Intelligence": ["empathy", "empathize", "emotion", "understand", "listen", "self-aware", "control"],
    "Transformational Leadership": ["inspire", "vision", "motivate", "change", "growth", "empower"],
    "Moral Foundations": ["fair", "justice", "care", "harm", "loyalty", "authority", "purity"],
    "Kohlberg’s Moral Development": ["rule", "obey", "law", "social contract", "universal", "justice"],
    "Dark Triad": ["manipulate", "narcissist", "deceive", "control", "ego"],
    "Servant Leadership": ["serve", "humble", "team", "support", "selfless"],
    "Rest’s Model": ["moral awareness", "judgment", "intent", "action"],
    "Situational Leadership": ["adapt", "flexible", "delegate", "directive", "supportive"],
    "Leadership Competency": ["problem-solving", "decision", "communication", "feedback", "accountability"]
}

def analyze_frameworks(text):
    response_summary = {}
    text = text.lower()

    for framework, criteria in framework_keywords.items():
        if isinstance(criteria, dict):  # For Big Five subcategories
            sub_results = {}
            for trait, words in criteria.items():
                hits = [word for word in words if re.search(rf'\b{word}\b', text)]
                if hits:
                    sub_results[trait] = hits
            if sub_results:
                response_summary[framework] = sub_results
        else:
            hits = [word for word in criteria if re.search(rf'\b{word}\b', text)]
            if hits:
                response_summary[framework] = hits

    return response_summary
