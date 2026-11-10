import unittest
from unittest.mock import patch
from pathlib import Path
from services.rag.answer import answer_question
from services.rag.types import Chunk, Hit
class IncludedSources(unittest.TestCase):
    def test_sources_only_include_evidence_sent_to_model(self):
        hits=[Hit(Chunk(('x'*3000)+str(i)+'.py',1,1,'needle'),1) for i in range(6)]
        prompts=[]
        with patch('services.rag.answer.retrieve',return_value=hits):
            result=answer_question(Path('.'),'needle',model_chat=lambda p:prompts.append(p) or 'Answer')
        self.assertLess(len(result['sources']),len(hits))
        self.assertEqual(len(result['sources']),prompts[0].count('\nSOURCE ['))
        for ref in result['sources']: self.assertIn(ref['citation'],prompts[0])
