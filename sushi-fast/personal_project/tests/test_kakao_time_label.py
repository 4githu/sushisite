import json
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def pure_results(tmp_path_factory):
    source = Path(__file__).resolve().parents[3] / "ops" / "kakao_bridge.swift"
    swift = source.read_text()
    helpers = swift[swift.index("func isTimeLabel("):swift.index("// Kakao converts only")]
    temp = tmp_path_factory.mktemp("kakao-time-label")
    harness = temp / "main.swift"
    harness.write_text("import Foundation\nimport CoreGraphics\n" + helpers + r'''
let labels = try JSONSerialization.jsonObject(with: FileHandle.standardInput.readDataToEndOfFile()) as! [String]
let left = CGRect(x:0,y:0,width:10,height:10)
let right = CGRect(x:20,y:0,width:10,height:10)
let overlap = CGRect(x:5,y:0,width:10,height:10)
let result: [String:Any] = ["labels":labels.map(isTimeLabel),
 "directions":[messageDirection(right,left),messageDirection(left,right),
               messageDirection(left,overlap),messageDirection(nil,left),messageDirection(left,nil)],
 "profileFallback":[messageDirection(left,nil,hasProfile:true),
                    messageDirection(left,nil,hasProfile:false),
                    messageDirection(right,left,hasProfile:true),
                    messageDirection(left,right,hasProfile:true)]]
print(String(data:try JSONSerialization.data(withJSONObject:result),encoding:.utf8)!)
''')
    exe = temp / "pure-time-tests"
    subprocess.run(["swiftc", str(harness), "-o", str(exe)], check=True, capture_output=True)
    labels = ["오후 9:14", "오전 12:00", "AM 9:14", "9:14 pm", "23:59", "0:00", "09:04",
              "1", "249", "2026-11-09", "2026.11.09", "9:14 회의", "오후 9:14 확인", "24:00",
              "23:60", "오후 13:01", "오전 0:30", "AM 00:01", "9:14\n메시지", "",
              "1\n오후 10:05", "2\nAM 9:14", "0\n오후 10:05", "01\n오후 10:05",
              "1\n오후 25:05", "1\n오후 10:05\n추가", "오후 10:05\n1", "1 오후 10:05",
              "1\n2026-11-09", "1\n오후 10:05 확인", "1\n\n오후 10:05"]
    proc = subprocess.run([str(exe)], input=json.dumps(labels, ensure_ascii=False), text=True,
                          capture_output=True, check=True)
    return labels, json.loads(proc.stdout)


def test_clock_labels_are_anchored_and_valid(pure_results):
    labels, result = pure_results
    expected = [True] * 7 + [False] * 13 + [True, True, False, True] + [False] * 7
    assert result["labels"] == expected


def test_explicit_profile_fallback_preserves_incoming_without_inventing_outgoing(pure_results):
    assert pure_results[1]["profileFallback"] == ["incoming", "unknown", "outgoing", "incoming"]


def test_direction_requires_nonoverlapping_content_and_clock_bounds(pure_results):
    assert pure_results[1]["directions"] == ["outgoing", "incoming", "unknown", "unknown", "unknown"]
