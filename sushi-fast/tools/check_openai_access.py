"""Check the configured GPT endpoint without audio or printing credentials."""
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from openai import OpenAI
from odi.EVC.config import OPENAI_EVC_MODEL
from odi.EVC.schema import SegmentEvaluation
from odi.EVC.evaluation import SYSTEM_PROMPT


def diagnostic(exc):
    result = {'exception': type(exc).__name__, 'http_status': getattr(exc, 'status_code', None)}
    for attr in ('code', 'type', 'param'):
        value = getattr(exc, attr, None)
        if isinstance(value, str) and re.fullmatch(r'[a-zA-Z_][a-zA-Z_0-9.]{0,63}', value):
            result[attr] = value
    return result


def main():
    if not os.getenv('OPENAI_API_KEY'):
        raise SystemExit('OPENAI_API_KEY is not set in this terminal.')
    client = OpenAI(max_retries=0, timeout=20)
    url = urlsplit(str(client.base_url))
    print(json.dumps({'model': OPENAI_EVC_MODEL,
        'official_openai_host': url.hostname == 'api.openai.com',
        'base_path_is_v1': url.path.rstrip('/') == '/v1',
        'custom_base_url_set': bool(os.getenv('OPENAI_BASE_URL'))}))
    try:
        client.models.retrieve(OPENAI_EVC_MODEL)
        print('MODEL_LOOKUP_OK')
    except Exception as exc:
        print('MODEL_LOOKUP_FAILED', json.dumps(diagnostic(exc)))
    try:
        client.chat.completions.parse(model=OPENAI_EVC_MODEL,
            messages=[{'role':'system','content':SYSTEM_PROMPT},
                      {'role':'user','content':json.dumps({'latest_speech':'오늘은 발표 연습 시스템의 목적을 설명하겠습니다.', 'current_slide':None},ensure_ascii=False)}],
            response_format=SegmentEvaluation)
        print('STRUCTURED_EVALUATION_OK')
    except Exception as exc:
        print('STRUCTURED_EVALUATION_FAILED', json.dumps(diagnostic(exc)))
        if getattr(exc, 'code', None) == 'model_not_found':
            print('The configured model is unavailable for this endpoint/key/project.')
        raise SystemExit(1)


if __name__ == '__main__':
    main()
