import unittest
from services.rag.tokenize import retrieval_query_terms, _RETRIEVAL_STOP_WORDS
class SalientBudget(unittest.TestCase):
    def test_question_scaffolding_cannot_consume_term_budget(self):
        query=' '.join(sorted(_RETRIEVAL_STOP_WORDS))+' authentication'
        self.assertEqual(retrieval_query_terms(query),('authentication',))
        self.assertEqual(len(retrieval_query_terms(' '.join('term'+str(i) for i in range(50)))),32)
