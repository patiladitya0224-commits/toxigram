"""
NLP Engine for ToxiGram
- Toxicity detection using VADER + custom word lists
- Comment neutralization (replace bad words with synonyms)
- Sentiment analysis
- Toxicity scoring (0-100%)
"""

import re
import random
from better_profanity import profanity
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from nltk.corpus import wordnet
from textblob import TextBlob
import nltk

# Download required NLTK data
for pkg in ['vader_lexicon', 'wordnet', 'averaged_perceptron_tagger', 'punkt']:
    try:
        nltk.download(pkg, quiet=True)
    except:
        pass

# Initialize tools
profanity.load_censor_words()
sia = SentimentIntensityAnalyzer()

# ── Extended toxic word list with replacements ──────────────────────────────
TOXIC_REPLACEMENTS = {
    # Insults → kind words
    "idiot":      "person",
    "stupid":     "confused",
    "dumb":       "mistaken",
    "moron":      "individual",
    "loser":      "learner",
    "ugly":       "unique",
    "fat":        "human",
    "hate":       "strongly dislike",
    "pathetic":   "struggling",
    "useless":    "unhelpful",
    "trash":      "low quality",
    "garbage":    "poor content",
    "kill":       "stop",
    "die":        "go away",
    "dumb":       "uninformed",
    "shut up":    "please be quiet",
    "jerk":       "unkind person",
    "fool":       "mistaken person",
    "liar":       "mistaken speaker",
    "evil":       "misguided",
    "gross":      "unpleasant",
    "horrible":   "unpleasant",
    "terrible":   "poor",
    "awful":      "not great",
    "worst":      "least favorable",
    "disgusting": "unpleasant",
    "freak":      "unique individual",
    "creep":      "uncomfortable person",
    "idiot":      "uninformed person",
    "crazy":      "overwhelmed",
    "insane":     "extreme",
}

# Aggressive intensifiers
TOXIC_INTENSIFIERS = ["very", "extremely", "totally", "absolutely", "completely"]

# ── Core NLP Functions ───────────────────────────────────────────────────────

def compute_toxicity_score(text: str) -> float:
    """
    Returns toxicity score from 0.0 to 1.0
    Combines: profanity detection + VADER negativity + TextBlob subjectivity
    """
    score = 0.0

    # 1. Profanity check (heaviest weight)
    if profanity.contains_profanity(text):
        score += 0.5

    # 2. Check custom toxic words
    lower = text.lower()
    found_toxic = sum(1 for word in TOXIC_REPLACEMENTS if word in lower)
    score += min(found_toxic * 0.1, 0.3)

    # 3. VADER negativity score
    vs = sia.polarity_scores(text)
    score += vs['neg'] * 0.3  # neg ranges 0..1, weight it 30%

    # 4. ALL CAPS = aggression
    words = text.split()
    if words:
        caps_ratio = sum(1 for w in words if w.isupper() and len(w) > 2) / len(words)
        score += caps_ratio * 0.2

    # 5. Excessive punctuation (!!!???)
    excl = text.count('!') + text.count('?')
    score += min(excl * 0.02, 0.1)

    return min(round(score, 3), 1.0)


def get_toxicity_label(score: float) -> dict:
    """Returns label + color for the toxicity score."""
    if score < 0.2:
        return {"label": "Clean ✅", "color": "#22c55e", "level": "clean"}
    elif score < 0.4:
        return {"label": "Mild ⚠️", "color": "#eab308", "level": "mild"}
    elif score < 0.6:
        return {"label": "Moderate 🔶", "color": "#f97316", "level": "moderate"}
    elif score < 0.8:
        return {"label": "Toxic ❌", "color": "#ef4444", "level": "toxic"}
    else:
        return {"label": "Highly Toxic 🚨", "color": "#7f1d1d", "level": "extreme"}


def neutralize_text(text: str) -> dict:
    """
    Main neutralization function.
    Returns: {
        original: str,
        neutralized: str,
        toxicity_score: float,
        toxicity_label: dict,
        replacements_made: list,
        sentiment: str,
        was_modified: bool
    }
    """
    original = text
    neutralized = text
    replacements_made = []

    # Step 1: Replace custom toxic words
    lower_check = neutralized.lower()
    for toxic_word, replacement in TOXIC_REPLACEMENTS.items():
        pattern = re.compile(re.escape(toxic_word), re.IGNORECASE)
        if pattern.search(neutralized):
            # Preserve original casing style
            def replace_match(m):
                original_word = m.group(0)
                if original_word.isupper():
                    return replacement.upper()
                elif original_word[0].isupper():
                    return replacement.capitalize()
                return replacement

            new_text = pattern.sub(replace_match, neutralized)
            if new_text != neutralized:
                replacements_made.append({
                    "original": toxic_word,
                    "replacement": replacement
                })
                neutralized = new_text

    # Step 2: Censor remaining profanity with asterisks then try wordnet
    if profanity.contains_profanity(neutralized):
        # Get word by word
        words = neutralized.split()
        new_words = []
        for word in words:
            clean_word = re.sub(r'[^\w]', '', word).lower()
            if profanity.contains_profanity(clean_word):
                # Try to find a synonym via WordNet
                synonym = get_positive_synonym(clean_word) or "[removed]"
                replacements_made.append({
                    "original": clean_word,
                    "replacement": synonym
                })
                new_words.append(synonym)
            else:
                new_words.append(word)
        neutralized = " ".join(new_words)

    # Step 3: De-aggressify ALL CAPS words
    def de_caps(match):
        word = match.group(0)
        if len(word) > 2 and word.isupper():
            return word.capitalize()
        return word

    neutralized = re.sub(r'\b[A-Z]{3,}\b', de_caps, neutralized)

    # Step 4: Trim excessive punctuation
    neutralized = re.sub(r'([!?]){3,}', r'\1\1', neutralized)

    # Sentiment
    blob = TextBlob(original)
    polarity = blob.sentiment.polarity
    if polarity > 0.1:
        sentiment = "Positive 😊"
    elif polarity < -0.1:
        sentiment = "Negative 😞"
    else:
        sentiment = "Neutral 😐"

    score = compute_toxicity_score(original)
    label = get_toxicity_label(score)

    return {
        "original": original,
        "neutralized": neutralized,
        "toxicity_score": score,
        "toxicity_percent": int(score * 100),
        "toxicity_label": label,
        "replacements_made": replacements_made,
        "sentiment": sentiment,
        "was_modified": original.strip().lower() != neutralized.strip().lower()
    }


def get_positive_synonym(word: str) -> str:
    """Try to find a neutral/positive synonym via WordNet."""
    try:
        synsets = wordnet.synsets(word)
        for synset in synsets:
            for lemma in synset.lemmas():
                candidate = lemma.name().replace('_', ' ')
                if candidate.lower() != word.lower() and not profanity.contains_profanity(candidate):
                    return candidate
    except:
        pass
    return None


def analyze_sentiment_trend(comments: list) -> dict:
    """Analyze overall sentiment of a post's comments."""
    if not comments:
        return {"positive": 0, "negative": 0, "neutral": 0, "overall": "No comments yet"}

    pos = neg = neu = 0
    for comment in comments:
        vs = sia.polarity_scores(comment)
        if vs['compound'] >= 0.05:
            pos += 1
        elif vs['compound'] <= -0.05:
            neg += 1
        else:
            neu += 1

    total = len(comments)
    result = {
        "positive": round(pos / total * 100),
        "negative": round(neg / total * 100),
        "neutral": round(neu / total * 100),
    }

    if pos > neg:
        result["overall"] = "Mostly Positive 😊"
    elif neg > pos:
        result["overall"] = "Mostly Negative 😞"
    else:
        result["overall"] = "Mixed 😐"

    return result


def extract_keywords(text: str) -> list:
    """Extract important keywords from text using TextBlob."""
    try:
        blob = TextBlob(text)
        # Get noun phrases
        keywords = list(set(blob.noun_phrases))
        return keywords[:5]  # top 5
    except:
        return []


def auto_suggest_positive(text: str) -> str:
    """Suggest a more positive version of a mildly negative comment."""
    blob = TextBlob(text)
    if blob.sentiment.polarity < -0.2:
        # Simple transformation: append a softener
        softeners = [
            "but I appreciate your effort",
            "though everyone has different opinions",
            "but keep it up",
            "yet I respect your perspective"
        ]
        return text.rstrip('.!?') + ", " + random.choice(softeners) + "."
    return text
