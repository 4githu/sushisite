"""Isolated synthetic regressions for remaining Aura review findings."""
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

os.environ.setdefault('PERSONAL_PROJECT_DB_PATH', str(Path(tempfile.mkdtemp(prefix='aura-review-')) / 'bootstrap.sqlite'))

import pytest
from fastapi import HTTPException
from personal_project import db as project_db, repository as repo
from personal_project import ai_report
from personal_project.make_report_test import db_repository as score_repo
from personal_project.report_pdf import _html
from personal_project.schemas import ClinicRoundCreate, SchoolCreate, TargetReportUpdate


@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    monkeypatch.setattr(project_db, 'DB_PATH', tmp_path / 'synthetic.sqlite')
    monkeypatch.setattr(repo, 'ATTACHMENT_ROOT', tmp_path / 'images')
    project_db.init_db()
    school = repo.create_school(101, SchoolCreate(admission_year=2026, school_name='합성학교'))
    round_ = repo.create_clinic_round(101, ClinicRoundCreate(
        school_id=school['id'], round_number=1, student_names=['합성 학생'],
        start_time=datetime.fromisoformat('2026-09-16T09:00:00+09:00'),
        end_time=datetime.fromisoformat('2026-09-16T10:00:00+09:00')))
    report = repo.get_or_create_target_report(101, round_['targets'][0]['id'])
    return tmp_path, round_, report


def test_reopening_report_clears_submitted_timestamp(synthetic):
    _, _, report = synthetic
    submitted = repo.update_target_report(101, report['id'], None, submit=True)
    assert submitted['status'] == 'submitted'
    assert submitted['submittedAt']
    reopened = repo.update_target_report(101, report['id'], TargetReportUpdate(status='draft'))
    assert reopened['status'] == 'draft'
    assert reopened['submittedAt'] is None


def test_pdf_null_generated_assessment_preserves_manual_items(tmp_path):
    html = _html({
        'studentName': '합성 학생',
        'assessmentJson': {'items': [{'name': '수동 평가', 'score': 4}]},
        'generatedReportJson': {'assessment': None},
    }, [], tmp_path)
    assert '수동 평가' in html


def test_init_db_does_not_overwrite_historical_round_amount(synthetic):
    _, round_, _ = synthetic
    with project_db.connection() as conn:
        conn.execute('UPDATE aura_clinic_rounds SET hourly_rate = 12345, amount = 67890 WHERE id = ?', (round_['id'],))
        conn.commit()
    project_db.init_db()
    with project_db.connection() as conn:
        row = conn.execute('SELECT hourly_rate, amount FROM aura_clinic_rounds WHERE id = ?', (round_['id'],)).fetchone()
    assert tuple(row) == (12345, 67890)


@pytest.fixture
def fake_generation(synthetic, monkeypatch):
    tmp_path, round_, _ = synthetic
    monkeypatch.setattr(score_repo, 'DB_PATH', tmp_path / 'synthetic.sqlite')
    # ai_report imported the repository functions directly; their global DB_PATH is shared.
    calls = []

    class FakeService:
        last_cache_mode = 'implicit'
        cache_notice = None

        def __init__(self, **kwargs):
            pass

        @staticmethod
        def read_prompt():
            return 'synthetic prompt'

        @staticmethod
        def prompt_hash(prompt):
            return 'synthetic-prompt-hash'

        def generate(self, *, report_input, score_mode, score_format):
            calls.append((json.loads(json.dumps(report_input)), score_mode,
                          json.loads(json.dumps(score_format))))
            assessment = ({'formatName': score_format['name'],
                           'items': [{'name': name, 'score': 3} for name in score_format['items']]}
                          if score_format else None)
            return {'assessment': assessment}, None

        def close(self):
            pass

    monkeypatch.setattr(ai_report, 'GeminiReportService', FakeService)
    target_id = round_['targets'][0]['id']
    report_input = score_repo.build_report_input(target_id)

    def generate(**kwargs):
        return ai_report.generate(101, target_id, **kwargs)['results'][0]

    return generate, report_input, calls


def test_active_score_format_change_invalidates_ai_input_hash(fake_generation):
    generate, report_input, calls = fake_generation
    first_id = score_repo.save_generated_score_format(report_input, '합성 평가', ['첫 항목'])
    first = generate()
    assert first['reused'] is False
    assert calls[-1][0]['options']['scoreFormatSnapshot'] == calls[-1][2] == {
        'id': first_id, 'name': '합성 평가', 'items': ['첫 항목'], 'source': 'generated'}
    again = generate()
    assert again['reused'] is True
    assert (again['runId'], again['inputHash']) == (first['runId'], first['inputHash'])
    assert len(calls) == 1
    with score_repo.connect() as conn:
        stored = conn.execute('SELECT input_json FROM clinic_report_generation_runs WHERE id=?',
                              (first['runId'],)).fetchone()[0]
    assert json.loads(stored)['options']['scoreFormatSnapshot'] == calls[-1][2]
    second_id = score_repo.save_generated_score_format(report_input, '합성 평가', ['교체 항목'])
    assert second_id != first_id
    changed = generate()
    assert changed['reused'] is False
    assert changed['runId'] != first['runId']
    assert changed['inputHash'] != first['inputHash']
    assert calls[-1][2]['id'] == second_id


def test_same_score_format_id_content_and_order_changes_hash(fake_generation):
    generate, report_input, calls = fake_generation
    format_id = score_repo.save_generated_score_format(report_input, '합성 평가', ['A', 'B'])
    hashes = [generate()['inputHash']]
    for name, items in [('바뀐 이름', ['A', 'B']), ('바뀐 이름', ['A', 'C']),
                        ('바뀐 이름', ['C', 'A'])]:
        with score_repo.connect() as conn:
            conn.execute('UPDATE clinic_report_score_formats SET name=?, items_json=? WHERE id=?',
                         (name, json.dumps(items), format_id))
            conn.commit()
        result = generate()
        assert result['reused'] is False
        assert result['inputHash'] not in hashes
        assert calls[-1][0]['options']['scoreFormatSnapshot'] == calls[-1][2]
        hashes.append(result['inputHash'])


def test_explicit_db_format_version_changes_hash(fake_generation):
    generate, report_input, calls = fake_generation
    score_repo.migrate()
    with score_repo.connect() as conn:
        conn.execute('ALTER TABLE clinic_report_score_formats ADD COLUMN version INTEGER')
        conn.commit()
    format_id = score_repo.save_generated_score_format(report_input, '합성 평가', ['A'])
    with score_repo.connect() as conn:
        conn.execute('UPDATE clinic_report_score_formats SET version=1 WHERE id=?', (format_id,))
        conn.commit()
    first = generate()
    assert calls[-1][2]['version'] == 1
    with score_repo.connect() as conn:
        conn.execute('UPDATE clinic_report_score_formats SET version=2 WHERE id=?', (format_id,))
        conn.commit()
    second = generate()
    assert second['reused'] is False
    assert second['inputHash'] != first['inputHash']
    assert calls[-1][0]['options']['scoreFormatSnapshot']['version'] == 2


def test_no_format_records_null_and_auto_fallback_keeps_requested_mode(fake_generation, monkeypatch):
    generate, _, calls = fake_generation
    def forbidden_lookup(_):
        raise AssertionError('none must not look up an active format')
    first = generate()
    assert calls[-1][0]['options']['scoreFormatSnapshot'] is None
    assert calls[-1][1:] == ('auto', None)
    second = generate()
    assert second['reused'] is False
    assert second['inputHash'] != first['inputHash']
    assert calls[-1][0]['options']['requestedScoreMode'] == 'auto'
    assert calls[-1][0]['options']['scoreMode'] == 'none'
    assert calls[-1][0]['options']['scoreFormatSnapshot'] is None
    monkeypatch.setattr(ai_report, 'get_active_score_format', forbidden_lookup)
    generate(score_mode='none')


def test_none_ignores_active_format_and_force_bypasses_cache(fake_generation):
    generate, report_input, calls = fake_generation
    score_repo.save_generated_score_format(report_input, '합성', ['A'])
    auto = generate()
    none = generate(score_mode='none')
    assert none['inputHash'] != auto['inputHash']
    assert calls[-1][1:] == ('none', None)
    assert calls[-1][0]['options']['scoreFormatSnapshot'] is None
    score_repo.save_generated_score_format(report_input, '다른 양식', ['B'])
    reused = generate(score_mode='none')
    assert reused['reused'] is True
    assert (reused['runId'], reused['inputHash']) == (none['runId'], none['inputHash'])
    forced = generate(score_mode='none', force=True)
    assert forced['reused'] is False
    assert forced['inputHash'] == none['inputHash']
    assert forced['runId'] != none['runId']


def test_previous_generation_fallback_snapshot_is_stable(fake_generation):
    generate, report_input, calls = fake_generation
    score_repo.migrate()
    target_id = report_input['target']['targetId']
    prior_id = score_repo.start_run(target_id, 'older-model', 'implicit', 'older-prompt')
    score_repo.finish_run(prior_id, response_json={
        'assessment': {'formatName': '지난 양식', 'items': [{'name': 'A'}, {'name': 'B'}]}})
    first = generate()
    assert calls[-1][0]['options']['scoreFormatSnapshot'] == calls[-1][2] == {
        'id': None, 'name': '지난 양식', 'items': ['A', 'B'], 'source': 'previous_generation'}
    again = generate()
    assert again['reused'] is True
    assert again['inputHash'] == first['inputHash']


def test_first_user_items_fallback_tracks_effective_selection(fake_generation, monkeypatch):
    generate, _, calls = fake_generation
    # No DB format is persisted here: after first completion the effective selection
    # switches from user to previous_generation, then stabilizes on that fallback.
    monkeypatch.setattr(ai_report, 'save_generated_score_format', lambda *args: None)
    items = [{'name': 'A', 'score': 4}, {'name': 'B', 'score': 2}]
    first = generate(assessment_items=items)
    assert calls[-1][0]['options']['scoreFormatSnapshot'] == calls[-1][2] == {
        'id': None, 'name': '학습 내용 및 암기 정도 평가', 'items': ['A', 'B'], 'source': 'user'}
    second = generate(assessment_items=items)
    assert second['reused'] is False
    assert second['inputHash'] != first['inputHash']
    assert calls[-1][2]['source'] == 'previous_generation'
    third = generate(assessment_items=items)
    assert third['reused'] is True
    assert (third['runId'], third['inputHash']) == (second['runId'], second['inputHash'])


def test_first_user_items_persist_then_reuse_active_selection(fake_generation):
    generate, _, calls = fake_generation
    items = [{'name': 'A', 'score': 4}, {'name': 'B', 'score': 2}]
    first = generate(assessment_items=items)
    assert calls[-1][2]['source'] == 'user'
    second = generate(assessment_items=items)
    assert second['reused'] is False  # persisted DB format is a new effective selection
    assert second['inputHash'] != first['inputHash']
    assert calls[-1][2]['items'] == ['A', 'B']
    assert calls[-1][2]['source'] == 'generated'
    third = generate(assessment_items=items)
    assert third['reused'] is True
    assert (third['runId'], third['inputHash']) == (second['runId'], second['inputHash'])


def test_failed_parent_file_cleanup_leaves_recoverable_reference(synthetic, monkeypatch):
    tmp_path, round_, report = synthetic
    repo.save_target_report_attachment(101, round_['targets'][0]['id'], 'blank_test',
                                       'synthetic.png', 'image/png', b'synthetic')
    assert list((tmp_path / 'images').rglob('*.png'))
    def fail_cleanup(_files):
        raise OSError('synthetic filesystem outage')
    monkeypatch.setattr(repo, '_remove_attachment_files', fail_cleanup)
    with pytest.raises(OSError, match='synthetic filesystem outage'):
        repo.delete_clinic_round(101, round_['id'])
    with project_db.connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM aura_report_attachments WHERE target_report_id = ?',
                            (report['id'],)).fetchone()[0] == 0
        journal = conn.execute('SELECT * FROM aura_attachment_cleanup_journal').fetchone()
        assert journal['user_id'] == 101 and journal['target_report_id'] == report['id']
        assert journal['status'] == 'pending'
        assert journal['reason'] == 'round'
    assert repo.dry_run_attachment_cleanup(journal['id'])['classification'] == 'safe'
    assert list((tmp_path / 'images').rglob('*.png'))


def test_parent_journal_rolls_back_with_failed_commit(synthetic, monkeypatch):
    tmp_path, round_, _ = synthetic
    attachment = repo.save_target_report_attachment(101, round_['targets'][0]['id'], 'blank_test',
                                                     'synthetic.png', 'image/png', b'synthetic')
    real_connection = repo.connection
    from contextlib import contextmanager
    class Proxy:
        def __init__(self, conn): self.conn = conn
        def __getattr__(self, name): return getattr(self.conn, name)
        def commit(self): raise OSError('commit blocked')
    @contextmanager
    def blocked():
        with real_connection() as conn:
            yield Proxy(conn)
    monkeypatch.setattr(repo, 'connection', blocked)
    with pytest.raises(OSError, match='commit blocked'):
        repo.delete_clinic_round(101, round_['id'])
    monkeypatch.setattr(repo, 'connection', real_connection)
    with project_db.connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM aura_attachment_cleanup_journal').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM aura_report_attachments WHERE id=?', (attachment['id'],)).fetchone()[0] == 1
    assert list((tmp_path / 'images').rglob('*.png'))


def test_pending_dry_run_is_read_only_and_refuses_hazards(synthetic, monkeypatch):
    tmp_path, round_, _ = synthetic
    repo.save_target_report_attachment(101, round_['targets'][0]['id'], 'blank_test',
                                       'synthetic.png', 'image/png', b'synthetic')
    monkeypatch.setattr(repo, '_remove_attachment_files', lambda _: None)  # simulated post-commit crash
    repo.delete_clinic_round(101, round_['id'])
    with project_db.connection() as conn:
        row = conn.execute('SELECT * FROM aura_attachment_cleanup_journal').fetchone()
        journal_id = row['id']
    project_db.init_db()  # synthetic restart must retain the pending provenance
    with project_db.connection() as conn:
        assert conn.execute('SELECT status FROM aura_attachment_cleanup_journal WHERE id=?', (journal_id,)).fetchone()[0] == 'pending'
    path = next((tmp_path / 'images').rglob('*.png'))
    assert repo.dry_run_attachment_cleanup(journal_id)['classification'] == 'safe'
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(result['classification'] == 'safe' for result in pool.map(repo.dry_run_attachment_cleanup, [journal_id] * 8))
    assert repo.dry_run_attachment_cleanup(999999)['classification'] == 'ambiguous'
    assert path.is_file()
    with project_db.connection() as conn:
        assert conn.execute('SELECT status FROM aura_attachment_cleanup_journal WHERE id=?', (journal_id,)).fetchone()[0] == 'pending'
        conn.execute('UPDATE aura_attachment_cleanup_journal SET storage_name=? WHERE id=?', ('../escape.png', journal_id))
        conn.commit()
    assert repo.dry_run_attachment_cleanup(journal_id)['classification'] == 'unsafe'
    with project_db.connection() as conn:
        conn.execute('UPDATE aura_attachment_cleanup_journal SET storage_name=? WHERE id=?', (row['storage_name'], journal_id))
        conn.commit()
    path.write_bytes(b'changed')
    assert repo.dry_run_attachment_cleanup(journal_id)['classification'] == 'unsafe'
    path.unlink()
    path.symlink_to(tmp_path / 'outside')
    assert repo.dry_run_attachment_cleanup(journal_id)['classification'] == 'unsafe'
    path.unlink()
    assert repo.dry_run_attachment_cleanup(journal_id)['classification'] == 'missing'


def test_live_reference_blocks_pending_candidate(synthetic, monkeypatch):
    _, round_, _ = synthetic
    repo.save_target_report_attachment(101, round_['targets'][0]['id'], 'blank_test',
                                       'synthetic.png', 'image/png', b'synthetic')
    monkeypatch.setattr(repo, '_remove_attachment_files', lambda _: None)
    repo.delete_clinic_round(101, round_['id'])
    with project_db.connection() as conn:
        row = conn.execute('SELECT * FROM aura_attachment_cleanup_journal').fetchone()
    school = repo.create_school(202, SchoolCreate(admission_year=2026, school_name='다른학교'))
    other = repo.create_clinic_round(202, ClinicRoundCreate(
        school_id=school['id'], round_number=1, student_names=['가상'],
        start_time=datetime.fromisoformat('2026-09-17T09:00:00+09:00'),
        end_time=datetime.fromisoformat('2026-09-17T10:00:00+09:00')))
    report = repo.get_or_create_target_report(202, other['targets'][0]['id'])
    with project_db.connection() as conn:
        conn.execute("""INSERT INTO aura_report_attachments
            (user_id,target_report_id,kind,mime_type,storage_name,byte_size)
            VALUES (202,?,'blank_test','image/png',?,9)""", (report['id'], row['storage_name']))
        conn.commit()
    assert repo.dry_run_attachment_cleanup(row['id'])['classification'] == 'unsafe'


def test_journal_records_school_and_individual_deletions(synthetic):
    _, round_, report = synthetic
    school_id = round_['schoolId']
    first = repo.save_target_report_attachment(101, round_['targets'][0]['id'], 'blank_test',
                                               'one.png', 'image/png', b'one')
    repo.delete_target_report_attachment(101, first['id'])
    second = repo.save_target_report_attachment(101, round_['targets'][0]['id'], 'blank_test',
                                                'two.png', 'image/png', b'two')
    repo.delete_school(101, school_id)
    with project_db.connection() as conn:
        records = conn.execute('SELECT * FROM aura_attachment_cleanup_journal ORDER BY id').fetchall()
    assert [(r['attachment_id'], r['reason'], r['status']) for r in records] == [
        (first['id'], 'attachment', 'completed'), (second['id'], 'school', 'completed')]
    assert all(r['target_report_id'] == report['id'] and r['user_id'] == 101 for r in records)
    assert repo.dry_run_attachment_cleanup(records[0]['id'])['classification'] == 'unsafe'


def test_pending_symlink_parent_and_idempotent_dry_run(synthetic, monkeypatch):
    tmp_path, round_, report = synthetic
    repo.save_target_report_attachment(101, round_['targets'][0]['id'], 'blank_test',
                                       'test.png', 'image/png', b'test')
    monkeypatch.setattr(repo, '_remove_attachment_files', lambda _: None)
    repo.delete_clinic_round(101, round_['id'])
    with project_db.connection() as conn:
        journal_id = conn.execute('SELECT id FROM aura_attachment_cleanup_journal').fetchone()[0]
    directory = tmp_path / 'images' / '101' / str(report['id'])
    relocated = tmp_path / 'relocated'
    directory.rename(relocated)
    directory.symlink_to(relocated, target_is_directory=True)
    assert repo.dry_run_attachment_cleanup(journal_id)['classification'] == 'unsafe'
    assert repo.dry_run_attachment_cleanup(journal_id)['classification'] == 'unsafe'
    assert list(relocated.iterdir())


def test_postcommit_unlink_failure_reports_committed_deletion(synthetic, monkeypatch):
    _, round_, _ = synthetic
    attachment = repo.save_target_report_attachment(101, round_['targets'][0]['id'], 'blank_test',
                                                     'synthetic.png', 'image/png', b'synthetic')
    def fail_unlink(*args, **kwargs):
        raise OSError('synthetic filesystem outage')
    monkeypatch.setattr(repo.os, 'unlink', fail_unlink)
    with pytest.raises(HTTPException, match='삭제는 완료됐으나') as exc:
        repo.delete_target_report_attachment(101, attachment['id'])
    assert exc.value.status_code == 500
    with project_db.connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM aura_report_attachments WHERE id=?', (attachment['id'],)).fetchone()[0] == 0
        assert conn.execute('SELECT status FROM aura_attachment_cleanup_journal').fetchone()[0] == 'pending'


def test_student_removal_refuses_existing_report_and_preserves_file(synthetic):
    tmp_path, round_, _ = synthetic
    target = round_['targets'][0]['id']
    repo.save_target_report_attachment(101, target, 'blank_test', 'synthetic.png', 'image/png', b'synthetic')
    path = next((tmp_path / 'images').rglob('*.png'))
    with pytest.raises(HTTPException) as refusal:
        repo.delete_round_target(101, target, confirm=True)
    assert refusal.value.status_code == 409
    assert path.read_bytes() == b'synthetic'
