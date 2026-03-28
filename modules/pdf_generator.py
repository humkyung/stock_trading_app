# modules/pdf_generator.py

import datetime
import os
import re
from typing import Optional, Tuple

import streamlit as st
from fpdf import FPDF


def _find_korean_font() -> Optional[str]:
    """시스템에서 한글 폰트 파일을 찾는다."""
    candidates = [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "C:\\Windows\\Fonts\\malgun.ttf",
        "C:\\Windows\\Fonts\\NanumGothic.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def _strip_html_tags(text: str) -> str:
    """HTML 태그를 제거하고 일부 엔티티를 변환한다."""
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"</(p|div|h[1-6]|li|tr)>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&nbsp;", " ")
    text = text.replace("&quot;", '"')
    # 연속 빈 줄 정리
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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
    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    try:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # 한글 폰트 설정
        font_path = _find_korean_font()
        if font_path:
            pdf.add_font("Korean", "", font_path, uni=True)
            font_name = "Korean"
        else:
            font_name = "Helvetica"

        # 제목
        pdf.set_font(font_name, size=16)
        pdf.set_text_color(44, 62, 80)
        pdf.cell(0, 12, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(52, 152, 219)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(4)

        # 작성일
        pdf.set_font(font_name, size=9)
        pdf.set_text_color(149, 165, 166)
        pdf.cell(0, 8, f"작성일: {date_str}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        # 본문 (Markdown → plain text)
        import markdown

        html_content = markdown.markdown(
            content or "",
            extensions=["fenced_code", "tables", "nl2br"],
            output_format="html5",
        )
        plain_text = _strip_html_tags(html_content)

        pdf.set_font(font_name, size=10)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 6, plain_text)

        # 매매 기록 테이블
        if trades_data is not None:
            try:
                pdf.ln(8)
                pdf.set_font(font_name, size=13)
                pdf.set_text_color(52, 73, 94)
                pdf.cell(
                    0, 10, "실제 매매 기록", new_x="LMARGIN", new_y="NEXT"
                )
                pdf.ln(2)

                columns = list(trades_data.columns)
                col_count = len(columns)
                col_width = (pdf.w - 20) / col_count if col_count else 40

                # 헤더
                pdf.set_font(font_name, size=8)
                pdf.set_fill_color(242, 245, 247)
                pdf.set_text_color(0, 0, 0)
                for col in columns:
                    pdf.cell(col_width, 7, str(col), border=1, fill=True)
                pdf.ln()

                # 데이터
                pdf.set_font(font_name, size=8)
                for _, row in trades_data.iterrows():
                    for col in columns:
                        pdf.cell(
                            col_width, 6, str(row[col])[:20], border=1
                        )
                    pdf.ln()
            except Exception:
                pass

        # 생성일 (우측 하단)
        pdf.ln(10)
        pdf.set_font(font_name, size=9)
        pdf.set_text_color(149, 165, 166)
        pdf.cell(0, 8, f"생성일: {generated_at}", align="R")

        pdf_bytes = pdf.output()
        return bytes(pdf_bytes), filename
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
