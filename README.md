# 📈 Stock Supervisor (주식 퀀트 & 시스템 통합 현황판)

> **GitHub Pages 배포 지원 웹 대시보드**  
> Mac 로컬에서 가동 중인 주식 퀀트, 무한 스윙 트레이딩, 텔레그램 알람 시스템 9종의 데몬 가동 상태와 실행 로그를 한눈에 모니터링하는 관제탑(Supervisor) 대시보드입니다.

---

## 🖥️ 주요 기능

- **다크 테마 핀테크 대시보드**: 모던 글래스모피즘 & 네온 포인트 디자인 (모바일/태블릿/PC 반응형)
- **통합 KPI 지표**:
  - 총 관리 프로젝트 수 (9개)
  - 로컬 `launchd` 스케줄러 및 실시간 데몬 정상 등록 현황
  - 오늘 실행 완료된 파이프라인 수
  - 한국(KRX) 및 미국(US) 시장 커버리지
- **타임라인 스케줄러**:
  - `08:30` (월) 주간 배당 TOP 7 스캔
  - `08:40` (매일) SEPA x 피벗 감시 (한국)
  - `08:45` (평일) 스톡 스나이퍼 (수급 x RS 상대강도 x 52주 신고가)
  - `09:30` (매일) K-Bit 특징주 봇
  - `11:00` (매일) KRX 시클리컬 6대 섹터 퀀트
  - `17:00` (화) 미국 3배 레버리지(US3X) & HTP 모멘텀 TOP 10
  - `21:30` (매일) SEPA x 피벗 감시 (미국)
  - `24/7 상시` 227선 자율 진화 무한 스윙 분할매수 데몬
- **로그 즉시 확인**: 각 프로젝트별 최근 10줄의 실행 로그를 모달 팝업으로 조회
- **검색 및 마켓별 필터링**: 한국(KRX), 미국(US), 가동 중(Active) 필터 및 실시간 텍스트 검색

---

## 🚀 빠른 시작

### 방법 1. 브라우저로 바로 열기
저장소 폴더 내의 `index.html` 파일을 더블 클릭하여 크롬이나 사파리로 바로 열 수 있습니다.

### 방법 2. 로컬 실시간 서버 실행 (권장)
```bash
./serve.py
# 또는 python3 serve.py
```
- 브라우저(`http://localhost:8080`)가 자동으로 열립니다.
- 상단의 **[새로고침]** 버튼을 누르면 로컬 `launchctl`과 최신 로그 파일을 실시간으로 재수집하여 대시보드에 즉시 반영됩니다.

### 방법 3. 최신 상태 데이터 수동 동기화
```bash
./update_status.py
```
- `data/status.json`과 `index.html` 내장 데이터가 최신 상태로 갱신됩니다.

---

## 🌐 GitHub Pages로 웹 배포하기

이 프로젝트를 GitHub Pages에 올리면 언제 어디서나 모바일 폰이나 외부 PC에서도 `https://bluem00000000n.github.io/stock-supervisor` 주소로 현황판을 열람할 수 있습니다.

### 1) GitHub에 새 저장소 생성
GitHub(github.com)에서 `stock-supervisor` 이름으로 새 저장소(Public)를 만듭니다.

### 2) 로컬 코드 커밋 & 푸시
```bash
cd /Users/tothemoon/stock-supervisor
git init
git add .
git commit -m "feat: Initial commit for Stock Supervisor dashboard"
git branch -M main
git remote add origin https://github.com/bluem00000000n/stock-supervisor.git
git push -u origin main
```

### 3) GitHub Pages 켜기
1. GitHub 저장소 페이지(`https://github.com/bluem00000000n/stock-supervisor`) 접속
2. 상단 메뉴 **[Settings]** 탭 클릭
3. 좌측 사이드바에서 **[Pages]** 클릭
4. **Branch** 항목에서 `main` 브랜치 및 `/ (root)` 선택 후 **[Save]** 클릭
5. 1~2분 후 배포가 완료되며 웹 접속 링크가 활성화됩니다:
   👉 **`https://bluem00000000n.github.io/stock-supervisor`**

---

## 📁 관리 대상 주식 프로젝트 목록

| 프로젝트 | 시장 | 실행 주기 | 핵심 알고리즘 |
| :--- | :---: | :--- | :--- |
| **stock-sniper** | 🇰🇷 KRX | 평일 08:45 | 외인/기관 수급 × RS 상대강도 × 52주 신고가 × 지수 ETF 주도주 5선 |
| **stock-sepa-pivot** | 🇰🇷 🇺🇸 | 매일 08:40 / 21:30 | 마크 미너비니 SEPA 13대 조건 × 댄 쟁거 VCP 차트 패턴 피벗 감시 |
| **stock-swing** | 🇰🇷 🇺🇸 | 24/7 데몬 | 한국/미국 227선 자율 진화 무한 스윙 분할 모아가기(Scale-in) |
| **stock-us3x** | 🇺🇸 US | 매주 화 08:30, 17:00 | 미국 3배 레버리지(TQQQ, SOXL 등) 무한매수 & 변동성 리밸런싱 |
| **stock-dividend_top7** | 🇰🇷 KRX | 매주 월 08:30 | 한국 거래소 6대 핵심 배당 기준 상위 7대 배당 성장주 선별 |
| **stock-htp-top10** | 🇺🇸 US | 매주 화 17:00 | High-to-Price 파워 모멘텀 알고리즘 기반 S&P 500/러셀 2000 탑10 |
| **stock-cyclical-screener** | 🇰🇷 KRX | 매일 11:00 | KRX 반도체/자동차/화학/철강/조선/해운 6대 시클리컬 섹터 퀀트 |
| **kbit-bot** | 🇰🇷 KRX | 매일 09:30 | 한국 당일 장중 특징주 & 60일 캔들 기술적 분석 자동 포스팅 |
| **signal_forge_alert** | 🌐 Global | 이벤트 기반 | Zero Paid API 기반 독립 AI 거시경제 시장 감시 인텔리전스 |
