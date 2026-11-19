# 접속 경로 전환 준비 및 외부 검증

## 실제 수행 결과
- 맥미니 en0: 192.168.0.4, 1000baseT/full-duplex. 공유기 ipTIME A2004SR, 게이트웨이 192.168.0.1, WAN 공인 주소 147.47.160.229. 글로벌 IPv6 없음.
- 표준 UPnP 조회 및 제한시간 포트 매핑이 가능해 공유기 관리자 비밀번호는 필요하지 않았다. 관리자 로그인/공유기 보안 설정 변경은 하지 않았다.
- Caddy 2.11.4, miniupnpc 2.3.3, lego 5.5.2를 Homebrew로 설치했다.
- 기존 Cloudflare cert.pem의 scoped 인증으로 DNS-only direct.chobab.app 시험 레코드를 생성했다. 토큰을 출력하거나 소스에 저장하지 않았다.
- 443→8443, 80→8080, 18443→8443 시험 포트만 한시적으로 생성했다.
- HTTP/TLS 인증 시 외부 검증 실패. DNS 인증으로 전환하고 로컬 재귀 DNS의 오래된 TXT 응답 문제를 우회해 1.1.1.1에서 검증했다.
- Let's Encrypt 공개 인증서 발급 완료: direct.chobab.app, chobab.app, aura.chobab.app, rehear.chobab.app. 인증서/키는 `/Users/sagi/Library/Application Support/sushisite-direct-tls` 아래 저장. 자동 갱신은 운영 전환 시 설치해야 한다.
- 인증 과정에서 sgonsisgood@gmail.com 연락처의 Let's Encrypt 및 ZeroSSL ACME 계정이 자동 생성됐다. ACME 계정은 비밀번호 대신 로컬 키로 인증하며 사용자가 준 신규가입 비밀번호를 사용하지 않았다. ZeroSSL 인증서 발급은 완료되지 않았다.

## 외부 검증
- 동일 LAN에서 direct HTTPS health 응답은 HTTP 200, TTFB 약 13ms. 이는 NAT loopback 측정이므로 외부 사용자의 성능으로 제시하면 안 된다.
- Globalping 한국 지점에서 기존 Cloudflare health 경로: HostHatch 서울 총 639ms(SIN), Oracle 춘천 91ms(ICN), KT 수원 1120ms(LAX). 서로 다른 회선에서 해외 경유가 실제 관측됨.
- 직접 443: KT 서울, Oracle 춘천, HostHatch 서울 모두 ECONNRESET.
- 직접 18443: KT/Oracle 모두 ECONNRESET. 원인이 공유기의 외부 접근 정책인지 상위 회선 정책인지 확정되지 않았으나, 외부 직접 연결은 운영 가능한 상태가 아니다.
- 측정 ID(공개 비인증 health 경로만 측정):
  - 기존: 2d8zIsw3oraQ84C4b00021CR2
  - 직접443: 2Jd9cm6LRJvFNoIgQ00021CR3
  - 직접18443: 2Rl5QTlPyXIV2pAUC00021CR5
- 시험 Caddy 종료. 시험 포트 3개와 direct DNS 레코드는 제거 대상으로 확인 후 정리했다. 인증서와 배포 설정은 보존했다. 기존 운영 DNS/Cloudflare Tunnel은 그대로이다.

## 준비된 다음 경로
방문자 → 서울 중계 VPS TCP 443 → 맥미니가 먼저 연결한 SSH reverse tunnel → 맥미니 Caddy TLS → 기존 Node/FastAPI

- 중계 서버에는 앱 데이터/DB/HTTPS 비밀키를 두지 않는다. TLS는 맥미니에서 종료한다.
- `ops/seoul-relay-setup.sh`: 새 Ubuntu 24.04 전용 중계 호스트에서 nginx stream 및 제한된 SSH remote forwarding 사용자 설정.
- `ops/seoul-relay-connect.sh`: 호스트 키를 별도로 검증한 전용 SSH 키로 outbound 연결. 전달 포트는 relay loopback에만 바인딩.
- `ops/Caddyfile.direct`: 현재 운영 host/path를 보존하는 프록시 구성. 설정 검증 통과. 운영 도메인으로 실행하지 않았다.
- 배포 스크립트는 bash 문법 검사만 통과했고 실제 Linux 인스턴스에서 아직 실행/검증하지 않았다.
- 권장 시험 인스턴스: AWS Lightsail 서울, Linux public IPv4, 1GB $7/월 기본요금, 2TB 포함. 세금 및 초과 트래픽 별도. 비용 동의 전 결제/인스턴스 생성하지 않았다.
- 다음 작업: 비용/전환 승인 → 인스턴스 확보 → 전용 SSH 키 생성 및 호스트 키 검증 → probe만 연결 → 같은 외부 회선 비교 → 더 빠르고 정상인 경우 운영 DNS 전환 → 자동 재연결/인증서 갱신/트래픽 관리/공인주소 갱신/롤백 검증.

## 승인 제한
자동 승인 검토가 운영 도메인과 로그인/API를 Cloudflare 보호 밖으로 직접 공개하는 실행을 거부했다. 허용된 무데이터 시험 endpoint만 실행하고 종료했다. 따라서 실서비스의 Cloudflare 우회 전환은 추가 명시적 승인 필요. 이를 우회하기 위해 다른 실행 방법을 사용하지 않았다.

참고: https://aws.amazon.com/lightsail/pricing/
