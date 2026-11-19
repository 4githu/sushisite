// Mac-local KakaoTalk adapter. Every send rechecks the exact room and composer.
import AppKit
import ApplicationServices
import Carbon.HIToolbox
import Foundation
import IOKit
import Darwin
struct Failure: Error { let message: String; let code:String; let diagnostics:[String:Any] }
func fail(_ message: String, code:String="bridge_error", diagnostics:[String:Any]=[:]) throws -> Never { throw Failure(message: message,code:code,diagnostics:diagnostics) }
var axDeadline=Date.distantFuture
var axBudgetExceeded=false
var cleanupResult:[String:Any]?
var cleanupOnExit:(()->[String:Any])?
var readCacheEnabled=false
var readCache:[String:CFTypeRef]=[:]
func attr(_ e: AXUIElement, _ name: String) -> CFTypeRef? { guard Date()<axDeadline else{axBudgetExceeded=true;return nil};let key="\(CFHash(e)):\(name)";if readCacheEnabled,let cached=readCache[key]{return cached};var out: CFTypeRef?;let result=AXUIElementCopyAttributeValue(e,name as CFString,&out) == .success ? out : nil;if readCacheEnabled,let result=result{readCache[key]=result};return result }
func str(_ e: AXUIElement,_ name:String)->String { attr(e,name) as? String ?? "" }
func kids(_ e:AXUIElement)->[AXUIElement] { attr(e,kAXChildrenAttribute) as? [AXUIElement] ?? [] }
func walk(_ e:AXUIElement,_ depth:Int=0)->[AXUIElement] { if depth>12{return []};return [e]+kids(e).prefix(800).flatMap{walk($0,depth+1)} }
func role(_ e:AXUIElement,_ r:String)->Bool { str(e,kAXRoleAttribute)==r }
func strictBool(_ value:Any?)->Bool? {
 guard let number=value as? NSNumber,CFGetTypeID(number)==CFBooleanGetTypeID() else{return nil}
 return number.boolValue
}
func lockPermits(_ session:[String:Any]?)->Bool {
 guard let session=session else{return false}
 if session["CGSSessionScreenIsLocked"] != nil {
  return strictBool(session["CGSSessionScreenIsLocked"]) == false
 }
 // Unlocked sessions may omit the private CGSSessionScreenIsLocked key.
 // Require affirmative session ownership and an explicit I/O Registry Boolean instead.
 return strictBool(session["IOConsoleLocked"]) == false &&
        strictBool(session["sessionOnConsole"]) == true &&
        strictBool(session["sessionLoginDone"]) == true &&
        strictBool(session["sessionOwnedByCaller"]) == true
}
func currentLockSnapshot()->[String:Any]? {
 guard var session=CGSessionCopyCurrentDictionary() as? [String:Any] else{return nil}
 session["sessionOnConsole"]=session[kCGSessionOnConsoleKey]
 session["sessionLoginDone"]=session[kCGSessionLoginDoneKey]
 session["sessionOwnedByCaller"]=(session[kCGSessionUserIDKey] as? NSNumber)?.uint32Value == getuid()
 let root=IORegistryGetRootEntry(kIOMainPortDefault)
 if root != 0 {
  defer{IOObjectRelease(root)}
  if let property=IORegistryEntryCreateCFProperty(root,"IOConsoleLocked" as CFString,kCFAllocatorDefault,0)?.takeRetainedValue() {
   session["IOConsoleLocked"]=property
  }
 }
 return session
}
func sessionLocked()->Bool {
 !lockPermits(currentLockSnapshot())
}
func label(_ e:AXUIElement)->String { [str(e,kAXTitleAttribute),str(e,kAXDescriptionAttribute),str(e,kAXValueAttribute)].filter{ !$0.isEmpty }.joined(separator:" ") }
func matches(_ e:AXUIElement,_ text:String)->Bool { [str(e,kAXTitleAttribute),str(e,kAXDescriptionAttribute),str(e,kAXValueAttribute)].contains(text) }
func press(_ e:AXUIElement) throws { guard AXUIElementPerformAction(e,kAXPressAction as CFString) == .success else {try fail("버튼을 실행하지 못했습니다.",code:"ax_action_failed")} }
func set(_ e:AXUIElement,_ value:String) throws { guard AXUIElementSetAttributeValue(e,kAXValueAttribute as CFString,value as CFString) == .success else {try fail("입력창에 값을 넣지 못했습니다.")} }
func key(_ code:CGKeyCode,_ flags:CGEventFlags=[]) { for down in [true,false] { let e=CGEvent(keyboardEventSource:nil,virtualKey:code,keyDown:down);e?.flags=down ? flags:[];e?.post(tap:.cghidEventTap) };usleep(200000) }
func searchKey(_ code:CGKeyCode,_ flags:CGEventFlags=[]) -> [String:Any] {
 let preflight=CGPreflightPostEventAccess()
 let current=CGEventSource.flagsState(.combinedSessionState)
 let secureInput=IsSecureEventInputEnabled()
 let modifiers:[String:Bool] = ["command":current.contains(.maskCommand),"shift":current.contains(.maskShift),
                              "option":current.contains(.maskAlternate),"control":current.contains(.maskControl)]
 let modifiersClear = current.intersection([.maskCommand,.maskShift,.maskAlternate,.maskControl]).subtracting(flags).isEmpty
 guard preflight else {
  return ["postEventAllowed":false,"eventDownCreated":false,"eventUpCreated":false,
          "postAttempted":false,"secureInputEnabled":secureInput,"modifiers":modifiers,
          "modifierStateClear":modifiersClear]
 }
 guard modifiersClear else {
  return ["postEventAllowed":true,"eventDownCreated":false,"eventUpCreated":false,
          "postAttempted":false,"secureInputEnabled":secureInput,"modifiers":modifiers,
          "modifierStateClear":false]
 }
 let down=CGEvent(keyboardEventSource:nil,virtualKey:code,keyDown:true)
 let up=CGEvent(keyboardEventSource:nil,virtualKey:code,keyDown:false)
 guard let down=down,let up=up else {
  return ["postEventAllowed":true,"eventDownCreated":down != nil,"eventUpCreated":up != nil,
          "postAttempted":false,"secureInputEnabled":secureInput,"modifiers":modifiers,
          "modifierStateClear":true]
 }
 down.flags=flags;up.flags=[]
 down.post(tap:.cghidEventTap);up.post(tap:.cghidEventTap)
 usleep(200000)
 return ["postEventAllowed":true,"eventDownCreated":true,"eventUpCreated":true,
         "postAttempted":true,"secureInputEnabled":secureInput,"modifiers":modifiers,
         "modifierStateClear":true]
}
func eventInputStatus()->[String:Any] {
 let flags=CGEventSource.flagsState(.combinedSessionState)
 return ["eventPostingPreflightAllowed":CGPreflightPostEventAccess(),
         "secureEventInputEnabled":IsSecureEventInputEnabled(),
         "modifiers":["command":flags.contains(.maskCommand),"shift":flags.contains(.maskShift),
                      "option":flags.contains(.maskAlternate),"control":flags.contains(.maskControl)],
         "uid":Int(getuid())]
}
func geometryDiagnostic(_ rect:CGRect?)->Any {
 guard let rect,rect.minX.isFinite,rect.minY.isFinite,rect.width.isFinite,rect.height.isFinite else{return NSNull()}
 return ["x":Double(rect.minX),"y":Double(rect.minY),"width":Double(rect.width),"height":Double(rect.height)]
}
func actionNamesDiagnostic(_ element:AXUIElement)->Any {
 var names:CFArray?
 guard AXUIElementCopyActionNames(element,&names) == .success,let names else{return NSNull()}
 return names as? [String] ?? []
}
// Search only the non-message UI; incomplete traversal must not imply uniqueness.
func sendButtonCandidates(_ window:AXUIElement)->[AXUIElement]? {
 var candidates:[AXUIElement]=[]
 var visited=0
 func visit(_ element:AXUIElement,_ depth:Int)->Bool {
  if role(element,"AXTable") {return true}
  guard depth<=12,visited<5000 else{return false}
  visited+=1
  if role(element,"AXButton") && matches(element,"전송") {candidates.append(element)}
  let children=kids(element)
  guard children.count<=800 else{return false}
  for child in children {if !visit(child,depth+1) {return false}}
  return true
 }
 return visit(window,0) ? candidates:nil
}
func roomStatusDiagnostics(_ root:AXUIElement?,_ room:String)->[String:Any] {
 let matchingWindows=(root.map{attr($0,kAXWindowsAttribute) as? [AXUIElement] ?? kids($0)} ?? [])
  .filter{role($0,"AXWindow")&&str($0,kAXTitleAttribute)==room}
 let point=NSEvent.mouseLocation
 var diagnostics:[String:Any]=[
  "matchingRoomWindowCount":matchingWindows.count,
  "roomWindowBounds":NSNull(),
  "sendButtonCandidateCount":0,
  "sendButtonCandidates":[],
  "mousePoint":["x":Double(point.x),"y":Double(point.y)]
 ]
 guard matchingWindows.count==1 else{return diagnostics}
 let window=matchingWindows[0]
 diagnostics["roomWindowBounds"]=geometryDiagnostic(bounds(window))
 guard let candidates=sendButtonCandidates(window) else {
  diagnostics["sendButtonCandidateCount"]=NSNull()
  diagnostics["sendButtonCandidates"]=NSNull()
  return diagnostics
 }
 diagnostics["sendButtonCandidateCount"]=candidates.count
 diagnostics["sendButtonCandidates"]=candidates.map{button -> [String:Any] in
  let enabled:Any=strictBool(attr(button,kAXEnabledAttribute)).map{$0 as Any} ?? NSNull()
  return ["bounds":geometryDiagnostic(bounds(button)),"AXEnabled":enabled,
          "actionNames":actionNamesDiagnostic(button)]
 }
 return diagnostics
}
func editMenuAction(_ root:AXUIElement,_ name:String) -> [String:Any] {
 // Never AXPress a menu-bar item: Kakao can enter nested NSMenuTrackingSession loops.
 guard ["paste","select-all"].contains(name) else{return ["actionAttempted":false,"actionSucceeded":false]}
 let event=searchKey(name=="paste" ? 9:0,.maskCommand)
 return ["inputMethod":"focused_shortcut","keyEvent":event,
         "actionAttempted":event["postAttempted"] as? Bool ?? false,
         "actionSucceeded":event["postAttempted"] as? Bool ?? false]
}

func selectedRange(_ element:AXUIElement)->CFRange? {
 guard let raw=attr(element,kAXSelectedTextRangeAttribute),CFGetTypeID(raw)==AXValueGetTypeID() else{return nil}
 let value=raw as! AXValue
 var range=CFRange(location:0,length:0)
 guard AXValueGetValue(value,.cfRange,&range) else{return nil}
 return range
}
func selectedRangeLength(_ element:AXUIElement)->Int? {selectedRange(element)?.length}
func click(_ e:AXUIElement,_ twice:Bool=false) throws {
 guard let frame=bounds(e) else{try fail("화면에서 대상을 찾지 못했습니다.")}
 let point=CGPoint(x:frame.midX,y:frame.midY)
 for count in 1...(twice ? 2:1) {
  guard let down=CGEvent(mouseEventSource:nil,mouseType:.leftMouseDown,mouseCursorPosition:point,mouseButton:.left),
        let up=CGEvent(mouseEventSource:nil,mouseType:.leftMouseUp,mouseCursorPosition:point,mouseButton:.left) else {
   try fail("마우스 클릭 이벤트를 만들지 못했습니다.",code:"mouse_click_unavailable")
  }
  down.setIntegerValueField(.mouseEventClickState,value:Int64(count))
  up.setIntegerValueField(.mouseEventClickState,value:Int64(count))
  down.post(tap:.cghidEventTap);up.post(tap:.cghidEventTap)
 }
 usleep(300000)
}
func find(_ e:AXUIElement,_ test:(AXUIElement)->Bool,_ skipTables:Bool=false,_ depth:Int=0)->AXUIElement? { if depth>12{return nil};if test(e){return e};if skipTables && role(e,"AXTable"){return nil};for child in kids(e).prefix(800){if let result=find(child,test,skipTables,depth+1){return result}};return nil }
func cleanupUI(_ root:AXUIElement,_ room:String,closeRoom:Bool)->[String:Any] {
 // Never walk message tables to find a close button, or close an unrelated window.
 let windows=attr(root,kAXWindowsAttribute) as? [AXUIElement] ?? kids(root)
 var cleared=true
 if let main=windows.first(where:{str($0,"AXIdentifier")=="Main Window"}),
    let field=find(main,{role($0,"AXTextField")&&(label($0).contains("검색")||str($0,kAXSubroleAttribute)=="AXSearchField")},true) {
  _=AXUIElementSetAttributeValue(field,kAXValueAttribute as CFString,"" as CFString)
  cleared=str(field,kAXValueAttribute).isEmpty
 }
 let exact=windows.filter{role($0,"AXWindow")&&str($0,kAXTitleAttribute)==room}
 var closed = exact.isEmpty
 var preservedDraft=false
 if closeRoom,exact.count==1 {
  if !prepared,let box=composer(exact[0]),!str(box,kAXValueAttribute).isEmpty {
   preservedDraft=true
  } else {
   if prepared,let sheet=find(exact[0],{role($0,"AXSheet")},true),
      let cancel=find(sheet,{role($0,"AXButton")&&["취소","Cancel"].contains(str($0,kAXTitleAttribute))}) {
    _=AXUIElementPerformAction(cancel,kAXPressAction as CFString)
   }
   if let raw=attr(exact[0],kAXCloseButtonAttribute) {
    _=AXUIElementPerformAction(raw as! AXUIElement,kAXPressAction as CFString)
    let until=Date().addingTimeInterval(1)
    repeat {
     let current=attr(root,kAXWindowsAttribute) as? [AXUIElement] ?? kids(root)
     closed = !current.contains{role($0,"AXWindow")&&str($0,kAXTitleAttribute)==room}
     if closed {break};RunLoop.current.run(until:Date(timeIntervalSinceNow:0.05))
    } while Date()<until
   }
  }
 }
 return ["searchCleared":cleared,"roomClosed":closed,"closeRequested":closeRoom,"preservedExistingDraft":preservedDraft]
}
func composer(_ w:AXUIElement)->AXUIElement? { find(w,{role($0,"AXTextArea")&&str($0,kAXDescriptionAttribute)=="메시지 입력"},true) }
func bounds(_ e:AXUIElement)->CGRect? {
 guard let rawPosition=attr(e,kAXPositionAttribute),CFGetTypeID(rawPosition)==AXValueGetTypeID(),
       let rawSize=attr(e,kAXSizeAttribute),CFGetTypeID(rawSize)==AXValueGetTypeID() else{return nil}
 let position=rawPosition as! AXValue,sizeValue=rawSize as! AXValue
 var point=CGPoint.zero;var size=CGSize.zero
 guard AXValueGetValue(position,.cgPoint,&point),AXValueGetValue(sizeValue,.cgSize,&size),
       point.x.isFinite,point.y.isFinite,size.width.isFinite,size.height.isFinite,
       size.width>0,size.height>0 else{return nil}
 return CGRect(origin:point,size:size)
}
func bounds(_ e:AXUIElement,_ parent:AXUIElement)->Bool {
 guard let child=bounds(e),let container=bounds(parent) else{return false}
 return container.contains(child)
}
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
// Only an explicit, stable empty marker after a fresh query can prove absence.
struct SearchSettle {
 var pass=0
 var emptyCount=0
 var exactCount=0
 mutating func observe(_ sample:[String:Any], room:String)->String? {
  guard sample["locked"] as? Bool != true else{return "unverified"}
  guard (sample["mainWindow"] as? Bool) != false else{return "unverified"}
  if pass==1 {
   guard sample["query"] as? String == "", sample["empty"] as? Bool == false,
         (sample["rows"] as? [String])?.isEmpty == true else{return "unverified"}
   pass=2;emptyCount=0;return nil
  }
  guard sample["query"] as? String == room else{return "unverified"}
  let rows=sample["rows"] as? [String] ?? []
  let exact=rows.filter{$0==room}
  if exact.count>1{return "ambiguous"}
  if exact.count==1 {
   emptyCount=0; exactCount+=1
   return exactCount>=3 ? "unique_exact" : nil
  }
  exactCount=0
  // A partial list is not proof that this room does not exist.
  if !rows.isEmpty{return "unverified"}
  if sample["empty"] as? Bool == true {
   emptyCount+=1
   if emptyCount>=3 {emptyCount=0;if pass==2{return "confirmed_absent"};pass=1}
  } else {emptyCount=0;if pass==2{pass=0}}
  return nil
 }
}
// Shared by the real send path and the isolated send-simulation. A snapshot is
// evidence only for the instant before the click, never a delivery receipt.
struct SendSnapshot {
 let windows:[String]
 let composerOwned:Bool
 let buttonOwned:Bool
 let frontmostTargetApp:Bool
 let keyWindowOwned:Bool
 let buttonBoundsOwned:Bool
 let composerFocused:Bool
 let buttonEnabled:Bool?
}
// Accept a clock atom, optionally preceded by one positive unread-count line.
func isTimeLabel(_ text:String)->Bool {
 let pattern = #"\A(?:[0-9]*[1-9][0-9]*\n)?(?:(?:오전|오후|(?i:AM|PM))[ \t\u00a0\u202f]+(?:0?[1-9]|1[0-2]):[0-5][0-9]|(?:0?[1-9]|1[0-2]):[0-5][0-9][ \t\u00a0\u202f]+(?:오전|오후|(?i:AM|PM))|(?:[01]?[0-9]|2[0-3]):[0-5][0-9])\z"#
 return text.range(of:pattern,options:.regularExpression) != nil
}
func newOutgoingReceipt(_ before:[[String:Any]],_ after:[[String:Any]],text:String?=nil,attachment:Bool=false)->Bool {
 let old=Set(before.compactMap{$0["identity"] as? String})
 return after.contains {row in
  guard let id=row["identity"] as? String,!old.contains(id),row["direction"] as? String=="outgoing" else{return false}
  if attachment{return row["photo"] as? Bool==true || row["file"] as? Bool==true}
  return text != nil && row["text"] as? String==text
 }
}
func messageDirection(_ content:CGRect?,_ clock:CGRect?,hasProfile:Bool=false)->String {
 if let content,let clock {
  if content.minX>=clock.maxX {return "outgoing"}
  if content.maxX<=clock.minX {return "incoming"}
 }
 return hasProfile ? "incoming":"unknown"
}
// A photo bundle can omit its clock entirely. Only classify its direction if
// there is no incoming profile and its whole frame is strongly right-aligned.
func groupedImageDirection(photo:Bool,hasProfile:Bool,hasClock:Bool,imageCount:Int,left:Int,right:Int)->String {
 guard photo && !hasProfile && !hasClock && imageCount>1 && left>=280 && right>=950 && right<=1010 else{return "unknown"}
 return "outgoing"
}
func attachmentReceiptDiagnostics(_ before:[[String:Any]],_ after:[[String:Any]],budgetExceeded:Bool,samples:Int)->[String:Any] {
 let old=Set(before.compactMap{$0["identity"] as? String})
 let fresh=after.filter{row in guard let id=row["identity"] as? String else{return false};return !old.contains(id)}
 func count(_ key:String)->Int {fresh.filter{$0[key] as? Bool == true}.count}
 let photos=fresh.filter{$0["photo"] as? Bool == true}
 let left=photos.compactMap{$0["imageLeftPermille"] as? Int}.min() ?? -1
 let right=photos.compactMap{$0["imageRightPermille"] as? Int}.max() ?? -1
 return ["stage":"image-receipt","beforeRows":before.count,"afterRows":after.count,"newRows":fresh.count,
         "newOutgoing":fresh.filter{$0["direction"] as? String == "outgoing"}.count,
         "newUnknown":fresh.filter{$0["direction"] as? String == "unknown"}.count,
         "newIncoming":fresh.filter{$0["direction"] as? String == "incoming"}.count,
         "newPhoto":count("photo"),"newHasImage":count("hasImage"),"newHasClock":count("hasClock"),
         "newHasShare":count("hasShare"),"newHasText":count("hasText"),"samples":samples,"budgetExceeded":budgetExceeded,
         "newPhotoMinLeftPermille":left,"newPhotoMaxRightPermille":right]
}
// Kakao converts only a line-start "- " list marker into a bullet and tab.
// Accept that exact rendering change; every other character must stay identical.
func composerTextEquivalent(_ expected:String,_ actual:String)->Bool {
 let expectedLines=expected.components(separatedBy:"\n")
 let actualLines=actual.components(separatedBy:"\n")
 guard expectedLines.count==actualLines.count else{return false}
 for (expectedLine,actualLine) in zip(expectedLines,actualLines) {
  let expectedBytes=Array(expectedLine.utf8),actualBytes=Array(actualLine.utf8)
  if expectedBytes==actualBytes {continue}
  guard expectedBytes.starts(with:[0x2D,0x20]),actualBytes.starts(with:[0xE2,0x80,0xA2,0x09]),
        Array(expectedBytes.dropFirst(2))==Array(actualBytes.dropFirst(4)) else{return false}
 }
 return true
}
func sendContextPermitted(_ lock:[String:Any]?,_ snapshot:SendSnapshot,room:String)->Bool {
 lockPermits(lock) && snapshot.windows.filter{$0==room}.count==1 &&
 snapshot.composerOwned && snapshot.buttonOwned && snapshot.frontmostTargetApp &&
 snapshot.keyWindowOwned && snapshot.buttonBoundsOwned && snapshot.composerFocused
}
func sendPermitted(_ lock:[String:Any]?,_ snapshot:SendSnapshot,room:String)->Bool {
 sendContextPermitted(lock,snapshot,room:room) && snapshot.buttonEnabled == true
}
func awaitSendReady(room:String,observe:()->([String:Any]?,SendSnapshot),expired:()->Bool,pause:()->Void) throws {
 while !expired() {
  let (lock,snapshot)=observe()
  guard !expired() else {break}
  guard sendContextPermitted(lock,snapshot,room:room) else {
   try fail("전송 대기 중 방 또는 입력 상태가 변경됐습니다. 클릭하지 않았습니다.",code:"send_readiness_context_changed",diagnostics:["matchingWindows":snapshot.windows.filter{$0==room}.count,"composerOwned":snapshot.composerOwned,"buttonOwned":snapshot.buttonOwned,"frontmostTargetApp":snapshot.frontmostTargetApp,"keyWindowOwned":snapshot.keyWindowOwned,"buttonBoundsOwned":snapshot.buttonBoundsOwned,"composerFocused":snapshot.composerFocused,"budgetExceeded":axBudgetExceeded])
  }
  guard let enabled=snapshot.buttonEnabled else {
   try fail("전송 버튼 활성 상태를 확인하지 못했습니다. 클릭하지 않았습니다.",code:"send_readiness_unknown")
  }
  if enabled {return}
  pause()
 }
 try fail("전송 버튼이 제한 시간 내 활성화되지 않았습니다. 클릭하지 않았습니다.",code:"send_readiness_timeout")
}
func checkedSendClick(room:String,observe:()->([String:Any]?,SendSnapshot),click:() throws -> Void) throws {
 let (lock,snapshot)=observe()
 guard sendPermitted(lock,snapshot,room:room) else {
  try fail("잠금 또는 정확한 채팅방 창·입력창·전송 버튼을 확인하지 못했습니다.",code:"send_context_unverified",diagnostics:["matchingWindows":snapshot.windows.filter{$0==room}.count,"composerOwned":snapshot.composerOwned,"buttonOwned":snapshot.buttonOwned,"frontmostTargetApp":snapshot.frontmostTargetApp,"keyWindowOwned":snapshot.keyWindowOwned,"buttonBoundsOwned":snapshot.buttonBoundsOwned,"composerFocused":snapshot.composerFocused,"buttonEnabled":snapshot.buttonEnabled.map{$0 as Any} ?? NSNull(),"budgetExceeded":axBudgetExceeded])
 }
 committed=true // A posted mouse click may still have an unobserved delivery result.
 try click()
}
// A single mouse click can still have an unobserved result. Never click
// twice: reconcile using a new outgoing row in the same validated room.
func checkedSendWithReceipt(room:String,observe:()->([String:Any]?,SendSnapshot),click:() throws -> Void,confirm:() throws -> Bool,diagnostics:()->[String:Any]={[:]}) throws {
 var attempted=false
 var clickFailure:Error?
 do {
  try checkedSendClick(room:room,observe:observe,click:{attempted=true;try click()})
 } catch {
  guard attempted else{throw error}
  clickFailure=error
 }
 guard try confirm() else {
  if let error=clickFailure{throw error}
  try fail("전송 버튼을 한 번 눌렀지만 대화방에서 전송 결과를 확인하지 못했습니다. 자동 재전송하지 마세요.",code:"delivery_not_observed",diagnostics:diagnostics())
 }
}
var committed=false
var prepared=false
let input=FileHandle.standardInput.readDataToEndOfFile()
func run() throws -> [String:Any] {
 let req=try JSONSerialization.jsonObject(with:input) as! [String:Any]
 let command=req["command"] as? String ?? "status"
 if command=="search-simulation" {
  let room=req["room"] as? String ?? ""
  var settle=SearchSettle();var outcome="unverified"
  for sample in req["snapshots"] as? [[String:Any]] ?? [] {
   if let result=settle.observe(sample,room:room){outcome=result;break}
  }
  return ["searchEvidence":outcome]
 }
 if command=="send-simulation" {
  let room=req["room"] as? String ?? ""
  let stages=req["stages"] as? [[String:Any]] ?? []
  var clicks=0
  var textMatches:Bool?
  if let expected=req["expectedText"] as? String,let actual=req["actualText"] as? String {
   textMatches=composerTextEquivalent(expected,actual)
   if textMatches==false{return ["clicks":0,"committed":false,"uncertain":false,"manualCheck":true,"textMatches":false]}
  } else if req["expectedText"] != nil || req["actualText"] != nil {
   try fail("합성 메시지 비교 입력이 불완전합니다.")
  }
  func observation(_ stage:[String:Any])->([String:Any]?,SendSnapshot) {
   let lock=stage["session"] as? [String:Any]
   let snapshot=SendSnapshot(windows:stage["windows"] as? [String] ?? [],
                             composerOwned:stage["composerOwned"] as? Bool == true,
                             buttonOwned:stage["buttonOwned"] as? Bool == true,
                             frontmostTargetApp:stage["frontmostTargetApp"] as? Bool == true,
                             keyWindowOwned:stage["keyWindowOwned"] as? Bool == true,
                             buttonBoundsOwned:stage["buttonBoundsOwned"] as? Bool == true,
                             composerFocused:stage["composerFocused"] as? Bool == true,
                             buttonEnabled:strictBool(stage["buttonEnabled"]))
   return (lock,snapshot)
  }
  guard ["text","attachment"].contains(req["kind"] as? String ?? ""),stages.count==2 else{try fail("합성 전송 입력을 확인해주세요.")}
  let (initialLock,initial)=observation(stages[0])
  guard sendPermitted(initialLock,initial,room:room) else{return ["clicks":0,"committed":false,"uncertain":false,"manualCheck":false]}
  do {
   if let samples=req["readiness"] as? [[String:Any]] {
    var index=0
    try awaitSendReady(room:room,observe:{observation(samples[index])},expired:{index>=samples.count},pause:{index+=1})
   }
   try checkedSendWithReceipt(room:room,observe:{observation(stages[1])},click:{clicks+=1
    if req["clickFails"] as? Bool == true {try fail("합성 클릭 결과 불확실")}
   },confirm:{req["deliveryObserved"] as? Bool ?? (req["clickFails"] as? Bool != true)})
   var result:[String:Any] = ["clicks":clicks,"committed":true,"uncertain":false]
   if let textMatches {result["textMatches"]=textMatches}
   return result
  } catch {
   var result:[String:Any] = ["clicks":clicks,"committed":false,"uncertain":committed,"manualCheck":true]
   if let textMatches {result["textMatches"]=textMatches}
   return result
  }
 }
 let running=NSRunningApplication.runningApplications(withBundleIdentifier:"com.kakao.KakaoTalkMac").first
 if command=="status" {
  var status=eventInputStatus()
  status["trusted"]=AXIsProcessTrusted()
  status["running"]=running != nil
  status["locked"]=sessionLocked()
  if let room=req["room"] as? String,!room.isEmpty {
   var root:AXUIElement?
   if let running {
    root=AXUIElementCreateApplication(running.processIdentifier)
    if let root {AXUIElementSetMessagingTimeout(root,2)}
   }
   status.merge(roomStatusDiagnostics(root,room)){current,_ in current}
  }
  return status
 }
 guard AXIsProcessTrusted() else {try fail("macOS 손쉬운 사용 권한이 필요합니다. 권한을 우회하지 않습니다.")}
 guard !sessionLocked() else {try fail("Mac 화면 잠금 상태 또는 세션 확인 불가입니다. 잠금 해제 후 다시 시도해주세요. 방 부재로 취급하지 않습니다.")}
 guard let app=running else {try fail("Mac 카카오톡을 실행하고 로그인해주세요.")}
 // Set the timeout on the process-wide AX object, including child elements.
 AXUIElementSetMessagingTimeout(AXUIElementCreateSystemWide(),0.4)
 axDeadline=Date().addingTimeInterval(command=="read-latest" || command=="read" ? 10:35)
 let lockPath=FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Caches/sushisite-kakao-ui.lock").path
 let lockFD=open(lockPath,O_CREAT|O_RDWR,0o600)
 guard lockFD>=0 else{try fail("카카오 도구 잠금 파일을 열지 못했습니다.",code:"ui_lock_unavailable")}
 guard flock(lockFD,LOCK_EX|LOCK_NB)==0 else{close(lockFD);try fail("다른 카카오 도구가 실행 중입니다. 중복 실행하지 않았습니다.",code:"ui_busy")}
 defer{flock(lockFD,LOCK_UN);close(lockFD)}
 let root=AXUIElementCreateApplication(app.processIdentifier);AXUIElementSetMessagingTimeout(root,0.4)
 let room=req["room"] as? String ?? "";guard !room.isEmpty else {try fail("정확한 채팅방 이름이 필요합니다.")}
 func roomWindow() throws -> AXUIElement {let ws=(attr(root,kAXWindowsAttribute) as? [AXUIElement] ?? kids(root)).filter{role($0,"AXWindow")&&str($0,kAXTitleAttribute)==room&&composer($0) != nil};guard ws.count==1 else {try fail("정확히 일치하는 채팅방 창 하나가 필요합니다. 중복된 이름의 방은 자동 선택하지 않습니다.")};return ws[0]}
 var searchOpened=false
 var keepRoomAfterSuccess=false
 if command=="cleanup" {return cleanupUI(root,room,closeRoom:true)}
 if command=="send" || command=="search" {
  cleanupOnExit={cleanupUI(root,room,closeRoom:(command=="send" && !keepRoomAfterSuccess) || (command=="search" && !searchOpened))}
 }
 defer {
  if let cleanup=cleanupOnExit {
   // Cleanup has its own small budget even when the main operation expired.
   axDeadline=Date().addingTimeInterval(2)
   cleanupResult=cleanup();cleanupOnExit=nil
  }
 }
 if command=="search" {
  let existingWindows=(attr(root,kAXWindowsAttribute) as? [AXUIElement] ?? kids(root)).filter{role($0,"AXWindow")&&str($0,kAXTitleAttribute)==room}
  if existingWindows.count>1 {try fail("같은 제목의 채팅방 창이 중복됩니다. 자동 선택하지 않습니다.")}
  // A single already-open window cannot prove the search has no namesake.
  // Always inspect the list before selecting a recipient.
  app.activate()
  // After macOS wakes, KakaoTalk may take longer than a single 300 ms pause
  // to restore its accessibility tree and publish the main window.
  var mainWindow:AXUIElement?
  let mainWindowDeadline=Date().addingTimeInterval(8)
  while Date()<mainWindowDeadline {
   mainWindow=kids(root).first(where:{str($0,"AXIdentifier")=="Main Window"})
   if mainWindow != nil {break}
   RunLoop.current.run(until:Date(timeIntervalSinceNow:0.25))
  }
  guard let main=mainWindow else{try fail("카카오톡 메인 창을 8초 안에 확인하지 못했습니다. Mac 잠금 해제 후 카카오톡 메인 화면을 열고 다시 시도해주세요.",code:"main_window_unavailable")}
  AXUIElementPerformAction(main,kAXRaiseAction as CFString)
  // Select chats explicitly. A friend's identical name is not a room search.
  guard let chats=find(main,{role($0,"AXButton")&&str($0,"AXIdentifier")=="chatrooms"},true) else {
   try fail("카카오톡 로그인 후 채팅 목록을 열어주세요.",code:"chat_list_unavailable")
  }
  try press(chats)
  RunLoop.current.run(until:Date(timeIntervalSinceNow:0.1))
  if find(main,{role($0,"AXTextField")},true)==nil,let search=find(main,{role($0,"AXButton")&&matches($0,"검색")},true){try press(search);usleep(200000)}
  guard let field=find(main,{role($0,"AXTextField")&&(label($0).contains("검색")||str($0,kAXSubroleAttribute)=="AXSearchField")},true) else {try fail("채팅 목록 검색창을 먼저 열어주세요.")}
  // AXValue alone changes the displayed string without reliably notifying
  // Kakao's search controller; old recipient rows can remain underneath it.
  // Deliver a real paste into this exact focused search field, preserving clipboard.
  func enterSearch(_ value:String) throws {
   let pb=NSPasteboard.general
   var pasteboardWriteAccepted=false
   var pasteboardReadAvailable:Bool?
   var pasteboardReadLength:Int?
   var pasteboardReadMatchesExpected:Bool?
   var selectAllRangeLength:Int?
   var keyEvents:[String:Any]=[:]
   var menuActions:[String:Any]=[:]
   func sendSearchKey(_ code:CGKeyCode,_ stage:String,_ flags:CGEventFlags=[]) throws {
    let event=searchKey(code,flags);keyEvents[stage]=event
    guard event["postEventAllowed"] as? Bool == true else {
     try fail("이 검색을 실행하는 kakao-bridge 프로세스에 macOS Post Event 권한이 필요합니다. 권한 우회는 하지 않았습니다.",code:"search_post_event_permission_required",diagnostics:diagnostics(stage))
    }
    guard event["modifierStateClear"] as? Bool == true else {
     try fail("검색 입력 전에 modifier 키 상태가 해제되지 않았습니다. 키 입력을 보내지 않았습니다.",code:"search_modifier_state_unexpected",diagnostics:diagnostics(stage))
    }
    guard event["eventDownCreated"] as? Bool == true,event["eventUpCreated"] as? Bool == true,
          event["postAttempted"] as? Bool == true else {
     try fail("검색 키 이벤트를 생성하지 못했습니다.",code:"search_key_event_unavailable",diagnostics:diagnostics(stage))
    }
   }
   func keyWindowMatches()->Bool {
    guard let focusedWindow=attr(root,kAXFocusedWindowAttribute) else{return false}
    return CFEqual(focusedWindow,main)
   }
   func activeField()->AXUIElement? {
    guard NSWorkspace.shared.frontmostApplication?.processIdentifier == app.processIdentifier,
          keyWindowMatches(),
          let focusedValue=attr(root,kAXFocusedUIElementAttribute),
          CFEqual(focusedValue,field),
          let current=find(main,{role($0,"AXTextField")&&(label($0).contains("검색")||str($0,kAXSubroleAttribute)=="AXSearchField")},true),
          CFEqual(current,field) else{return nil}
    return current
   }
   func diagnostics(_ stage:String)->[String:Any] {
    let current=find(main,{role($0,"AXTextField")&&(label($0).contains("검색")||str($0,kAXSubroleAttribute)=="AXSearchField")},true)
    let actual=str(field,kAXValueAttribute)
    var details:[String:Any]=["stage":stage,"fieldPresent":current != nil,"fieldIdentityStable":current != nil && CFEqual(current!,field),
            "focusedField":activeField() != nil,"keyWindowMatches":keyWindowMatches(),
            "frontmostTargetApp":NSWorkspace.shared.frontmostApplication?.processIdentifier == app.processIdentifier,
            "expectedLength":(value as NSString).length,"actualLength":(actual as NSString).length,
            "pasteboardWriteAccepted":pasteboardWriteAccepted,"keyEvents":keyEvents,"menuActions":menuActions]
    if let pasteboardReadAvailable {details["pasteboardReadAvailable"]=pasteboardReadAvailable}
    if let pasteboardReadLength {details["pasteboardReadLength"]=pasteboardReadLength}
    if let pasteboardReadMatchesExpected {details["pasteboardReadMatchesExpected"]=pasteboardReadMatchesExpected}
    if let selectAllRangeLength {details["selectAllRangeLength"]=selectAllRangeLength}
    if let finalSelectionLength=selectedRangeLength(field){details["finalSelectionLength"]=finalSelectionLength}
    return details
   }
   guard AXUIElementSetAttributeValue(field,kAXFocusedAttribute as CFString,kCFBooleanTrue) == .success else {
    try fail("검색 입력창의 실제 포커스를 확인하지 못했습니다.",code:"search_focus_unverified",diagnostics:diagnostics("focus-request"))
   }
   let focusDeadline=Date().addingTimeInterval(1.5)
   while Date()<focusDeadline && activeField()==nil {RunLoop.current.run(until:Date(timeIntervalSinceNow:0.05))}
   guard activeField() != nil else {try fail("검색 입력창의 실제 포커스를 확인하지 못했습니다.",code:"search_focus_unverified",diagnostics:diagnostics("focus-confirm"))}
   let original=str(field,kAXValueAttribute)
   if original==value {return}
   let saved=(pb.pasteboardItems ?? []).map{item -> NSPasteboardItem in let copy=NSPasteboardItem();for type in item.types{if let data=item.data(forType:type){copy.setData(data,forType:type)}};return copy}
   var pasteAttempted=false
   var inputObserved=false
   var ourPasteboardChangeCount:Int?
   defer {
    if (!pasteAttempted || inputObserved),let count=ourPasteboardChangeCount,pb.changeCount==count {
     pb.clearContents();pb.writeObjects(saved)
    }
   }
   menuActions["select-all"]=editMenuAction(root,"select-all")
   guard (menuActions["select-all"] as? [String:Any])?["actionSucceeded"] as? Bool == true else {
    try fail("카카오톡 편집 메뉴의 전체 선택 동작을 확인하지 못했습니다.",code:"search_select_all_menu_unavailable",diagnostics:diagnostics("select-all-menu"))
   }
   let selectionDeadline=Date().addingTimeInterval(1.5)
   var selectionConfirmed=false
   repeat {
    guard activeField() != nil,str(field,kAXValueAttribute)==original else {
     try fail("검색 입력 중 포커스 또는 입력값이 바뀌었습니다.",code:"search_focus_changed",diagnostics:diagnostics("select-all-wait"))
    }
    if let range=selectedRange(field),range.location==0,range.length==(original as NSString).length {
     selectAllRangeLength=range.length;selectionConfirmed=true;break
    }
    RunLoop.current.run(until:Date(timeIntervalSinceNow:0.05))
   } while Date()<selectionDeadline
   guard selectionConfirmed else {try fail("검색어 전체 선택을 확인하지 못했습니다.",code:"search_selection_unverified",diagnostics:diagnostics("select-all-timeout"))}
   if value.isEmpty {try sendSearchKey(51,"delete")} else {
    pb.clearContents();pasteboardWriteAccepted=pb.setString(value,forType:.string)
    ourPasteboardChangeCount=pb.changeCount
    guard pasteboardWriteAccepted else {try fail("검색어 입력을 확인하지 못했습니다.",code:"search_pasteboard_unavailable",diagnostics:diagnostics("pasteboard-write"))}
    let readback=pb.string(forType:.string)
    pasteboardReadAvailable=readback != nil
    if let readback=readback {
     pasteboardReadLength=(readback as NSString).length
     pasteboardReadMatchesExpected=readback==value
    }
    guard readback==value else {try fail("검색어 입력을 확인하지 못했습니다.",code:"search_pasteboard_unavailable",diagnostics:diagnostics("pasteboard-readback"))}
    guard activeField() != nil,str(field,kAXValueAttribute)==original,
          let range=selectedRange(field),range.location==0,range.length==(original as NSString).length else {
     try fail("검색 입력 중 포커스 또는 선택 범위가 바뀌었습니다.",code:"search_selection_unverified",diagnostics:diagnostics("before-paste-menu"))
    }
    pasteAttempted=true
    menuActions["paste"]=editMenuAction(root,"paste")
    guard (menuActions["paste"] as? [String:Any])?["actionSucceeded"] as? Bool == true else {
     try fail("카카오톡 편집 메뉴의 붙여넣기 동작을 확인하지 못했습니다.",code:"search_paste_menu_unavailable",diagnostics:diagnostics("paste-menu"))
    }
   }
   let inputDeadline=Date().addingTimeInterval(2)
   while Date()<inputDeadline {
    if activeField() != nil && str(field,kAXValueAttribute)==value {inputObserved=true;return}
    guard activeField() != nil else {try fail("검색 입력 중 다른 창으로 포커스가 바뀌었습니다.",code:"search_focus_changed",diagnostics:diagnostics("input-wait"))}
    RunLoop.current.run(until:Date(timeIntervalSinceNow:0.05))
   }
   try fail("검색어 입력을 확인하지 못했습니다.",code:"search_input_unverified",diagnostics:diagnostics("input-timeout"))
  }
  try enterSearch(room)
  var settle=SearchSettle()
  let deadline=Date().addingTimeInterval(15)
  var sampleCount=0;var lastExact=0
  while Date()<deadline {
   guard !sessionLocked() else {try fail("Mac 화면이 잠겼습니다. 방 부재로 취급하지 않습니다.")}
   guard kids(root).contains(where:{str($0,"AXIdentifier")=="Main Window"}),str(field,kAXValueAttribute)==room else {try fail("검색 화면 또는 입력값이 바뀌어 결과를 확인하지 못했습니다.")}
   // Only inspect chat result headers, never message previews or ad webviews.
   // Searching the entire window can spend the full deadline inside unrelated AX trees.
   readCache.removeAll();readCacheEnabled=true
   let resultTable=find(main,{role($0,"AXTable")})
   let resultRows=(resultTable.map{kids($0)} ?? []).filter{role($0,"AXRow")}
   func headers(_ e:AXUIElement,_ depth:Int=0)->[AXUIElement] {
    if depth>6{return []}
    let kind=str(e,kAXRoleAttribute)
    if kind=="AXStaticText" {return [e]}
    if ["AXTextArea","AXWebArea","AXImage","AXButton"].contains(kind){return []}
    return kids(e).prefix(100).flatMap{headers($0,depth+1)}
   }
   func chrome(_ e:AXUIElement,_ depth:Int=0)->[AXUIElement] {
    if depth>8 || role(e,"AXTable") || role(e,"AXWebArea"){return []}
    return [e]+kids(e).prefix(100).flatMap{chrome($0,depth+1)}
   }
   let candidates=resultRows.filter{headers($0).contains{str($0,kAXValueAttribute)==room}}
   let marker=resultTable != nil && resultRows.isEmpty || resultRows.isEmpty && chrome(main).contains{role($0,"AXStaticText") && ["검색 결과가 없습니다.","검색 결과가 없습니다","검색 결과 없음"].contains(str($0,kAXValueAttribute))}
   let sample:[String:Any]=["query":str(field,kAXValueAttribute),"rows":candidates.map{_ in room},"empty":marker]
   readCacheEnabled=false;readCache.removeAll()
   sampleCount+=1;lastExact=candidates.count
   let oldPass=settle.pass
   if let outcome=settle.observe(sample,room:room) {
    if outcome=="confirmed_absent" {return ["found":false,"room":room,"searchEvidence":outcome]}
    if outcome=="ambiguous" {try fail("일치하는 검색 결과가 2개 이상입니다. 정확한 방을 직접 열어주세요.")}
    if outcome=="unique_exact" {
     // AX exposes off-screen rows as well as visible rows. Never click their
     // reported coordinates until the exact row is within the main window.
     var selected=candidates[0]
     for _ in 0..<20 {
      guard !sessionLocked(),str(field,kAXValueAttribute)==room,
            let r=bounds(selected),let w=bounds(main) else {break}
      let visible=w.insetBy(dx:10,dy:90)
      if visible.contains(CGPoint(x:r.midX,y:r.midY)) {break}
      guard CGPreflightPostEventAccess(), NSWorkspace.shared.frontmostApplication?.processIdentifier==app.processIdentifier else {
       try fail("카카오톡 스크롤 권한 또는 활성 창을 확인하지 못했습니다.",code:"search_scroll_unverified")
      }
      let direction:Int32 = r.midY > visible.maxY ? -180 : 180
      guard let event=CGEvent(scrollWheelEvent2Source:nil,units:.pixel,wheelCount:1,wheel1:direction,wheel2:0,wheel3:0) else {break}
      event.location=CGPoint(x:w.midX,y:w.midY);event.post(tap:.cghidEventTap)
      RunLoop.current.run(until:Date(timeIntervalSinceNow:0.2))
      let rows=(find(main,{role($0,"AXTable")}).map{kids($0)} ?? []).filter{role($0,"AXRow")}
      let matches=rows.filter{headers($0).contains{str($0,kAXValueAttribute)==room}}
      guard matches.count==1 else {try fail("검색 결과가 변경되어 방을 확인하지 못했습니다.",code:"search_unverified")}
      selected=matches[0]
     }
     guard !sessionLocked(),str(field,kAXValueAttribute)==room,
           let r=bounds(selected),let w=bounds(main),
           w.insetBy(dx:10,dy:90).contains(CGPoint(x:r.midX,y:r.midY)) else {
      try fail("검색 결과가 화면에 보이지 않아 방을 열지 않았습니다.",code:"search_result_offscreen")
     }
     try click(selected,true)
     let windowDeadline=Date().addingTimeInterval(5)
     var confirmedWindow:AXUIElement?
     while Date()<windowDeadline {
      if let found=try? roomWindow(){confirmedWindow=found;break}
      RunLoop.current.run(until:Date(timeIntervalSinceNow:0.1))
     }
     guard confirmedWindow != nil else {_ = try roomWindow();try fail("채팅방 확인에 실패했습니다.")}
     searchOpened=true
     return ["opened":true,"room":room,"searchEvidence":outcome]
    }
    try fail("검색 상태를 확인하지 못했습니다.")
   }
   if oldPass==0 && settle.pass==1 {
    try enterSearch("");RunLoop.current.run(until:Date(timeIntervalSinceNow:0.25))
    let resetDeadline=Date().addingTimeInterval(2)
    var resetHasRows=false
    repeat {
     if let table=find(main,{role($0,"AXTable")}),kids(table).contains(where:{role($0,"AXRow")}) {resetHasRows=true;break}
     RunLoop.current.run(until:Date(timeIntervalSinceNow:0.1))
    } while Date()<resetDeadline
    guard resetHasRows else {try fail("검색 초기화 후 채팅 목록을 확인하지 못했습니다.",code:"search_reset_unverified")}
    let cleared=false
    let clearSample:[String:Any]=["query":str(field,kAXValueAttribute),"rows":[],"empty":cleared,"locked":sessionLocked(),
                                   "mainWindow":kids(root).contains(where:{str($0,"AXIdentifier")=="Main Window"})]
    guard settle.observe(clearSample,room:room)==nil,settle.pass==2 else {try fail("검색 결과가 갱신됐는지 확인하지 못했습니다. 대체 수신자로 보내지 않습니다.")}
    try enterSearch(room)
   }
   RunLoop.current.run(until:Date(timeIntervalSinceNow:0.3))
  }
  try fail("검색 결과가 안정화되지 않아 시간 초과됐습니다. 대체 수신자로 보내지 않습니다.",code:"search_unsettled",diagnostics:["stage":"settling","samples":sampleCount,"exactRows":lastExact,"stableSamples":settle.exactCount,"budgetExceeded":axBudgetExceeded])
 }
 var candidate=try? roomWindow()
 if candidate==nil {app.activate();usleep(300000);candidate=try? roomWindow()}
 guard let window=candidate else {try fail("지정된 채팅방 창을 확인하지 못했습니다. Mac 잠금과 카카오톡 로그인 상태를 확인해주세요.",code:"room_window_unavailable")}
 func rows(_ receiptOnly:Bool=false)->[[String:Any]] {
  let priorCache=readCacheEnabled
  readCache.removeAll();readCacheEnabled=true
  defer{readCacheEnabled=priorCache;readCache.removeAll()}
  readCache.removeAll();readCacheEnabled=true;defer{readCacheEnabled=false;readCache.removeAll()}
  guard let table=find(window,{role($0,"AXTable")}) else{return []}
  let indexed=Array(kids(table).filter{role($0,"AXRow")}.enumerated())
  let selected=receiptOnly ? Array(indexed.suffix(30)):indexed
  return selected.map{index,row in
   let ns=walk(row),texts=ns.filter{role($0,"AXTextArea")}.map{str($0,kAXValueAttribute)}
   let profile=ns.first{role($0,"AXButton")&&matches($0,"프로필")}
   let statics=ns.filter{role($0,"AXStaticText")}
   if receiptOnly {
    let content=ns.first{role($0,"AXTextArea")} ?? ns.first{role($0,"AXImage")}
    let clock=statics.first{isTimeLabel(str($0,kAXValueAttribute))}
    var direction=messageDirection(content.flatMap{bounds($0)},clock.flatMap{bounds($0)},hasProfile:profile != nil)
    let hasImage=ns.contains{role($0,"AXImage")},hasShare=ns.contains{role($0,"AXButton")&&matches($0,"공유")}
    let photo=hasImage && texts.isEmpty && hasShare
    let roomFrame=bounds(window)
    let imageFrames=ns.filter{role($0,"AXImage")}.compactMap{bounds($0)}
    let left=roomFrame.flatMap{frame in frame.width > 0 ? imageFrames.map{Int(($0.minX-frame.minX)*1000/frame.width)}.min():nil} ?? -1
    let right=roomFrame.flatMap{frame in frame.width > 0 ? imageFrames.map{Int(($0.maxX-frame.minX)*1000/frame.width)}.max():nil} ?? -1
    if direction=="unknown" {
     direction=groupedImageDirection(photo:photo,hasProfile:profile != nil,hasClock:clock != nil,imageCount:(req["files"] as? [String] ?? []).count,left:left,right:right)
    }
    return ["identity":String(CFHash(row)),"index":index,"text":texts.joined(separator:"\n"),"direction":direction,"photo":photo,"file":false,"hasImage":hasImage,"hasClock":clock != nil,"hasShare":hasShare,"hasText":!texts.isEmpty,"imageLeftPermille":left,"imageRightPermille":right]
   }
   let metadata=statics.map{str($0,kAXValueAttribute)}.joined(separator:" ")
   let date=statics.map{str($0,kAXHelpAttribute)}.first{ !$0.isEmpty } ?? ""
   let image=ns.contains{role($0,"AXImage")} && texts.isEmpty && ns.contains{role($0,"AXButton")&&matches($0,"공유")}
   let fileName=statics.map{str($0,kAXValueAttribute)}.first{ $0.range(of:"(?i)\\.[a-z0-9]{1,8}$",options:.regularExpression) != nil } ?? ""
   let fileButtons=ns.filter{role($0,"AXButton")}.map{label($0)}
   let content=ns.first{role($0,"AXTextArea")} ?? ns.first{role($0,"AXImage")} ?? statics.first{str($0,kAXValueAttribute)==fileName}
   let clock=statics.first{isTimeLabel(str($0,kAXValueAttribute))}
   let direction=messageDirection(content.flatMap{bounds($0)},clock.flatMap{bounds($0)},hasProfile:profile != nil)
   let mentions=ns.filter{role($0,"AXTextArea")}.flatMap{highlightedMentions($0)}
   return ["index":index,"text":texts.joined(separator:"\n"),"mentions":mentions,"metadata":metadata,"date":date,"direction":direction,"newSender":profile != nil,"photo":image,"photoCount":image ? ns.filter{role($0,"AXImage")}.count:0,"fileName":fileName,"file":!fileName.isEmpty && fileButtons.contains{ $0.contains("저장") || $0.contains("다운로드") || $0.contains("열기") }]
  }
 }
 func revealLatestRow() {
  guard let table=find(window,{role($0,"AXTable")}) else{return}
  // Kakao virtualizes older rows. Asking the final loaded row to become visible
  // is enough to return a scrolled chat to its live edge without focusing the
  // composer or synthesizing keyboard input.
  if let last=kids(table).last { _=AXUIElementPerformAction(last,"AXScrollToVisible" as CFString) }
  func controls(_ e:AXUIElement,_ depth:Int=0)->[AXUIElement]{if depth>12 || role(e,"AXTable"){return []};return [e]+kids(e).flatMap{controls($0,depth+1)}}
  for bar in controls(window).filter({role($0,"AXScrollBar") && str($0,kAXOrientationAttribute)==kAXVerticalOrientationValue}) {
   _=AXUIElementSetAttributeValue(bar,kAXValueAttribute as CFString,NSNumber(value:1.0))
  }
  usleep(250000)
 }
 if command=="read" || command=="read-latest" {
  if command=="read-latest" {revealLatestRow()}
  let result=rows()
  guard !axBudgetExceeded else{try fail("메시지 읽기의 10초 한도를 초과했습니다. 불완전한 읽기를 성공으로 처리하지 않습니다.",code:"ax_read_budget_exceeded")}
  return ["room":room,"rows":result,"coverage":"loaded_messages_only","latestRequested":command=="read-latest"]
 }
 if command=="receipt-inspect" {
  func summary(_ rs:[[String:Any]])->[[String:Any]] {rs.map{r in ["identity":r["identity"] ?? "","photo":r["photo"] ?? false,"direction":r["direction"] ?? "unknown"]}}
  let a=rows(true);let b=rows(true)
  return ["first":summary(a),"second":summary(b),"budgetExceeded":axBudgetExceeded]
 }
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
 if command=="prepare-inspect" {
  guard let text=req["text"] as? String,!text.isEmpty,req["files"] == nil else {
   try fail("진단에는 비어 있지 않은 텍스트만 필요합니다.",code:"prepare_inspect_invalid_request")
  }
 }
 app.activate();AXUIElementPerformAction(window,kAXRaiseAction as CFString);usleep(200000)
 guard let box=composer(window),str(box,kAXValueAttribute).isEmpty else {try fail("작성 중인 메시지가 있어 중단했습니다.")}
 if command=="send" || command=="prepare-inspect" {
  let text=req["text"] as? String ?? ""
  let files=req["files"] as? [String] ?? []
  let initialRows=command=="send" ? rows(true) : []
  // Check again after preparation; the final gate below checks once more before the single mouse click.
  guard !sessionLocked() else{try fail("잠금 상태를 확인하지 못했습니다. 자동 재시도하지 마세요.")}
  func composerPasteEvidence(_ stage:String,_ expectedLength:Int?=nil,_ pasteboardWriteAccepted:Bool?=nil,_ menuAction:[String:Any]?=nil)->[String:Any] {
   let ws=(attr(root,kAXWindowsAttribute) as? [AXUIElement] ?? kids(root)).filter{role($0,"AXWindow")}
   let exact=ws.filter{str($0,kAXTitleAttribute)==room}
   let current=exact.count==1 && CFEqual(exact[0],window) ? exact[0]:nil
   let currentComposer=current.flatMap{composer($0)}
   let focusedWindow=attr(root,kAXFocusedWindowAttribute)
   let focusedElement=attr(root,kAXFocusedUIElementAttribute)
   var evidence:[String:Any]=["stage":stage,"roomWindowExact":current != nil,
    "composerPresent":currentComposer != nil,"composerIdentityStable":currentComposer != nil && CFEqual(currentComposer!,box),
    "focusedComposer":focusedElement != nil && CFEqual(focusedElement!,box),
    "keyWindowMatches":focusedWindow != nil && CFEqual(focusedWindow!,window),
    "frontmostTargetApp":NSWorkspace.shared.frontmostApplication?.processIdentifier==app.processIdentifier,
    "locked":sessionLocked(),"actualLength":(str(box,kAXValueAttribute) as NSString).length]
   if let expectedLength {evidence["expectedLength"]=expectedLength}
   if let pasteboardWriteAccepted {evidence["pasteboardWriteAccepted"]=pasteboardWriteAccepted}
   if let menuAction {evidence["menuAction"]=menuAction}
   return evidence
  }
  func pasteIntoComposer(_ stage:String,_ expectedLength:Int?=nil,_ pasteboardWriteAccepted:Bool,_ clipboardGeneration:Int)throws->[String:Any] {
   AXUIElementPerformAction(window,kAXRaiseAction as CFString)
   let focusSet=AXUIElementSetAttributeValue(box,kAXFocusedAttribute as CFString,kCFBooleanTrue) == .success
   let focusUntil=Date().addingTimeInterval(1.5)
   while Date()<focusUntil {
    let current=composerPasteEvidence(stage+"-focus",expectedLength,pasteboardWriteAccepted)
    if current["keyWindowMatches"] as? Bool==true && current["focusedComposer"] as? Bool==true {break}
    guard current["frontmostTargetApp"] as? Bool==true,current["roomWindowExact"] as? Bool==true else{break}
    RunLoop.current.run(until:Date(timeIntervalSinceNow:0.05))
   }
   let before=composerPasteEvidence(stage+"-before",expectedLength,pasteboardWriteAccepted)
   let beforeIsSafe=before["roomWindowExact"] as? Bool==true && before["composerIdentityStable"] as? Bool==true &&
    before["keyWindowMatches"] as? Bool==true && before["focusedComposer"] as? Bool==true &&
    before["frontmostTargetApp"] as? Bool==true && before["locked"] as? Bool==false
   guard focusSet && beforeIsSafe else {try fail("메시지 입력창의 방·포커스를 확인하지 못했습니다.",code:"composer_focus_unverified",diagnostics:before)}
   guard NSPasteboard.general.changeCount==clipboardGeneration else{
    try fail("입력 준비 중 클립보드가 변경됐습니다. 새 클립보드를 보존하고 전송을 중단했습니다.",code:"clipboard_changed")
   }
   let action=editMenuAction(root,"paste")
   let after=composerPasteEvidence(stage,expectedLength,pasteboardWriteAccepted,action)
   guard action["actionSucceeded"] as? Bool==true else {
    try fail("카카오톡 편집 메뉴 붙여넣기를 확인하지 못했습니다.",code:"composer_paste_menu_unavailable",diagnostics:after)
   }
   return after
  }
  if !text.isEmpty {
   var verifiedComposerText:String?
   let pb=NSPasteboard.general;let saved=(pb.pasteboardItems ?? []).map{item -> NSPasteboardItem in let copy=NSPasteboardItem();for type in item.types{if let data=item.data(forType:type){copy.setData(data,forType:type)}};return copy}
   var ownedClipboardGeneration:Int?
   defer{if ownedClipboardGeneration==pb.changeCount{pb.clearContents();pb.writeObjects(saved)}}
   prepared=true
   pb.clearContents();let pasteboardWriteAccepted=pb.setString(text,forType:.string)
   ownedClipboardGeneration=pb.changeCount
   let readback=pb.string(forType:.string)
   guard pasteboardWriteAccepted,readback==text else {
    var evidence=composerPasteEvidence("composer-pasteboard",(text as NSString).length,pasteboardWriteAccepted)
    evidence["pasteboardReadAvailable"]=readback != nil;evidence["pasteboardReadMatchesExpected"]=readback==text
    try fail("메시지 입력 검증에 실패했습니다.",code:"composer_pasteboard_unverified",diagnostics:evidence)
   }
   var pasteEvidence=try pasteIntoComposer("composer-text-paste",(text as NSString).length,pasteboardWriteAccepted,ownedClipboardGeneration!)
   pasteEvidence["pasteboardReadAvailable"]=readback != nil
   pasteEvidence["pasteboardReadMatchesExpected"]=readback==text
   let inputDeadline=Date().addingTimeInterval(2)
   while Date()<inputDeadline {
    let actual=str(box,kAXValueAttribute)
    if composerTextEquivalent(text,actual) {verifiedComposerText=actual;break}
    let current=composerPasteEvidence("composer-text-input-wait",(text as NSString).length,pasteboardWriteAccepted,pasteEvidence["menuAction"] as? [String:Any])
    guard current["roomWindowExact"] as? Bool==true,current["composerIdentityStable"] as? Bool==true,
          current["keyWindowMatches"] as? Bool==true,current["frontmostTargetApp"] as? Bool==true,
          current["locked"] as? Bool==false,current["focusedComposer"] as? Bool==true else {
     try fail("메시지 입력 중 방 또는 포커스가 바뀌었습니다.",code:"composer_focus_changed",diagnostics:current)
    }
    RunLoop.current.run(until:Date(timeIntervalSinceNow:0.05))
   }
   guard let finalVerifiedComposerText=verifiedComposerText else {
    pasteEvidence=composerPasteEvidence("composer-text-input-timeout",(text as NSString).length,pasteboardWriteAccepted,pasteEvidence["menuAction"] as? [String:Any])
    pasteEvidence["pasteboardReadAvailable"]=readback != nil;pasteEvidence["pasteboardReadMatchesExpected"]=readback==text
    try fail("메시지 입력 검증에 실패했습니다.",code:"composer_input_unverified",diagnostics:pasteEvidence)
   }
   if command=="prepare-inspect" {
    let started=ProcessInfo.processInfo.systemUptime
    let deadline=started+3.0
    var first:Bool?
    var last:Bool?
    var sampled=false
    repeat {
     let evidence=composerPasteEvidence("prepare-inspect")
     guard evidence["roomWindowExact"] as? Bool==true,
           evidence["composerIdentityStable"] as? Bool==true,
           evidence["focusedComposer"] as? Bool==true,
           evidence["keyWindowMatches"] as? Bool==true,
           evidence["frontmostTargetApp"] as? Bool==true,
           evidence["locked"] as? Bool==false,
           str(box,kAXValueAttribute)==finalVerifiedComposerText else {
      try fail("진단 중 방·포커스 또는 입력이 변경됐습니다.",code:"prepare_inspect_context_changed",diagnostics:evidence)
     }
     let button=find(window,{role($0,"AXButton")&&matches($0,"전송")},true)
     let enabled=button.flatMap{strictBool(attr($0,kAXEnabledAttribute))}
     if !sampled {first=enabled;sampled=true}
     last=enabled
     let remaining=deadline-ProcessInfo.processInfo.systemUptime
     if remaining<=0 {break}
     RunLoop.current.run(until:Date(timeIntervalSinceNow:min(0.05,remaining)))
    } while ProcessInfo.processInfo.systemUptime<deadline
    let elapsedMs=Int((ProcessInfo.processInfo.systemUptime-started)*1000)
    var result=roomStatusDiagnostics(root,room)
    let evidence=composerPasteEvidence("prepare-inspect-complete")
    for key in ["roomWindowExact","composerPresent","composerIdentityStable","focusedComposer","keyWindowMatches","frontmostTargetApp","locked"] {result[key]=evidence[key]}
    result["composerTextVerified"]=str(box,kAXValueAttribute)==finalVerifiedComposerText
    result["initialEnabled"]=first.map{$0 as Any} ?? NSNull()
    result["finalEnabled"]=last.map{$0 as Any} ?? NSNull()
    result["elapsedMs"]=elapsedMs
    result["clicked"]=false
    return result
   }
   var send:AXUIElement?
   func observeTextSend()->([String:Any]?,SendSnapshot) {
    let ws=(attr(root,kAXWindowsAttribute) as? [AXUIElement] ?? kids(root)).filter{role($0,"AXWindow")}
    let exact=ws.filter{str($0,kAXTitleAttribute)==room}
    let current=exact.count==1 && CFEqual(exact[0],window) ? exact[0]:nil
    let fresh=current.flatMap{composer($0)}
    let buttons=current.flatMap{sendButtonCandidates($0)}
    send=buttons?.count==1 ? buttons?[0]:nil
    let focusedWindow=attr(root,kAXFocusedWindowAttribute)
    let focusedElement=attr(root,kAXFocusedUIElementAttribute)
    let snapshot=SendSnapshot(windows:ws.map{str($0,kAXTitleAttribute)},
     composerOwned:fresh != nil && CFEqual(fresh!,box) && str(fresh!,kAXValueAttribute)==finalVerifiedComposerText,
     buttonOwned:send != nil,
     frontmostTargetApp:NSWorkspace.shared.frontmostApplication?.processIdentifier==app.processIdentifier,
     keyWindowOwned:focusedWindow != nil && current != nil && CFEqual(focusedWindow!,current!),
     buttonBoundsOwned:send != nil && current != nil && bounds(send!,current!),
     composerFocused:focusedElement != nil && CFEqual(focusedElement!,box),
     buttonEnabled:send.flatMap{strictBool(attr($0,kAXEnabledAttribute))})
    return (currentLockSnapshot(),snapshot)
   }
   let readinessDeadline=ProcessInfo.processInfo.systemUptime+3.0
   try awaitSendReady(room:room,observe:observeTextSend,
    expired:{ProcessInfo.processInfo.systemUptime>=readinessDeadline},
    pause:{let remaining=readinessDeadline-ProcessInfo.processInfo.systemUptime
     if remaining>0 {RunLoop.current.run(until:Date(timeIntervalSinceNow:min(0.05,remaining)))}})
   try checkedSendWithReceipt(room:room,observe:observeTextSend,click:{try click(send!)},confirm:{
    let deadline=Date().addingTimeInterval(5)
    repeat {
     _=try roomWindow()
     guard !sessionLocked() else{return false}
     if str(box,kAXValueAttribute).isEmpty && newOutgoingReceipt(initialRows,rows(true),text:finalVerifiedComposerText){return true}
     RunLoop.current.run(until:Date(timeIntervalSinceNow:0.2))
    } while Date()<deadline
    return false
   })
  }
  if !files.isEmpty {
   var receiptDiagnostics:[String:Any]=[:]
   var receiptSamples=0
   _=try roomWindow()
   guard !sessionLocked() else{try fail("잠금 상태를 확인하지 못했습니다. 자동 재시도하지 마세요.")}
   let pb=NSPasteboard.general;let backup=(pb.pasteboardItems ?? []).map{item -> NSPasteboardItem in let copy=NSPasteboardItem();for type in item.types{if let data=item.data(forType:type){copy.setData(data,forType:type)}};return copy}
   var ownedClipboardGeneration:Int?
   defer{if ownedClipboardGeneration==pb.changeCount{pb.clearContents();pb.writeObjects(backup)}}
   guard files.count<=20,files.allSatisfy({FileManager.default.fileExists(atPath:$0)}) else{try fail("리포트 이미지는 최대 20장까지 보낼 수 있습니다.")}
   prepared=true
   pb.clearContents();let pasteboardWriteAccepted=pb.writeObjects(files.map{URL(fileURLWithPath:$0) as NSURL})
   ownedClipboardGeneration=pb.changeCount
   let pasteEvidence=try pasteIntoComposer("composer-file-paste",nil,pasteboardWriteAccepted,ownedClipboardGeneration!)
   usleep(600000)
   guard let sheet=find(window,{role($0,"AXSheet")},true) else{try fail("첨부 확인창을 찾지 못했습니다.",code:"composer_attachment_paste_unverified",diagnostics:pasteEvidence)}
   if let bundle=find(sheet,{(role($0,"AXCheckBox") || role($0,"AXButton"))&&label($0).contains("묶어")}), (attr(bundle,kAXValueAttribute) as? NSNumber)?.intValue != 1 {try press(bundle)}
   guard let send=find(sheet,{role($0,"AXButton")&&matches($0,"\(files.count)개 전송")}) else {try fail("첨부 확인창을 찾지 못했습니다.")}
   var freshSend:AXUIElement?
   func observeAttachment()->([String:Any]?,SendSnapshot) {
    let ws=(attr(root,kAXWindowsAttribute) as? [AXUIElement] ?? kids(root)).filter{role($0,"AXWindow")}
    let exact=ws.filter{str($0,kAXTitleAttribute)==room}
    let current=exact.count==1 && CFEqual(exact[0],window) ? exact[0]:nil
    let fresh=current.flatMap{composer($0)}
    let freshSheet=current.flatMap{find($0,{role($0,"AXSheet")},true)}
    freshSend=freshSheet.flatMap{find($0,{role($0,"AXButton")&&matches($0,"\(files.count)개 전송")})}
    let focusedWindow=attr(root,kAXFocusedWindowAttribute)
    let snapshot=SendSnapshot(windows:ws.map{str($0,kAXTitleAttribute)},
     composerOwned:fresh != nil && CFEqual(fresh!,box),
     buttonOwned:freshSheet != nil && CFEqual(freshSheet!,sheet) && freshSend != nil && CFEqual(freshSend!,send),
     frontmostTargetApp:NSWorkspace.shared.frontmostApplication?.processIdentifier==app.processIdentifier,
     keyWindowOwned:focusedWindow != nil && current != nil &&
      (CFEqual(focusedWindow!,current!) ||
       (freshSheet != nil && CFEqual(freshSheet!,sheet) && CFEqual(focusedWindow!,freshSheet!))),
     buttonBoundsOwned:freshSheet != nil && freshSend != nil && bounds(freshSend!,freshSheet!),
     composerFocused:true,
     buttonEnabled:freshSend.flatMap{strictBool(attr($0,kAXEnabledAttribute))})
    return (currentLockSnapshot(),snapshot)
   }
   let attachmentReadyUntil=ProcessInfo.processInfo.systemUptime+3
   try awaitSendReady(room:room,observe:observeAttachment,
    expired:{ProcessInfo.processInfo.systemUptime>=attachmentReadyUntil},
    pause:{RunLoop.current.run(until:Date(timeIntervalSinceNow:0.05))})
   try checkedSendWithReceipt(room:room,observe:observeAttachment,click:{try click(freshSend!)},confirm:{
   var finalRows=rows(true);receiptSamples+=1
   let deadline=Date().addingTimeInterval(20)
   while !newOutgoingReceipt(initialRows,finalRows,attachment:true) && Date()<deadline {
    let nodes=walk(window)
    if let alert=nodes.first(where:{role($0,"AXAlert")}) {
     let details=walk(alert).map(label).filter{!$0.isEmpty}.joined(separator:" ")
     try fail(details.isEmpty ? "카카오톡 오류 알림이 표시됐습니다. 대화방을 확인해주세요." : "카카오톡 오류 알림: \(details)")
    }
    let visibleError=nodes.filter{role($0,"AXStaticText") || role($0,"AXTextArea")}.map(label).first{
     ["예상치 못한 오류","전송 실패","전송하지 못","잠시 후 다시"].contains(where:$0.contains)
    }
    if let visibleError {try fail("카카오톡 오류: \(visibleError)")}
    RunLoop.current.run(until:Date(timeIntervalSinceNow:0.5))
    finalRows=rows(true);receiptSamples+=1
   }
   receiptDiagnostics=attachmentReceiptDiagnostics(initialRows,finalRows,budgetExceeded:axBudgetExceeded,samples:receiptSamples)
   return newOutgoingReceipt(initialRows,finalRows,attachment:true)
   },diagnostics:{receiptDiagnostics})
  }
  keepRoomAfterSuccess = (req["keepRoomOpen"] as? Bool == true)
  return ["sent":true,"room":room,"text":!text.isEmpty,"photos":files.count,"verifiedBy":"outgoing_rows"]
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
do {var result=try run();if let cleanupResult{result["cleanup"]=cleanupResult};print(String(data:try JSONSerialization.data(withJSONObject:result),encoding:.utf8)!)}catch{let failure=error as? Failure;let detail=failure?.message ?? error.localizedDescription;let message=prepared && !committed ? detail+" 작성 내용이 남을 수 있으니 수동 점검하세요. 자동 재시도하거나 대체 수신자로 보내지 마세요." : detail;var payload:[String:Any] = ["error":message,"errorCode":failure?.code ?? "bridge_error","committed":committed,"uncertain":committed,"manualCheck":prepared];if let cleanupResult{payload["cleanup"]=cleanupResult};if let diagnostics=failure?.diagnostics, !diagnostics.isEmpty {payload["diagnostics"]=diagnostics};print(String(data:try! JSONSerialization.data(withJSONObject:payload),encoding:.utf8)!);exit(1)}
