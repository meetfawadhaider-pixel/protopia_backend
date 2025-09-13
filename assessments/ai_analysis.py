import re
import numpy as np

# --- Optional deps: guard for environments where transformers/torch may be missing
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
except Exception:  # pragma: no cover
    SentimentIntensityAnalyzer = None

try:
    import torch
    from transformers import BertTokenizer, BertModel
except Exception:  # pragma: no cover
    torch = None
    BertTokenizer = None
    BertModel = None


# =========================
# Model init (lazy + robust)
# =========================
_vader = SentimentIntensityAnalyzer() if SentimentIntensityAnalyzer else None
_tokenizer = None
_bert = None

def _load_bert():
    global _tokenizer, _bert
    if _tokenizer is None or _bert is None:
        if BertTokenizer is None or BertModel is None:
            return False
        _tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")
        _bert = BertModel.from_pretrained("bert-base-uncased")
    return True


# =========================
# Trait dictionaries (kept)
# =========================
valid_display_traits = {
    "empathy": ["Sensitivity", "Compassion"],
    "ethical_reasoning": ["Fairness", "Judgment"],
    "authenticity": ["Consistency", "Honesty"],
    "critical_thinking": ["Logic", "Problem Solving"],
    "inclusiveness": ["Openness", "Respect for Diversity"],
    "accountability": ["Responsibility", "Ownership"],
    "clarity": ["Understanding", "Precision"]
}

all_trait_scores = {
    **valid_display_traits,
    "tone_balance": ["Communication", "Tone Regulation"],
    "vocabulary_richness": ["Linguistic Diversity", "Fluency"],
    "leadership_signal": ["Initiative", "Influence"]
}


# =========================
# Helpers (strict anti-cheat)
# =========================
_AI_PHRASES = [
    "in conclusion", "to conclude", "it is important to note",
    "one of the most important", "this highlights", "this demonstrates",
    "leadership is the cornerstone", "it is essential", "furthermore",
    "moreover", "in summary"
]

_FILLERS = {"um","uh","erm","like","basically","actually","literally","you know","sort of","kind of"}

_WORD_RE = re.compile(r"[a-z']+", re.I)

def _words(text: str):
    return _WORD_RE.findall(text.lower())

def lexical_diversity(text: str) -> float:
    w = _words(text)
    return len(set(w)) / max(len(w), 1)

def looks_ai_generated(text: str) -> bool:
    tl = text.lower()
    return any(p in tl for p in _AI_PHRASES)

def _max_repeat_run(words):
    best = cur = 1
    for i in range(1, len(words)):
        if words[i] == words[i-1]:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    return best if words else 0

def _repetitiveness_ratio(words, n=2):
    """Max frequency of top n-gram normalized by total n-grams."""
    if len(words) < n:
        return 0.0
    counts = {}
    for i in range(len(words)-n+1):
        g = tuple(words[i:i+n])
        counts[g] = counts.get(g, 0) + 1
    max_count = max(counts.values()) if counts else 0
    total = max(len(words)-n+1, 1)
    return max_count / total

def _filler_ratio(text):
    tl = " " + text.lower() + " "
    count = 0
    for f in _FILTERS_LIST:  # populated below
        count += tl.count(" " + f + " ")
    words = _words(text)
    return count / max(len(words), 1)

_FILTERS_LIST = list(_FILLERS)

def _vader_sentiment(text):
    if not _vader:
        return 0.0
    return float(_vader.polarity_scores(text)["compound"])

def _embedding(text):
    """Mean-pooled BERT embedding (safe fallback if unavailable)."""
    if not _load_bert():
        return None
    tokens = _tokenizer(text, return_tensors="pt", truncation=True, max_length=512, padding=True)
    with torch.no_grad():
        out = _bert(**tokens).last_hidden_state.mean(dim=1).squeeze()
    return out.detach().cpu().numpy()

def _semantic_flow(texts):
    """Average L2 distance between consecutive essay embeddings (authenticity proxy)."""
    embs = []
    for t in texts:
        e = _embedding(t)
        if e is None:
            return 0.5  # neutral if BERT not available
        embs.append(e)
    if len(embs) < 2:
        return 0.5
    diffs = [np.linalg.norm(embs[i]-embs[i-1]) for i in range(1, len(embs))]
    # Normalize by a loose scale so typical varied answers land ~0.6-0.9
    flow = float(np.mean(diffs))
    return min(max(flow / 5.0, 0.0), 1.0)


# =========================
# Summary comment (kept)
# =========================
def generate_summary_comment(score, authenticity, flags):
    if score >= 85:
        base = "Exceptional leadership integrity with strong ethics and empathy. Clear, original, and trustworthy responses detected."
    elif score >= 70:
        base = "Solid integrity and leadership indicators. Slight concerns over authenticity and tone, but overall trustworthy performance."
    elif score >= 50:
        base = "Moderate leadership signals. Improvements needed in tone, originality, and ethical consistency to build integrity."
    else:
        base = "Weak leadership indicators. High risk of generic or manipulated content. Authentic reflection and ethics must improve."
    return " ".join(base.split()[:20])


# =========================
# Essay Analyzer (strict)
# =========================
def analyze_essay(texts, times, paste_flags):
    """
    Args:
        texts: list[str] (3–10 answers)
        times: list[int] seconds per answer (same length as texts)
        paste_flags: list[bool] detected paste per answer

    Returns (unchanged keys):
        {
          "authenticity": 0..1,
          "empathy_signal": 0..1,
          "ethical_reasoning": 0..1,
          "tone": "Positive|Neutral|Negative",
          "final_ai_score": 0..100,
          "traits": { ... 0..1 ... },
          "subtraits": valid_display_traits,
          "ai_comment": str
        }
    """
    texts = texts or []
    times = times or [0] * len(texts)
    paste_flags = paste_flags or [False] * len(texts)

    # Basic guards
    if not texts:
        return {
            "authenticity": 0.0, "empathy_signal": 0.0, "ethical_reasoning": 0.0,
            "tone": "Neutral", "final_ai_score": 0.0,
            "traits": {}, "subtraits": valid_display_traits,
            "ai_comment": "No content provided."
        }

    # ---------- Per-essay metrics
    word_lists = [_words(t) for t in texts]
    word_counts = [len(w) for w in word_lists]
    uniq_ratios = [ (len(set(w)) / max(len(w),1)) for w in word_lists ]
    repeat_runs = [ _max_repeat_run(w) for w in word_lists ]
    bigram_rep = [ _repetitiveness_ratio(w, n=2) for w in word_lists ]
    trigram_rep = [ _repetitiveness_ratio(w, n=3) for w in word_lists ]
    filler_ratios = []
    for t in texts:
        tl = t.lower()
        filler_cnt = sum(tl.count(" " + f + " ") for f in _FILTERS_LIST)
        filler_ratios.append(filler_cnt / max(len(_words(t)), 1))
    ai_flags = sum(looks_ai_generated(t) for t in texts)
    paste_count = sum(1 for p in paste_flags if p)

    # typing speed heuristic (words per minute) – very high suggests paste/automation
    wpm = []
    for n, sec in zip(word_counts, times):
        if sec <= 0:
            wpm.append(0.0)
        else:
            wpm.append( (n / max(sec,1)) * 60.0 )

    # Very short answers
    very_short_flags = [n < 40 for n in word_counts]
    very_short_any = any(very_short_flags)

    # Short time yet long content (suspicious)
    short_time_flags = [ (sec < 20 and n >= 50) for sec, n in zip(times, word_counts) ]
    short_time_count = sum(short_time_flags)

    # Sentiment (tone)
    comp_scores = [_vader_sentiment(t) for t in texts]
    tone_mean = float(np.mean(comp_scores)) if comp_scores else 0.0
    tone = "Positive" if tone_mean > 0.4 else "Negative" if tone_mean < -0.4 else "Neutral"

    # Semantic flow authenticity (0..1)
    authenticity = _semantic_flow(texts)

    # ---------- Trait estimates (0..1)
    empathy = round((tone_mean + 1) / 2, 2)                 # maps -1..1 -> 0..1
    ethics = round((authenticity + empathy) / 2, 2)
    clarity = round(float(np.mean(uniq_ratios)) * 0.9, 2)
    critical_thinking = round(ethics * 0.9, 2)
    inclusiveness = round((empathy + tone_mean + 1) / 3, 2)
    accountability = round((authenticity + ethics) / 2, 2)
    vocabulary_richness = round(float(np.mean(uniq_ratios)), 2)
    tone_balance = round(tone_mean, 2)
    leadership_signal = round((authenticity + empathy) / 2, 2)

    trait_scores = {
        "empathy": empathy,
        "ethical_reasoning": ethics,
        "authenticity": authenticity,
        "clarity": clarity,
        "critical_thinking": critical_thinking,
        "inclusiveness": inclusiveness,
        "accountability": accountability,
        "vocabulary_richness": vocabulary_richness,
        "tone_balance": tone_balance,
        "leadership_signal": leadership_signal,
    }

    # ---------- STRICT penalties
    # Core indicators aggregated across essays
    n_mean = float(np.mean(word_counts))
    uniq_mean = float(np.mean(uniq_ratios))
    rep_run_max = int(max(repeat_runs) if repeat_runs else 0)
    bi_rep_max = float(max(bigram_rep) if bigram_rep else 0.0)
    tri_rep_max = float(max(trigram_rep) if trigram_rep else 0.0)
    filler_mean = float(np.mean(filler_ratios)) if filler_ratios else 0.0
    wpm_max = float(max(wpm) if wpm else 0.0)

    penalty = 0.0

    # very short overall
    if n_mean < 60:
        penalty += 0.35
    if uniq_mean < 0.50:
        penalty += 0.35

    # spam/repetition
    if rep_run_max >= 3:
        penalty += 0.40       # “yes yes yes” etc.
    if bi_rep_max > 0.35 or tri_rep_max > 0.25:
        penalty += 0.30

    # filler / fluff
    if filler_mean > 0.08:
        penalty += 0.15

    # AI-ish phrasing
    if ai_flags >= 2:
        penalty += 0.40
    elif ai_flags == 1:
        penalty += 0.20

    # timing anomalies
    if paste_count > 0:
        penalty += 0.70
    if short_time_count >= 2 or very_short_any:
        penalty += 0.30
    if wpm_max >= 180:  # implausibly fast consistent typing
        penalty += 0.25

    # ---------- Base content score (0..1)
    # Scales with length (cap ~180 words avg), boosted by diversity
    length_component = min(1.0, n_mean / 180.0)
    diversity_component = min(1.0, max(0.0, (uniq_mean - 0.35) / 0.45))  # 0.35→0, 0.80→1
    content_norm = 0.6 * length_component + 0.4 * diversity_component

    # Clamp penalties and apply
    penalty = min(penalty, 1.0)
    content_after_penalty = max(0.0, content_norm * (1.0 - penalty))

    # ---------- Feature bonus from tone/authenticity
    # small bonus, never letting junk pass high
    feature_norm = 0.25 * max(0.0, (tone_mean + 1) / 2) + 0.75 * authenticity
    feature_norm = min(feature_norm, 1.0)

    # ---------- Raw & final (0..100)
    raw = 0.70 * content_after_penalty + 0.30 * feature_norm
    final_score = round(max(0.0, min(raw, 1.0)) * 100.0, 2)

    # Hard clamps for clear abuse
    if rep_run_max >= 3 and uniq_mean < 0.4 and n_mean < 40:
        final_score = min(final_score, 5.0)   # “yes yes yes” → near zero
    if paste_count > 0:
        final_score = min(final_score, 60.0)

    # Cap displayed subtraits into [0.10, 0.94] like before (≈0.5–4.7 when scaled)
    for k in trait_scores:
        trait_scores[k] = max(min(trait_scores[k], 0.94), 0.10)

    filtered_scores = {k: v for k, v in trait_scores.items() if k in valid_display_traits}

    return {
        "authenticity": round(authenticity, 2),
        "empathy_signal": round(empathy, 2),
        "ethical_reasoning": round(ethics, 2),
        "tone": tone,
        "final_ai_score": final_score,
        "traits": trait_scores,
        "subtraits": valid_display_traits,
        "ai_comment": generate_summary_comment(final_score, authenticity, ai_flags)
    }


# =========================
# (Optional) VR answer scorer
# =========================
def score_vr_answer(transcript: str, features: dict, rubric: dict | None = None):
    """
    Strict 0..50 scoring for VR (content + delivery).
    - Heavily punishes short/repetitive answers (e.g., “yes yes yes”).
    - Uses speech features: speech_rate_wps (ideal ≈2), avg_pause_sec (ideal ≈0.6),
      and challenge_passed (liveness).
    """
    text = (transcript or "").strip()
    words = _words(text)
    n = len(words)
    uniq = len(set(words))
    uniq_ratio = (uniq / n) if n else 0.0
    repeat_run = _max_repeat_run(words)
    bi_rep = _repetitiveness_ratio(words, 2)
    tri_rep = _repetitiveness_ratio(words, 3)

    # Content (0..30)
    length_comp = min(1.0, n / 120.0)
    diversity_comp = min(1.0, max(0.0, (uniq_ratio - 0.40) / 0.45))
    content_norm = 0.6 * length_comp + 0.4 * diversity_comp

    penalty = 0.0
    if n < 12: penalty += 0.60
    if uniq_ratio < 0.50: penalty += 0.35
    if repeat_run >= 3: penalty += 0.60
    if bi_rep > 0.40 or tri_rep > 0.30: penalty += 0.30

    content = max(0.0, content_norm * (1.0 - min(1.0, penalty))) * 30.0

    # Delivery features (0..20)
    sr = float(features.get("speech_rate_wps", 0.0) or 0.0)     # ideal ≈2
    pauses = float(features.get("avg_pause_sec", 0.6) or 0.6)   # ideal ≈0.6
    live_ok = bool(features.get("challenge_passed", False))

    sr_comp = max(0.0, 1.0 - abs(sr - 2.0) / 2.0)          # 2 → 1, 0 or 4 → 0
    pause_comp = max(0.0, 1.0 - abs(pauses - 0.6) / 1.4)

    delivery = (0.5 * (1.0 if live_ok else 0.0) + 0.3 * sr_comp + 0.2 * pause_comp) * 20.0

    total = round(min(50.0, content + delivery), 2)

    # Absolute spam clamp
    if n < 6 or (repeat_run >= 3 and uniq_ratio < 0.45):
        total = min(total, 3.0)

    return {
        "score_content": round(content, 2),
        "score_features": round(delivery, 2),
        "score_total": total,
    }
