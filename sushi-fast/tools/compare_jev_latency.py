"""Replay one WAV through the real /update route using GPT and Jev.

Run from sushi-fast. Live provider calls need the normal application dependencies
and TYPESAFE_API_KEY, OPENAI_API_KEY plus the selected STT credentials.
No deployed sessions are touched. ASGI send is measured, NOT Unity receipt.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import os
from pathlib import Path
import statistics
import sys
import time
from uuid import uuid4
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def chunks(path, seconds):
    with wave.open(str(path)) as source:
        params = source.getparams()
        frames = int(params.framerate * seconds)
        offset = 0
        while data := source.readframes(frames):
            count = len(data) // (params.nchannels * params.sampwidth)
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as target:
                target.setparams(params)
                target.writeframes(data)
            yield offset / params.framerate, (offset + count) / params.framerate, buffer.getvalue()
            offset += count


async def run(args):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from odi.EVC import pipeline, router as routes
    from odi.EVC.evaluation import OpenAISegmentEvaluationProvider
    from odi.EVC.jev_evaluation import JevSegmentEvaluationProvider
    from odi.EVC.schema import SmartStartOptions, SlideInfo
    from odi.EVC.session_store import SessionStore
    from odi.EVC.speech2text import provider_for_name, validate_provider_configuration

    if not args.self_test:
        for key_name in ('TYPESAFE_API_KEY', 'OPENAI_API_KEY', 'DEEPGRAM_API_KEY', 'AZURE_SPEECH_KEY'):
            value = os.getenv(key_name, '')
            if value and (not value.isascii() or any(c.isspace() for c in value)):
                raise SystemExit(f'{key_name} contains whitespace or non-ASCII characters; re-enter it without copied spaces')
        missing = [name for name in ('TYPESAFE_API_KEY', 'OPENAI_API_KEY') if not os.getenv(name)]
        if missing:
            raise SystemExit('Missing credentials: ' + ', '.join(missing))
        validate_provider_configuration(args.stt)
    if args.check:
        print('Provider configuration available; no API requests sent.')
        return

    # Synthetic fixtures are ONLY for testing this tool, never benchmark evidence.
    if args.self_test:
        from odi.EVC.tests.test_command_pipeline_api import STTProvider, EvaluationProvider
        stt = STTProvider()
        evaluators = {'gpt': EvaluationProvider(), 'jev': EvaluationProvider()}
    else:
        stt = provider_for_name(args.stt)
        evaluators = {'gpt': OpenAISegmentEvaluationProvider(), 'jev': JevSegmentEvaluationProvider()}

    audio_chunks = list(chunks(args.audio, args.chunk_seconds))
    if not audio_chunks:
        raise SystemExit('Empty audio')
    slides = [] if not args.slides_json else [SlideInfo.model_validate(x) for x in json.loads(args.slides_json.read_text())]
    slide_indices = [0] * len(audio_chunks)
    if args.slide_indices:
        slide_indices = [int(x) for x in args.slide_indices.split(',')]
        if len(slide_indices) != len(audio_chunks):
            raise SystemExit('--slide-indices requires one index per audio chunk')
    store = SessionStore()
    selected = {}
    provider_failure = {}
    async def update(**kwargs):
        provider_failure.clear()
        try:
            return await pipeline.update_pipeline(**kwargs, store=store, stt_provider=stt,
                                                 evaluation_provider=selected[kwargs['session_id']])
        except Exception as exc:
            # Only exception types and numeric statuses; never headers, keys or bodies.
            chain = []
            seen = set()
            current = exc
            while current is not None and id(current) not in seen:
                seen.add(id(current))
                item = {'exception_type': type(current).__name__}
                code = getattr(current, 'code', None)
                if code in ('model_not_found', 'invalid_api_key', 'insufficient_quota', 'rate_limit_exceeded', 'permission_denied'):
                    item['upstream_error_code'] = code
                status = getattr(current, 'status_code', None)
                if status is None:
                    status = getattr(getattr(current, 'response', None), 'status_code', None)
                if type(status) is int:
                    item['upstream_http_status'] = status
                chain.append(item)
                current = current.__cause__ or current.__context__
            provider_failure['exception_chain'] = chain
            raise
    original_store, original_update = routes.session_store, routes.update_pipeline
    routes.session_store, routes.update_pipeline = store, update
    app = FastAPI()
    app.include_router(routes.router)
    observed = {}
    async def timed_app(scope, receive, send):
        start = time.perf_counter()
        async def measured_receive():
            message = await receive()
            if message['type'] == 'http.request' and message.get('body'):
                observed.setdefault('first_body', time.perf_counter())
            return message
        async def measured_send(message):
            await send(message)
            if message['type'] == 'http.response.body' and not message.get('more_body', False):
                observed['asgi_response_ms'] = (time.perf_counter() - observed.get('first_body', start)) * 1000
        await app(scope, measured_receive, measured_send)

    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    metadata = {
        'measurement': 'first ASGI request body received to final ASGI response body sent',
        'unity_receive_or_playback_measured': False,
        'network_upload_download_measured': False,
        'audio_collection_wait_included': False,
        'recording_seconds': audio_chunks[-1][1], 'chunk_seconds': args.chunk_seconds,
        'audio_sha256': hashlib.sha256(args.audio.read_bytes()).hexdigest(),
        'mock_providers': args.self_test, 'rounds': args.rounds,
        'audience_count': args.audience_count, 'seed': args.seed,
        'slides_supplied': bool(slides), 'slide_indices': slide_indices,
        'stt': args.stt, 'evaluation_models': {k: getattr(v, 'model', 'synthetic') for k,v in evaluators.items()},
        'comparison': 'existing GPT workflow versus Jev workflow; GPT summary/reason and differing history retained',
        'reaction_mode': 'legacy update commands; no independent polling',
    }
    (args.output / 'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    try:
        async with AsyncClient(transport=ASGITransport(app=timed_app), base_url='http://benchmark', timeout=None) as client:
            with (args.output / 'segments.jsonl').open('w') as log:
                for trial in range(args.rounds):
                    sessions = {}
                    for name, evaluator in evaluators.items():
                        session = await pipeline.create_pipeline_session(SmartStartOptions(
                            presentation_title=args.title, audience_count=args.audience_count,
                            seed=args.seed, independent_reactions=False), slides=slides, store=store)
                        selected[session.session_id] = evaluator
                        sessions[name] = session
                    for index, (begin, end, audio) in enumerate(audio_chunks):
                        order = ['gpt', 'jev'] if (trial + index) % 2 == 0 else ['jev', 'gpt']
                        for name in order:
                            session = sessions[name]
                            request_id = uuid4()
                            observed.clear()
                            response = await client.post('/xreal_rehear/evc/update',
                                headers={'X-EVC-Session-Token': session.session_token},
                                data={'session_id': str(session.session_id), 'request_id': str(request_id),
                                      'expected_step': str(index), 'client_time_s': str(end),
                                      'current_slide_index': str(slide_indices[index]), 'language': 'ko'},
                                files={'audio': ('segment.wav', audio, 'audio/wav')})
                            if response.status_code != 200:
                                # Do not persist upstream error bodies, which may contain secrets.
                                log.write(json.dumps({'trial': trial + 1, 'segment': index + 1,
                                    'provider': name, 'http_status': response.status_code, 'failed': True,
                                    'error_code': response.json().get('detail', {}).get('code'), **provider_failure}) + '\n')
                                log.flush()
                                raise RuntimeError(f'{name}: segment {index + 1} HTTP {response.status_code}; '
                                    f"code={response.json().get('detail', {}).get('code')}; "
                                    f'diagnostics={provider_failure}; comparison incomplete')
                            data = response.json()
                            record = await store.get_authorized_session(session.session_id, session.session_token)
                            trace = record.timing_traces[request_id]
                            row = {'trial': trial + 1, 'segment': index + 1, 'provider': name,
                                'audio_start_s': begin, 'audio_end_s': end,
                                'asgi_response_ms': observed['asgi_response_ms'],
                                'pipeline_ms': trace.processing_s * 1000,
                                'stt_ms': trace.stt_s * 1000, 'evaluation_ms': trace.evaluation_s * 1000,
                                'post_evaluation_ms': (trace.response_ready_monotonic - trace.evaluation_finished_monotonic) * 1000,
                                'transcript': data['latest_speech'], 'evaluation': data['evaluation'],
                                'audience_count': len(data['audiences']), 'commands': data['commands'],
                                'warnings': data['warnings'], 'mock_providers': args.self_test}
                            assert row['audience_count'] == args.audience_count
                            rows.append(row)
                            log.write(json.dumps(row, ensure_ascii=False) + '\n'); log.flush()
                            print(f"round={trial+1} segment={index+1} {name} response_ms={row['asgi_response_ms']:.1f} commands={len(row['commands'])}", flush=True)
    finally:
        routes.session_store, routes.update_pipeline = original_store, original_update
    summary = {'mock_providers': args.self_test, 'results': {}}
    for name in evaluators:
        group = [r for r in rows if r['provider'] == name]
        summary['results'][name] = {'samples': len(group),
            'segments_without_commands': sum(not r['commands'] for r in group),
            **{metric: {'mean': statistics.mean(r[metric] for r in group),
                        'median': statistics.median(r[metric] for r in group),
                        'max': max(r[metric] for r in group)}
               for metric in ('asgi_response_ms', 'stt_ms', 'evaluation_ms', 'post_evaluation_ms')}}
    paired = []
    for trial in range(1, args.rounds + 1):
        for index in range(1, len(audio_chunks) + 1):
            pair = {r['provider']: r for r in rows if r['trial'] == trial and r['segment'] == index}
            paired.append({'trial': trial, 'segment': index,
                'gpt_minus_jev_ms': pair['gpt']['asgi_response_ms'] - pair['jev']['asgi_response_ms'],
                'same_transcript': pair['gpt']['transcript'] == pair['jev']['transcript']})
    summary['paired_comparisons'] = paired
    (args.output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--title', default='Re:hear: XR 기반 실시간 발표 코칭 시스템')
    parser.add_argument('--stt', choices=['deepgram', 'azure'], default='deepgram')
    parser.add_argument('--chunk-seconds', type=float, default=30)
    parser.add_argument('--rounds', type=int, default=3)
    parser.add_argument('--audience-count', type=int, default=6)
    parser.add_argument('--seed', type=int, default=2026)
    parser.add_argument('--slides-json', type=Path)
    parser.add_argument('--slide-indices', help='Comma-separated index per audio chunk')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--self-test', action='store_true', help='Synthetic providers; never a live speed comparison')
    args = parser.parse_args()
    if args.chunk_seconds <= 0 or args.rounds < 1 or not 1 <= args.audience_count <= 50:
        parser.error('invalid chunk duration, rounds or audience count')
    if args.env_file:
        from dotenv import load_dotenv
        load_dotenv(args.env_file, override=False)
    asyncio.run(run(args))


if __name__ == '__main__':
    main()
