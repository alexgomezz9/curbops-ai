from types import SimpleNamespace
from app.agents.runner import usage_from_llm_result


def test_gemini_tokens_are_read_when_reported_by_langchain():
    response=SimpleNamespace(generations=[[SimpleNamespace(message=SimpleNamespace(usage_metadata={
        'input_tokens': 120, 'output_tokens': 40,
    }))]])
    assert usage_from_llm_result(response)==(120,40)


def test_token_count_is_unknown_when_provider_omits_metadata():
    response=SimpleNamespace(generations=[[SimpleNamespace(message=SimpleNamespace(content='done'))]])
    assert usage_from_llm_result(response) is None
