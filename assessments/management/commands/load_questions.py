from django.core.management.base import BaseCommand
from assessments.models import Question
import random

class Command(BaseCommand):
    help = "Load 100 high-quality leadership questions into the database"

    def handle(self, *args, **kwargs):
        traits = [
            "integrity", "empathy", "self_control", "vision", "accountability",
            "adaptability", "communication", "decision_making", "inclusiveness", "influence"
        ]

        professions = ["Manager", "Developer", "Psychologist", "Consultant", "HR Officer", "Trainer"]
        age_groups = ["16–20", "21–30", "31–40", "41–50"]
        genders = [None, "Male", "Female"]

        # Question bank with realistic, professional wording
        question_templates = {
            "integrity": [
                "I maintain honesty even when it may negatively impact me.",
                "I take responsibility for my mistakes without shifting blame.",
                "I avoid conflicts of interest in professional decisions.",
                "I follow through on ethical commitments even under pressure.",
                "I am honest with team members even when the truth is difficult.",
                "I hold others accountable for unethical actions.",
                "I disclose relevant information transparently.",
                "I uphold organizational values consistently.",
                "I avoid exaggeration or deception in communication.",
                "I would report unethical behavior even if it risks relationships."
            ],
            "empathy": [
                "I understand how others feel even if they don’t express it.",
                "I can sense tension or emotional states in a team.",
                "I adapt my communication based on others' emotional responses.",
                "I consider others’ perspectives during conflicts.",
                "I am able to comfort or support distressed colleagues.",
                "I notice when someone is struggling even without being told.",
                "I listen attentively without interrupting.",
                "I acknowledge others’ emotions even if I don’t agree.",
                "I make space for different emotional expressions in meetings.",
                "I respond compassionately when someone shares personal challenges."
            ],
            "self_control": [
                "I stay calm in heated arguments.",
                "I do not let stress cloud my judgment.",
                "I take a pause before reacting emotionally.",
                "I avoid impulsive decisions in leadership roles.",
                "I keep my tone professional even when provoked.",
                "I regulate my emotions to maintain clarity.",
                "I separate personal feelings from professional duties.",
                "I remain composed when facing unexpected obstacles.",
                "I avoid venting frustrations to team members.",
                "I use breathing or reflection techniques under pressure."
            ],
            "vision": [
                "I create long-term goals aligned with team strengths.",
                "I articulate a clear vision during change.",
                "I motivate others by connecting their role to bigger goals.",
                "I challenge the team to pursue ambitious outcomes.",
                "I integrate innovation into strategic planning.",
                "I frame setbacks as part of broader progress.",
                "I ensure the team understands the long-term direction.",
                "I build momentum through shared future planning.",
                "I align team efforts to organizational vision.",
                "I communicate purpose beyond daily tasks."
            ],
            "accountability": [
                "I admit when I fall short of expectations.",
                "I hold myself and others accountable to timelines.",
                "I follow through on deliverables even without reminders.",
                "I respond constructively to performance feedback.",
                "I evaluate my contributions critically.",
                "I take ownership of team performance.",
                "I recognize gaps and proactively address them.",
                "I complete tasks with minimal supervision.",
                "I ensure commitments are realistic and met.",
                "I escalate risks or delays transparently."
            ],
            "adaptability": [
                "I stay productive even when roles or plans change.",
                "I adapt quickly to new technology or systems.",
                "I remain flexible with evolving expectations.",
                "I learn from mistakes and apply improvements quickly.",
                "I support others during change transitions.",
                "I take initiative in uncertain situations.",
                "I try new methods when old ones don’t work.",
                "I shift strategies in response to feedback.",
                "I re-prioritize smoothly under shifting conditions.",
                "I remain open to different ways of working."
            ],
            "communication": [
                "I communicate clearly under tight deadlines.",
                "I tailor my message to different audiences.",
                "I explain complex topics simply.",
                "I provide timely, respectful feedback.",
                "I document and share key decisions.",
                "I actively seek clarification if unclear.",
                "I confirm mutual understanding during collaboration.",
                "I use data and examples to support communication.",
                "I adjust tone for different settings.",
                "I avoid jargon when working cross-functionally."
            ],
            "decision_making": [
                "I make decisions after weighing all options.",
                "I remain confident in high-stakes choices.",
                "I consult others before important decisions.",
                "I balance logic and intuition in decisions.",
                "I evaluate risks before acting.",
                "I take decisive action when needed.",
                "I revise decisions when new evidence arises.",
                "I avoid delays in decision-making.",
                "I align decisions to organizational goals.",
                "I consider ethical impact before choosing."
            ],
            "inclusiveness": [
                "I invite input from diverse team members.",
                "I ensure all voices are heard in meetings.",
                "I value cultural and background differences.",
                "I challenge biased assumptions when I notice them.",
                "I accommodate team needs for fairness.",
                "I advocate for underrepresented perspectives.",
                "I celebrate cultural events in the workplace.",
                "I encourage participation from quieter individuals.",
                "I avoid favoritism in group settings.",
                "I support diversity initiatives actively."
            ],
            "influence": [
                "I persuade others by framing mutual benefits.",
                "I build trust before making proposals.",
                "I use storytelling to inspire action.",
                "I rally people toward common goals.",
                "I use facts and credibility to gain support.",
                "I negotiate with empathy and firmness.",
                "I influence without needing authority.",
                "I adjust influence style to the audience.",
                "I maintain confidence when challenged.",
                "I inspire follow-through through leading by example."
            ]
        }

        # Clear old questions
        Question.objects.all().delete()

        # Save curated 100 questions
        for trait, questions in question_templates.items():
            for text in questions:
                Question.objects.create(
                    text=text,
                    trait=trait,
                    profession_tags=random.sample(professions, k=random.randint(1, 3)),
                    age_group=random.choice(age_groups),
                    gender_specific=random.choice(genders),
                    weight=round(random.uniform(0.8, 1.2), 2),
                    reverse_score=random.choice([True, False])
                )

        self.stdout.write(self.style.SUCCESS("✅ 100 high-quality leadership questions loaded successfully."))
