import re
from knowledge_base import KNOWLEDGE_BASE



# Text preprocessing
def preprocess_text(text: str) -> str:
    """
    Normalize user input before matching.
    """

    text = text.lower()

    # Remove special characters
    text = re.sub(r"[^a-z0-9\s.-]", " ", text)

    # Remove extra spaces
    text = re.sub(r"\s+", " ", text).strip()

    return text



# Keyword matching


def keyword_matches(question: str, keywords: list[str]) -> list[str]:
    """
    Find keywords/phrases that appear in the user's question.
    """

    question = preprocess_text(question)

    matched = []

    for keyword in keywords:

        keyword = preprocess_text(keyword)

        if not keyword:
            continue

        # Phrase matching
        if keyword in question:
            matched.append(keyword)

    return matched



# Calculate keyword scor
def calculate_score(
    question: str,
    keywords: list[str]
) -> tuple[int, list[str]]:
    """
    Calculate how strongly an intent matches the question.

    Multi-word phrases receive more weight because they are
    generally more specific than single generic words.
    """

    matched_keywords = keyword_matches(
        question,
        keywords
    )

    score = 0

    for keyword in matched_keywords:

        # Specific phrases are more valuable
        if " " in keyword:

            # Number of words in the phrase
            word_count = len(keyword.split())

            score += 2 + word_count

        else:

            # Single keyword
            score += 1

    return score, matched_keywords


def find_intent(question: str):
    """
    Find the best matching intent from the knowledge base.

    The matcher compares all intents and returns the strongest
    candidate along with a confidence score.
    """

    question = preprocess_text(question)

    if not question:
        return {
            "intent": None,
            "confidence": 0.0,
            "matched_keywords": [],
            "answer": None
        }

    intent_scores = []

    # Calculate score for every intent

    for intent, data in KNOWLEDGE_BASE.items():

        score, matched_keywords = calculate_score(
            question,
            data["keywords"]
        )

        if score > 0:

            intent_scores.append({
                "intent": intent,
                "score": score,
                "matched_keywords": matched_keywords
            })

    
    # Nothing matched
    if not intent_scores:

        return {
            "intent": None,
            "confidence": 0.0,
            "matched_keywords": [],
            "answer": None
        }

    
    # Sort intents by score
    intent_scores.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    best = intent_scores[0]

    # Second-best score
    second_score = (
        intent_scores[1]["score"]
        if len(intent_scores) > 1
        else 0
    )

    best_score = best["score"]

    # Confidence calculation
    confidence = min(
        best_score / 4,
        1.0
    )

    # Ambiguous match protection
    if second_score > 0:

        score_difference = best_score - second_score

        if score_difference == 0:

            confidence *= 0.5

        elif score_difference == 1:

            confidence *= 0.75

    confidence = round(confidence, 2)
    # Return result

    return {
        "intent": best["intent"],
        "confidence": confidence,
        "matched_keywords": best["matched_keywords"],
        "answer": KNOWLEDGE_BASE[
            best["intent"]
        ]["answer"]
    }



