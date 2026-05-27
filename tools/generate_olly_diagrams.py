from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "final_report_assets"

FONT_PATHS = [
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/System/Library/Fonts/Supplemental/NotoSansGothic-Regular.ttf",
]

COLORS = {
    "bg": "#F8FAFC",
    "text": "#111827",
    "muted": "#64748B",
    "line": "#475569",
    "border": "#CBD5E1",
    "shadow": "#D9E2EC",
    "blue": "#2563EB",
    "blue_fill": "#DBEAFE",
    "green": "#059669",
    "green_fill": "#D1FAE5",
    "purple": "#7C3AED",
    "purple_fill": "#EDE9FE",
    "amber": "#D97706",
    "amber_fill": "#FEF3C7",
    "rose": "#E11D48",
    "rose_fill": "#FFE4E6",
    "slate_fill": "#E2E8F0",
    "white": "#FFFFFF",
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in FONT_PATHS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


FONTS = {
    "title": font(46, True),
    "subtitle": font(25),
    "h": font(27, True),
    "body": font(24),
    "small": font(20),
    "tiny": font(17),
    "badge": font(21, True),
}


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if text_size(draw, candidate, fnt)[0] <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
                current = word
            while text_size(draw, current, fnt)[0] > max_width and len(current) > 1:
                cut = len(current)
                while cut > 1 and text_size(draw, current[:cut], fnt)[0] > max_width:
                    cut -= 1
                lines.append(current[:cut])
                current = current[cut:]
        if current:
            lines.append(current)
    return lines


def draw_centered_lines(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    lines: list[str],
    fnt: ImageFont.FreeTypeFont,
    fill: str = COLORS["text"],
    line_gap: int = 7,
) -> None:
    x1, y1, x2, y2 = rect
    heights = [text_size(draw, line, fnt)[1] for line in lines]
    total = sum(heights) + line_gap * max(0, len(lines) - 1)
    y = y1 + (y2 - y1 - total) / 2
    for line, height in zip(lines, heights):
        width, _ = text_size(draw, line, fnt)
        draw.text((x1 + (x2 - x1 - width) / 2, y), line, font=fnt, fill=fill)
        y += height + line_gap


def box(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    title: str,
    body: str | None = None,
    fill: str = COLORS["white"],
    outline: str = COLORS["border"],
    accent: str | None = None,
    radius: int = 18,
    title_font: ImageFont.FreeTypeFont | None = None,
) -> None:
    x1, y1, x2, y2 = rect
    draw.rounded_rectangle((x1 + 8, y1 + 9, x2 + 8, y2 + 9), radius=radius, fill=COLORS["shadow"])
    draw.rounded_rectangle(rect, radius=radius, fill=fill, outline=outline, width=3)
    if accent:
        draw.rounded_rectangle((x1, y1, x1 + 12, y2), radius=radius, fill=accent)
        draw.rectangle((x1 + 7, y1, x1 + 13, y2), fill=accent)
    f_title = title_font or FONTS["h"]
    if body:
        title_lines = wrap_text(draw, title, f_title, x2 - x1 - 42)
        body_lines = wrap_text(draw, body, FONTS["small"], x2 - x1 - 42)
        title_heights = [text_size(draw, line, f_title)[1] for line in title_lines]
        body_heights = [text_size(draw, line, FONTS["small"])[1] for line in body_lines]
        total = sum(title_heights) + sum(body_heights) + 8 * max(0, len(title_lines) - 1) + 7 * max(0, len(body_lines) - 1) + 15
        y = y1 + (y2 - y1 - total) / 2
        for line, height in zip(title_lines, title_heights):
            w, _ = text_size(draw, line, f_title)
            draw.text((x1 + (x2 - x1 - w) / 2, y), line, font=f_title, fill=COLORS["text"])
            y += height + 8
        y += 7
        for line, height in zip(body_lines, body_heights):
            w, _ = text_size(draw, line, FONTS["small"])
            draw.text((x1 + (x2 - x1 - w) / 2, y), line, font=FONTS["small"], fill=COLORS["muted"])
            y += height + 7
    else:
        lines = wrap_text(draw, title, f_title, x2 - x1 - 38)
        draw_centered_lines(draw, rect, lines, f_title)


def title(draw: ImageDraw.ImageDraw, text: str, subtitle: str | None = None) -> None:
    draw.text((70, 45), text, font=FONTS["title"], fill=COLORS["text"])
    if subtitle:
        draw.text((72, 103), subtitle, font=FONTS["subtitle"], fill=COLORS["muted"])


def band(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], label: str, fill: str) -> None:
    draw.rounded_rectangle(rect, radius=26, fill=fill, outline="#E2E8F0", width=2)
    draw.text((rect[0] + 24, rect[1] + 17), label, font=FONTS["small"], fill=COLORS["muted"])


def arrow(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[int, int]],
    color: str = COLORS["line"],
    width: int = 4,
    dashed: bool = False,
) -> None:
    if dashed:
        for start, end in zip(points, points[1:]):
            dashed_segment(draw, start, end, color, width)
    else:
        draw.line(points, fill=color, width=width, joint="curve")
    x1, y1 = points[-2]
    x2, y2 = points[-1]
    angle = math.atan2(y2 - y1, x2 - x1)
    size = 16
    left = (x2 - size * math.cos(angle - math.pi / 6), y2 - size * math.sin(angle - math.pi / 6))
    right = (x2 - size * math.cos(angle + math.pi / 6), y2 - size * math.sin(angle + math.pi / 6))
    draw.polygon([(x2, y2), left, right], fill=color)


def dashed_segment(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    color: str,
    width: int,
    dash: int = 18,
    gap: int = 12,
) -> None:
    x1, y1 = start
    x2, y2 = end
    length = math.hypot(x2 - x1, y2 - y1)
    if length == 0:
        return
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    pos = 0
    while pos < length:
        end_pos = min(pos + dash, length)
        draw.line(
            [(x1 + ux * pos, y1 + uy * pos), (x1 + ux * end_pos, y1 + uy * end_pos)],
            fill=color,
            width=width,
        )
        pos += dash + gap


def badge(draw: ImageDraw.ImageDraw, center: tuple[int, int], number: str, fill: str) -> None:
    x, y = center
    draw.ellipse((x - 24, y - 24, x + 24, y + 24), fill=fill, outline="#FFFFFF", width=4)
    w, h = text_size(draw, number, FONTS["badge"])
    draw.text((x - w / 2, y - h / 2 - 1), number, font=FONTS["badge"], fill="#FFFFFF")


def save(img: Image.Image, filename: str) -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    path = ASSETS / filename
    img.save(path, "PNG", optimize=True)
    print(path)


def architecture_overview() -> None:
    img = Image.new("RGB", (2200, 1380), COLORS["bg"])
    draw = ImageDraw.Draw(img)
    title(draw, "OLLY 전체 아키텍처", "사용자 요청 처리, 관측성 수집, 운영 분석과 알림 흐름")

    band(draw, (55, 160, 725, 1285), "Interface & Rule Input", "#F1F5F9")
    band(draw, (760, 160, 1450, 1285), "OLLY Application", "#EFF6FF")
    band(draw, (1490, 160, 2105, 1045), "CNCF Observability", "#F0FDF4")
    band(draw, (1490, 1080, 2105, 1320), "Alert & Operations", "#FFF7ED")

    user = (95, 250, 335, 360)
    chat = (425, 225, 705, 385)
    api = (835, 270, 1025, 370)
    retrieve = (1120, 210, 1360, 310)
    llm = (1120, 365, 1430, 485)
    post = (1120, 535, 1360, 635)
    response = (1120, 695, 1360, 795)
    otel = (825, 875, 1125, 995)
    collector = (1235, 875, 1505, 995)
    prom = (1650, 725, 1990, 835)
    jaeger = (1650, 900, 1990, 1010)
    dash_api = (1640, 515, 2000, 625)
    custom = (95, 560, 360, 670)
    store = (450, 560, 715, 670)
    evaluator = (1160, 1130, 1505, 1250)
    summary = (1640, 1095, 1990, 1185)
    discord = (1640, 1215, 1990, 1305)

    box(draw, user, "사용자 / 운영자", fill=COLORS["white"], accent=COLORS["blue"])
    box(draw, chat, "Chat UI / Dashboard", "FastAPI 정적 화면", fill=COLORS["white"], accent=COLORS["blue"])
    box(draw, api, "/chat API", "request_id · trace_id", fill=COLORS["blue_fill"], outline="#93C5FD", accent=COLORS["blue"])
    box(draw, retrieve, "retrieve", "검색 / 문맥 준비", fill=COLORS["white"])
    box(draw, llm, "llm_call", "Ollama gemma3:1b", fill=COLORS["white"])
    box(draw, post, "postprocess", "응답 정리", fill=COLORS["white"])
    box(draw, response, "응답 반환", "answer + metadata", fill=COLORS["white"])
    box(draw, otel, "OpenTelemetry", "Trace / Metric 기록", fill=COLORS["purple_fill"], outline="#C4B5FD", accent=COLORS["purple"])
    box(draw, collector, "OTel Collector", "OTLP 수집 / 전달", fill=COLORS["white"], accent=COLORS["purple"])
    box(draw, prom, "Prometheus", "metrics · PromQL · alerts", fill=COLORS["green_fill"], outline="#86EFAC", accent=COLORS["green"])
    box(draw, jaeger, "Jaeger", "request trace · span", fill=COLORS["purple_fill"], outline="#C4B5FD", accent=COLORS["purple"])
    box(draw, dash_api, "Dashboard API", "Prometheus / Jaeger 조회", fill=COLORS["white"], accent=COLORS["green"])
    box(draw, custom, "Custom Alert Rule", "운영자 임계값 설정", fill=COLORS["white"], accent=COLORS["amber"])
    box(draw, store, "AlertStore", "alert_rules.json", fill=COLORS["amber_fill"], outline="#FCD34D", accent=COLORS["amber"])
    box(draw, evaluator, "AlertEvaluator", "주기 실행 · 조건 평가", fill=COLORS["amber_fill"], outline="#FCD34D", accent=COLORS["amber"])
    box(draw, summary, "LLM 한 줄 요약", "optional", fill=COLORS["white"])
    box(draw, discord, "Discord Webhook", "POST notification", fill=COLORS["rose_fill"], outline="#FDA4AF", accent=COLORS["rose"])

    arrow(draw, [(335, 305), (425, 305)])
    arrow(draw, [(705, 305), (835, 320)])
    arrow(draw, [(1025, 310), (1120, 260)])
    arrow(draw, [(1025, 330), (1120, 425)])
    arrow(draw, [(1025, 350), (1120, 585)])
    arrow(draw, [(1235, 635), (1235, 695)])
    arrow(draw, [(1120, 745), (780, 745), (780, 350), (705, 350)])
    arrow(draw, [(930, 370), (930, 875)])
    arrow(draw, [(1125, 935), (1235, 935)], color=COLORS["purple"])
    arrow(draw, [(1505, 910), (1650, 780)], color=COLORS["green"])
    arrow(draw, [(1505, 965), (1650, 955)], color=COLORS["purple"])
    arrow(draw, [(1820, 835), (1820, 900)], color=COLORS["muted"], dashed=True)
    arrow(draw, [(360, 615), (450, 615)], color=COLORS["amber"])
    arrow(draw, [(715, 615), (870, 615), (870, 1130), (1160, 1190)], color=COLORS["amber"])
    arrow(draw, [(1330, 1130), (1690, 835)], color=COLORS["green"], dashed=True)
    arrow(draw, [(1505, 1190), (1640, 1140)], color=COLORS["amber"])
    arrow(draw, [(1815, 1185), (1815, 1215)], color=COLORS["rose"])
    arrow(draw, [(1640, 570), (1540, 570), (1540, 780), (1650, 780)], color=COLORS["green"], dashed=True)
    arrow(draw, [(1640, 585), (1540, 585), (1540, 955), (1650, 955)], color=COLORS["purple"], dashed=True)
    save(img, "15_architecture_overview.png")


def user_flow() -> None:
    img = Image.new("RGB", (2050, 1120), COLORS["bg"])
    draw = ImageDraw.Draw(img)
    title(draw, "OLLY 시연 및 운영자 분석 플로우", "하나의 요청이 request_id와 trace_id로 연결되는 과정")

    band(draw, (60, 170, 1990, 495), "사용자 요청 흐름", "#EFF6FF")
    band(draw, (60, 560, 1990, 1025), "운영자 분석 흐름", "#F0FDF4")

    steps_top = [
        ((110, 260, 360, 390), "질문 입력", "/chat-ui"),
        ((475, 260, 735, 390), "/chat 처리", "retrieve → llm_call → postprocess"),
        ((850, 260, 1135, 390), "응답 + metadata", "request_id · trace_id · latency · token · cost"),
        ((1265, 260, 1535, 390), "대시보드 반영", "Recent Requests / KPI"),
        ((1660, 260, 1920, 390), "운영 질문", "분석 챗봇 질의"),
    ]
    steps_bottom = [
        ((160, 685, 435, 815), "요청 식별", "request_id 선택"),
        ((575, 685, 870, 815), "Trace Detail", "trace_id 확인"),
        ((1015, 685, 1310, 815), "Jaeger 분석", "span duration 비교"),
        ((1455, 685, 1750, 815), "Prometheus/Grafana", "추세 · 비용 · 토큰 확인"),
        ((1455, 875, 1750, 995), "Alerts", "임계값 · Discord 알림"),
    ]

    for idx, (rect, name, body) in enumerate(steps_top, start=1):
        box(draw, rect, name, body, fill=COLORS["white"], accent=COLORS["blue"])
        badge(draw, (rect[0] + 5, rect[1] + 5), str(idx), COLORS["blue"])
    for idx, (rect, name, body) in enumerate(steps_bottom, start=6):
        box(draw, rect, name, body, fill=COLORS["white"], accent=COLORS["green"])
        badge(draw, (rect[0] + 5, rect[1] + 5), str(idx), COLORS["green"])

    for (_, _, x2, _), (next_rect, _, _) in zip([s[0] for s in steps_top], steps_top[1:]):
        arrow(draw, [(x2, 325), (next_rect[0], 325)], color=COLORS["blue"])
    arrow(draw, [(1400, 390), (1400, 610), (300, 610), (300, 685)], color=COLORS["green"])
    for (_, _, x2, _), (next_rect, _, _) in zip([s[0] for s in steps_bottom[:4]], steps_bottom[1:4]):
        arrow(draw, [(x2, 750), (next_rect[0], 750)], color=COLORS["green"])
    arrow(draw, [(1605, 815), (1605, 875)], color=COLORS["amber"])
    arrow(draw, [(1605, 875), (1605, 815)], color=COLORS["amber"])

    note = (95, 965, 1040, 1040)
    draw.rounded_rectangle(note, radius=18, fill="#FFFFFF", outline="#CBD5E1", width=2)
    draw.text((120, 985), "보고서 시연 설명 포인트: Chat UI의 metadata가 Dashboard, Jaeger, Prometheus 분석의 공통 키가 된다.", font=FONTS["small"], fill=COLORS["muted"])
    save(img, "16_user_flow.png")


def observability_pipeline() -> None:
    img = Image.new("RGB", (2100, 1180), COLORS["bg"])
    draw = ImageDraw.Draw(img)
    title(draw, "CNCF 관측성 파이프라인", "OpenTelemetry로 수집하고 Prometheus와 Jaeger에서 분석")

    band(draw, (70, 175, 630, 1030), "Instrumented Service", "#EFF6FF")
    band(draw, (720, 175, 1130, 1030), "Collection", "#F5F3FF")
    band(draw, (1220, 175, 1995, 1030), "Storage · Query · Action", "#F0FDF4")

    service = (150, 280, 545, 410)
    spans = (150, 520, 545, 650)
    metrics = (150, 760, 545, 890)
    collector = (780, 520, 1080, 660)
    prom = (1260, 360, 1575, 490)
    jaeger = (1260, 660, 1575, 790)
    dashboard = (1690, 360, 1950, 490)
    analysis = (1690, 660, 1950, 790)
    alert = (1260, 900, 1575, 1015)
    discord = (1690, 900, 1950, 1015)

    box(draw, service, "FastAPI /chat", "retrieve · llm_call · postprocess", fill=COLORS["white"], accent=COLORS["blue"])
    box(draw, spans, "Span Attributes", "request_id · trace_id · model · stage", fill=COLORS["purple_fill"], outline="#C4B5FD", accent=COLORS["purple"])
    box(draw, metrics, "Custom Metrics", "latency · tokens · cost · errors", fill=COLORS["green_fill"], outline="#86EFAC", accent=COLORS["green"])
    box(draw, collector, "OpenTelemetry Collector", "OTLP endpoint · export", fill=COLORS["white"], accent=COLORS["purple"])
    box(draw, prom, "Prometheus", "metric storage · PromQL", fill=COLORS["green_fill"], outline="#86EFAC", accent=COLORS["green"])
    box(draw, jaeger, "Jaeger", "trace storage · span view", fill=COLORS["purple_fill"], outline="#C4B5FD", accent=COLORS["purple"])
    box(draw, dashboard, "OLLY Dashboard", "KPI · Traces · Signals", fill=COLORS["white"], accent=COLORS["blue"])
    box(draw, analysis, "분석 챗봇", "근거 기반 운영 답변", fill=COLORS["white"], accent=COLORS["blue"])
    box(draw, alert, "AlertEvaluator", "PromQL 평가 · cooldown", fill=COLORS["amber_fill"], outline="#FCD34D", accent=COLORS["amber"])
    box(draw, discord, "Discord Webhook", "alert notification", fill=COLORS["rose_fill"], outline="#FDA4AF", accent=COLORS["rose"])

    arrow(draw, [(345, 410), (345, 520)], color=COLORS["purple"])
    arrow(draw, [(345, 410), (345, 760)], color=COLORS["green"])
    arrow(draw, [(545, 585), (780, 565)], color=COLORS["purple"])
    arrow(draw, [(545, 825), (780, 625)], color=COLORS["green"])
    arrow(draw, [(1080, 570), (1260, 425)], color=COLORS["green"])
    arrow(draw, [(1080, 615), (1260, 725)], color=COLORS["purple"])
    arrow(draw, [(1575, 425), (1690, 425)], color=COLORS["green"], dashed=True)
    arrow(draw, [(1575, 725), (1690, 725)], color=COLORS["purple"], dashed=True)
    arrow(draw, [(1690, 445), (1625, 445), (1625, 700), (1690, 700)], color=COLORS["blue"], dashed=True)
    arrow(draw, [(1575, 425), (1625, 425), (1625, 958), (1575, 958)], color=COLORS["amber"], dashed=True)
    arrow(draw, [(1575, 958), (1690, 958)], color=COLORS["rose"])

    draw.text((150, 935), "Metrics path", font=FONTS["small"], fill=COLORS["green"])
    draw.line((280, 948, 390, 948), fill=COLORS["green"], width=5)
    draw.text((150, 975), "Trace path", font=FONTS["small"], fill=COLORS["purple"])
    draw.line((270, 988, 380, 988), fill=COLORS["purple"], width=5)
    save(img, "17_observability_pipeline.png")


def kubernetes_deployment() -> None:
    img = Image.new("RGB", (2150, 1250), COLORS["bg"])
    draw = ImageDraw.Draw(img)
    title(draw, "Kubernetes(kind) 배포 구조", "Namespace olly 안에서 실행되는 서비스, 저장소, 외부 접속 포트")

    cluster = (60, 170, 2070, 1160)
    draw.rounded_rectangle(cluster, radius=30, fill="#FFFFFF", outline="#CBD5E1", width=3)
    draw.text((95, 200), "kind cluster: olly / namespace: olly", font=FONTS["h"], fill=COLORS["text"])

    external = (105, 305, 430, 1035)
    draw.rounded_rectangle(external, radius=24, fill="#F8FAFC", outline="#CBD5E1", width=2)
    draw.text((135, 335), "Localhost 접속", font=FONTS["h"], fill=COLORS["text"])
    ports = [
        ("8001", "Chat UI / Dashboard"),
        ("16686", "Jaeger"),
        ("9090", "Prometheus"),
        ("3001", "Grafana"),
    ]
    y = 410
    for port, label in ports:
        draw.rounded_rectangle((145, y, 385, y + 70), radius=16, fill=COLORS["white"], outline="#CBD5E1", width=2)
        draw.text((165, y + 12), f"localhost:{port}", font=FONTS["small"], fill=COLORS["blue"])
        draw.text((165, y + 39), label, font=FONTS["tiny"], fill=COLORS["muted"])
        y += 115

    sample = (560, 290, 920, 430)
    ollama = (560, 540, 920, 680)
    otel = (1050, 290, 1395, 430)
    prom = (1050, 540, 1395, 680)
    jaeger = (1535, 290, 1885, 430)
    grafana = (1535, 540, 1885, 680)
    pvc_alert = (560, 820, 920, 950)
    pvc_ollama = (1050, 820, 1395, 950)
    job = (1535, 820, 1885, 950)

    box(draw, sample, "Deployment", "sample-llm-api\nFastAPI / OTel SDK", fill=COLORS["blue_fill"], outline="#93C5FD", accent=COLORS["blue"])
    box(draw, ollama, "Deployment", "ollama\ngemma3:1b", fill=COLORS["white"], accent=COLORS["blue"])
    box(draw, otel, "Deployment", "otel-collector\n4317 / 4318 / 8889", fill=COLORS["purple_fill"], outline="#C4B5FD", accent=COLORS["purple"])
    box(draw, prom, "Deployment", "prometheus\nmetrics + alert rules", fill=COLORS["green_fill"], outline="#86EFAC", accent=COLORS["green"])
    box(draw, jaeger, "Deployment", "jaeger\ntrace UI", fill=COLORS["purple_fill"], outline="#C4B5FD", accent=COLORS["purple"])
    box(draw, grafana, "Deployment", "grafana\nPrometheus dashboard", fill=COLORS["white"], accent=COLORS["green"])
    box(draw, pvc_alert, "PVC", "olly-alert-rules\n64Mi", fill=COLORS["amber_fill"], outline="#FCD34D", accent=COLORS["amber"])
    box(draw, pvc_ollama, "PVC", "ollama-data\n4Gi", fill=COLORS["amber_fill"], outline="#FCD34D", accent=COLORS["amber"])
    box(draw, job, "Job", "ollama-pull-gemma\nmodel preload", fill=COLORS["white"], accent=COLORS["amber"])

    arrow(draw, [(385, 445), (480, 445), (480, 360), (560, 360)], color=COLORS["blue"])
    arrow(draw, [(385, 560), (480, 560), (480, 250), (1535, 250), (1535, 360)], color=COLORS["purple"])
    arrow(draw, [(385, 675), (480, 675), (480, 755), (990, 755), (990, 610), (1050, 610)], color=COLORS["green"])
    arrow(draw, [(385, 790), (500, 790), (500, 755), (1460, 755), (1460, 610), (1535, 610)], color=COLORS["green"])

    arrow(draw, [(920, 360), (1050, 360)], color=COLORS["purple"])
    arrow(draw, [(740, 430), (740, 540)], color=COLORS["blue"])
    arrow(draw, [(1395, 360), (1535, 360)], color=COLORS["purple"])
    arrow(draw, [(1535, 610), (1395, 610)], color=COLORS["green"], dashed=True)
    arrow(draw, [(1220, 430), (1220, 540)], color=COLORS["green"])
    arrow(draw, [(650, 430), (510, 430), (510, 885), (560, 885)], color=COLORS["amber"], dashed=True)
    arrow(draw, [(920, 610), (985, 610), (985, 885), (1050, 885)], color=COLORS["amber"], dashed=True)
    arrow(draw, [(1535, 885), (1395, 885)], color=COLORS["amber"], dashed=True)

    draw.text((600, 1070), "NodePort mapping: 30001→8001, 30002→16686, 30003→9090, 30004→3001", font=FONTS["small"], fill=COLORS["muted"])
    save(img, "18_kubernetes_deployment.png")


def main() -> None:
    architecture_overview()
    user_flow()
    observability_pipeline()
    kubernetes_deployment()


if __name__ == "__main__":
    main()
