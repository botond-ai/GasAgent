from typing import Set
from domain.participant import Participant

class AgeEstimator:
    def __init__(self, agify_client):
        self.agify_client = agify_client

    def estimate(self, names: Set[str]) -> Set[Participant]:
        participants = set()

        for name in names:
            age = self.agify_client.get_age(name)
            participants.add(Participant(name=name, age=age))

        return participants
