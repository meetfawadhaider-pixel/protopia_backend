from rest_framework.decorators import api_view
from rest_framework.response import Response
from transformers import pipeline
from nltk.sentiment import SentimentIntensityAnalyzer
import nltk

# Custom framework mapper
from .framework_mapper import analyze_frameworks

nltk.download('vader_lexicon')

bert_pipeline = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")
vader = SentimentIntensityAnalyzer()

@api_view(['POST'])
def analyze_response(request):
    text = request.data.get("text", "")
    if not text:
        return Response({"error": "Text is required"}, status=400)

    # Analyze with BERT and VADER
    bert_result = bert_pipeline(text)[0]
    vader_result = vader.polarity_scores(text)

    # Analyze leadership frameworks
    framework_results = analyze_frameworks(text)

    # Final verdict logic
    verdict = "Positive" if bert_result["label"] == "POSITIVE" and vader_result["compound"] > 0.3 else "Concerning"

    return Response({
        "bert_label": bert_result["label"],
        "bert_score": round(bert_result["score"], 2),
        "vader": vader_result,
        "verdict": verdict,
        "frameworks": framework_results  # 👈 new addition
    })
