from __future__ import annotations

import subprocess
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Mm, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ASSETS = DOCS / "final_report_assets"
OUTPUT = DOCS / "OLLY_최종_보고서.docx"

FONT_KO = "맑은 고딕"
FONT_LATIN = "Arial"
FONT_MONO = "Consolas"


def run_text(command: list[str], timeout: int = 8) -> str:
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except Exception as exc:
        return f"(명령 실행 실패: {exc})"
    return result.stdout.strip() or "(출력 없음)"


def set_run_font(run, size: int | None = None, bold: bool | None = None, color: str | None = None) -> None:
    run.font.name = FONT_LATIN
    run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_KO)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_cell_text(cell, text: str, bold: bool = False, color: str | None = None) -> None:
    cell.text = ""
    paragraph = cell.paragraphs[0]
    run = paragraph.add_run(text)
    set_run_font(run, 9, bold, color)


def configure_document(doc: Document) -> None:
    section = doc.sections[0]
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.top_margin = Mm(18)
    section.bottom_margin = Mm(18)
    section.left_margin = Mm(18)
    section.right_margin = Mm(18)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = FONT_LATIN
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_KO)
    normal.font.size = Pt(10.5)

    for name, size, color in [
        ("Title", 24, "111827"),
        ("Heading 1", 17, "111827"),
        ("Heading 2", 14, "1F2937"),
        ("Heading 3", 12, "374151"),
    ]:
        style = styles[name]
        style.font.name = FONT_LATIN
        style._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_KO)
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)

    if "Code Block" not in styles:
        code = styles.add_style("Code Block", 1)
        code.font.name = FONT_MONO
        code._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_MONO)
        code.font.size = Pt(8.5)

    if "Report Caption" not in styles:
        caption = styles.add_style("Report Caption", 1)
        caption.font.name = FONT_LATIN
        caption._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_KO)
        caption.font.size = Pt(8.5)
        caption.font.italic = True
        caption.font.color.rgb = RGBColor.from_string("4B5563")


def add_paragraph(doc: Document, text: str = "", bold_prefix: str | None = None) -> None:
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(4)
    if bold_prefix and text.startswith(bold_prefix):
        run = paragraph.add_run(bold_prefix)
        set_run_font(run, 10, True)
        tail = paragraph.add_run(text[len(bold_prefix):])
        set_run_font(tail, 10)
    else:
        run = paragraph.add_run(text)
        set_run_font(run, 10)


def add_bullets(doc: Document, items: list[str]) -> None:
    for item in items:
        paragraph = doc.add_paragraph(style="List Bullet")
        paragraph.paragraph_format.space_after = Pt(2)
        run = paragraph.add_run(item)
        set_run_font(run, 10)


def add_numbered(doc: Document, items: list[str]) -> None:
    for item in items:
        paragraph = doc.add_paragraph(style="List Number")
        paragraph.paragraph_format.space_after = Pt(2)
        run = paragraph.add_run(item)
        set_run_font(run, 10)


def add_code_block(doc: Document, text: str) -> None:
    table = doc.add_table(rows=1, cols=1)
    table.style = "Table Grid"
    cell = table.cell(0, 0)
    set_cell_shading(cell, "F3F4F6")
    cell.text = ""
    for idx, line in enumerate(text.strip().splitlines()):
        paragraph = cell.paragraphs[0] if idx == 0 else cell.add_paragraph()
        paragraph.style = "Code Block"
        paragraph.paragraph_format.space_after = Pt(0)
        run = paragraph.add_run(line)
        run.font.name = FONT_MONO
        run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_MONO)
        run.font.size = Pt(8.5)
    doc.add_paragraph()


def add_caption(doc: Document, text: str) -> None:
    paragraph = doc.add_paragraph(style="Report Caption")
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(text)
    set_run_font(run, 8, False, "4B5563")


def add_image(doc: Document, filename: str, caption: str, width_inches: float = 6.5) -> None:
    path = ASSETS / filename
    if not path.exists():
        add_code_block(doc, f"[캡쳐 파일 없음] {path}")
        return
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    run.add_picture(str(path), width=Inches(width_inches))
    add_caption(doc, caption)


def add_table(doc: Document, headers: list[str], rows: list[list[str]], widths: list[float] | None = None) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    header_cells = table.rows[0].cells
    for idx, header in enumerate(headers):
        set_cell_shading(header_cells[idx], "E5E7EB")
        set_cell_text(header_cells[idx], header, bold=True)
        if widths:
            header_cells[idx].width = Inches(widths[idx])
    for row in rows:
        cells = table.add_row().cells
        for idx, value in enumerate(row):
            set_cell_text(cells[idx], value)
            if widths:
                cells[idx].width = Inches(widths[idx])
    doc.add_paragraph()


def add_toc(doc: Document) -> None:
    paragraph = doc.add_paragraph()
    run = paragraph.add_run()
    fld_char = OxmlElement("w:fldChar")
    fld_char.set(qn("w:fldCharType"), "begin")
    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = 'TOC \\o "1-3" \\h \\z \\u'
    fld_char2 = OxmlElement("w:fldChar")
    fld_char2.set(qn("w:fldCharType"), "separate")
    fld_char3 = OxmlElement("w:fldChar")
    fld_char3.set(qn("w:fldCharType"), "end")
    run._r.append(fld_char)
    run._r.append(instr_text)
    run._r.append(fld_char2)
    run._r.append(fld_char3)
    note = doc.add_paragraph()
    note_run = note.add_run("※ Word에서 문서를 열고 목차를 선택한 뒤 '필드 업데이트'를 누르면 페이지 번호가 자동 갱신됩니다.")
    set_run_font(note_run, 9, False, "6B7280")


def add_title_page(doc: Document) -> None:
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_before = Pt(110)
    title_run = title.add_run("OLLY 최종 보고서")
    set_run_font(title_run, 26, True, "111827")

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle_run = subtitle.add_run("실무형 LLM 서비스 관측성 플랫폼 MVP")
    set_run_font(subtitle_run, 15, True, "4F46E5")

    summary = doc.add_paragraph()
    summary.alignment = WD_ALIGN_PARAGRAPH.CENTER
    summary.paragraph_format.space_before = Pt(20)
    run = summary.add_run("Kubernetes, OpenTelemetry, Prometheus, Jaeger 기반 운영 관측성 구현")
    set_run_font(run, 11, False, "374151")

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.paragraph_format.space_before = Pt(90)
    meta_run = meta.add_run("오픈소스분석(클라우드) | 5조")
    set_run_font(meta_run, 11, False, "111827")
    doc.add_page_break()


def add_overview_box(doc: Document) -> None:
    add_table(
        doc,
        ["구분", "내용"],
        [
            ["프로젝트명", "OLLY"],
            ["핵심 목표", "LLM 요청의 비용, 토큰, 지연, 병목, 실패, 알림 원인을 데이터 기반으로 관측"],
            ["현재 MVP 대상", "Ollama gemma3:1b 기반 로컬 SLM 샘플 서비스"],
            ["실무 적용 방향", "사용자용 LLM/RAG 챗봇 서비스의 /chat API에 OLLY 계측을 연결"],
            ["실무성 기준", "기존 서비스 교체 없이 계측 추가, 표준 도구 기반 운영, 알림과 추적 자동화, 프롬프트 보안 고려"],
            ["CNCF 적용", "Kubernetes, OpenTelemetry, Prometheus, Jaeger"],
        ],
        [1.6, 4.8],
    )


def main() -> None:
    doc = Document()
    configure_document(doc)

    health = run_text(["curl", "-sS", "--max-time", "5", "http://localhost:8001/health"])
    k8s_status = run_text(["kubectl", "-n", "olly", "get", "pods,svc,pvc,job"], timeout=12)

    add_title_page(doc)
    doc.add_heading("문서 목차", level=1)
    add_toc(doc)
    doc.add_page_break()

    doc.add_heading("1. 서론", level=1)
    add_paragraph(
        doc,
        "LLM 기반 서비스는 일반적인 웹 API보다 운영 원인을 파악하기 어렵다. 같은 /chat API를 호출하더라도 "
        "프롬프트 길이, 검색 문맥, 모델 종류, 출력 길이에 따라 비용과 응답 시간이 크게 달라진다. 사용자는 "
        "답변이 느리거나 실패했다는 결과만 경험하지만, 운영자는 검색 단계, 모델 호출 단계, 후처리 단계 중 어디에서 "
        "문제가 발생했는지 별도로 추적해야 한다.",
    )
    add_paragraph(
        doc,
        "OLLY는 이러한 운영 문제를 해결하기 위해 LLM 요청을 request_id와 trace_id 중심으로 연결하고, 비용, 토큰, "
        "latency, 단계별 병목, 실패, 알림을 한 화면에서 확인할 수 있도록 구현한 관측성 MVP이다. 본 프로젝트는 "
        "상용 LLM 서비스를 그대로 구축한 것이 아니라, 로컬 SLM 기반 샘플 서비스를 대상으로 관측성 구조를 구현하고 "
        "실제 LLM/RAG 챗봇 서비스에 적용 가능한 형태로 확장 가능성을 검증한 결과물이다. 특히 실무 환경에서 요구되는 "
        "표준 계측, 장애 추적, 비용 관리, 알림, 보안 고려를 MVP 범위 안에서 확인할 수 있도록 설계했다.",
    )
    add_overview_box(doc)

    doc.add_heading("2. 프로젝트 목표와 적용 범위", level=1)
    doc.add_heading("2.1 관측 대상의 정의", level=2)
    add_paragraph(
        doc,
        "본 보고서에서 LLM 서비스는 사용자의 자연어 요청을 받아 모델 호출 또는 RAG 검색을 거쳐 답변을 반환하는 서비스를 의미한다. "
        "Claude, Gemini, OpenAI 같은 외부 LLM API를 사용하는 서비스, 내부 문서 검색을 결합한 RAG 챗봇, Ollama 기반 "
        "로컬 SLM 서비스가 모두 이 범주에 포함된다.",
    )
    add_bullets(
        doc,
        [
            "외부 LLM API형 서비스: 모델 제공사의 API를 호출하고 토큰 기반 비용이 발생한다.",
            "RAG 기반 챗봇형 서비스: 검색 단계와 모델 생성 단계가 분리되므로 단계별 병목 분석이 중요하다.",
            "로컬 SLM형 서비스: API 과금은 없지만 CPU/GPU 실행 시간과 인프라 비용이 주요 관측 대상이 된다.",
        ],
    )
    doc.add_heading("2.2 MVP 구현 범위", level=2)
    add_paragraph(
        doc,
        "현재 구현은 비용과 재현성을 고려하여 Ollama gemma3:1b를 사용하는 FastAPI 샘플 서비스를 관측 대상으로 삼았다. "
        "사용자 챗봇 UI는 이 샘플 서비스에 질문을 보내고, 운영자 대시보드와 분석 챗봇은 Prometheus와 Jaeger에 쌓인 "
        "관측 데이터를 조회한다. 따라서 현재 OLLY는 로컬 SLM 기반 샘플 서비스를 관측하는 독립 실행형 MVP이며, "
        "운영자 분석 챗봇은 관측 대상 자체가 아니라 관측 결과를 해석하는 인터페이스이다.",
    )
    doc.add_heading("2.3 실무 적용 방향", level=2)
    add_paragraph(
        doc,
        "실무에서 OLLY는 사용자용 챗봇 서비스를 대체하지 않고, 기존 LLM/RAG 챗봇 API에 연결되는 관측성 계층으로 동작한다. "
        "서비스 코드에 OpenTelemetry 계측과 metric 기록을 추가하면 OLLY 대시보드가 해당 요청의 request_id, trace_id, "
        "모델, 토큰, 비용, latency, 단계별 duration, alert를 조회한다.",
    )
    add_code_block(
        doc,
        """
사용자용 LLM/RAG 챗봇
  -> /chat API
  -> retrieve 또는 tool call
  -> llm_call
  -> postprocess

OLLY 관측 계층
  -> OpenTelemetry trace
  -> Prometheus metric
  -> Jaeger trace detail
  -> 운영자 대시보드 / 분석 챗봇
        """,
    )
    doc.add_heading("2.4 실무 적용성을 고려한 설계 원칙", level=2)
    add_paragraph(
        doc,
        "OLLY의 실무 적용성은 새로운 챗봇을 별도로 만드는 데 있지 않고, 이미 운영 중인 사용자용 LLM/RAG 서비스에 관측성 계층을 "
        "덧붙일 수 있다는 점에 있다. 따라서 구현에서는 특정 벤더의 전용 기능보다 OpenTelemetry, Prometheus, Jaeger처럼 "
        "운영 현장에서 널리 쓰이는 표준 도구와 인터페이스를 우선하였다.",
    )
    add_bullets(
        doc,
        [
            "기존 서비스 침투 최소화: /chat API의 핵심 로직은 유지하고 trace와 metric 기록을 추가하는 구조로 설계했다.",
            "운영자 워크플로우 반영: KPI 확인, request_id 조회, trace 분석, alert 확인, Discord 알림까지 장애 대응 흐름을 연결했다.",
            "벤더 종속성 완화: 외부 LLM API, RAG 챗봇, 로컬 SLM 모두 같은 관측 모델로 수집할 수 있게 했다.",
            "보안과 개인정보 고려: raw prompt 저장보다 template id, token count, 익명화된 식별자 중심의 관측을 권장한다.",
            "확장 가능한 배포 단위: Docker Compose와 Kubernetes manifest를 모두 제공해 로컬 검증과 클러스터 배포를 구분했다.",
        ],
    )
    doc.add_heading("2.5 관측 범위의 기준", level=2)
    add_paragraph(
        doc,
        "본 프로젝트는 프롬프트 내용과 모델 응답의 의미적 품질을 모두 자동 판정하는 시스템이 아니라, 운영자가 비용과 성능 문제를 "
        "재현 가능한 데이터로 추적하게 하는 operational observability에 초점을 맞추었다. 프롬프트 관측은 OpenTelemetry가 "
        "자동으로 제공하는 기능이 아니라 서비스 코드에서 남길 정보를 결정해야 하는 계측 설계 문제로 정의하였다.",
    )
    add_bullets(
        doc,
        [
            "동일한 /chat API라도 request_id, trace_id, feature, prompt_template_id, token count, latency를 함께 남기면 요청별 차이를 비교할 수 있다.",
            "개인정보 보호를 위해 raw prompt 전체 저장보다 prompt template id, prompt length, token count, 익명화된 user/org id 저장을 우선한다.",
            "할루시네이션 자동 검출은 이번 MVP에서 구현하지 않았으며, 향후 semantic quality monitoring 영역으로 분리한다.",
        ],
    )

    doc.add_heading("3. 시스템 아키텍처", level=1)
    doc.add_heading("3.1 요청 처리 흐름", level=2)
    add_code_block(
        doc,
        """
Chat UI
  -> FastAPI /chat
     -> retrieve
     -> llm_call
     -> postprocess
  -> Ollama gemma3:1b
  -> 사용자에게 답변 반환
        """,
    )
    doc.add_heading("3.2 관측성 데이터 흐름", level=2)
    add_code_block(
        doc,
        """
FastAPI
  -> OpenTelemetry SDK
  -> OpenTelemetry Collector
     -> Prometheus: 요청 수, 토큰, 비용, latency, error, stage duration
     -> Jaeger: POST /chat trace와 retrieve/llm_call/postprocess span
        """,
    )
    doc.add_heading("3.3 운영 분석 흐름", level=2)
    add_code_block(
        doc,
        """
운영 질문
  -> analysis_intents.py: 질문 의도, 기간, request_id, trace_id 파싱
  -> analysis.py: 답변 생성 orchestration
  -> Prometheus / Jaeger 조회
  -> 근거 수치가 포함된 한국어 운영 답변 반환
        """,
    )
    add_image(doc, "15_architecture_overview.png", "그림 1. OLLY 전체 아키텍처: 사용자 요청 처리, 관측성 수집, 운영 분석과 알림 흐름", 6.8)
    add_image(doc, "16_user_flow.png", "그림 2. OLLY 시연 및 운영자 분석 플로우: request_id와 trace_id 기반 추적 흐름", 6.8)
    add_paragraph(
        doc,
        "전체 구조는 데모 화면 중심이 아니라 운영 환경에서 필요한 역할 분리를 기준으로 구성했다. 사용자 요청 처리 경로와 관측 데이터 "
        "수집 경로를 분리하고, 운영자 화면은 Prometheus와 Jaeger에 저장된 데이터를 조회하는 소비자로 두었다. 이 방식은 실제 서비스에 "
        "OLLY를 붙일 때도 애플리케이션 코드, 관측 파이프라인, 운영 화면을 독립적으로 교체하거나 확장할 수 있게 한다.",
    )
    add_image(doc, "01_chat_ui.png", "그림 3. 사용자/운영자 챗봇 UI: 질문, 응답, request metadata를 확인하는 화면")
    add_image(doc, "02_dashboard.png", "그림 4. OLLY 운영자 대시보드: KPI, 최근 요청, 병목 단계, 알림 상태를 통합 표시")

    doc.add_heading("4. 핵심 기능 구현", level=1)
    doc.add_heading("4.1 사용자 챗봇 UI", level=2)
    add_paragraph(
        doc,
        "사용자는 /chat-ui에서 질문을 입력한다. 응답에는 answer뿐 아니라 request_id, trace_id, latency, input/output token, "
        "cost, model, status가 함께 표시된다. 이 metadata가 운영자 대시보드와 Jaeger trace를 연결하는 핵심 식별자이다.",
    )
    add_image(doc, "06_chat_quick_question_selected.png", "그림 5. 빠른 질문 선택: 자주 묻는 운영 질문을 클릭해 입력창에 바로 채우는 화면")
    add_image(doc, "07_chat_quick_status_summary.png", "그림 6. 빠른 질문 응답: 상태 요약 답변과 request_id, trace_id, latency, token, cost metadata")
    doc.add_heading("4.2 운영자 대시보드", level=2)
    add_paragraph(
        doc,
        "대시보드는 Prometheus와 Jaeger 데이터를 조합해 평균 latency, p95 latency, total tokens, total cost, success rate, "
        "최근 요청, 단계별 병목, 활성 알림을 보여준다. Recent Requests, Trace Detail, Signals, Alerts 영역을 통해 "
        "요청 단위 추적과 전체 지표 추세를 함께 확인할 수 있다.",
    )
    add_image(doc, "13_dashboard_traces.png", "그림 7. 요청 추적 화면: request_id와 trace_id 기준으로 최근 요청과 단계별 병목을 확인")
    add_image(doc, "12_dashboard_signals.png", "그림 8. 실시간 지표 화면: Grafana 패널로 p95 latency, token trend, cost, stage p95를 확인")
    doc.add_heading("4.3 분석 챗봇", level=2)
    add_paragraph(
        doc,
        "분석 챗봇은 단순 LLM 답변이 아니라 운영 질문을 분류한 뒤 Prometheus와 Jaeger 데이터를 조회해 답변한다. "
        "예를 들어 검색 단계와 모델 호출 단계 중 어느 구간이 느린지 묻는 질문에 대해 retrieve p95와 llm_call p95를 "
        "비교해 근거를 제시한다.",
    )
    doc.add_heading("4.4 비용, 토큰, 병목 분석", level=2)
    add_paragraph(
        doc,
        "OLLY는 요청별 비용과 토큰 사용량을 metric으로 저장하고, feature와 scenario 단위로 집계할 수 있게 했다. "
        "또한 retrieve, llm_call, postprocess span을 분리하여 전체 응답 시간이 길어진 경우 어느 단계가 원인인지 확인한다. "
        "이 구조는 RAG 검색 지연과 모델 생성 지연을 구분하는 데 핵심적인 역할을 한다.",
    )
    doc.add_heading("4.5 알림", level=2)
    add_paragraph(
        doc,
        "Prometheus alert rule로 p95 latency, error rate, token usage spike, retrieve slow, local inference cost spike를 감시한다. "
        "또한 운영자가 직접 metric, 조건, 임계값, 평가 window, cooldown, Discord webhook을 설정하는 커스텀 알림 기능을 구현했다.",
    )
    add_paragraph(
        doc,
        "실무에서는 장애가 발생한 뒤 대시보드를 수동으로 확인하는 것만으로는 대응이 늦다. OLLY는 임계값 기반 알림과 LLM 한 줄 요약을 "
        "함께 제공해 운영자가 어떤 지표가 왜 문제가 되었는지 빠르게 파악하도록 설계했다.",
    )
    add_image(doc, "14_dashboard_alert_rules.png", "그림 9. 알림 관리 화면: 커스텀 알림 규칙, Discord webhook, 최근 발화 이력")

    doc.add_heading("5. CNCF 기반 관측성 구성", level=1)
    add_paragraph(
        doc,
        "과제의 핵심 요구사항인 CNCF 적용은 Kubernetes, OpenTelemetry, Prometheus, Jaeger 중심으로 충족했다. Grafana는 CNCF 핵심 적용 "
        "항목으로 분류하지 않고 Prometheus 시각화 보조 도구로 설명한다.",
    )
    add_image(doc, "17_observability_pipeline.png", "그림 10. CNCF 관측성 파이프라인: OpenTelemetry 수집, Prometheus metric, Jaeger trace 분석", 6.8)
    add_table(
        doc,
        ["CNCF 도구", "프로젝트 내 역할", "구현 근거", "효과"],
        [
            ["Kubernetes", "kind 기반 로컬 클러스터 실행", "Deployment, Service, PVC, Job, ConfigMap, NodePort", "서비스 단위 배포와 재현 가능한 실행 환경"],
            ["OpenTelemetry", "애플리케이션 계측 표준", "FastAPI, retrieve, llm_call, postprocess span 생성", "요청 흐름을 vendor-neutral 방식으로 추적"],
            ["Prometheus", "metric 저장과 PromQL 분석", "requests, tokens, cost, latency, errors, alert rules", "운영 지표 집계와 알림"],
            ["Jaeger", "분산 trace 시각화", "POST /chat trace와 단계별 span 확인", "요청 하나의 병목 위치를 확인"],
        ],
        [1.25, 1.7, 2.1, 1.7],
    )
    add_paragraph(
        doc,
        "이 조합은 실무 운영 환경에서도 설명 가능하다. OpenTelemetry는 애플리케이션 계측을 표준화하고, Prometheus는 metric과 alert "
        "운영을 담당하며, Jaeger는 요청 단위 원인 분석을 지원한다. OLLY가 특정 클라우드나 LLM 벤더의 전용 기능에 의존하지 않도록 "
        "구성한 이유도 실제 서비스에 적용할 때 교체 비용과 종속성을 줄이기 위해서이다.",
    )
    add_image(doc, "03_jaeger_trace.png", "그림 11. Jaeger trace: POST /chat 요청 안에서 retrieve, llm_call span을 확인")
    add_image(doc, "04_prometheus_alerts.png", "그림 12. Prometheus alerts: OLLY MVP alert rule 상태 확인")

    doc.add_heading("6. Docker 및 Kubernetes 배포", level=1)
    add_image(doc, "18_kubernetes_deployment.png", "그림 13. Kubernetes(kind) 배포 구조: namespace, Deployment, Service, PVC, Job, NodePort 연결", 6.8)
    doc.add_heading("6.1 Docker Compose", level=2)
    add_paragraph(
        doc,
        "Docker Compose는 로컬 데모용 실행 환경이다. sample-llm-api, ollama, otel-collector, jaeger, prometheus, grafana를 "
        "함께 실행하며, 첫 실행 시 ollama-pull-gemma 컨테이너가 gemma3:1b 모델을 내려받는다.",
    )
    add_code_block(
        doc,
        """
docker compose -f deploy/docker-compose.yml up -d --build
curl http://localhost:8001/health
        """,
    )
    doc.add_heading("6.2 Kubernetes(kind)", level=2)
    add_paragraph(
        doc,
        "Kubernetes 배포는 kind 기반 로컬 클러스터에서 검증했다. Namespace, PVC, Deployment, Service, Job, ConfigMap을 사용하며, "
        "NodePort와 kind extraPortMappings를 통해 localhost에서 각 도구에 접근한다.",
    )
    add_paragraph(
        doc,
        "kind와 NodePort는 과제 환경에서 재현성을 확보하기 위한 선택이다. 실무 환경으로 확장할 때는 동일한 Deployment와 Service 구조를 "
        "기반으로 Ingress, TLS, Secret, 외부 저장소, 장기 metric 보관, 접근 권한 제어를 추가하는 방식으로 발전시킬 수 있다.",
    )
    add_code_block(doc, "cd k8s\nmake up\nmake status")
    add_paragraph(doc, "검증 시점의 /health 응답은 다음과 같다.")
    add_code_block(doc, health)
    add_paragraph(doc, "Kubernetes 리소스 상태는 다음과 같다.")
    add_code_block(doc, k8s_status)

    doc.add_heading("7. 시연 및 검증 결과", level=1)
    add_paragraph(
        doc,
        "검증은 normal, slow_retrieve, slow_llm, high_token, error 시나리오를 기준으로 수행했다. 시연은 하나의 사용자 요청이 "
        "생성된 뒤 동일한 request_id와 trace_id로 대시보드, Jaeger, Prometheus 지표까지 연결되는 과정을 확인하는 방식으로 구성했다. "
        "각 시나리오에서는 Chat UI 응답 metadata, Dashboard의 요청 상세, Jaeger span, Prometheus/Grafana 지표가 같은 요청을 "
        "설명하는지 확인하였다.",
    )
    doc.add_heading("7.1 정상 요청 및 운영 요약", level=2)
    add_paragraph(
        doc,
        "정상 요청에서는 answer와 metadata가 함께 생성되는지 확인했다. 운영 요약 질문은 현재 지표를 기반으로 상태를 설명하며, "
        "request_id와 trace_id가 이후 대시보드 분석의 기준이 된다.",
    )
    doc.add_heading("7.2 검색 지연 시나리오", level=2)
    add_paragraph(
        doc,
        "slow_retrieve 시나리오는 RAG 검색 또는 retrieve 단계의 지연을 가정한다. 대시보드의 stage p95와 Jaeger span을 통해 "
        "모델 생성 자체가 아니라 검색 단계가 병목 후보임을 확인할 수 있다.",
    )
    add_image(doc, "08_chat_slow_retrieve_response.png", "그림 14. RAG/검색 지연 시나리오: retrieve와 llm_call 중 병목 후보를 설명하는 채팅 화면")
    doc.add_heading("7.3 모델 응답 지연 시나리오", level=2)
    add_paragraph(
        doc,
        "slow_llm 시나리오는 llm_call 단계의 지연을 가정한다. 동일한 요청 추적 방식으로 모델 호출 시간이 전체 응답 시간에 "
        "어떤 영향을 주는지 확인한다.",
    )
    add_image(doc, "09_chat_slow_llm_response.png", "그림 15. 모델 응답 지연 시나리오: llm_call 지연과 모델 실행 리소스 점검 포인트")
    doc.add_heading("7.4 토큰 과다 사용 시나리오", level=2)
    add_paragraph(
        doc,
        "high_token 시나리오는 입력 또는 출력 토큰이 증가할 때 비용 지표가 함께 증가하는지 검증한다. 이는 외부 LLM API를 사용하는 "
        "실무 서비스에서 기능별 비용 원인을 설명하는 데 필요한 지표이다.",
    )
    add_image(doc, "10_chat_high_token_response.png", "그림 16. 토큰 과다 사용 시나리오: 토큰 사용량과 비용 증가 관계를 설명하는 화면")
    doc.add_heading("7.5 실패 요청 시나리오", level=2)
    add_paragraph(
        doc,
        "error 시나리오는 실패 요청이 metric과 trace에 남는지 확인한다. 운영자는 실패 응답의 request_id와 trace_id를 기준으로 "
        "대시보드와 Jaeger에서 원인을 추적할 수 있다.",
    )
    add_image(doc, "11_chat_error_response.png", "그림 17. 실패 요청 시나리오: ERROR 상태와 request_id, trace_id 기반 추적 정보")
    add_image(doc, "05_grafana.png", "그림 18. Grafana 보조 대시보드 접속 화면: Prometheus 기반 시각화 도구")

    doc.add_heading("8. 설계상 한계와 확장 방향", level=1)
    doc.add_heading("8.1 할루시네이션 검출의 범위", level=2)
    add_paragraph(
        doc,
        "이번 MVP에서는 할루시네이션 자동 검출을 구현하지 않았다. 현재 OLLY가 다루는 영역은 semantic quality monitoring이 아니라 "
        "operational observability이다. 즉 답변이 사실인지 판별하기보다, 요청이 얼마나 느렸는지, 어느 단계가 병목인지, 비용과 토큰이 "
        "어디서 증가했는지, 실패와 알림이 발생했는지를 관측한다.",
    )
    doc.add_heading("8.2 프롬프트 관측의 보안 기준", level=2)
    add_paragraph(
        doc,
        "프롬프트 관측은 가능하지만, 원문을 그대로 저장하는 방식은 개인정보와 보안 측면에서 위험하다. 실무 적용 시에는 raw prompt "
        "전체 저장보다 prompt_template_id, prompt_length, input/output token, feature, model, 익명화된 user/org id를 "
        "우선 기록하고, 원문이 필요한 경우에는 샘플링과 마스킹 정책을 함께 적용하는 방식이 적절하다.",
    )
    add_paragraph(
        doc,
        "따라서 OLLY의 실무형 확장 방향은 단순히 더 많은 값을 저장하는 것이 아니라, 운영 분석에 필요한 최소한의 메타데이터를 정하고 "
        "민감정보 저장을 제한하는 정책까지 함께 설계하는 것이다.",
    )
    add_code_block(
        doc,
        """
request_id + trace_id
  + feature
  + prompt_template_id
  + input_tokens / output_tokens
  + model
  + latency_ms
  + cost_usd
  + stage durations
= 같은 /chat API 안에서도 요청별 차이를 비교할 수 있는 관측 단위
        """,
    )
    doc.add_heading("8.3 발표 이후 정리한 설계 기준", level=2)
    add_paragraph(
        doc,
        "주제 발표 이후에는 OLLY의 범위를 더 명확히 정리했다. 첫째, OLLY가 말하는 LLM 서비스는 특정 제품 하나가 아니라 "
        "외부 LLM API, RAG 기반 챗봇, 로컬 SLM 서비스를 포함하는 운영 대상이다. 둘째, OpenTelemetry는 프롬프트를 자동으로 "
        "보여주는 도구가 아니므로 서비스 코드가 prompt template, token count, feature, model 같은 메타데이터를 직접 남겨야 한다. "
        "셋째, 할루시네이션 검출은 이번 구현 범위가 아니며 향후 품질 평가 기능으로 확장할 항목이다.",
    )
    doc.add_heading("8.4 향후 확장 방향", level=2)
    add_bullets(
        doc,
        [
            "RAG 근거 문서와 답변 문장의 일치도 검사",
            "답변에 citation을 강제하고 인용 근거가 실제 검색 결과에 존재하는지 검증",
            "LLM-as-a-judge를 사용한 자동 평가",
            "사용자 피드백과 운영자 라벨링 데이터를 수집",
            "정답 데이터셋 기반 regression eval로 모델 변경 전후 품질 비교",
            "실제 Vector DB, 인증/권한, 장기 저장소, 조직별 비용 분리 기능 추가",
            "운영 환경용 Ingress/TLS, Secret 관리, RBAC, 감사 로그, metric retention 정책 추가",
            "SLO 기반 alert rule과 배포 전후 regression dashboard 구성",
        ],
    )

    doc.add_heading("9. 결론", level=1)
    add_paragraph(
        doc,
        "OLLY는 LLM 서비스 운영자가 비용, 지연, 병목, 실패를 주관적 판단이 아니라 데이터 기반으로 판단하도록 지원하는 관측성 MVP이다. "
        "요청마다 request_id와 trace_id를 남기고, Prometheus metric과 Jaeger trace를 결합해 운영 질문에 답할 수 있도록 구현했다.",
    )
    add_paragraph(
        doc,
        "이번 구현의 의의는 CNCF 생태계의 도구를 LLM 서비스 운영 문제에 직접 적용했다는 점이다. Kubernetes는 배포 환경을, "
        "OpenTelemetry는 계측 표준을, Prometheus는 지표 저장과 알림을, Jaeger는 요청 단위 추적을 담당한다.",
    )
    add_paragraph(
        doc,
        "또한 OLLY는 실무 적용을 전제로 기존 서비스에 붙는 관측성 계층으로 설계되었다. 운영자는 request_id와 trace_id를 기준으로 "
        "사용자 요청, 비용, 토큰, 단계별 병목, 알림을 연결해서 확인할 수 있으며, 이는 실제 LLM 서비스 운영에서 필요한 장애 대응과 "
        "비용 통제 절차에 직접 대응한다.",
    )
    add_paragraph(
        doc,
        "현재 구현 범위 역시 명확히 구분된다. MVP는 로컬 SLM 샘플 서비스를 대상으로 하며, 할루시네이션 자동 검출이나 장기 저장소, 인증/권한, 실제 Vector DB 연동은 "
        "구현하지 않았다. 그러나 구현 범위와 향후 과제를 명확히 분리했기 때문에 OLLY는 실제 사용자용 LLM/RAG 챗봇에 연결 가능한 관측성 계층으로 확장될 수 있다.",
    )

    doc.add_page_break()
    doc.add_heading("부록 A. 주요 PromQL", level=1)
    add_code_block(
        doc,
        """
sum(increase(olly_requests_total[1h]))
sum(increase(olly_tokens_total[1h])) by (feature)
sum(increase(olly_cost_usd_total[1h])) by (feature)
histogram_quantile(0.95, sum by (stage, le) (increase(olly_stage_duration_seconds_bucket[1h])))
sum(increase(olly_errors_total[5m])) / clamp_min(sum(increase(olly_requests_total[5m])), 1)
        """,
    )
    doc.add_heading("부록 B. 주요 Metric", level=1)
    add_table(
        doc,
        ["Metric", "의미"],
        [
            ["olly_requests_total", "LLM chat 요청 수"],
            ["olly_tokens_total", "입력/출력 토큰 사용량"],
            ["olly_cost_usd_total", "토큰 비용과 로컬 인프라 비용을 합산한 추정 비용"],
            ["olly_token_cost_usd_total", "외부 API형 모델에서의 토큰 기반 비용"],
            ["olly_infra_cost_usd_total", "로컬 모델 실행 시간 기반 인프라 비용"],
            ["olly_stage_duration_seconds", "retrieve, llm_call, postprocess 단계별 소요 시간"],
            ["olly_request_duration_seconds", "요청 전체 소요 시간"],
            ["olly_errors_total", "실패 요청 수"],
        ],
        [2.25, 4.0],
    )

    doc.core_properties.title = "OLLY 최종 보고서"
    doc.core_properties.subject = "LLM 서비스 관측성 플랫폼 MVP"
    doc.core_properties.author = "OLLY 5조"
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
