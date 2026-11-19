import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from personal_project.tests.test_scheduled_synthetic_regression import scenario


def test_click_time_and_request_id_remain_stable_after_cancel(scenario):
    client, _, base, _ = scenario
    path = base + '/kakao-clinic/scheduled-deliveries'
    clicked = time.time() - 20
    body = {'clickedAt': clicked, 'requestId': uuid.uuid4().hex}
    first = client.post(path, json=body)
    assert first.status_code == 200
    job = first.json()
    assert job['requestedAt'] == clicked
    assert job['sendAfter'] == clicked + 5400
    assert client.delete(path + '/' + job['id']).status_code == 200
    again = client.post(path, json=body)
    assert again.status_code == 200
    assert again.json()['id'] == job['id']
    assert again.json()['state'] == 'cancelled'


def test_concurrent_retries_share_one_request(scenario):
    client, _, base, _ = scenario
    path = base + '/kakao-clinic/scheduled-deliveries'
    body = {'clickedAt': time.time(), 'requestId': uuid.uuid4().hex}
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: client.post(path, json=body), range(16)))
    assert all(result.status_code == 200 for result in results)
    assert len({result.json()['id'] for result in results}) == 1


def test_future_or_stale_click_is_rejected(scenario):
    client, _, base, _ = scenario
    path = base + '/kakao-clinic/scheduled-deliveries'
    for clicked in (time.time() + 60, time.time() - 3600):
        response = client.post(path, json={'clickedAt': clicked, 'requestId': uuid.uuid4().hex})
        assert response.status_code == 422
