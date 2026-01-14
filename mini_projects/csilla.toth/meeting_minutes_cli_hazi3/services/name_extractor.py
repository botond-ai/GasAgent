import re
from typing import Set

class NameExtractor:
    """
    Egyszerű névkinyerés:
    - nagybetűvel kezdődő szavakat tekint névnek - ami nem túl szofisztiált, de llm használat nélkül
    is működik egy alapvető szintű névkinyeréshez.
    """

    NAME_PATTERN = re.compile(r"\b[A-ZÁÉÍÓÖŐÚÜŰ][a-záéíóöőúüű]+\b")

    def extract(self, text: str) -> Set[str]:
        names = set(self.NAME_PATTERN.findall(text))
        return names
