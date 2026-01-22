from abc import ABC, abstractmethod

class DisplayWriterInterface(ABC):
    @abstractmethod
    def write(self, content: str) -> None:
        """Writes content to the display"""
        pass