#!/usr/bin/env bash
# scripts/install_launchd_monthly_rotation.sh
# 미국 ETF 자금순환(Sector Rotation) 월간 자동 보고 launchd 데몬 등록 스크립트

set -e

PLIST_NAME="com.stock.monthly-sector-rotation.plist"
SOURCE_PLIST="/Users/tothemoon/stock-supervisor/launchd/${PLIST_NAME}"
TARGET_DIR="${HOME}/Library/LaunchAgents"
TARGET_PLIST="${TARGET_DIR}/${PLIST_NAME}"

echo "=== [launchd] 미국 ETF 자금순환 월간 자동 스케줄러 등록 ==="

mkdir -p "${TARGET_DIR}"
mkdir -p "/Users/tothemoon/stock-supervisor/logs"

# 기존 서비스 언로드 (등록되어 있는 경우)
if launchctl list | grep -q "com.stock.monthly-sector-rotation"; then
    echo "• 기존 launchd 데몬 언로드 중..."
    launchctl unload "${TARGET_PLIST}" 2>/dev/null || true
fi

# plist 복사 및 권한 설정
cp "${SOURCE_PLIST}" "${TARGET_PLIST}"
chmod 644 "${TARGET_PLIST}"

# 신규 서비스 로드
echo "• 신규 launchd 데몬 로드 중..."
launchctl load "${TARGET_PLIST}"

# 등록 상태 확인
if launchctl list | grep -q "com.stock.monthly-sector-rotation"; then
    echo "✅ [성공] com.stock.monthly-sector-rotation 스케줄러가 정상 등록되었습니다."
    echo "• 실행 주기: 매월 1일 오전 08:30 KST"
    echo "• 로그 경로: /Users/tothemoon/stock-supervisor/logs/monthly_sector_rotation.log"
else
    echo "⚠️ [주의] launchctl 목록에 데몬이 즉시 나타나지 않았습니다. 상태를 재확인하세요."
fi
