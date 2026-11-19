import json,shutil,subprocess,sys
from pathlib import Path
import pytest

@pytest.mark.parametrize('saved,requested,expected',[(1,4,2),(4,4,0)])
def test_cached_attempt_must_match_reproduction_conditions(tmp_path,saved,requested,expected):
    source=Path(__file__).resolve().parents[3]/'ops/kakao_sequence_check.py'
    script=tmp_path/'ops/kakao_sequence_check.py';script.parent.mkdir();shutil.copy2(source,script)
    ledger=tmp_path/'sushi-fast/.runtime/kakao-live-checks';ledger.mkdir(parents=True)
    path=ledger/'sequence-20261111-installed-fixture.json'
    receipt={'state':'succeeded','pages':saved,'closedFirst':True};path.write_text(json.dumps(receipt))
    result=subprocess.run([sys.executable,str(script),'--attempt-id','fixture','--pages',str(requested),'--close-first'],capture_output=True,text=True)
    assert result.returncode==expected
    assert json.loads(path.read_text())==receipt
    assert len(list(ledger.iterdir()))==1
