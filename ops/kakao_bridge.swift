// Mac-local KakaoTalk adapter. Every send rechecks the exact room and composer.
import AppKit
import ApplicationServices
import Foundation
struct Failure: Error { let message: String }
func fail(_ message: String) throws -> Never { throw Failure(message: message) }
func attr(_ e: AXUIElement, _ name: String) -> CFTypeRef? { var out: CFTypeRef?; return AXUIElementCopyAttributeValue(e,name as CFString,&out) == .success ? out : nil }
func str(_ e: AXUIElement,_ name:String)->String { attr(e,name) as? String ?? "" }
func kids(_ e:AXUIElement)->[AXUIElement] { attr(e,kAXChildrenAttribute) as? [AXUIElement] ?? [] }
func walk(_ e:AXUIElement,_ depth:Int=0)->[AXUIElement] { if depth>12{return []};return [e]+kids(e).prefix(800).flatMap{walk($0,depth+1)} }
func role(_ e:AXUIElement,_ r:String)->Bool { str(e,kAXRoleAttribute)==r }
func label(_ e:AXUIElement)->String { [str(e,kAXTitleAttribute),str(e,kAXDescriptionAttribute),str(e,kAXValueAttribute)].filter{ !$0.isEmpty }.joined(separator:" ") }
func matches(_ e:AXUIElement,_ text:String)->Bool { [str(e,kAXTitleAttribute),str(e,kAXDescriptionAttribute),str(e,kAXValueAttribute)].contains(text) }
func press(_ e:AXUIElement) throws { guard AXUIElementPerformAction(e,kAXPressAction as CFString) == .success else {try fail("버튼을 실행하지 못했습니다.")} }
func set(_ e:AXUIElement,_ value:String) throws { guard AXUIElementSetAttributeValue(e,kAXValueAttribute as CFString,value as CFString) == .success else {try fail("입력창에 값을 넣지 못했습니다.")} }
func key(_ code:CGKeyCode,_ flags:CGEventFlags=[]) { for down in [true,false] { let e=CGEvent(keyboardEventSource:nil,virtualKey:code,keyDown:down);e?.flags=flags;e?.post(tap:.cghidEventTap) };usleep(200000) }
func click(_ e:AXUIElement,_ twice:Bool=false) throws { guard let raw=attr(e,kAXPositionAttribute),let size=attr(e,kAXSizeAttribute) else {try fail("화면에서 대상을 찾지 못했습니다.")};var p=CGPoint.zero;var s=CGSize.zero;AXValueGetValue(raw as! AXValue,.cgPoint,&p);AXValueGetValue(size as! AXValue,.cgSize,&s);guard s.width>0&&s.height>0 else{try fail("대상이 보이지 않습니다.")};p.x+=s.width/2;p.y+=s.height/2;for count in 1...(twice ? 2:1){for type in [CGEventType.leftMouseDown,.leftMouseUp]{let ev=CGEvent(mouseEventSource:nil,mouseType:type,mouseCursorPosition:p,mouseButton:.left);ev?.setIntegerValueField(.mouseEventClickState,value:Int64(count));ev?.post(tap:.cghidEventTap)}};usleep(300000) }
func find(_ e:AXUIElement,_ test:(AXUIElement)->Bool,_ skipTables:Bool=false,_ depth:Int=0)->AXUIElement? { if depth>12{return nil};if test(e){return e};if skipTables && role(e,"AXTable"){return nil};for child in kids(e).prefix(800){if let result=find(child,test,skipTables,depth+1){return result}};return nil }
func composer(_ w:AXUIElement)->AXUIElement? { find(w,{role($0,"AXTextArea")&&str($0,kAXDescriptionAttribute)=="메시지 입력"},true) }
var committed=false
let input=FileHandle.standardInput.readDataToEndOfFile()
func run() throws -> [String:Any] {
 let req=try JSONSerialization.jsonObject(with:input) as! [String:Any]
 let command=req["command"] as? String ?? "status"
 let running=NSRunningApplication.runningApplications(withBundleIdentifier:"com.kakao.KakaoTalkMac").first
 if command=="status" {return ["trusted":AXIsProcessTrusted(),"running":running != nil]}
 guard AXIsProcessTrusted() else {try fail("macOS 손쉬운 사용 권한이 필요합니다. 권한을 우회하지 않습니다.")}
 guard let app=running else {try fail("Mac 카카오톡을 실행하고 로그인해주세요.")}
 let root=AXUIElementCreateApplication(app.processIdentifier);AXUIElementSetMessagingTimeout(root,2)
 let room=req["room"] as? String ?? "";guard !room.isEmpty else {try fail("정확한 채팅방 이름이 필요합니다.")}
 func roomWindow() throws -> AXUIElement {let ws=kids(root).filter{role($0,"AXWindow")&&str($0,kAXTitleAttribute)==room&&composer($0) != nil};guard ws.count==1 else {try fail("정확히 일치하는 채팅방 창 하나가 필요합니다. 중복된 이름의 방은 자동 선택하지 않습니다.")};return ws[0]}
 if command=="search" {
  if (try? roomWindow()) != nil {return ["opened":true,"room":room]}
  app.activate();guard let main=kids(root).first(where:{str($0,"AXIdentifier")=="Main Window"}) else{try fail("카카오톡 메인 창을 열어주세요.")}
  AXUIElementPerformAction(main,kAXRaiseAction as CFString)
  if find(main,{role($0,"AXTextField")},true)==nil,let search=find(main,{role($0,"AXButton")&&matches($0,"검색")},true){try press(search);usleep(200000)}
  guard let field=find(main,{role($0,"AXTextField")&&(label($0).contains("검색")||str($0,kAXSubroleAttribute)=="AXSearchField")},true) else {try fail("채팅 목록 검색창을 먼저 열어주세요.")}
  try set(field,room);AXUIElementSetAttributeValue(field,kAXFocusedAttribute as CFString,kCFBooleanTrue);key(36);usleep(600000)
  let candidates=walk(main).filter{role($0,"AXRow")&&walk($0).contains{matches($0,room)}}
  guard candidates.count==1 else {try fail("일치하는 검색 결과가 \(candidates.count)개입니다. 정확한 방을 직접 열어주세요.")}
  try click(candidates[0],true);usleep(500000);_=try roomWindow();return ["opened":true,"room":room]
 }
 let window=try roomWindow()
 func rows()->[[String:Any]] {
  guard let table=find(window,{role($0,"AXTable")}) else{return []}
  return kids(table).filter{role($0,"AXRow")}.enumerated().map{index,row in
   let ns=walk(row),texts=ns.filter{role($0,"AXTextArea")}.map{str($0,kAXValueAttribute)}
   let profile=ns.first{role($0,"AXButton")&&matches($0,"프로필")}
   let statics=ns.filter{role($0,"AXStaticText")}
   let metadata=statics.map{str($0,kAXValueAttribute)}.joined(separator:" ")
   let date=statics.map{str($0,kAXHelpAttribute)}.first{ !$0.isEmpty } ?? ""
   let image=ns.contains{role($0,"AXImage")} && texts.isEmpty && ns.contains{role($0,"AXButton")&&matches($0,"공유")}
   return ["index":index,"text":texts.joined(separator:"\n"),"metadata":metadata,"date":date,"newSender":profile != nil,"photo":image]
  }
 }
 if command=="read" {return ["room":room,"rows":rows(),"coverage":"loaded_messages_only"]}
 app.activate();AXUIElementPerformAction(window,kAXRaiseAction as CFString);usleep(200000)
 guard let box=composer(window),str(box,kAXValueAttribute).isEmpty else {try fail("작성 중인 메시지가 있어 중단했습니다.")}
 if command=="send" {
  let text=req["text"] as? String ?? ""
  let files=req["files"] as? [String] ?? []
  if !text.isEmpty {
   let before=rows().filter{($0["text"] as? String)==text}.count
   let pb=NSPasteboard.general;let saved=(pb.pasteboardItems ?? []).map{item -> NSPasteboardItem in let copy=NSPasteboardItem();for type in item.types{if let data=item.data(forType:type){copy.setData(data,forType:type)}};return copy}
   defer{pb.clearContents();pb.writeObjects(saved)}
   pb.clearContents();pb.setString(text,forType:.string);AXUIElementSetAttributeValue(box,kAXFocusedAttribute as CFString,kCFBooleanTrue);key(9,[.maskCommand]);usleep(200000)
   guard str(box,kAXValueAttribute)==text else{try fail("메시지 입력 검증에 실패했습니다.")}
   _=try roomWindow();guard let send=find(window,{role($0,"AXButton")&&matches($0,"전송")},true) else{try fail("전송 버튼을 찾지 못했습니다.")}
   committed=true;try? press(send);usleep(600000)
   guard str(box,kAXValueAttribute).isEmpty,rows().filter({($0["text"] as? String)==text}).count==before+1 else{try fail("전송 여부를 확인하지 못했습니다. 재전송하지 말고 대화방을 확인해주세요.")}
  }
  for file in files {
   _=try roomWindow();let before=rows().filter{($0["photo"] as? Bool)==true}.count
   key(31,[.maskCommand]);usleep(400000);key(5,[.maskCommand,.maskShift]);usleep(300000)
   guard let field=walk(root).first(where:{str($0,"AXIdentifier")=="PathTextField"||role($0,"AXComboBox")||role($0,"AXTextField")&&str($0,kAXDescriptionAttribute).contains("경로")}) else {try fail("파일 경로 입력창을 찾지 못했습니다.")}
   try set(field,file);key(36);usleep(300000)
   guard let open=walk(root).first(where:{role($0,"AXButton")&&matches($0,"열기")}) else {try fail("파일 선택창을 찾지 못했습니다.")};try press(open);usleep(400000)
   guard let send=walk(root).first(where:{role($0,"AXButton")&&matches($0,"1개 전송")}) else {try fail("첨부 확인창을 찾지 못했습니다.")}
   _=try roomWindow();committed=true;try? press(send);usleep(800000)
   guard rows().filter({($0["photo"] as? Bool)==true}).count>before else{try fail("사진 전송 여부를 확인하지 못했습니다. 대화방을 확인해주세요.")}
  }
  return ["sent":true,"room":room,"text":!text.isEmpty,"photos":files.count]
 }
 if command=="photo" {
  guard let index=req["index"] as? Int,let expected=req["expected"] as? String,let output=req["output"] as? String,let table=find(window,{role($0,"AXTable")}) else{try fail("사진 식별 정보가 필요합니다.")}
  let rs=kids(table).filter{role($0,"AXRow")};guard index>0&&index<rs.count else{try fail("사진 위치가 변경되었습니다.")}
  let previous=walk(rs[index-1]).filter{role($0,"AXTextArea")}.map{str($0,kAXValueAttribute)}.joined(separator:"\n")
  guard previous==expected,rows()[index]["photo"] as? Bool==true,let image=walk(rs[index]).first(where:{role($0,"AXImage")}) else {try fail("멘션 바로 다음 사진임을 확인하지 못했습니다.")}
  let pb=NSPasteboard.general;let backup=(pb.pasteboardItems ?? []).map{item -> NSPasteboardItem in let copy=NSPasteboardItem();for type in item.types{if let data=item.data(forType:type){copy.setData(data,forType:type)}};return copy}
  defer{pb.clearContents();pb.writeObjects(backup)}
  try click(image,true);usleep(400000)
  guard let viewer=kids(root).first(where:{role($0,"AXWindow")&&composer($0)==nil&&walk($0).contains{role($0,"AXButton")&&matches($0,"더보기")}}),let more=walk(viewer).first(where:{role($0,"AXButton")&&matches($0,"더보기")}) else {try fail("사진 뷰어를 확인하지 못했습니다.")}
  defer{if let close=walk(viewer).first(where:{str($0,kAXSubroleAttribute)=="AXCloseButton"}){try? press(close)}}
  try? press(more);usleep(150000);guard let copy=walk(root).first(where:{role($0,"AXMenuItem")&&matches($0,"복사하기")}) else{try fail("사진 복사 메뉴를 찾지 못했습니다.")}
  pb.clearContents();try? press(copy);usleep(300000)
  var copied:NSImage? = nil
  for _ in 0..<20 {
   copied=(pb.readObjects(forClasses:[NSImage.self]) as? [NSImage])?.first
   if copied == nil,let bytes=pb.data(forType:.png) ?? pb.data(forType:.tiff){copied=NSImage(data:bytes)}
   if copied != nil {break};RunLoop.current.run(until:Date(timeIntervalSinceNow:0.15))
  }
  guard let image=copied,let tiff=image.tiffRepresentation,let rep=NSBitmapImageRep(data:tiff),let png=rep.representation(using:.png,properties:[:]) else{try fail("사진을 읽지 못했습니다. 클립보드 형식: " + (pb.types ?? []).map{$0.rawValue}.joined(separator:","))}
  try png.write(to:URL(fileURLWithPath:output),options:.atomic);return ["saved":true,"format":"png","source":"KakaoTalk image copy (not original encoding)"]
 }
 try fail("지원하지 않는 명령입니다.")
}
do {let result=try run();print(String(data:try JSONSerialization.data(withJSONObject:result),encoding:.utf8)!)}catch{let message=(error as? Failure)?.message ?? error.localizedDescription;print(String(data:try! JSONSerialization.data(withJSONObject:["error":message,"uncertain":committed]),encoding:.utf8)!);exit(1)}
