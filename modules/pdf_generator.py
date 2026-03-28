# modules/pdf_generator.py

import datetime
import io
from typing import Optional, Tuple

import markdown
import streamlit as st
from xhtml2pdf import pisa


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
            trades_html = ""

    # 3) HTML 템플릿
    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    html_template = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    @font-face {{
      font-family: "NotoSansCJK";
      src: url("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc");
    }}
    @font-face {{
      font-family: "NanumGothic";
      src: url("/usr/share/fonts/truetype/nanum/NanumGothic.ttf");
    }}
    body {{ font-family: "NanumGothic", "NotoSansCJK", sans-serif; line-height: 1.6; margin: 40px; }}
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
  <p class="muted">작성일: {date_str}</p>

  <div style="margin-top: 20px;">
    {html_content}
  </div>

  <div style="margin-top: 30px;">
    {trades_html}
  </div>

  <p class="muted" style="margin-top: 50px; text-align: right;">
    생성일: {generated_at}
  </p>
</body>
</html>"""

    # 4) xhtml2pdf로 PDF 생성
    try:
        result = io.BytesIO()
        pisa_status = pisa.CreatePDF(io.StringIO(html_template), dest=result)
        if pisa_status.err:
            st.error("PDF 생성 중 오류가 발생했습니다.")
            return None, filename
        return result.getvalue(), filename
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
