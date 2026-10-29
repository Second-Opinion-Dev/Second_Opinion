"""Allowlisted providers; credentials are request-scoped and never persisted."""
import json
import os
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from claude_assistant import SYSTEM_PROMPT, explain_with_claude

PROVIDERS = {
    'anthropic': ('Anthropic', 'ANTHROPIC_API_KEY', 'ANTHROPIC_MODEL'),
    'openai': ('OpenAI', 'OPENAI_API_KEY', 'OPENAI_MODEL'),
    'xai': ('xAI', 'XAI_API_KEY', 'XAI_MODEL'),
}

def explain(evidence, question, language, *, provider='anthropic', model='', api_key='', consent=False):
    if not consent:
        raise PermissionError('Explicit permission to send this case is required.')
    if provider not in PROVIDERS:
        raise ValueError('Choose Anthropic, OpenAI or xAI.')
    name, key_env, model_env = PROVIDERS[provider]
    key = (api_key or os.environ.get(key_env, '')).strip()
    model = (model or os.environ.get(model_env, '')).strip()
    if not key:
        raise ValueError(f'Enter an API key for {name} or configure {key_env}.')
    if len(key)>4096 or any(ord(c)<33 or ord(c)>126 for c in key):
        raise ValueError('Invalid API key format.')
    if model and not re.fullmatch(r'[A-Za-z0-9._:/-]{1,160}', model):
        raise ValueError('Enter a valid model ID.')
    if provider == 'anthropic':
        return explain_with_claude(evidence, question, language, consent=True, api_key=key, model=model)
    if not model:
        raise ValueError(f'Enter a model ID supported by your {name} account.')
    content = json.dumps({'language':language,'evidence':evidence,'question':question}, ensure_ascii=False)
    if provider == 'openai':
        url='https://api.openai.com/v1/responses'
        payload={'model':model,'instructions':SYSTEM_PROMPT,'input':content,'max_output_tokens':2000,'store':False}
    else:
        url='https://api.x.ai/v1/chat/completions'
        payload={'model':model,'messages':[{'role':'system','content':SYSTEM_PROMPT},{'role':'user','content':content}],'max_tokens':2000}
    request=Request(url,data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    try:
        with urlopen(request,timeout=60) as response:
            result=json.load(response)
        if provider == 'openai':
            text='\n'.join(c.get('text','') for item in result.get('output',[]) if item.get('type')=='message' for c in item.get('content',[]) if c.get('type')=='output_text')
        else:
            text=result.get('choices',[{}])[0].get('message',{}).get('content','')
        if not isinstance(text,str) or not text.strip():
            raise ValueError('Empty response')
        return text.strip()
    except HTTPError as exc:
        raise RuntimeError(f'{name} request failed (HTTP {exc.code}). Check API key, model access and account limits.') from None
    except (URLError,TimeoutError,OSError):
        raise RuntimeError(f'{name} is unavailable. Local evidence is still available.') from None
    except (ValueError,TypeError,KeyError,IndexError,AttributeError):
        raise RuntimeError(f'{name} returned no usable text. Local evidence is still available.') from None
