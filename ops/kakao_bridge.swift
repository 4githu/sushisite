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
func bounds(_ e:AXUIElement)->CGRect? {guard let p=attr(e,kAXPositionAttribute),let s=attr(e,kAXSizeAttribute) else{return nil};var point=CGPoint.zero;var size=CGSize.zero;AXValueGetValue(p as! AXValue,.cgPoint,&point);AXValueGetValue(s as! AXValue,.cgSize,&size);return CGRect(origin:point,size:size)}
func highlightedMentions(_ e:AXUIElement)->[String] {
 let text=str(e,kAXValueAttribute) as NSString
 guard text.contains("@"),text.length<40000 else{return []}
 var range=CFRange(location:0,length:text.length);var raw:CFTypeRef?
 guard let parameter=AXValueCreate(.cfRange,&range),AXUIElementCopyParameterizedAttributeValue(e,"AXAttributedStringForRange" as CFString,parameter,&raw) == .success,let rich=raw as? NSAttributedString else{return []}
 let regex=try! NSRegularExpression(pattern:"(?<![\\w@])@[^\\s,:;.!?\\[\\]()]+")
 return regex.matches(in:text as String,range:NSRange(location:0,length:text.length)).compactMap{match in
  var highlighted=true
  rich.enumerateAttributes(in:match.range,options:[]){attrs,_,_ in
   guard let value=attrs[NSAttributedString.Key("AXBackgroundColor")] else{highlighted=false;return}
   let ref=value as CFTypeRef
   if CFGetTypeID(ref) != CGColor.typeID || (ref as! CGColor).alpha<0.01 {highlighted=false}
  }
  return highlighted ? String(text.substring(with:match.range).dropFirst()):nil
 }
}
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
  if let existing=try? roomWindow() {app.activate();AXUIElementPerformAction(existing,kAXRaiseAction as CFString);return ["opened":true,"room":room]}
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
   let fileName=statics.map{str($0,kAXValueAttribute)}.first{ $0.range(of:"(?i)\\.[a-z0-9]{1,8}$",options:.regularExpression) != nil } ?? ""
   let fileButtons=ns.filter{role($0,"AXButton")}.map{label($0)}
   let content=ns.first{role($0,"AXTextArea")} ?? ns.first{role($0,"AXImage")} ?? statics.first{str($0,kAXValueAttribute)==fileName}
   let clock=statics.first{str($0,kAXValueAttribute).range(of:"^\\d+",options:.regularExpression) != nil}
   var direction=profile != nil ? "incoming":"unknown"
   if let c=content,let m=clock,let cb=bounds(c),let mb=bounds(m) {if cb.minX>=mb.maxX {direction="outgoing"} else if cb.maxX<=mb.minX {direction="incoming"}}
   let mentions=ns.filter{role($0,"AXTextArea")}.flatMap{highlightedMentions($0)}
   return ["index":index,"text":texts.joined(separator:"\n"),"mentions":mentions,"metadata":metadata,"date":date,"direction":direction,"newSender":profile != nil,"photo":image,"photoCount":image ? ns.filter{role($0,"AXImage")}.count:0,"fileName":fileName,"file":!fileName.isEmpty && fileButtons.contains{ $0.contains("저장") || $0.contains("다운로드") || $0.contains("열기") }]
  }
 }
 if command=="read" {return ["room":room,"rows":rows(),"coverage":"loaded_messages_only"]}
 if command=="mention-inspect" {
  guard let table=find(window,{role($0,"AXTable")}) else{return ["mentions":[]]}
  var result:[[String:Any]]=[]
  for row in kids(table).filter({role($0,"AXRow")}) {
   for node in walk(row).filter({role($0,"AXTextArea") && str($0,kAXValueAttribute).contains("NETAQ 멘션 검수")}) {
    var names:CFArray?;AXUIElementCopyParameterizedAttributeNames(node,&names)
    var range=CFRange(location:0,length:(str(node,kAXValueAttribute) as NSString).length);let value=AXValueCreate(.cfRange,&range)!
    var rich:CFTypeRef?;let code=AXUIElementCopyParameterizedAttributeValue(node,"AXAttributedStringForRange" as CFString,value,&rich)
    var spans:[[String:Any]]=[]
    if let attributed=rich as? NSAttributedString {attributed.enumerateAttributes(in:NSRange(location:0,length:attributed.length),options:[]){attrs,r,_ in spans.append(["range":"\(r)","attributes":Dictionary(uniqueKeysWithValues:attrs.map{($0.key.rawValue,String(describing:$0.value))})])}}
    result.append(["text":str(node,kAXValueAttribute),"parameters":names as? [String] ?? [],"code":code.rawValue,"spans":spans])
   }
  };return ["mentions":result]
 }
 if command=="attachment-inspect" {
  guard let table=find(window,{role($0,"AXTable")}) else{return ["attachments":[]]}
  let rs=kids(table).filter{role($0,"AXRow")}
  let info=rows().filter{($0["photo"] as? Bool)==true || ($0["file"] as? Bool)==true}.suffix(3).map{r -> [String:Any] in
   let index=r["index"] as! Int
   return ["index":index,"elements":walk(rs[index]).map{["role":str($0,kAXRoleAttribute),"label":label($0),"id":str($0,"AXIdentifier")]}]
  };return ["attachments":info]
 }
 app.activate();AXUIElementPerformAction(window,kAXRaiseAction as CFString);usleep(200000)
 guard let box=composer(window),str(box,kAXValueAttribute).isEmpty else {try fail("작성 중인 메시지가 있어 중단했습니다.")}
 if command=="send" {
  let text=req["text"] as? String ?? ""
  let files=req["files"] as? [String] ?? []
  let initialRows=rows()
  if !text.isEmpty {
   let pb=NSPasteboard.general;let saved=(pb.pasteboardItems ?? []).map{item -> NSPasteboardItem in let copy=NSPasteboardItem();for type in item.types{if let data=item.data(forType:type){copy.setData(data,forType:type)}};return copy}
   defer{pb.clearContents();pb.writeObjects(saved)}
   pb.clearContents();pb.setString(text,forType:.string);AXUIElementSetAttributeValue(box,kAXFocusedAttribute as CFString,kCFBooleanTrue);key(9,[.maskCommand]);usleep(200000)
   guard str(box,kAXValueAttribute)==text else{try fail("메시지 입력 검증에 실패했습니다.")}
   _=try roomWindow();guard let send=find(window,{role($0,"AXButton")&&matches($0,"전송")},true) else{try fail("전송 버튼을 찾지 못했습니다.")}
   committed=true;try? press(send);usleep(600000)
   guard str(box,kAXValueAttribute).isEmpty else{try fail("전송 여부를 확인하지 못했습니다. 재전송하지 말고 대화방을 확인해주세요.")}
  }
  if !files.isEmpty {
   _=try roomWindow()
   let pb=NSPasteboard.general;let backup=(pb.pasteboardItems ?? []).map{item -> NSPasteboardItem in let copy=NSPasteboardItem();for type in item.types{if let data=item.data(forType:type){copy.setData(data,forType:type)}};return copy}
   defer{pb.clearContents();pb.writeObjects(backup)}
   guard files.count<=10,files.allSatisfy({FileManager.default.fileExists(atPath:$0)}) else{try fail("첨부파일을 확인해주세요. 최대 10개입니다.")}
   pb.clearContents();pb.writeObjects(files.map{URL(fileURLWithPath:$0) as NSURL});AXUIElementSetAttributeValue(box,kAXFocusedAttribute as CFString,kCFBooleanTrue);key(9,[.maskCommand]);usleep(600000)
   guard let sheet=find(window,{role($0,"AXSheet")},true) else{try fail("첨부 확인창을 찾지 못했습니다.")}
   if let bundle=find(sheet,{(role($0,"AXCheckBox") || role($0,"AXButton"))&&label($0).contains("묶어")}), (attr(bundle,kAXValueAttribute) as? NSNumber)?.intValue != 1 {try press(bundle)}
   guard let send=find(sheet,{role($0,"AXButton")&&matches($0,"\(files.count)개 전송")}) else {try fail("첨부 확인창을 찾지 못했습니다.")}
   _=try roomWindow();committed=true;try? press(send);usleep(800000)
  }
  let finalRows=rows()
  if !text.isEmpty && finalRows.filter({($0["text"] as? String)==text}).count != initialRows.filter({($0["text"] as? String)==text}).count+1 {try fail("텍스트 전송 여부를 확인하지 못했습니다. 대화방을 확인해주세요.")}
  func attachmentCount(_ rs:[[String:Any]])->Int {rs.filter{(($0["photo"] as? Bool)==true || ($0["file"] as? Bool)==true) && ($0["direction"] as? String)=="outgoing"}.count}
  if !files.isEmpty && attachmentCount(finalRows)<=attachmentCount(initialRows){try fail("첨부 전송 여부를 확인하지 못했습니다. 대화방을 확인해주세요.")}
  return ["sent":true,"room":room,"text":!text.isEmpty,"photos":files.count]
 }
 if command=="photo" || command=="file" {
  guard let index=req["index"] as? Int,let expected=req["expected"] as? String,let output=req["output"] as? String,let table=find(window,{role($0,"AXTable")}) else{try fail("사진 식별 정보가 필요합니다.")}
  let rs=kids(table).filter{role($0,"AXRow")};let anchor=req["anchor"] as? Int ?? (index-1)
  guard anchor>=0&&index>anchor&&index<rs.count else{try fail("사진 위치가 변경되었습니다.")}
  let snapshot=rows();let previous=walk(rs[anchor]).filter{role($0,"AXTextArea")}.map{str($0,kAXValueAttribute)}.joined(separator:"\n")
  let direction=snapshot[anchor]["direction"] as? String ?? "unknown"
  guard previous==expected,direction != "unknown",!(anchor+1...index).contains(where:{snapshot[$0]["newSender"] as? Bool==true || snapshot[$0]["direction"] as? String != direction}) else {try fail("멘션과 같은 발신자의 첨부임을 확인하지 못했습니다.")}
  let pb=NSPasteboard.general;let backup=(pb.pasteboardItems ?? []).map{item -> NSPasteboardItem in let copy=NSPasteboardItem();for type in item.types{if let data=item.data(forType:type){copy.setData(data,forType:type)}};return copy}
  defer{pb.clearContents();pb.writeObjects(backup)}
  if command=="file" {
   guard snapshot[index]["file"] as? Bool==true,let name=snapshot[index]["fileName"] as? String,!name.isEmpty else{try fail("파일 첨부가 아닙니다.")}
   if let download=walk(rs[index]).first(where:{role($0,"AXButton") && (matches($0,"저장") || matches($0,"다운로드"))}) {try press(download);usleep(800000)}
   guard let reveal=walk(rs[index]).first(where:{role($0,"AXButton")&&matches($0,"Finder에서 보기")}) else{try fail("파일 다운로드가 완료되지 않았습니다. 카카오톡에서 저장한 뒤 다시 확인해주세요.")}
   try press(reveal);usleep(500000)
   guard let finder=NSRunningApplication.runningApplications(withBundleIdentifier:"com.apple.finder").first,NSWorkspace.shared.frontmostApplication?.bundleIdentifier=="com.apple.finder" else{try fail("첨부파일의 Finder 위치를 확인하지 못했습니다.")}
   let finderRoot=AXUIElementCreateApplication(finder.processIdentifier)
   guard walk(finderRoot).contains(where:{matches($0,name) && (attr($0,kAXSelectedAttribute) as? NSNumber)?.boolValue==true}) else{try fail("첨부파일 선택이 변경되었습니다.")}
   pb.clearContents();key(8,[.maskCommand,.maskAlternate]);usleep(200000)
   guard let path=pb.string(forType:.string),URL(fileURLWithPath:path).lastPathComponent==name else{try fail("첨부파일 경로가 일치하지 않습니다.")}
   let url=URL(fileURLWithPath:path);let info=try url.resourceValues(forKeys:[.isRegularFileKey,.isSymbolicLinkKey,.fileSizeKey])
   guard info.isRegularFile==true,info.isSymbolicLink != true,let size=info.fileSize,size>0,size<=50*1024*1024 else{try fail("50MB 이하의 일반 파일만 가져올 수 있습니다.")}
   try FileManager.default.copyItem(at:url,to:URL(fileURLWithPath:output));app.activate();AXUIElementPerformAction(window,kAXRaiseAction as CFString)
   return ["saved":true,"name":name,"size":size]
  }
  let images=walk(rs[index]).filter{role($0,"AXImage")};let subindex=req["subindex"] as? Int ?? 0
  guard snapshot[index]["photo"] as? Bool==true,subindex>=0,subindex<images.count else{try fail("사진 첨부가 아닙니다.")}
  let image=images[subindex]
  try click(image,true);usleep(400000)
  guard let viewer=kids(root).first(where:{role($0,"AXWindow")&&composer($0)==nil&&walk($0).contains{role($0,"AXButton")&&matches($0,"더보기")}}),let more=walk(viewer).first(where:{role($0,"AXButton")&&matches($0,"더보기")}) else {try fail("사진 뷰어를 확인하지 못했습니다.")}
  defer{if let close=walk(viewer).first(where:{str($0,kAXSubroleAttribute)=="AXCloseButton"}){try? press(close)}}
  try? press(more);usleep(150000);guard let copy=find(root,{role($0,"AXMenuItem")&&matches($0,"복사하기")},true) else{try fail("사진 복사 메뉴를 찾지 못했습니다.")}
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
