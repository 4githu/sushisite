NETAQ Android Widget 2.0.1 / versionCode 9

Android 8(API26) 이상. applicationId app.chobab.widget를 유지합니다.
설치: https://netaq.chobab.app/downloads/android-widget
연결: https://netaq.chobab.app/personal-project/calendar/widgets

홈 화면 위젯: 다음 일정 2x2, 오늘 4x2, 주간, 월간, 할 일, 메모, 일별 계획.
기존 CalendarWidget 주간 공급자는 숨김 호환 공급자로 유지해 기존 배치가 보존됩니다.
할 일 완료, 빠른 기록, 수동 갱신과 JobService 백그라운드 갱신을 지원합니다.

개발 도구: JDK17, Android SDK35, Gradle8.11.1(wrapper 포함).
JAVA_HOME, ANDROID_HOME을 지정하고 ./gradlew :app:testDebugUnitTest :app:assembleDebug :app:lintDebug 실행.
APK: app/build/outputs/apk/debug/app-debug.apk
운영 웹의 APK 사본 두 곳은 빌드 완료 후 함께 교체하고 Node 운영 빌드를 다시 생성합니다.
  sushi-app/src/lib/server/assets/ondo-widget.apk
  sushi-app/static/downloads/ondo-widget.apk
다운로드 표시 버전도 sushi-app/src/routes/downloads/android-widget/+server.ts에서 갱신합니다.

이번 APK는 기존 배포와 같은 Android Debug 인증서로 서명했습니다.
업데이트 호환을 위해 서명 키를 유지해야 합니다. 키 파일을 저장소에 추가하지 마세요.
Robolectric 6개 검사 및 lint/build를 통과했습니다. 실제 단말/런처 설치는 아직 확인하지 않았습니다.
