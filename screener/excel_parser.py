#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
screener/excel_parser.py
외부 라이브러리(openpyxl, pandas) 의존성 없는 순수 파이썬 .xlsx / .csv 파서
ZIP + XML 기반으로 엑셀 시트 데이터를 행/열 딕셔너리로 초고속 변환
"""

import os
import re
import csv
import glob
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


def _parse_xml_shared_strings(zf: zipfile.ZipFile) -> List[str]:
    """xl/sharedStrings.xml 파싱하여 문자열 테이블 추출"""
    strings = []
    if "xl/sharedStrings.xml" not in zf.namelist():
        return strings

    try:
        xml_content = zf.read("xl/sharedStrings.xml")
        root = ET.fromstring(xml_content)
        # 네임스페이스 제거 처리
        for elem in root.findall(".//{*}si"):
            # <t> 태그들을 합침
            texts = [t.text for t in elem.findall(".//{*}t") if t.text]
            strings.append("".join(texts))
    except Exception as e:
        print(f"⚠️ sharedStrings 파싱 경고: {e}")
    return strings


def _col_letter_to_index(col_str: str) -> int:
    """'A' -> 0, 'B' -> 1, 'AA' -> 26 변환"""
    num = 0
    for c in col_str:
        num = num * 26 + (ord(c.upper()) - ord('A') + 1)
    return num - 1


def read_xlsx_rows(filepath: str, sheet_index: int = 0) -> List[List[Any]]:
    """
    순수 표준 라이브러리로 .xlsx 파일의 특정 시트를 2차원 리스트(행 x 열)로 읽기
    """
    if not os.path.exists(filepath):
        return []

    rows = []
    with zipfile.ZipFile(filepath, 'r') as zf:
        shared_strings = _parse_xml_shared_strings(zf)

        # 첫 번째 워크시트 파일 탐색
        sheet_path = f"xl/worksheets/sheet{sheet_index + 1}.xml"
        if sheet_path not in zf.namelist():
            sheets = [n for n in zf.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")]
            if not sheets:
                return []
            sheet_path = sorted(sheets)[0]

        xml_content = zf.read(sheet_path)
        root = ET.fromstring(xml_content)

        for row_elem in root.findall(".//{*}row"):
            row_data = {}
            max_col = -1
            for c in row_elem.findall(".//{*}c"):
                ref = c.attrib.get('r', '')
                col_match = re.match(r'([A-Za-z]+)', ref)
                if not col_match:
                    continue
                col_idx = _col_letter_to_index(col_match.group(1))
                if col_idx > max_col:
                    max_col = col_idx

                cell_type = c.attrib.get('t', '')
                v_elem = c.find(".//{*}v")
                if v_elem is not None and v_elem.text is not None:
                    raw_val = v_elem.text
                    if cell_type == 's': # shared string
                        str_idx = int(raw_val)
                        val = shared_strings[str_idx] if str_idx < len(shared_strings) else raw_val
                    elif cell_type == 'b': # boolean
                        val = (raw_val == '1')
                    else:
                        # 숫자 또는 일반 텍스트
                        try:
                            if '.' in raw_val:
                                val = float(raw_val)
                            else:
                                val = int(raw_val)
                        except ValueError:
                            val = raw_val
                else:
                    # 인라인 문자열 <is><t>...</t></is>
                    t_elem = c.find(".//{*}t")
                    val = t_elem.text if t_elem is not None else ""

                row_data[col_idx] = val

            if max_col >= 0:
                row_list = [row_data.get(i, "") for i in range(max_col + 1)]
                rows.append(row_list)

    return rows


def read_csv_rows(filepath: str) -> List[List[Any]]:
    """CSV 파일 읽기 (UTF-8, CP949 자동 감지)"""
    for enc in ('utf-8-sig', 'cp949', 'euc-kr', 'utf-8'):
        try:
            with open(filepath, 'r', encoding=enc) as f:
                reader = csv.reader(f)
                return list(reader)
        except (UnicodeDecodeError, Exception):
            continue
    return []


def clean_header_name(name: str) -> str:
    """헤더 정규화: 소문자화, 공백 및 특수문자 제거"""
    if not isinstance(name, str):
        name = str(name)
    s = re.sub(r'[\s\(\)\[\]\_\-\/\%\,\.]', '', name.lower())
    return s


# 주요 필드별 매핑 패턴
FIELD_PATTERNS = {
    "name": [r"종목명", r"기업명", r"회사명", r"^종목$", r"name", r"itemname"],
    "code": [r"종목코드", r"코드", r"^code$", r"^ticker$", r"symbol"],
    "market_cap": [r"시가총액", r"시총", r"marketcap", r"marcap"],
    "price": [r"현재가", r"종가", r"^주가$", r"^price$", r"^close$"],
    "sales_growth_27": [r"27.*매출.*증감", r"27.*매출.*증가", r"2027.*매출.*증감", r"2027.*sales.*growth", r"27e.*매출"],
    "op_growth_27": [r"27.*영업.*증감", r"27.*영업.*증가", r"2027.*영업.*증감", r"2027.*op.*growth", r"27e.*영업"],
    "roe_26": [r"26.*roe", r"2026.*roe", r"26e.*roe", r"roe.*26"],
    "eps_chg_1m": [r"eps.*1m", r"eps.*1개월", r"1m.*eps"],
    "eps_chg_3m": [r"eps.*3m", r"eps.*3개월", r"3m.*eps"],
    "vol_change_rate": [r"거래량.*52.*5.*변화", r"52.*5.*변화", r"거래량변화율", r"vol.*change"],
    "vol_52w": [r"52주.*거래량", r"52w.*vol"],
    "vol_5d": [r"5일.*거래량", r"5d.*vol"],
    "foreign_net_buy_20d": [r"외국인.*20일", r"외인.*20일", r"외국인.*순매수.*20", r"foreign.*20d"],
    "trailing_pb": [r"트레일링.*p\/?b", r"트레일링.*pbr", r"trailing.*pb", r"^pb$", r"^pbr$"]
}


def match_column_indices(header_row: List[Any]) -> Dict[str, int]:
    """헤더 행에서 필드별 열 인덱스를 자동 매칭"""
    mapping = {}
    cleaned_headers = [clean_header_name(h) for h in header_row]

    for field, patterns in FIELD_PATTERNS.items():
        for idx, h_clean in enumerate(cleaned_headers):
            for pat in patterns:
                pat_clean = clean_header_name(pat)
                if re.search(pat_clean, h_clean):
                    if field not in mapping:
                        mapping[field] = idx
                        break
            if field in mapping:
                break

    return mapping


def parse_screener_file(filepath: str) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    엑셀 또는 CSV 파일을 파싱하여 정형화된 행 딕셔너리 리스트 반환
    """
    if filepath.endswith('.xlsx'):
        rows = read_xlsx_rows(filepath)
    elif filepath.endswith('.csv'):
        rows = read_csv_rows(filepath)
    else:
        return [], {}

    if not rows or len(rows) < 2:
        return [], {}

    # 헤더 행 찾기 (상위 5행 중 문자열이 가장 많은 행)
    header_idx = 0
    max_strings = 0
    for i, r in enumerate(rows[:5]):
        str_count = sum(1 for c in r if isinstance(c, str) and len(c.strip()) > 0)
        if str_count > max_strings:
            max_strings = str_count
            header_idx = i

    header_row = rows[header_idx]
    mapping = match_column_indices(header_row)

    results = []
    for row in rows[header_idx + 1:]:
        if not any(row):
            continue

        item = {}
        for field, col_idx in mapping.items():
            if col_idx < len(row):
                val = row[col_idx]
                item[field] = val
            else:
                item[field] = None

        # 원본 행 전체도 보관
        item["_raw_row"] = row
        results.append(item)

    return results, mapping


def find_latest_screener_file(search_dirs: Optional[List[str]] = None) -> Optional[str]:
    """
    지정 디렉토리들(기본: data/screener, ~/Downloads)에서 최신 스크리너 파일 탐색
    """
    if search_dirs is None:
        base_dir = Path(__file__).resolve().parent.parent
        search_dirs = [
            str(base_dir / "data" / "screener"),
            os.path.expanduser("~/Downloads")
        ]

    candidate_files = []
    patterns = ["*.xlsx", "*.xls", "*.csv"]

    for d in search_dirs:
        if not os.path.exists(d):
            continue
        for p in patterns:
            for f in glob.glob(os.path.join(d, p)):
                # 임시 파일이나 lock 파일 제외
                if "~$" in os.path.basename(f) or os.path.basename(f).startswith('.'):
                    continue
                mtime = os.path.getmtime(f)
                candidate_files.append((mtime, f))

    if not candidate_files:
        return None

    # 가장 최근 수정된 파일 반환
    candidate_files.sort(key=lambda x: x[0], reverse=True)
    return candidate_files[0][1]
