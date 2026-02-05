from abc import ABC, abstractmethod
from typing import List, Dict

class NewsScraper(ABC):
    @abstractmethod
    def fetch_news(self) -> List[Dict]:
        """
        Fetches news items.
        Returns a list of dictionaries with keys:
        - title
        - link
        - source
        - published_at (optional)
        - summary (optional)
        """
        pass
