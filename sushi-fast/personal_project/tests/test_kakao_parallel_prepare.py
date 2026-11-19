from personal_project import native_kakao


def test_preparing_another_report_keeps_first_report_job():
    first = native_kakao.create_job(85121, 85122)
    second = native_kakao.create_job(85121, 85123)
    try:
        assert native_kakao._owned_job(first['jobId'], 85121, 85122).state == 'uploading'
        assert native_kakao._owned_job(second['jobId'], 85121, 85123).state == 'uploading'
    finally:
        with native_kakao._jobs_lock:
            for job_id in (first['jobId'], second['jobId']):
                job = native_kakao._jobs.get(job_id)
                if job:
                    native_kakao._remove_job(job)
