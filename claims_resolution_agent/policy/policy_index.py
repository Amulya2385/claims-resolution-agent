"""Hybrid retrieval: TF-IDF arm + keyword-overlap arm, fused by
reciprocal rank — same design as Project 1. No entitlement scoping
here; unlike Project 1's contract corpus, policy text is not
legal-restricted, so this file is simpler than retrieval.py's Project
1 counterpart on purpose, not by oversight.
"""
import os
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from chunk import chunk_corpus

_STOP = {"the", "a", "an", "of", "to", "in", "for", "and", "or", "is", "this", "by", "on", "its"}


class Index:
    def __init__(self, chunks):
        self.chunks = chunks
        self.texts = [c["text"] for c in chunks]
        self.vectorizer = TfidfVectorizer()
        self.tfidf_matrix = self.vectorizer.fit_transform(self.texts)

    def _tfidf_rank(self, query):
        qvec = self.vectorizer.transform([query])
        sims = cosine_similarity(qvec, self.tfidf_matrix)[0]
        return sorted(range(len(self.chunks)), key=lambda i: -sims[i])

    def _keyword_rank(self, query):
        terms = {t for t in re.findall(r"[a-z]+", query.lower()) if t not in _STOP}
        scores = []
        for text in self.texts:
            words = set(re.findall(r"[a-z]+", text.lower()))
            scores.append(len(terms & words))
        return sorted(range(len(self.chunks)), key=lambda i: -scores[i])

    def search(self, query, k=4):
        tfidf_order = self._tfidf_rank(query)
        kw_order = self._keyword_rank(query)
        rrf = {}
        for rank, i in enumerate(tfidf_order):
            rrf[i] = rrf.get(i, 0) + 1.0 / (60 + rank)
        for rank, i in enumerate(kw_order):
            rrf[i] = rrf.get(i, 0) + 1.0 / (60 + rank)
        fused = sorted(rrf.keys(), key=lambda i: -rrf[i])[:k]
        return [{**self.chunks[i], "rrf_score": round(rrf[i], 5)} for i in fused]


_INDEX = None


def get_index() -> Index:
    global _INDEX
    if _INDEX is None:
        chunks = chunk_corpus(os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs"))
        _INDEX = Index(chunks)
    return _INDEX
