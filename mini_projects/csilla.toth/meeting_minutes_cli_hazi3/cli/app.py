from services.age_estimator import AgeEstimator
from infrastructure.agify_client import AgifyClient
from infrastructure.openai_name_extractor import OpenAINameExtractor


class MeetingMinutesApp:
    def __init__(self):
        self.name_extractor = OpenAINameExtractor()
        self.age_estimator = AgeEstimator(AgifyClient())

    def run(self, text: str) -> None:
        names = self.name_extractor.extract(text)
        participants = self.age_estimator.estimate(names)

        print("\nRésztvevők és becsült életkoruk:\n")
        for participant in sorted(participants, key=lambda p: p.name):
            print(f"- {participant.name}: {participant.age} év")
