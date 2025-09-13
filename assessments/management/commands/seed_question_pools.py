import random
import string
from django.core.management.base import BaseCommand
from assessments.models import VRQuestion, EssayPrompt

PILLARS = [
    {"key": "integrity_ethics", "name": "Integrity & Ethical Reasoning"},
    {"key": "empathy_compassion", "name": "Empathy & Compassion"},
    {"key": "authentic_selfawareness", "name": "Authenticity & Self-Awareness"},
    {"key": "transformational_leadership", "name": "Transformational Leadership"},
    {"key": "emotional_regulation_social", "name": "Emotional Regulation & Social Skills"},
]

SCENARIOS = [
    "data privacy breach",
    "whistleblowing dilemma",
    "conflict of interest with a vendor",
    "pressure from manager to bend rules",
    "team member underperforming",
    "deadline vs quality trade-off",
    "inclusion concern raised by a teammate",
    "budget overrun discovered late",
    "customer complaint about hidden fees",
    "misattribution of credit in a project",
    "AI system shows biased recommendations",
    "remote worker burnout signs",
    "leak of confidential roadmap",
    "security vulnerability disclosure timing",
    "gift policy violation by stakeholder",
    "harassment allegation in the team",
    "accessibility bug in production",
    "overtime without compensation issue",
    "junior made a costly mistake",
    "hiring decision with implicit bias risk",
    "vendor bribery attempt",
    "regulatory non-compliance risk",
    "toxic behavior from a top performer",
    "confidential data request by partner",
    "unrealistic deadline promised to client",
]

TONES = [
    "calm and confident",
    "empathetic and firm",
    "transparent and direct",
    "measured and principled",
    "supportive yet accountable",
]

VR_TEMPLATES = [
    "In a {scenario}, what is your first action and why?",
    "You notice a {scenario}. How do you address it with your team?",
    "A peer suggests ignoring a {scenario}. What do you say?",
    "How would you balance empathy and accountability in a {scenario}?",
    "Describe your decision process for a {scenario}.",
    "How do you communicate the resolution of a {scenario} to stakeholders?",
    "What signals would tell you your approach to a {scenario} is working?",
    "What ethical principles guide you in a {scenario}?",
    "How would you protect psychological safety during a {scenario}?",
    "How do you prevent this {scenario} from recurring?",
]

ESSAY_TEMPLATES = [
    "Describe a situation where you handled a {scenario}. What options did you consider, and why did you choose your final approach?",
    "Reflect on a past experience involving a {scenario}. What would you do differently now and why?",
    "Explain how you would coach a team through a {scenario} while maintaining trust and momentum.",
    "Write a plan to remediate a {scenario} including stakeholders, timelines, risks, and communication.",
    "How would you measure success after resolving a {scenario}? Include ethical, human, and business indicators.",
    "Discuss how your core values would influence decisions in a {scenario}.",
]

def unique_generate(count, make_item):
    """Generate 'count' unique text items using a factory function."""
    items = []
    seen = set()
    attempts = 0
    max_attempts = count * 20
    while len(items) < count and attempts < max_attempts:
        item = make_item()
        attempts += 1
        txt = item["text"].strip()
        if txt not in seen:
            seen.add(txt)
            items.append(item)
    return items

class Command(BaseCommand):
    help = "Seed DB with VR (default 150) and Essay (default 100) question pools. No JSON needed."

    def add_arguments(self, parser):
        parser.add_argument("--vr_count", type=int, default=150)
        parser.add_argument("--essay_count", type=int, default=100)
        parser.add_argument("--shuffle_seed", type=int, default=42)

    def handle(self, *args, **opts):
        vr_count = int(opts.get("vr_count", 150))
        essay_count = int(opts.get("essay_count", 100))
        random.seed(int(opts.get("shuffle_seed", 42)))

        self.stdout.write(self.style.NOTICE(f"Seeding VR questions: target {vr_count}"))
        vr_items = unique_generate(vr_count, self.make_vr_item)
        created_vr = 0
        for it in vr_items:
            obj, created = VRQuestion.objects.get_or_create(
                text=it["text"],
                defaults={
                    "pillar_key": it["pillar_key"],
                    "pillar_name": it["pillar_name"],
                    "tags": it["tags"],
                    "expected_tone": it["expected_tone"],
                    "rubric": it["rubric"],
                },
            )
            if created:
                created_vr += 1
        self.stdout.write(self.style.SUCCESS(f"✅ VR: requested {vr_count}, created {created_vr}, existing {len(vr_items)-created_vr}"))

        self.stdout.write(self.style.NOTICE(f"Seeding Essay prompts: target {essay_count}"))
        essay_items = unique_generate(essay_count, self.make_essay_item)
        created_es = 0
        for it in essay_items:
            obj, created = EssayPrompt.objects.get_or_create(
                text=it["text"],
                defaults={
                    "pillar_key": it["pillar_key"],
                    "pillar_name": it["pillar_name"],
                    "tags": it["tags"],
                    "rubric": it["rubric"],
                },
            )
            if created:
                created_es += 1
        self.stdout.write(self.style.SUCCESS(f"✅ Essay: requested {essay_count}, created {created_es}, existing {len(essay_items)-created_es}"))

        self.stdout.write(self.style.SUCCESS("🎉 Seeding complete."))

    # --------- factories ----------
    def make_vr_item(self):
        pillar = random.choice(PILLARS)
        scenario = random.choice(SCENARIOS)
        template = random.choice(VR_TEMPLATES)
        text = template.format(scenario=scenario)
        return {
            "text": text,
            "pillar_key": pillar["key"],
            "pillar_name": pillar["name"],
            "tags": [scenario.replace(" ", "_"), "spoken", "liveness"],
            "expected_tone": random.choice(TONES),
            "rubric": {
                "content": "Addresses stakeholders, risks, ethics, remediation steps",
                "tone": f"Consistent with {pillar['name']}",
                "signals": ["clarity", "justification", "accountability", "empathy"],
            },
        }

    def make_essay_item(self):
        pillar = random.choice(PILLARS)
        scenario = random.choice(SCENARIOS)
        template = random.choice(ESSAY_TEMPLATES)
        text = template.format(scenario=scenario)
        return {
            "text": text,
            "pillar_key": pillar["key"],
            "pillar_name": pillar["name"],
            "tags": [scenario.replace(" ", "_"), "written", "reflection"],
            "rubric": {
                "structure": "Intro → options → decision rationale → impact → lessons",
                "alignment": f"Aligns with {pillar['name']}",
                "signals": ["critical_thinking", "ethical_reasoning", "empathy", "ownership"],
            },
        }
