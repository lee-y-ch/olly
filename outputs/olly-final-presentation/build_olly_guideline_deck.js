const pptxgen = require("pptxgenjs");
const path = require("path");

const pptx = new pptxgen();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "OLLY Team";
pptx.company = "OLLY Team";
pptx.subject = "CNCF 오픈소스 기반 LLM 운영 관측성 MVP";
pptx.title = "OLLY 최종 발표 - 가이드라인 반영";
pptx.lang = "ko-KR";
pptx.theme = {
  headFontFace: "Apple SD Gothic Neo",
  bodyFontFace: "Apple SD Gothic Neo",
  lang: "ko-KR",
};
pptx.defineLayout({ name: "OLLY_WIDE", width: 13.333, height: 7.5 });
pptx.layout = "OLLY_WIDE";
pptx.margin = 0;

const C = {
  navy: "201B4C",
  navy2: "2D2A68",
  blue: "3B82F6",
  blue2: "2563EB",
  purple: "7C3AED",
  violet: "8B5CF6",
  green: "10B981",
  greenBg: "ECFDF5",
  orange: "F59E0B",
  red: "F43F5E",
  pinkBg: "FFF1F2",
  bg: "F7FAFF",
  bg2: "F3F7FE",
  line: "D8E2F1",
  text: "1F2937",
  muted: "64748B",
  lightText: "A7B2C5",
  white: "FFFFFF",
};

const W = 13.333;
const H = 7.5;
const font = "Apple SD Gothic Neo";

function addBg(slide, dark = false) {
  slide.background = { color: dark ? C.navy : C.bg };
  if (!dark) {
    slide.addShape(pptx.ShapeType.rect, {
      x: 0,
      y: 0,
      w: W,
      h: H,
      fill: { color: C.bg },
      line: { color: C.bg },
    });
    slide.addShape(pptx.ShapeType.ellipse, {
      x: -1.2,
      y: 4.35,
      w: 5.2,
      h: 3.4,
      fill: { color: "DFF8F9", transparency: 25 },
      line: { color: "DFF8F9", transparency: 100 },
    });
    slide.addShape(pptx.ShapeType.ellipse, {
      x: 9.6,
      y: -1.1,
      w: 4.2,
      h: 2.2,
      fill: { color: "EDEBFF", transparency: 18 },
      line: { color: "EDEBFF", transparency: 100 },
    });
  } else {
    slide.addShape(pptx.ShapeType.rect, {
      x: 0,
      y: 0,
      w: W,
      h: H,
      fill: { color: C.navy },
      line: { color: C.navy },
    });
    slide.addShape(pptx.ShapeType.ellipse, {
      x: -1.0,
      y: -0.8,
      w: 5.4,
      h: 4.4,
      fill: { color: "164E63", transparency: 35 },
      line: { transparency: 100 },
    });
    slide.addShape(pptx.ShapeType.ellipse, {
      x: 7.0,
      y: -0.8,
      w: 6.2,
      h: 4.9,
      fill: { color: "4C1D95", transparency: 28 },
      line: { transparency: 100 },
    });
  }
}

function text(slide, value, x, y, w, h, opts = {}) {
  slide.addText(value, {
    x,
    y,
    w,
    h,
    fontFace: font,
    fontSize: opts.size ?? 16,
    color: opts.color ?? C.text,
    bold: opts.bold ?? false,
    align: opts.align ?? "left",
    valign: opts.valign ?? "top",
    breakLine: false,
    fit: "shrink",
    margin: opts.margin ?? 0,
    paraSpaceAfterPt: opts.paraAfter ?? 0,
    breakLine: false,
  });
}

function header(slide, no, section, title, subtitle) {
  addBg(slide, false);
  text(slide, String(no).padStart(2, "0"), 0.64, 0.46, 0.34, 0.2, {
    size: 7.5,
    color: C.blue2,
    bold: true,
  });
  text(slide, section, 1.02, 0.43, 2.2, 0.26, { size: 7.5, color: C.blue2, bold: true });
  text(slide, title, 0.64, 0.76, 8.5, 0.44, { size: 20, color: C.text, bold: true });
  if (subtitle) text(slide, subtitle, 0.64, 1.23, 11.7, 0.32, { size: 8.6, color: C.muted });
}

function footer(slide, no, total = 14, dark = false) {
  text(slide, "OLLY", 0.64, 7.08, 0.42, 0.18, { size: 7, color: dark ? C.white : C.blue2, bold: true });
  text(slide, "·  LLM 운영 관측성 MVP", 1.08, 7.08, 2.0, 0.18, {
    size: 6.7,
    color: dark ? "CBD5E1" : C.lightText,
  });
  text(slide, `${String(no).padStart(2, "0")} / ${total}`, 12.08, 7.08, 0.6, 0.18, {
    size: 6.7,
    color: dark ? "CBD5E1" : C.lightText,
    align: "right",
  });
}

function card(slide, x, y, w, h, opts = {}) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x,
    y,
    w,
    h,
    rectRadius: 0.06,
    fill: { color: opts.fill ?? C.white, transparency: opts.transparency ?? 0 },
    line: { color: opts.line ?? C.line, transparency: opts.lineTrans ?? 0, width: opts.lineW ?? 0.8 },
    shadow: opts.shadow === false ? undefined : { type: "outer", color: "D7DEEC", opacity: 0.23, blur: 1.2, angle: 45, distance: 1 },
  });
}

function pill(slide, label, x, y, w, color = C.blue2) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x,
    y,
    w,
    h: 0.25,
    rectRadius: 0.06,
    fill: { color, transparency: 0 },
    line: { color, transparency: 100 },
  });
  text(slide, label, x, y + 0.055, w, 0.12, { size: 5.8, color: C.white, bold: true, align: "center" });
}

function miniIcon(slide, x, y, label, color, fill = "EEF4FF") {
  slide.addShape(pptx.ShapeType.roundRect, {
    x,
    y,
    w: 0.34,
    h: 0.34,
    rectRadius: 0.06,
    fill: { color: fill },
    line: { color: fill },
  });
  text(slide, label, x, y + 0.085, 0.34, 0.1, { size: 7.5, color, bold: true, align: "center" });
}

function arrow(slide, x1, y1, x2, y2, color = C.blue2, dashed = false) {
  slide.addShape(pptx.ShapeType.line, {
    x: x1,
    y: y1,
    w: x2 - x1,
    h: y2 - y1,
    line: { color, width: 1.3, beginArrowType: "none", endArrowType: "triangle", dash: dashed ? "dash" : "solid" },
  });
}

function addNotes(slide, notes) {
  // Speaker notes are intentionally omitted in the stable export. Some desktop
  // PowerPoint builds can show a repair warning on generated notes XML.
}

// 1. Cover
{
  const slide = pptx.addSlide();
  addBg(slide, true);
  text(slide, "OLLY", 0.64, 0.88, 3.0, 0.55, { size: 31, color: C.white, bold: true });
  text(slide, "CNCF 오픈소스 기반\nLLM 운영 관측성 MVP", 0.68, 1.68, 4.0, 0.72, {
    size: 13.5,
    color: C.white,
    bold: true,
  });
  text(slide, "비용 · 지연 · 병목 · 실패를 request_id 와 trace_id 로 추적하는 관측성 플랫폼", 0.68, 2.62, 6.9, 0.25, {
    size: 8.3,
    color: "DDE7FF",
  });
  ["Kubernetes", "OpenTelemetry", "Prometheus", "Jaeger"].forEach((v, i) => {
    pill(slide, v, 0.68 + i * 1.23, 3.2, 1.0 + (i === 1 ? 0.32 : 0), [C.blue2, C.purple, C.orange, "38BDF8"][i]);
  });
  const stats = [
    ["AVG LATENCY", "1.88s", C.blue2],
    ["SUCCESS RATE", "75.0%", C.green],
    ["TOTAL COST", "$0.00011", C.orange],
  ];
  stats.forEach((s, i) => {
    card(slide, 9.3, 0.68 + i * 0.92, 2.55, 0.68, { fill: C.white, lineTrans: 60 });
    text(slide, s[0], 9.48, 0.78 + i * 0.92, 1.25, 0.12, { size: 5.2, color: C.lightText, bold: true });
    text(slide, s[1], 9.48, 0.98 + i * 0.92, 1.3, 0.18, { size: 12, color: C.text, bold: true });
    miniIcon(slide, 11.35, 0.87 + i * 0.92, ["↗", "✓", "$"][i], s[2], ["EFF6FF", "ECFDF5", "FFFBEB"][i]);
  });
  text(slide, "RECENT TRACES", 9.36, 3.72, 1.5, 0.14, { size: 5.2, color: C.lightText, bold: true });
  card(slide, 9.3, 3.95, 2.55, 0.64, { fill: C.white, lineTrans: 70 });
  text(slide, "req_6cc69475", 9.48, 4.08, 1.2, 0.12, { size: 6.4, color: C.muted, bold: true });
  text(slide, "error", 11.07, 4.08, 0.5, 0.12, { size: 5.7, color: C.red, bold: true, align: "right" });
  text(slide, "req_b7a3a1ba", 9.48, 4.31, 1.2, 0.12, { size: 6.4, color: C.muted, bold: true });
  text(slide, "success", 11.0, 4.31, 0.58, 0.12, { size: 5.7, color: C.green, bold: true, align: "right" });
  text(slide, "오픈소스SW분석 (클라우드) · 5조", 0.68, 6.66, 4.3, 0.2, { size: 7.2, color: "CBD5E1" });
  text(slide, "최호준(32215116) | 이용찬(32213336) | 박주희(32221902) | 조하은(32234364)", 0.68, 6.88, 6.5, 0.2, {
    size: 6.6,
    color: "CBD5E1",
  });
  addNotes(slide, "안녕하세요. 저희는 CNCF 오픈소스 도구 기반 LLM 운영 관측성 MVP인 OLLY를 구현했습니다. 핵심은 LLM 요청 하나를 request_id와 trace_id로 연결해 비용, 지연, 병목, 실패를 끝까지 추적하는 것입니다.");
}

// 2. Problem
{
  const slide = pptx.addSlide();
  header(slide, 1, "문제 정의", "LLM 서비스는 일반 API와 다르다", "같은 /chat 요청이라도 프롬프트 · 검색 문맥 · 모델 호출 · 출력 토큰에 따라 비용과 지연이 달라진다");
  card(slide, 0.98, 2.05, 4.3, 2.75);
  text(slide, "기존 APM 모니터링", 1.25, 2.28, 3.6, 0.26, { size: 11.5, bold: true, color: C.text, align: "center" });
  [
    ["HTTP Status", "성공 / 실패 여부"],
    ["Latency", "전체 응답 시간"],
    ["Error rate", "오류 비율"],
  ].forEach((r, i) => {
    miniIcon(slide, 1.35, 2.78 + i * 0.55, ["✓", "↘", "!"][i], [C.green, C.blue2, C.red][i]);
    text(slide, r[0], 1.82, 2.77 + i * 0.55, 1.6, 0.15, { size: 8.2, color: C.text, bold: true });
    text(slide, r[1], 1.82, 2.96 + i * 0.55, 2.5, 0.13, { size: 6.4, color: C.muted });
  });
  slide.addShape(pptx.ShapeType.ellipse, { x: 5.64, y: 3.05, w: 0.52, h: 0.52, fill: { color: C.violet }, line: { transparency: 100 } });
  text(slide, "+", 5.64, 3.17, 0.52, 0.1, { size: 13, bold: true, color: C.white, align: "center" });
  card(slide, 6.5, 2.05, 4.9, 2.75);
  text(slide, "LLM 운영에 필요한 관측", 6.82, 2.28, 4.25, 0.26, { size: 11.5, bold: true, color: C.text, align: "center" });
  const chips = [
    ["Latency", C.blue2],
    ["Token", C.orange],
    ["Cost", C.green],
    ["Stage duration", C.purple],
    ["Error", C.red],
    ["Alert", "38BDF8"],
  ];
  chips.forEach((c, i) => {
    const x = 7.0 + (i % 2) * 2.0;
    const y = 2.84 + Math.floor(i / 2) * 0.57;
    miniIcon(slide, x, y, ["↘", "#", "$", "S", "!", "A"][i], c[1], "F7F8FF");
    text(slide, c[0], x + 0.45, y + 0.09, 1.3, 0.12, { size: 7.2, color: C.text, bold: true });
  });
  slide.addShape(pptx.ShapeType.roundRect, {
    x: 1.42,
    y: 5.52,
    w: 9.5,
    h: 0.42,
    rectRadius: 0.04,
    fill: { color: C.navy },
    line: { transparency: 100 },
  });
  text(slide, "HTTP 200이어도 운영 관점에서는 성공이 아니다. 왜 느린지, 왜 비용이 늘었는지, 어느 단계가 병목인지 알 수 있어야 한다.", 1.65, 5.66, 9.0, 0.1, { size: 6.8, color: C.white, align: "center" });
  footer(slide, 2);
  addNotes(slide, "LLM 서비스는 HTTP 200만으로 운영 상태를 판단하기 어렵습니다. 같은 API라도 검색 문맥, 모델 호출 시간, 토큰 수에 따라 비용과 지연이 달라지기 때문에 LLM에 맞는 관측성이 필요합니다.");
}

// 3. Changes since first presentation
{
  const slide = pptx.addSlide();
  header(slide, 2, "1차 발표 이후 변화", "아이디어 중심 구조에서 동작하는 MVP로 좁혔다", "가이드라인에 맞춰 최종 발표에서는 변경점과 설계 판단을 명확히 분리해 설명한다");
  const cols = [0.9, 4.2, 7.5];
  text(slide, "1차 발표 당시", cols[1], 1.78, 2.0, 0.18, { size: 9.5, color: C.muted, bold: true, align: "center" });
  text(slide, "최종 구현", cols[2], 1.78, 2.0, 0.18, { size: 9.5, color: C.blue2, bold: true, align: "center" });
  const rows = [
    ["아이디어 수준의 관측성 구조", "FastAPI 샘플 서비스 + 실제 관측 파이프라인 구현"],
    ["외부 LLM API 연동 검토", "비용과 재현성 때문에 Ollama gemma3:1b 로컬 SLM 선택"],
    ["대시보드 구상 중심", "Dashboard · Jaeger · Prometheus · Discord 알림 연결"],
    ["단순 모니터링 목표", "request_id / trace_id 기반 End-to-End 추적"],
    ["부가 기능 후보 다수", "비용 · 지연 · 토큰 · 실패 · 알림으로 MVP 범위 축소"],
  ];
  rows.forEach((r, i) => {
    const y = 2.18 + i * 0.72;
    card(slide, 1.0, y, 10.9, 0.5, { fill: i % 2 === 0 ? C.white : "F9FBFF", shadow: false });
    text(slide, String(i + 1).padStart(2, "0"), 1.25, y + 0.17, 0.36, 0.1, { size: 7, color: C.blue2, bold: true });
    text(slide, r[0], 1.82, y + 0.15, 3.6, 0.12, { size: 7.8, color: C.text, bold: true });
    arrow(slide, 5.55, y + 0.25, 6.35, y + 0.25, C.violet);
    text(slide, r[1], 6.62, y + 0.13, 4.85, 0.16, { size: 7.4, color: C.text, bold: true });
  });
  footer(slide, 3);
  addNotes(slide, "1차 발표 이후 가장 크게 바뀐 점은 아이디어 수준의 관측성 구조를 실제 동작하는 MVP로 좁힌 것입니다. 외부 API는 비용과 재현성 문제가 있어 로컬 SLM으로 변경했고, 대신 request_id와 trace_id를 중심으로 도구들을 연결하는 데 집중했습니다.");
}

// 4. Goal
{
  const slide = pptx.addSlide();
  header(slide, 3, "목표", "OLLY의 목표: LLM 운영 질문에 답하기", "답변 채점기가 아니라, 운영자가 실제로 궁금해하는 질문에 답하는 관측성 MVP");
  card(slide, 0.85, 1.82, 4.95, 4.25);
  text(slide, "운영자가 던지는 질문", 1.22, 2.08, 2.8, 0.18, { size: 9.4, bold: true, color: C.blue2 });
  [
    "어제 왜 비용이 증가했는가?",
    "어떤 기능이 토큰을 많이 쓰는가?",
    "응답 지연이 retrieve 때문인가, llm_call 때문인가?",
    "실패 요청은 어떤 trace 에서 발생했는가?",
    "대시보드를 보지 않아도 이상 신호를 받을 수 있는가?",
  ].forEach((q, i) => {
    miniIcon(slide, 1.25, 2.55 + i * 0.58, "?", [C.orange, C.blue2, C.purple, C.red, C.green][i], "F8FAFC");
    text(slide, q, 1.7, 2.62 + i * 0.58, 3.7, 0.11, { size: 7.1, color: C.text, bold: true });
  });
  card(slide, 7.0, 1.82, 4.85, 4.25, { fill: C.navy });
  text(slide, "MVP 목표", 7.38, 2.08, 2.4, 0.18, { size: 9.4, bold: true, color: C.white });
  [
    "모델 · 기능별 비용 가시화",
    "요청 단위 병목 추적",
    "실시간 알림",
    "request_id / trace_id 운영 흐름 연결",
  ].forEach((g, i) => {
    miniIcon(slide, 7.42, 2.6 + i * 0.72, ["$", "S", "A", "ID"][i], C.white, [C.purple, C.blue2, C.red, C.green][i]);
    text(slide, g, 7.92, 2.69 + i * 0.72, 3.3, 0.12, { size: 7.5, color: C.white, bold: true });
  });
  footer(slide, 4);
  addNotes(slide, "OLLY의 목표는 답변 품질 평가가 아니라 운영 질문에 답하는 것입니다. 비용 증가, 토큰 과다, 병목 단계, 실패 trace, 알림이라는 운영 흐름을 MVP 범위로 설정했습니다.");
}

// 5. Final architecture
{
  const slide = pptx.addSlide();
  header(slide, 4, "최종 아키텍처", "사용자 요청 처리 · 관측 데이터 수집 · 운영 분석을 분리했다", "업무 로직과 관측 파이프라인을 독립적으로 확장하기 위한 구조");
  const bands = [
    [0.65, 1.83, 3.75, 4.3, "Interface & Rule Input", "F3F7FE"],
    [4.58, 1.83, 3.85, 4.3, "OLLY Application", "EEF5FF"],
    [8.63, 1.83, 3.8, 4.3, "CNCF Observability", "ECFDF5"],
  ];
  bands.forEach((b) => {
    slide.addShape(pptx.ShapeType.roundRect, { x: b[0], y: b[1], w: b[2], h: b[3], rectRadius: 0.08, fill: { color: b[5] }, line: { color: C.line } });
    text(slide, b[4], b[0] + 0.18, b[1] + 0.18, 2.2, 0.12, { size: 6, color: C.muted, bold: true });
  });
  card(slide, 1.05, 2.48, 1.35, 0.54);
  text(slide, "사용자", 1.23, 2.68, 0.9, 0.1, { size: 7.3, bold: true, align: "center" });
  card(slide, 2.78, 2.32, 1.25, 0.8);
  text(slide, "Chat UI", 2.95, 2.55, 0.9, 0.1, { size: 7.6, bold: true, align: "center" });
  text(slide, "질문 생성", 2.94, 2.78, 0.9, 0.1, { size: 5.6, color: C.muted, align: "center" });
  arrow(slide, 2.42, 2.75, 2.78, 2.75);
  card(slide, 4.98, 2.36, 1.15, 0.67, { fill: "EFF6FF", line: "93C5FD" });
  text(slide, "/chat API", 5.13, 2.56, 0.83, 0.11, { size: 7.2, bold: true, color: C.blue2, align: "center" });
  text(slide, "request_id\ntrace_id", 5.16, 2.75, 0.72, 0.15, { size: 5, color: C.muted, align: "center" });
  arrow(slide, 4.03, 2.75, 4.98, 2.75);
  const stages = [
    ["retrieve", "검색 / 문맥 준비"],
    ["llm_call", "Ollama gemma3:1b"],
    ["postprocess", "응답 정리"],
  ];
  stages.forEach((s, i) => {
    card(slide, 6.72, 2.05 + i * 0.95, 1.5, 0.54);
    text(slide, s[0], 6.9, 2.19 + i * 0.95, 1.1, 0.1, { size: 8.2, bold: true, align: "center" });
    text(slide, s[1], 6.88, 2.39 + i * 0.95, 1.15, 0.09, { size: 5.4, color: C.muted, align: "center" });
    arrow(slide, 6.13, 2.69, 6.72, 2.32 + i * 0.95, C.muted);
  });
  card(slide, 5.15, 4.95, 1.5, 0.55, { fill: "F5F3FF", line: "C4B5FD" });
  text(slide, "OpenTelemetry", 5.32, 5.1, 1.18, 0.1, { size: 7, bold: true, color: C.purple, align: "center" });
  card(slide, 7.02, 4.95, 1.25, 0.55, { fill: "F5F3FF", line: "C4B5FD" });
  text(slide, "OTel Collector", 7.15, 5.11, 1.0, 0.1, { size: 6.7, bold: true, color: C.purple, align: "center" });
  arrow(slide, 5.55, 3.04, 5.55, 4.95, C.muted);
  arrow(slide, 6.65, 5.23, 7.02, 5.23, C.purple);
  card(slide, 9.24, 2.62, 1.8, 0.55);
  text(slide, "Dashboard API", 9.52, 2.79, 1.25, 0.1, { size: 6.8, bold: true, align: "center" });
  card(slide, 9.08, 3.72, 2.1, 0.62, { fill: "D1FAE5", line: "86EFAC" });
  text(slide, "Prometheus", 9.44, 3.88, 1.25, 0.1, { size: 7.4, bold: true, color: "047857", align: "center" });
  text(slide, "metric · alert", 9.55, 4.1, 1.0, 0.1, { size: 5.4, color: "047857", align: "center" });
  card(slide, 9.08, 4.88, 2.1, 0.62, { fill: "F5F3FF", line: "C4B5FD" });
  text(slide, "Jaeger", 9.64, 5.04, 1.0, 0.1, { size: 7.4, bold: true, color: C.purple, align: "center" });
  text(slide, "request trace · span", 9.48, 5.26, 1.3, 0.1, { size: 5.4, color: C.purple, align: "center" });
  arrow(slide, 8.27, 5.23, 9.08, 4.03, C.green);
  arrow(slide, 8.27, 5.23, 9.08, 5.19, C.purple);
  arrow(slide, 9.95, 4.34, 9.95, 4.88, C.muted);
  card(slide, 1.05, 4.55, 1.55, 0.54, { fill: "FFF7ED", line: "FDBA74" });
  text(slide, "Alert Rule", 1.32, 4.72, 0.95, 0.1, { size: 7, bold: true, color: C.orange, align: "center" });
  card(slide, 3.0, 4.55, 1.15, 0.54, { fill: "FFFBEB", line: "FBBF24" });
  text(slide, "AlertStore", 3.14, 4.72, 0.87, 0.1, { size: 6.9, bold: true, color: C.orange, align: "center" });
  arrow(slide, 2.6, 4.82, 3.0, 4.82, C.orange);
  card(slide, 8.22, 6.0, 1.45, 0.45, { fill: "FFFBEB", line: "FBBF24" });
  text(slide, "AlertEvaluator", 8.42, 6.14, 1.05, 0.09, { size: 6.4, bold: true, color: C.orange, align: "center" });
  card(slide, 10.15, 6.0, 1.6, 0.45, { fill: C.pinkBg, line: "FDA4AF" });
  text(slide, "Discord Webhook", 10.37, 6.14, 1.16, 0.09, { size: 6.3, bold: true, color: C.red, align: "center" });
  arrow(slide, 4.15, 4.82, 8.22, 6.2, C.orange);
  arrow(slide, 9.67, 6.22, 10.15, 6.22, C.orange);
  footer(slide, 5);
  addNotes(slide, "최종 아키텍처는 세 흐름입니다. 사용자가 /chat으로 요청을 보내는 처리 흐름, OpenTelemetry와 Collector를 거쳐 Prometheus와 Jaeger에 저장되는 관측 흐름, 그리고 Dashboard와 Discord로 운영자가 확인하는 분석 흐름입니다.");
}

// 6. CNCF roles
{
  const slide = pptx.addSlide();
  header(slide, 5, "CNCF 접목", "CNCF 프로젝트가 실제로 어떤 역할을 했는가?", "각 오픈소스 도구에 실제 운영 역할을 부여했다");
  const items = [
    ["Kubernetes", "전체 스택 배포와 서비스 연결", "컨테이너 기반 재현 가능한 실행 환경", C.blue2],
    ["OpenTelemetry", "/chat 요청과 내부 stage 계측", "trace_id 기반 요청 흐름 생성", C.purple],
    ["Prometheus", "latency · token · cost · error metric 저장", "운영 지표 조회 및 alert rule 근거", C.orange],
    ["Jaeger", "요청 단위 trace 시각화", "retrieve · llm_call · postprocess 병목 확인", "38BDF8"],
    ["Grafana", "Prometheus metric 시각화", "latency · token · cost 변화 확인용 보조 대시보드", C.red],
  ];
  items.forEach((it, i) => {
    const x = 0.72 + i * 2.48;
    card(slide, x, 2.02, 2.04, 2.38);
    miniIcon(slide, x + 0.84, 2.35, ["K", "OT", "P", "J", "G"][i], it[3], "F5F7FF");
    text(slide, it[0], x + 0.18, 2.88, 1.68, 0.13, { size: 7.5, bold: true, align: "center", color: C.text });
    text(slide, it[1], x + 0.18, 3.25, 1.68, 0.24, { size: 5.7, color: C.muted, align: "center" });
    text(slide, it[2], x + 0.18, 3.8, 1.68, 0.25, { size: 5.5, color: it[3], bold: true, align: "center" });
  });
  const y = 5.28;
  ["LLM 요청", "OpenTelemetry 계측", "Prometheus metric · Jaeger trace", "Dashboard · Grafana · Discord alert"].forEach((v, i) => {
    const x = [1.02, 3.05, 5.65, 9.55][i];
    const w = [1.35, 1.8, 2.72, 2.55][i];
    card(slide, x, y, w, 0.38, { fill: i === 0 ? "EFF6FF" : i === 3 ? "F5F3FF" : C.white, shadow: false });
    text(slide, v, x + 0.08, y + 0.13, w - 0.16, 0.08, { size: 5.8, color: i === 3 ? C.purple : C.blue2, bold: true, align: "center" });
    if (i < 3) arrow(slide, x + w + 0.05, y + 0.19, [3.0, 5.58, 9.48][i], y + 0.19, C.blue2);
  });
  footer(slide, 6);
  addNotes(slide, "Kubernetes는 실행 환경, OpenTelemetry는 계측, Prometheus는 metric과 alert, Jaeger는 trace, Grafana는 시각화 역할입니다. 단순히 도구 이름을 나열한 것이 아니라 LLM 운영 흐름 안에서 역할을 나눴습니다.");
}

// 7. Core design
{
  const slide = pptx.addSlide();
  header(slide, 6, "핵심 설계", "요청 하나를 끝까지 잇는 기준: request_id 와 trace_id", "이번 MVP에서는 요청 내부 단계를 공통 stage label로 기록해 병목을 구분했다");
  text(slide, "서비스 내부 처리 구간 예시", 1.05, 1.82, 2.5, 0.15, { size: 8.7, bold: true, color: C.text });
  text(slide, "OLLY에서 사용한 관측 stage", 7.25, 1.82, 2.8, 0.15, { size: 8.7, bold: true, color: C.text });
  const mapRows = [
    ["search_docs / vector_search", "retrieve"],
    ["call_openai / call_gemini / local_model", "llm_call"],
    ["format_answer / validation / safety_filter", "postprocess"],
  ];
  mapRows.forEach((r, i) => {
    const y = 2.45 + i * 0.92;
    card(slide, 1.1, y, 3.55, 0.48, { shadow: false });
    text(slide, r[0], 1.35, y + 0.17, 2.9, 0.1, { size: 7, color: C.muted, bold: true });
    text(slide, "계측 시\nStage label로 기록", 5.15, y + 0.08, 1.0, 0.23, { size: 5.7, color: C.muted, align: "center" });
    arrow(slide, 4.65, y + 0.24, 6.7, y + 0.24, C.violet);
    card(slide, 7.1, y, 2.25, 0.48, { fill: C.navy });
    text(slide, r[1], 7.4, y + 0.16, 1.65, 0.1, { size: 8, color: C.white, bold: true, align: "center" });
  });
  slide.addShape(pptx.ShapeType.roundRect, { x: 1.08, y: 5.45, w: 9.6, h: 0.4, rectRadius: 0.04, fill: { color: "EEF5FF" }, line: { color: C.line } });
  text(slide, "관측 데이터  request_id · trace_id · latency · input/output tokens · cost · status · stage durations", 1.3, 5.58, 9.0, 0.1, { size: 6.6, color: C.blue2, bold: true, align: "center" });
  text(slide, "실제 적용 시 기존 코드에 OpenTelemetry 계측을 추가하고, 해당 구간을 OLLY가 해석할 수 있는 stage label로 기록해야 한다.", 1.1, 6.25, 10.3, 0.16, { size: 7, color: C.muted });
  footer(slide, 7);
  addNotes(slide, "핵심은 request_id와 trace_id입니다. 서비스 내부 함수 이름이 다르더라도 retrieve, llm_call, postprocess라는 공통 stage로 기록하면 OLLY가 단계별 병목을 해석할 수 있습니다.");
}

// 8. Operational effects
{
  const slide = pptx.addSlide();
  header(slide, 7, "운영 효과", "OLLY로 얻는 운영 효과", "LLM 요청을 운영자가 추적 가능한 데이터로 바꾼다");
  const effects = [
    ["요청 단위 추적", "request_id와 trace_id로 하나의 요청을\nDashboard · Jaeger · Prometheus까지 연결", C.purple, "01"],
    ["병목 원인 분리", "전체 latency만 보는 것이 아니라\nretrieve · llm_call · postprocess 중 느린 단계를 확인", C.blue2, "02"],
    ["비용 · 토큰 가시화", "input/output token과 cost를 기록해\n토큰 과다 사용과 비용 증가 원인을 파악", C.orange, "03"],
    ["이상 상황 대응", "error나 threshold 초과 상황을 감지하고\nDiscord 알림으로 운영자에게 전달", C.green, "04"],
  ];
  effects.forEach((e, i) => {
    const x = 0.9 + (i % 2) * 5.6;
    const y = 2.08 + Math.floor(i / 2) * 1.75;
    card(slide, x, y, 5.0, 1.18);
    miniIcon(slide, x + 0.32, y + 0.34, ["ID", "S", "#", "A"][i], e[2], "F5F7FF");
    text(slide, e[0], x + 0.88, y + 0.28, 2.3, 0.14, { size: 9, color: C.text, bold: true });
    text(slide, e[1], x + 0.88, y + 0.58, 3.6, 0.3, { size: 6.5, color: C.muted });
    text(slide, e[3], x + 4.42, y + 0.28, 0.35, 0.13, { size: 9, color: "DEE6F4", bold: true, align: "right" });
  });
  footer(slide, 8);
  addNotes(slide, "운영 효과는 네 가지입니다. 요청 단위 추적, 병목 원인 분리, 비용과 토큰 가시화, 그리고 알림 기반 대응입니다.");
}

// 9. Demo scenarios
{
  const slide = pptx.addSlide();
  header(slide, 8, "데모 시나리오", "데모를 위해 정의한 4가지 운영 상황", "각 시나리오는 답변 내용이 아니라 metadata · trace · metric · alert 연결을 확인하기 위한 것이다");
  const sc = [
    ["normal", "정상 요청", "기준 상태 확인\nmetadata 정상 생성", C.green],
    ["slow_retrieve", "검색 단계 병목", "retrieve span 증가\nJaeger에서 단계 확인", C.orange],
    ["high_token", "토큰 과다 사용", "token · cost 증가\n비용 지표로 확인", C.orange],
    ["error", "실패 요청 추적", "error metric · trace\nrequest_id · alert 연결", C.red],
  ];
  sc.forEach((s, i) => {
    const x = 0.85 + i * 3.0;
    card(slide, x, 2.12, 2.35, 3.0);
    pill(slide, s[0], x + 0.25, 2.48, 1.05 + (i === 1 ? 0.35 : 0), s[3]);
    miniIcon(slide, x + 0.85, 3.04, ["✓", "R", "#", "!"][i], s[3], i === 3 ? C.pinkBg : "F7F8FF");
    text(slide, s[1], x + 0.38, 3.7, 1.6, 0.14, { size: 9, bold: true, color: C.text, align: "center" });
    text(slide, "관측 결과", x + 0.4, 4.18, 1.5, 0.1, { size: 6.3, color: C.muted, bold: true, align: "center" });
    text(slide, s[2], x + 0.36, 4.46, 1.65, 0.34, { size: 6.2, color: C.muted, align: "center" });
  });
  footer(slide, 9);
  addNotes(slide, "데모는 normal, slow_retrieve, high_token, error 네 가지입니다. 목적은 답변 품질이 아니라 요청 metadata, trace, metric, alert가 같은 요청으로 연결되는지 확인하는 것입니다.");
}

// 10. Demo flow
{
  const slide = pptx.addSlide();
  header(slide, 9, "데모", "Demo: 4가지 운영 상황을 관측 흐름으로 연결", "요청 생성부터 지표 · trace · 알림까지 하나의 운영 흐름으로 확인");
  card(slide, 1.1, 1.95, 5.1, 3.15, { fill: C.navy });
  pill(slide, "REC", 1.35, 2.2, 0.46, C.red);
  slide.addShape(pptx.ShapeType.ellipse, { x: 3.18, y: 3.05, w: 0.7, h: 0.7, fill: { color: C.violet }, line: { transparency: 100 } });
  text(slide, "▶", 3.42, 3.25, 0.16, 0.1, { size: 14, color: C.white, bold: true, align: "center" });
  text(slide, "데모 영상 · 1:30 - 2:00", 2.25, 4.14, 2.7, 0.14, { size: 9, color: C.white, bold: true, align: "center" });
  text(slide, "발표 당일 영상 삽입 · 핵심 화면 캡처로 대체 가능", 2.02, 4.45, 3.2, 0.12, { size: 6.4, color: "CBD5E1", align: "center" });
  const steps = [
    "Chat UI - 4개 시나리오 요청 생성",
    "Dashboard - Recent Request 수집 확인",
    "Trace - slow_retrieve 병목 확인",
    "Grafana - latency · token · cost 확인",
    "Discord - error 알림 수신",
    "Dashboard - 운영 요약",
  ];
  steps.forEach((s, i) => {
    const y = 1.85 + i * 0.62;
    card(slide, 7.0, y, 4.0, 0.4, { fill: "FFFFFF", shadow: false });
    slide.addShape(pptx.ShapeType.ellipse, { x: 7.15, y: y + 0.09, w: 0.22, h: 0.22, fill: { color: C.violet }, line: { transparency: 100 } });
    text(slide, String(i + 1), 7.15, y + 0.145, 0.22, 0.07, { size: 5, color: C.white, bold: true, align: "center" });
    text(slide, s, 7.55, y + 0.14, 3.2, 0.08, { size: 6.4, color: C.text, bold: true });
  });
  footer(slide, 10);
  addNotes(slide, "데모는 2분 안에 보여줍니다. Chat UI에서 요청을 만들고, Dashboard에서 수집을 확인한 뒤, Jaeger와 Grafana에서 병목과 지표를 확인하고, 마지막으로 Discord 알림까지 보여주는 흐름입니다.");
}

// 11. Measurement
{
  const slide = pptx.addSlide();
  header(slide, 10, "측정 결과 및 검증", "시나리오별 10회 반복으로 관측 신호를 확인했다", "총 50회 요청에서 request_id · trace_id · metric · span 연결 여부를 검증");
  const x = 0.8;
  const y = 1.78;
  const widths = [2.0, 1.05, 1.4, 1.4, 1.35, 3.65];
  const headers = ["검증 시나리오", "에러율", "p50 지연", "p95 지연", "총 토큰", "이상 감지 구간"];
  let cx = x;
  headers.forEach((h, i) => {
    slide.addShape(pptx.ShapeType.rect, { x: cx, y, w: widths[i], h: 0.46, fill: { color: C.navy }, line: { color: C.navy } });
    text(slide, h, cx + 0.08, y + 0.16, widths[i] - 0.16, 0.09, { size: 6.8, color: C.white, bold: true, align: "center" });
    cx += widths[i];
  });
  const rows = [
    ["normal", "0%", "1.47초", "3.02초", "243개", "llm_call (1.23초)"],
    ["slow_retrieve", "0%", "3.96초", "5.93초", "270개", "retrieve (1.80초, 정상 대비 약 12배 증가)"],
    ["slow_llm", "0%", "2.23초", "3.11초", "271개", "llm_call (1.99초)"],
    ["high_token", "0%", "34.58초", "36.86초", "457개", "llm_call (34.35초, 리소스 한계 도달)"],
    ["error", "100%", "0.15초", "0.15초", "0개", "retrieve (HTTP Error 조기 실패)"],
  ];
  rows.forEach((r, ri) => {
    let xx = x;
    const yy = y + 0.46 + ri * 0.62;
    r.forEach((v, ci) => {
      slide.addShape(pptx.ShapeType.rect, { x: xx, y: yy, w: widths[ci], h: 0.62, fill: { color: ri % 2 === 0 ? C.white : "F9FBFF" }, line: { color: C.line } });
      text(slide, v, xx + 0.08, yy + 0.22, widths[ci] - 0.16, 0.09, { size: ci === 5 ? 6.2 : 6.6, color: ci === 0 ? C.text : C.muted, bold: ci === 0 || ci === 5, align: ci === 5 ? "left" : "center" });
      xx += widths[ci];
    });
  });
  slide.addShape(pptx.ShapeType.roundRect, { x: 1.0, y: 5.72, w: 10.85, h: 0.48, rectRadius: 0.04, fill: { color: "EEF5FF" }, line: { color: C.line } });
  text(slide, "검증 기준: 같은 request_id와 trace_id가 Chat UI · Dashboard · Jaeger · Prometheus/Grafana에서 같은 요청을 설명하는가", 1.2, 5.89, 10.4, 0.09, { size: 6.5, color: C.blue2, bold: true, align: "center" });
  footer(slide, 11);
  addNotes(slide, "각 시나리오는 10회씩 반복해 총 50회 요청을 발생시켰습니다. 핵심 검증 기준은 같은 request_id와 trace_id가 Chat UI, Dashboard, Jaeger, Prometheus에서 같은 요청을 설명하는지였습니다.");
}

// 12. Interpretation
{
  const slide = pptx.addSlide();
  header(slide, 11, "결과 해석", "데모에서 운영자가 얻는 판단", "화면이 많다는 것이 아니라, 원인을 단계로 좁힐 수 있다는 점이 핵심");
  const headers = ["시나리오", "관측 결과", "운영자가 할 수 있는 판단"];
  const widths = [2.0, 3.65, 5.05];
  let x0 = 1.0;
  headers.forEach((h, i) => {
    slide.addShape(pptx.ShapeType.rect, { x: x0, y: 1.83, w: widths[i], h: 0.42, fill: { color: C.navy }, line: { color: C.navy } });
    text(slide, h, x0 + 0.1, 1.98, widths[i] - 0.2, 0.08, { size: 6.2, color: C.white, bold: true, align: "center" });
    x0 += widths[i];
  });
  const rows = [
    ["normal", "latency · token · cost 정상", "기준 상태 확인"],
    ["slow_retrieve", "retrieve span 증가", "RAG · 문서 검색 계층 점검"],
    ["slow_llm", "llm_call span 증가", "모델 리소스 · 외부 LLM API 지연 점검"],
    ["high_token", "token · cost 증가", "프롬프트 템플릿 · 검색 문맥 과다 주입 점검"],
    ["error", "error metric · trace 생성", "실패 요청의 원인 trace 추적"],
  ];
  rows.forEach((r, i) => {
    const y = 2.25 + i * 0.66;
    let x = 1.0;
    r.forEach((v, j) => {
      slide.addShape(pptx.ShapeType.roundRect, { x, y, w: widths[j], h: 0.44, rectRadius: 0.03, fill: { color: j === 0 ? ["ECFDF5", "FFFBEB", "EFF6FF", "FFFBEB", "FFF1F2"][i] : C.white }, line: { color: C.line } });
      text(slide, v, x + 0.1, y + 0.15, widths[j] - 0.2, 0.08, { size: 6.7, color: j === 0 ? [C.green, C.orange, C.blue2, C.orange, C.red][i] : C.text, bold: true, align: j === 0 ? "center" : "left" });
      if (j === 2) miniIcon(slide, x + widths[j] - 0.48, y + 0.11, "✓", C.green, "ECFDF5");
      x += widths[j];
    });
  });
  footer(slide, 12);
  addNotes(slide, "데모에서 운영자가 얻는 판단은 병목 원인을 단계로 좁히는 것입니다. retrieve가 느리면 검색 계층, llm_call이 느리면 모델 리소스나 외부 API, high_token이면 프롬프트와 검색 문맥을 점검할 수 있습니다.");
}

// 13. Limitations
{
  const slide = pptx.addSlide();
  header(slide, 12, "한계 및 향후 과제", "현재 MVP의 한계를 명확히 두고, 실무 적용 조건을 정리했다", "검증 범위와 프로덕션 적용 조건을 구분한다");
  card(slide, 0.9, 1.8, 5.15, 4.55);
  text(slide, "현재 한계", 1.22, 2.08, 1.6, 0.16, { size: 9.5, color: C.red, bold: true });
  [
    "로컬 SLM 기반이라 실제 외부 LLM 과금 검증은 아님",
    "10회 반복은 대규모 부하 테스트가 아니라 관측 파이프라인 검증",
    "Prometheus에 request_id를 장기 label로 저장하면 cardinality 문제 가능",
    "raw prompt 저장은 개인정보 · 내부정보 유출 위험",
    "답변 품질 · hallucination 평가는 MVP 범위 밖",
  ].forEach((v, i) => {
    miniIcon(slide, 1.22, 2.58 + i * 0.62, "!", C.red, C.pinkBg);
    text(slide, v, 1.7, 2.66 + i * 0.62, 3.75, 0.12, { size: 6.5, color: C.text, bold: true });
  });
  card(slide, 6.55, 1.8, 5.15, 4.55);
  text(slide, "향후 과제", 6.9, 2.08, 1.6, 0.16, { size: 9.5, color: C.blue2, bold: true });
  [
    "외부 LLM API 및 실제 Vector DB 기반 RAG 서비스 연동",
    "prompt masking · 권한 관리 · 장기 저장소 도입",
    "SLO 기준과 운영 환경용 alert rule 고도화",
    "request_id는 trace/log 중심, metric은 집계 label 중심으로 개선",
    "RAG 근거 일치도 · LLM-as-a-judge 품질 평가 추가",
  ].forEach((v, i) => {
    miniIcon(slide, 6.9, 2.58 + i * 0.62, "→", C.blue2, "EFF6FF");
    text(slide, v, 7.38, 2.66 + i * 0.62, 3.78, 0.12, { size: 6.5, color: C.text, bold: true });
  });
  footer(slide, 13);
  addNotes(slide, "한계는 명확합니다. 로컬 SLM 기반이라 실제 과금 환경을 완전히 재현한 것은 아니고, 10회 반복은 대규모 부하 테스트가 아니라 관측 연결성 검증입니다. 실무 적용에는 보안, 장기 저장, 권한, cardinality 관리가 필요합니다.");
}

// 14. Conclusion
{
  const slide = pptx.addSlide();
  addBg(slide, true);
  text(slide, "결론", 0.66, 0.6, 0.6, 0.14, { size: 7.6, color: C.green, bold: true });
  text(slide, "LLM 시대의 운영 핵심은 “요청 단위 운영 가시성”", 0.66, 0.95, 7.6, 0.4, { size: 20.2, color: C.white, bold: true });
  text(slide, "OLLY는 LLM 요청 하나를 비용 · 지연 · 병목 · 실패 · 알림까지 연결해 보여주는 관측성 MVP입니다.", 0.66, 1.62, 8.3, 0.25, { size: 8.2, color: "DDE7FF" });
  text(slide, "핵심 성과", 0.68, 2.35, 1.2, 0.18, { size: 8.2, color: C.green, bold: true });
  const outcomes = [
    ["요청 연결", "request_id / trace_id로\nChat UI · Dashboard · Jaeger · Prometheus 연결", "1", C.purple],
    ["CNCF 접목", "Kubernetes · OpenTelemetry · Prometheus · Jaeger를\nLLM 운영 흐름에 적용", "2", C.blue2],
    ["운영 판단", "느린 요청, 비용 증가, 실패 요청을\n데이터 기반으로 추적", "3", C.green],
  ];
  outcomes.forEach((o, i) => {
    const x = 0.95 + i * 3.85;
    card(slide, x, 3.18, 3.25, 1.6, { fill: "3A3477", line: "4A438B", lineTrans: 0 });
    miniIcon(slide, x + 0.3, 3.62, ["ID", "C", "✓"][i], C.white, o[3]);
    text(slide, o[2], x + 2.75, 3.42, 0.22, 0.12, { size: 12, color: C.white, bold: true, align: "right" });
    text(slide, o[0], x + 0.3, 4.02, 1.5, 0.12, { size: 8, color: C.white, bold: true });
    text(slide, o[1], x + 0.3, 4.25, 2.6, 0.26, { size: 5.8, color: "CBD5E1" });
  });
  slide.addShape(pptx.ShapeType.roundRect, { x: 0.92, y: 5.75, w: 10.75, h: 0.44, rectRadius: 0.04, fill: { color: "393374" }, line: { transparency: 100 } });
  text(slide, "즉, OLLY는 LLM 서비스를 운영하기 위한 관측성 계층입니다.", 1.22, 5.9, 10.0, 0.09, { size: 6.8, color: "B6F2E5", bold: true });
  text(slide, "OLLY · 오픈소스SW분석 (클라우드) 5팀", 10.25, 6.92, 2.3, 0.12, { size: 5.9, color: "CBD5E1", align: "right" });
  footer(slide, 14, 14, true);
  addNotes(slide, "결론적으로 OLLY는 LLM 서비스를 운영하기 위한 관측성 계층입니다. 기존 챗봇을 대체하지 않고, 요청별 비용, 지연, 병목, 실패, 알림을 연결해 운영자가 데이터 기반으로 판단할 수 있게 합니다.");
}

const out = path.resolve(__dirname, "OLLY_최종발표_가이드라인반영.pptx");
pptx.writeFile({ fileName: out });
