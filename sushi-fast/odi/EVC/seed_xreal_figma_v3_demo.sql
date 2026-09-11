-- Restores the Figma V3 report demo for the local Re:hear/Xreal ODI account.
-- The statements are idempotent: rerunning this file refreshes only figma-v3-* rows.

BEGIN IMMEDIATE;

INSERT INTO templates (template_id, owner_id, template, created_at, updated_at)
SELECT
  'figma-v3-report-template',
  '7',
  json_set(
    template,
    '$.id', 'figma-v3-report-template',
    '$.template_id', 'figma-v3-report-template',
    '$.owner_id', '7'
  ),
  '2026-09-10T20:00:00+09:00',
  '2026-09-10T20:00:00+09:00'
FROM sessions
WHERE session_id = 'session_7d7d034c4360'
ON CONFLICT(template_id) DO UPDATE SET
  template = excluded.template,
  updated_at = excluded.updated_at;

INSERT INTO templates (template_id, owner_id, template, created_at, updated_at) VALUES
(
  'figma-v3-academic-template', '7',
  json('{"id":"figma-v3-academic-template","template_id":"figma-v3-academic-template","owner_id":"7","type":"presentation","description":"학회 발표와 질의응답을 연습하는 템플릿입니다.","environment":{"title":"학회 발표 및 Q&A","purpose":"연구 결과 공유","language":"한국어","place":"학회 발표장","duration_minutes":30,"question_count":3},"audience":{"audience_type":"학회 청중","audience_count":50,"expertise_level":"높음","interest_level":"중간"},"files":{"slide":{"original_name":"학회 발표 슬라이드.pdf"},"script":{"original_name":"발표 스크립트.txt"},"paper":{"original_name":"참고 논문.pdf"}}}'),
  '2026-09-10T20:00:00+09:00', '2026-09-10T20:00:00+09:00'
),
(
  'figma-v3-seminar-template', '7',
  json('{"id":"figma-v3-seminar-template","template_id":"figma-v3-seminar-template","owner_id":"7","type":"presentation","description":"세미나실에서 30분 발표를 연습하는 템플릿입니다.","environment":{"title":"세미나실 발표 30분","purpose":"아이디어 제안","language":"한국어","place":"세미나실","duration_minutes":30,"question_count":2},"audience":{"audience_type":"일반 청중","audience_count":6,"expertise_level":"보통","interest_level":"높음"},"files":{"slide":{"original_name":"세미나 발표 슬라이드.pdf"},"script":{"original_name":"발표 스크립트.txt"},"paper":null}}'),
  '2026-09-10T20:00:00+09:00', '2026-09-10T20:00:00+09:00'
),
(
  'figma-v3-ir-template', '7',
  json('{"id":"figma-v3-ir-template","template_id":"figma-v3-ir-template","owner_id":"7","type":"presentation","description":"투자자를 대상으로 하는 IR 발표 템플릿입니다.","environment":{"title":"투자 IR 발표 10분","purpose":"투자 제안","language":"한국어","place":"회의실","duration_minutes":10,"question_count":3},"audience":{"audience_type":"투자 심사역","audience_count":6,"expertise_level":"높음","interest_level":"중간"},"files":{"slide":{"original_name":"IR 피치덱.pdf"},"script":{"original_name":"발표 스크립트.txt"},"paper":null}}'),
  '2026-09-10T20:00:00+09:00', '2026-09-10T20:00:00+09:00'
),
(
  'figma-v3-portfolio-template', '7',
  json('{"id":"figma-v3-portfolio-template","template_id":"figma-v3-portfolio-template","owner_id":"7","type":"interview","description":"포트폴리오 기반 실무자 면접 템플릿입니다.","environment":{"company_name":"디자인 스튜디오","position":"포트폴리오 면접 대비","interview_context":"포트폴리오 면접","duration_minutes":50,"interviewer_count":2},"files":{"slide":null,"script":null,"paper":null}}'),
  '2026-09-10T20:00:00+09:00', '2026-09-10T20:00:00+09:00'
),
(
  'figma-v3-executive-template', '7',
  json('{"id":"figma-v3-executive-template","template_id":"figma-v3-executive-template","owner_id":"7","type":"interview","description":"임원과 직무 전문가가 참여하는 심층 면접 템플릿입니다.","environment":{"company_name":"테크 기업","position":"고난이도 임원 면접 대비","interview_context":"임원 면접","duration_minutes":20,"interviewer_count":4},"files":{"slide":null,"script":null,"paper":null}}'),
  '2026-09-10T20:00:00+09:00', '2026-09-10T20:00:00+09:00'
)
ON CONFLICT(template_id) DO UPDATE SET
  template = excluded.template,
  updated_at = excluded.updated_at;

INSERT INTO sessions (
  session_id, user_id, template_id, template, feedback, state,
  started_at, ended_at, created_at, updated_at
)
SELECT
  'figma-v3-report-session',
  '7',
  'figma-v3-report-template',
  t.template,
  source.feedback,
  'completed',
  '2026-09-10T20:00:00+09:00',
  '2026-09-10T20:35:00+09:00',
  '2026-09-10T20:00:00+09:00',
  '2026-09-10T20:35:00+09:00'
FROM templates t
JOIN sessions source ON source.session_id = 'session_7d7d034c4360'
WHERE t.template_id = 'figma-v3-report-template'
ON CONFLICT(session_id) DO UPDATE SET
  template_id = excluded.template_id,
  template = excluded.template,
  feedback = excluded.feedback,
  state = excluded.state,
  started_at = excluded.started_at,
  ended_at = excluded.ended_at,
  updated_at = excluded.updated_at;

UPDATE users
SET
  recent_template = (SELECT template FROM templates WHERE template_id = 'figma-v3-report-template'),
  config = json_set(
    json_remove(config, '$.dashboard.average_score', '$.statistics.session_count'),
    '$.favorite_template_ids',
    json('["figma-v3-report-template","figma-v3-academic-template","figma-v3-seminar-template","figma-v3-ir-template","figma-v3-portfolio-template","figma-v3-executive-template","template_3a8fa15b5a64"]'),
    '$.preferences.report_view_version', 'v3',
    '$.preferences.show_timeline_video', 1,
    '$.demo_mode', 1,
    '$.demo_scenario_id', 'figma-v3-report',
    '$.statistics.practice_minutes', 62
  )
WHERE user_id = '7';

COMMIT;
