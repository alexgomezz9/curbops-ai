"""Diagnostic for a configured Gemini API key; never prints the key.

    docker compose exec api python -m app.agents.check_models

Google can restrict older model families for newly created projects. This utility
lists the models returned by the configured Google Developer API project.
"""
from __future__ import annotations
import json
import sys
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen
from ..settings import get_settings


def main() -> int:
    config=get_settings()
    if not config.google_api_key:
        print('GOOGLE_API_KEY is missing in the API container environment.', file=sys.stderr)
        return 2
    url='https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000'
    req=Request(url,headers={'x-goog-api-key':config.google_api_key,'Accept':'application/json'})
    try:
        with urlopen(req,timeout=15) as resp:
            payload=json.load(resp)
    except HTTPError as ex:
        print(f'Model listing failed: HTTP {ex.code}. Verify your key/project. No secret has been printed.',file=sys.stderr)
        return 1
    except (URLError,TimeoutError,ValueError) as ex:
        print(f'Model listing failed: {type(ex).__name__}. Check network/proxy settings.',file=sys.stderr)
        return 1
    models=[]
    for model in payload.get('models',[]):
        name=model.get('name','')
        methods=model.get('supportedGenerationMethods',[])
        if 'generateContent' in methods and 'gemini' in name.lower():
            models.append(name.removeprefix('models/'))
    print('Gemini generateContent models visible to your project:')
    for model in sorted(models):
        marker=' <- configured' if model==config.gemini_model else ''
        print(f'  {model}{marker}')
    if config.gemini_model not in models:
        print(f'\nConfigured GEMINI_MODEL={config.gemini_model} is not listed; select one of the above and recreate the API container.')
        return 3
    return 0


if __name__=='__main__':
    raise SystemExit(main())
