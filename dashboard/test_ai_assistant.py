import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import ai_assistant as ai

class ProviderTests(unittest.TestCase):
    def test_consent_and_provider_block_network(self):
        with patch.object(ai,'urlopen') as send:
            with self.assertRaises(PermissionError): ai.explain({},'', 'English',provider='openai')
            with self.assertRaises(ValueError): ai.explain({},'', 'English',provider='other',consent=True)
            send.assert_not_called()

    def test_routes_and_extracts_text(self):
        for provider, result, host in [
            ('openai',{'output':[{'type':'message','content':[{'type':'output_text','text':'Review records.'}]}]},'api.openai.com'),
            ('xai',{'choices':[{'message':{'content':'Review records.'}}]},'api.x.ai')]:
            with self.subTest(provider=provider),patch.object(ai,'urlopen',return_value=io.BytesIO(json.dumps(result).encode())) as send:
                text=ai.explain({'plant':'fictional'},'Explain','English',provider=provider,model='test-model',api_key='test-key',consent=True)
                self.assertEqual(text,'Review records.')
                req=send.call_args.args[0]
                self.assertIn(host,req.full_url)
                payload=json.loads(req.data)
                self.assertEqual(payload['model'],'test-model')
                self.assertNotIn('test-key',req.data.decode())
                if provider=='openai': self.assertFalse(payload['store'])

    def test_claude_key_is_request_scoped(self):
        with patch.object(ai,'explain_with_claude',return_value='Review') as send:
            ai.explain({},'', 'Nederlands',provider='anthropic',model='chosen-model',api_key='test-key',consent=True)
            self.assertEqual(send.call_args.kwargs['api_key'],'test-key')
            self.assertEqual(send.call_args.kwargs['model'],'chosen-model')

    def test_errors_do_not_echo_provider_body_or_key(self):
        with patch.object(ai,'urlopen',side_effect=HTTPError('url',401,'secret-test-key',{},None)):
            with self.assertRaises(RuntimeError) as caught:
                ai.explain({},'', 'English',provider='openai',model='test-model',api_key='secret-test-key',consent=True)
            self.assertNotIn('secret-test-key',str(caught.exception))
            self.assertIn('401',str(caught.exception))

    def test_missing_model_and_empty_response(self):
        with patch.dict(ai.os.environ,{},clear=True):
            with self.assertRaises(ValueError): ai.explain({},'', 'English',provider='xai',api_key='test-key',consent=True)
        with patch.object(ai,'urlopen',return_value=io.BytesIO(b'{"output":[]}')):
            with self.assertRaises(RuntimeError): ai.explain({},'', 'English',provider='openai',model='test-model',api_key='test-key',consent=True)
