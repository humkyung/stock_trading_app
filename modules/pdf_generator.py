# modules/pdf_generator.py

import datetime
import os
import shutil
from typing import Optional, Tuple

import markdown
import pdfkit
import streamlit as st


def _find_wkhtmltopdf() -> Optional[str]:
    """wkhtmltopdf 실행 파일 경로를 최대한 유연하게 찾는다."""
    # 1) 사용자가 명시적으로 지정한 경우
    for env_key in ("WKHTMLTOPDF_PATH", "WKHTMLTOPDF_BINARY", "WKHTMLTOPDF"):
        p = os.getenv(env_key)
        if p and os.path.exists(p):
            return p

    # 2) PATH에서 찾기
    p = shutil.which("wkhtmltopdf")
    if p:
        return p

    # 3) 흔한 설치 위치들 (리눅스/윈도우/맥)
    candidates = [
        "/usr/bin/wkhtmltopdf",
        "/usr/local/bin/wkhtmltopdf",
        "/app/.apt/usr/bin/wkhtmltopdf",  # Streamlit Cloud apt layer에서 흔히 쓰임
        "C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe",
        "C:\\Program Files (x86)\\wkhtmltopdf\\bin\\wkhtmltopdf.exe",
        "/opt/homebrew/bin/wkhtmltopdf",
        "/usr/local/opt/wkhtmltopdf/bin/wkhtmltopdf",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c

    return None


def _get_pdfkit_config() -> Optional[pdfkit.configuration]:
    wk = _find_wkhtmltopdf()
    if not wk:
        return None
    try:
        return pdfkit.configuration(wkhtmltopdf=wk)
    except Exception:
        return None


def create_journal_pdf_bytes(
    date, content: str, trades_data=None
) -> Tuple[Optional[bytes], str]:
    """
    매매 일지 내용을 받아 PDF 바이너리(bytes)로 생성합니다.

    Returns:
        (pdf_bytes, filename)
        - pdf_bytes: 성공 시 bytes, 실패 시 None
        - filename: 다운로드용 파일명
    """
    date_str = date.strftime("%Y-%m-%d")
    filename = f"{date_str}_journal.pdf"
    title = f"[{date_str}] 자동 매매 프로그램 복기 일지"

    # 1) Markdown → HTML
    # 코드블록/줄바꿈 호환을 위해 extensions를 약간 켬
    html_content = markdown.markdown(
        content or "",
        extensions=["fenced_code", "tables", "nl2br"],
        output_format="html5",
    )

    # 2) trades_data 테이블 (DataFrame 가정)
    trades_html = ""
    if trades_data is not None:
        try:
            trades_html = trades_data.to_html(index=False, border=0)
            trades_html = f"<h2>실제 매매 기록</h2>{trades_html}"
        except Exception:
            # DataFrame이 아니거나 to_html 불가하면 무시
            trades_html = ""

    # 3) HTML 템플릿
    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    html_template = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset=\"utf-8\">
  <title>{title}</title>
  <style>
    body {{ font-family: "Noto Sans CJK KR", "Noto Sans KR", "NanumGothic", "Nanum Gothic", Arial, sans-serif; line-height: 1.6; margin: 40px; }}
    h1 {{ color: #2C3E50; border-bottom: 2px solid #3498DB; padding-bottom: 10px; }}
    h2 {{ color: #34495E; margin-top: 28px; }}
    pre, code {{ background-color: #ECF0F1; padding: 4px 6px; border-radius: 3px; }}
    pre code {{ display: block; padding: 10px; white-space: pre-wrap; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
    thead th {{ background: #F2F5F7; }}
    th, td {{ border: 1px solid #BDC3C7; padding: 8px; text-align: left; font-size: 12px; }}
    .muted {{ color: #95A5A6; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <p class=\"muted\">작성일: {date_str}</p>

  <div style=\"margin-top: 20px;\">
    {html_content}
  </div>

  <div style=\"margin-top: 30px;\">
    {trades_html}
  </div>

  <p class=\"muted\" style=\"margin-top: 50px; text-align: right;\">
    생성일: {generated_at}
  </p>
</body>
</html>"""

    # 4) pdfkit 설정 (wkhtmltopdf 경로 포함)
    config = _get_pdfkit_config()
    if config is None:
        st.error(
            "wkhtmltopdf를 찾지 못해서 PDF를 생성할 수 없어.\n\n"
            "- 로컬: wkhtmltopdf 설치 후 PATH에 잡히게 하거나\n"
            "- 서버(Streamlit Cloud): packages.txt에 wkhtmltopdf를 추가하거나\n"
            "- 또는 환경변수 WKHTMLTOPDF_PATH 로 바이너리 경로를 지정해줘."
        )
        return None, filename

    # 5) PDF 생성 (output_path=False → bytes 반환)
    options = {
        "encoding": "UTF-8",
        "page-size": "A4",
        "margin-top": "12mm",
        "margin-right": "12mm",
        "margin-bottom": "12mm",
        "margin-left": "12mm",
        # Streamlit/리눅스에서 로컬 리소스 접근 이슈 방지용
        "enable-local-file-access": "",
    }

    try:
        pdf_bytes = pdfkit.from_string(
            html_template, False, options=options, configuration=config
        )
        return pdf_bytes, filename
    except Exception as e:
        st.error(f"PDF 생성 중 오류 발생: {e}")
        return None, filename


# main.py에서 쓰기 좋은 Streamlit 래퍼
def download_journal_pdf(date, content: str, trades_data=None):
    """PDF를 생성하고, 생성된 PDF를 Streamlit 다운로드 버튼으로 제공."""
    pdf_bytes, filename = create_journal_pdf_bytes(
        date, content, trades_data=trades_data
    )
    if not pdf_bytes:
        return

    st.download_button(
        label="PDF 파일 다운로드",
        data=pdf_bytes,
        file_name=filename,
        mime="application/pdf",
    )
