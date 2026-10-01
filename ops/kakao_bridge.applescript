-- Optional System Events probe/activation. It does not send chat messages.
-- osascript ops/kakao_bridge.applescript status
-- osascript ops/kakao_bridge.applescript activate "exact room title"
on run argv
    set operation to item 1 of argv
    tell application "System Events"
        if not (exists process "KakaoTalk") then error "카카오톡을 실행해주세요."
        tell process "KakaoTalk"
            if operation is "status" then return name of every window
            if operation is not "activate" or (count argv) is not 2 then error "지원하지 않는 명령입니다."
            set roomName to item 2 of argv
            set matches to every window whose name is roomName
            if (count matches) is not 1 then error "정확히 일치하는 방 하나를 열어주세요."
            set frontmost to true
            perform action "AXRaise" of item 1 of matches
            return name of item 1 of matches
        end tell
    end tell
end run
