"""
Abstract base class for all Demask subscriber ID processors.

Ported from chinthakadd7/Demask (backend/providers/base.py).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


@dataclass
class ProcessingResult:
    dataframe: pd.DataFrame
    total_records: int
    processed: int
    unprocessed: int
    errors: int


class BaseProcessor(ABC):
    """Abstract base -- subclass and implement process() to add a new provider."""

    @abstractmethod
    def process(self, df: pd.DataFrame, **kwargs) -> ProcessingResult: ...
