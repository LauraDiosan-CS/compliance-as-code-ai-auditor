"""Evidence collection (repo walking, chunking, signals) and retrieval."""

from ccauditor.evidence.collector import collect
from ccauditor.evidence.retriever import Retriever

__all__ = ["collect", "Retriever"]
