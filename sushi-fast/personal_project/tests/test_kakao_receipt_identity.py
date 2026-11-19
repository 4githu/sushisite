import json,subprocess
from pathlib import Path


def test_receipt_diagnostics_explain_missing_direction_without_private_data(tmp_path):
    source=(Path(__file__).resolve().parents[3]/'ops/kakao_bridge.swift').read_text()
    assert 'func attachmentReceiptDiagnostics(' in source
    helper=source[source.index('func attachmentReceiptDiagnostics('):source.index('// Kakao converts')]
    code='import Foundation\n'+helper+'''\nlet before:[[String:Any]]=[["identity":"old"]]
let after:[[String:Any]]=[["identity":"old"],["identity":"new","direction":"unknown","photo":false,"hasImage":true,"hasClock":false,"hasShare":true,"hasText":false,"text":"PRIVATE"]]
let result=attachmentReceiptDiagnostics(before,after,budgetExceeded:false,samples:2)
print(String(data:try JSONSerialization.data(withJSONObject:result),encoding:.utf8)!)
'''
    p=tmp_path/'main.swift';p.write_text(code);binary=tmp_path/'diag-test'
    subprocess.run(['swiftc',str(p),'-o',str(binary)],capture_output=True,check=True)
    result=json.loads(subprocess.check_output([str(binary)],text=True))
    assert result['newRows']==1 and result['newUnknown']==1 and result['newHasImage']==1
    assert result['newHasClock']==0 and result['newPhoto']==0 and result['samples']==2
    assert 'PRIVATE' not in json.dumps(result) and 'identity' not in result

def test_attachment_diagnostics_includes_nonidentifying_relative_geometry():
    source=(Path(__file__).resolve().parents[3]/'ops/kakao_bridge.swift').read_text()
    assert 'newPhotoMinLeftPermille' in source
    assert 'newPhotoMaxRightPermille' in source

def test_grouped_images_direction_requires_strict_right_alignment(tmp_path):
    source=(Path(__file__).resolve().parents[3]/'ops/kakao_bridge.swift').read_text()
    assert 'func groupedImageDirection(' in source
    helper=source[source.index('func groupedImageDirection('):source.index('func attachmentReceiptDiagnostics(')]
    code='import Foundation\n'+helper+'''\nprint(groupedImageDirection(photo:true,hasProfile:false,hasClock:false,imageCount:4,left:302,right:968))
print(groupedImageDirection(photo:true,hasProfile:true,hasClock:false,imageCount:4,left:302,right:968))
print(groupedImageDirection(photo:true,hasProfile:false,hasClock:false,imageCount:4,left:100,right:968))
print(groupedImageDirection(photo:true,hasProfile:false,hasClock:false,imageCount:1,left:302,right:968))
print(groupedImageDirection(photo:true,hasProfile:false,hasClock:false,imageCount:4,left:302,right:850))
'''
    p=tmp_path/'main.swift';p.write_text(code);binary=tmp_path/'group'
    subprocess.run(['swiftc',str(p),'-o',str(binary)],capture_output=True,check=True)
    assert subprocess.check_output([str(binary)],text=True).splitlines()==['outgoing','unknown','unknown','unknown','unknown']


def test_new_receipt_survives_clock_grouping_and_rejects_old_or_incoming(tmp_path):
    source=(Path(__file__).resolve().parents[3]/'ops/kakao_bridge.swift').read_text()
    helper=source[source.index('func newOutgoingReceipt('):source.index('func messageDirection(')]
    code='import Foundation\n'+helper+'''\nlet before:[[String:Any]]=[["identity":"old","direction":"outgoing","photo":true,"text":"note"]]
let regrouped:[[String:Any]]=[["identity":"old","direction":"unknown","photo":true],["identity":"new","direction":"outgoing","photo":true,"text":"note"]]
let oldOnly:[[String:Any]]=[["identity":"old","direction":"outgoing","photo":true,"text":"note"]]
let incoming:[[String:Any]]=[["identity":"new","direction":"incoming","photo":true,"text":"note"]]
let unknown:[[String:Any]]=[["identity":"new","direction":"unknown","photo":true,"text":"note"]]
let checks=[newOutgoingReceipt(before,regrouped,attachment:true),newOutgoingReceipt(before,regrouped,text:"note"),newOutgoingReceipt(before,oldOnly,attachment:true),newOutgoingReceipt(before,incoming,attachment:true),newOutgoingReceipt(before,unknown,attachment:true)]
print(String(data:try JSONSerialization.data(withJSONObject:checks),encoding:.utf8)!)
'''
    p=tmp_path/'main.swift';p.write_text(code);binary=tmp_path/'receipt-test'
    subprocess.run(['swiftc',str(p),'-o',str(binary)],capture_output=True,check=True)
    assert json.loads(subprocess.check_output([str(binary)],text=True))==[True,True,False,False,False]
