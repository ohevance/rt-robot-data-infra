// ---------------------------------------------------------------------------
// 장표 생성기 — slides.json(내용) → rt-robot-data-infra.pptx
//   node build_deck.js slides.json out.pptx
// 장표 종류(kind): title, section, bullets, two_col, table, image, code, process, chain, kpi, cards, path, compare, closing, diagram(자유 배치 도형 그림), chart(원생 막대 그래프)
// 모든 본문 장표 공통 선택 항목: crumb(위 오른쪽 "지금 어디" 알약), next(아래 "다음 ▶" 다리), foot(각주)
// section 의 flow {from, question, answer} = 앞에서 안 것 → ◇이 장의 질문 → 이 장의 답 (순서도 논리)
// 읽는 순서: THEME → 레이아웃(defineSlideMaster) → 도우미(addTitle, addBullets, ...) → kind 별 함수 → main
// ---------------------------------------------------------------------------
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(path.join(__dirname, "theme_colors.js"));   // 테마 색을 pptx 안에 써 넣는 도우미(같은 폴더)

const THEME = {
  name: "rt-robot-data-infra",
  headFontFace: "Malgun Gothic",
  bodyFontFace: "Malgun Gothic",
  colors: {
    dk1: "1F2A30", lt1: "FFFFFF", dk2: "0F766E", lt2: "EEF4F3",
    accent1: "0F766E", accent2: "F59E0B", accent3: "475569", accent4: "DC2626", accent5: "2563EB", accent6: "7C3AED",
    hlink: "0F766E", folHlink: "7C3AED",
  },
};
const CODE_FONT = "Consolas";
const W = 13.333, H = 7.5;
const MX = 0.5;                 // 좌우 여백
const TITLE_Y = 0.32, TITLE_H = 0.85;
const BODY_Y = 1.35, BODY_H = 5.25;   // 본문 영역 (아래 0.3" 은 '다음 ▶' 다리, 그 아래 0.6" 은 푸터)
const BRIDGE_Y = BODY_Y + BODY_H + 0.04; // 6.64: '다음 ▶' 다리 줄
const BODY_END = BODY_Y + BODY_H;         // 6.60

function hex(c) { return THEME.colors[c]; }

// ----- 순서도 길잡이: 위 오른쪽 '지금 어디' 알약, 아래 '다음 ▶' 다리 -----
function addNav(pres, slide, s) {
  if (s.crumb) {
    const cw = 6.2;
    slide.addText(s.crumb, { x: W - MX - cw, y: 0.05, w: cw, h: 0.24, fontSize: emWidth(s.crumb) > 46 ? 8 : 9, color: hex("dk2"), fill: { color: hex("lt2") }, align: "right", valign: "middle", isTextBox: true, margin: 4, shape: pres.ShapeType.roundRect, rectRadius: 0.1 });
  }
  if (s.next) {
    const tw = W - 2 * MX, lw = 0.95;
    const x0 = MX;
    slide.addText("다음 ▶", { shape: pres.ShapeType.homePlate, x: x0, y: BRIDGE_Y, w: lw, h: 0.3, fill: { color: hex("accent2") }, line: { color: hex("accent2"), width: 0 }, fontSize: 9.5, bold: true, color: hex("lt1"), align: "center", valign: "middle", margin: 2 });
    slide.addText(s.next, { x: x0 + lw + 0.05, y: BRIDGE_Y, w: tw - lw - 0.05, h: 0.3, fontSize: emWidth(s.next) > 88 ? 8.5 : 9.5, color: hex("dk1"), fill: { color: "FFF7E6" }, line: { color: hex("accent2"), width: 0.75 }, valign: "middle", isTextBox: true, margin: 4 });
  }
}

// ----- 텍스트 도우미 -----
// 글자 폭 어림: 영문·숫자 0.55 em, 한글·기호 1.0 em (Consolas/Malgun Gothic 기준). 상자 맞춤 계산에 쓴다
function emWidth(str) {
  let w = 0;
  for (const ch of String(str)) w += ch.charCodeAt(0) < 0x2000 ? 0.62 : 1.05;   // 넉넉하게(LibreOffice 대체 글꼴 기준) — 넘치는 것보다 조금 작은 것이 낫다
  return w;
}
function paras(lines, opts) {
  // lines: ["문장", {text, sub:true}, ...] → pptxgenjs 텍스트 배열
  const out = [];
  lines.forEach((ln, i) => {
    const last = i === lines.length - 1;
    if (typeof ln === "string") {
      out.push({ text: ln, options: Object.assign({ bullet: true, breakLine: !last, paraSpaceAfter: 6 }, opts || {}) });
    } else {
      const o = Object.assign({ bullet: ln.sub ? { indent: 18 } : true, breakLine: !last, paraSpaceAfter: 4 }, opts || {});
      if (ln.sub) { o.indentLevel = 1; o.fontSize = (opts && opts.fontSize ? opts.fontSize : 14) - 2; o.color = hex("accent3"); }
      if (ln.bold) o.bold = true;
      out.push({ text: ln.text, options: o });
    }
  });
  return out;
}

function addTitle(slide, text, dark) {
  slide.addText(text, { placeholder: "title" });
}

function addFooterNote(slide, s) {
  if (s.foot) {
    slide.addText(s.foot, { x: MX, y: 6.96, w: W - 2 * MX - 2.7, h: 0.4, fontSize: 9.5, color: hex("accent3"), isTextBox: true, margin: 0, valign: "top" });
  }
}

function addBulletsBox(slide, lines, x, y, w, h, fontSize) {
  slide.addText(paras(lines, { fontSize: fontSize || 14 }), { x, y, w, h, fontSize: fontSize || 14, color: hex("dk1"), valign: "top", isTextBox: true, margin: 4, paraSpaceAfter: 6 });
}

function addImageFit(slide, img, x, y, w, h) {
  const p = path.resolve(__dirname, img);
  slide.addImage({ path: p, x, y, w, h, sizing: { type: "contain", w, h } });
}

function addCode(slide, codeLines, x, y, w, h, fontSize) {
  const runs = codeLines.map((ln, i) => ({ text: ln === "" ? " " : ln, options: { breakLine: i < codeLines.length - 1 } }));
  // 글자 크기 자동 맞춤: 긴 줄은 접힌다고 보고(접힌 줄 수까지 세서) 전체 높이가 상자를 넘지 않는 가장 큰 크기를 고른다
  // 1.2 = 줄 간격 배수. 글자 폭은 emWidth(영문 0.55 em, 한글 1 em)
  const usableW = w - 0.25, usableH = h - 0.22;
  const widths = codeLines.map((l) => emWidth(l));
  // 짧은 코드는 조금 키운다(상자가 비어 보이지 않게): 14줄 이하 13pt, 22줄 이하 12pt 까지
  const n = codeLines.length;
  const cap = Math.max(fontSize || 11, n <= 14 ? 13 : n <= 22 ? 12 : 0);
  let fs = 7;
  for (let cand = cap; cand >= 7; cand -= 0.5) {
    const emPerLine = (usableW * 72) / cand;
    let visual = 0;
    for (const ew of widths) visual += Math.max(1, Math.ceil(ew / emPerLine));
    if ((visual * 1.2 * cand) / 72 <= usableH) { fs = cand; break; }
  }
  slide.addText(runs, { x, y, w, h, fontFace: CODE_FONT, fontSize: fs, color: hex("dk1"), fill: { color: "F3F4F6" },
    line: { color: "D1D5DB", width: 0.75 }, valign: "top", isTextBox: true, margin: 8 });
  return fs;
}

function addLabel(slide, text, x, y, w, h, opts) {
  slide.addText(text, Object.assign({ x, y, w, h, fontSize: 12, color: hex("dk1"), isTextBox: true, margin: 2, valign: "middle" }, opts || {}));
}

// ----- kind 별 -----
function slideTitle(pres, s) {
  const slide = pres.addSlide({ masterName: "DARK", sectionTitle: s.section });
  slide.addText(s.title, { x: 0.8, y: 2.0, w: W - 1.6, h: 1.4, fontSize: 40, bold: true, color: hex("lt1"), isTextBox: true, margin: 0 });
  if (s.subtitle) slide.addText(s.subtitle, { x: 0.8, y: 3.5, w: W - 1.6, h: 1.0, fontSize: 20, color: "CADCD9", isTextBox: true, margin: 0 });
  if (s.meta) slide.addText(s.meta, { x: 0.8, y: 5.6, w: W - 1.6, h: 0.8, fontSize: 13, color: "9FB3AF", isTextBox: true, margin: 0 });
  // 모티프: 오른쪽 아래 둥근 원 3개 (링 버퍼 느낌)
  [[11.2, 5.4, 1.1], [12.0, 6.2, 0.6], [10.7, 6.4, 0.4]].forEach(([x, y, d]) => slide.addShape(pres.ShapeType.ellipse, { x, y, w: d, h: d, fill: { color: hex("accent1"), transparency: 35 }, line: { color: hex("accent1"), width: 0 } }));
  return slide;
}

function slideSection(pres, s) {
  const slide = pres.addSlide({ masterName: "DARK", sectionTitle: s.section });
  slide.addText(s.num, { x: 0.8, y: 0.55, w: 3, h: 1.1, fontSize: 54, bold: true, color: hex("accent2"), isTextBox: true, margin: 0 });
  slide.addText(s.title, { x: 0.8, y: 1.55, w: W - 1.6, h: 1.0, fontSize: 32, bold: true, color: hex("lt1"), isTextBox: true, margin: 0, valign: "middle" });
  if (s.subtitle) slide.addText(s.subtitle, { x: 0.8, y: 2.55, w: W - 1.6, h: 0.75, fontSize: 16, color: "CADCD9", isTextBox: true, margin: 0, valign: "top" });
  // 순서도 한 줄: [앞에서 안 것] → ◇[이 장의 질문] → [이 장의 답]
  if (s.flow) {
    const y = 3.45, h = 1.35;
    const boxW = 3.9, qW = 3.5, gap = 0.55;
    const x1 = 0.8, x2 = x1 + boxW + gap, x3 = x2 + qW + gap;
    const arrow = (ax) => slide.addShape(pres.ShapeType.line, { x: ax + 0.05, y: y + h / 2, w: gap - 0.1, h: 0, line: { color: hex("accent2"), width: 2, endArrowType: "triangle" } });
    slide.addText("앞에서 안 것", { x: x1, y: y - 0.3, w: boxW, h: 0.28, fontSize: 10, color: "9FB3AF", isTextBox: true, margin: 0 });
    slide.addText(s.flow.from, { shape: pres.ShapeType.roundRect, rectRadius: 0.1, x: x1, y, w: boxW, h, fill: { color: "2A3B42" }, line: { color: "9FB3AF", width: 1 }, fontSize: 11.5, color: hex("lt1"), align: "left", valign: "middle", margin: 8 });
    arrow(x1 + boxW);
    slide.addText("이 장의 질문", { x: x2, y: y - 0.3, w: qW, h: 0.28, fontSize: 10, color: hex("accent2"), isTextBox: true, margin: 0, align: "center" });
    slide.addText(s.flow.question, { shape: pres.ShapeType.diamond, x: x2, y: y - 0.25, w: qW, h: h + 0.5, fill: { color: "3B2F12" }, line: { color: hex("accent2"), width: 1.5 }, fontSize: 10.5, bold: true, color: "FDE68A", align: "center", valign: "middle", margin: 1 });
    arrow(x2 + qW);
    slide.addText("이 장의 답", { x: x3, y: y - 0.3, w: W - 0.8 - x3, h: 0.28, fontSize: 10, color: "9FB3AF", isTextBox: true, margin: 0 });
    slide.addText(s.flow.answer, { shape: pres.ShapeType.roundRect, rectRadius: 0.1, x: x3, y, w: W - 0.8 - x3, h, fill: { color: hex("accent1") }, line: { color: hex("accent1"), width: 0 }, fontSize: 11.5, color: hex("lt1"), align: "left", valign: "middle", margin: 8 });
  }
  if (s.agenda) {
    const ay = s.flow ? 5.25 : 3.5;
    slide.addText("이 장의 차례", { x: 0.8, y: ay - 0.05, w: 4, h: 0.3, fontSize: 10, color: "9FB3AF", isTextBox: true, margin: 0 });
    slide.addText(paras(s.agenda, { fontSize: 12.5, color: "CADCD9" }), { x: 0.8, y: ay + 0.25, w: W - 1.6, h: 6.95 - ay - 0.25, fontSize: 12.5, color: "CADCD9", valign: "top", isTextBox: true, margin: 0 });
  }
  return slide;
}

function slideBullets(pres, s) {
  const slide = pres.addSlide({ masterName: "CONTENT", sectionTitle: s.section });
  addTitle(slide, s.title);
  if (s.image) {
    const iw = s.imageW || 6.0;
    addBulletsBox(slide, s.bullets, MX, BODY_Y, W - 2 * MX - iw - 0.3, BODY_H, s.fontSize);
    addImageFit(slide, s.image, W - MX - iw, BODY_Y, iw, BODY_H);
  } else if (s.callout) {
    addBulletsBox(slide, s.bullets, MX, BODY_Y, 8.0, BODY_H, s.fontSize);
    // 말풍선 상자 높이는 글 양에 맞춘다(제목 줄 수 + 본문 줄 수 어림)
    const titleLines = Math.max(1, Math.ceil(emWidth(s.callout.title) / 22));
    const bodyLines = String(s.callout.text).split("\n").reduce((a, ln) => a + Math.max(1, Math.ceil(emWidth(ln) / 26)), 0);
    const titleH = 0.22 + titleLines * 0.26;
    const bodyH = Math.min(BODY_H - 0.6 - titleH, 0.2 + bodyLines * 0.22);
    const boxH = Math.min(BODY_H - 0.2, titleH + bodyH + 0.35);
    slide.addShape(pres.ShapeType.roundRect, { x: 8.9, y: BODY_Y + 0.1, w: 3.9, h: boxH, fill: { color: hex("lt2") }, line: { color: hex("accent1"), width: 1 }, rectRadius: 0.15 });
    slide.addText(s.callout.title, { x: 9.1, y: BODY_Y + 0.22, w: 3.5, h: titleH, fontSize: 14, bold: true, color: hex("accent1"), isTextBox: true, margin: 0, valign: "top" });
    slide.addText(s.callout.text, { x: 9.1, y: BODY_Y + 0.22 + titleH, w: 3.5, h: bodyH, fontSize: 12, color: hex("dk1"), isTextBox: true, margin: 0, valign: "top" });
  } else {
    addBulletsBox(slide, s.bullets, MX, BODY_Y, W - 2 * MX, BODY_H, s.fontSize);
  }
  addFooterNote(slide, s);
  return slide;
}

function slideTwoCol(pres, s) {
  const slide = pres.addSlide({ masterName: "CONTENT", sectionTitle: s.section });
  addTitle(slide, s.title);
  const cw = (W - 2 * MX - 0.4) / 2;
  [s.left, s.right].forEach((col, i) => {
    const x = MX + i * (cw + 0.4);
    slide.addShape(pres.ShapeType.roundRect, { x, y: BODY_Y, w: cw, h: BODY_H, fill: { color: i === 0 ? hex("lt2") : "FFF7E6" }, line: { color: i === 0 ? hex("accent1") : hex("accent2"), width: 1 }, rectRadius: 0.12 });
    slide.addText(col.head, { x: x + 0.2, y: BODY_Y + 0.15, w: cw - 0.4, h: 0.5, fontSize: 17, bold: true, color: i === 0 ? hex("accent1") : "B45309", isTextBox: true, margin: 0 });
    addBulletsBox(slide, col.bullets, x + 0.15, BODY_Y + 0.7, cw - 0.3, BODY_H - 0.85, s.fontSize || 13);
  });
  addFooterNote(slide, s);
  return slide;
}

function slideTable(pres, s) {
  const slide = pres.addSlide({ masterName: "CONTENT", sectionTitle: s.section });
  addTitle(slide, s.title);
  const rows = s.rows.map((r, ri) => r.map((c) => ({ text: String(c), options: ri === 0 ? { bold: true, color: hex("lt1"), fill: { color: hex("accent1") } } : {} })));
  const fontSize = s.fontSize || (s.rows.length > 10 ? 10 : 12);
  const tw = s.tableW || (W - 2 * MX);
  const opts = { x: MX, y: BODY_Y, w: tw, fontSize, color: hex("dk1"), border: { type: "solid", color: "CBD5E1", pt: 0.5 }, valign: "middle", autoPage: false, margin: 3 };
  if (s.colW) opts.colW = s.colW;
  slide.addTable(rows, opts);
  if (s.note) slide.addText(s.note, { x: MX, y: BODY_END - 0.55, w: W - 2 * MX, h: 0.55, fontSize: 11, color: hex("accent3"), isTextBox: true, margin: 0 });
  if (s.side) {
    addBulletsBox(slide, s.side, MX + tw + 0.3, BODY_Y, W - 2 * MX - tw - 0.3, BODY_H, 12);
  }
  addFooterNote(slide, s);
  return slide;
}

function slideImage(pres, s) {
  const slide = pres.addSlide({ masterName: "CONTENT", sectionTitle: s.section });
  addTitle(slide, s.title);
  if (s.bullets) {
    const bw = s.bulletsW || 3.9;
    addImageFit(slide, s.image, MX, BODY_Y, W - 2 * MX - bw - 0.3, BODY_H - (s.caption ? 0.5 : 0));
    addBulletsBox(slide, s.bullets, W - MX - bw, BODY_Y, bw, BODY_H, 12);
  } else {
    addImageFit(slide, s.image, MX, BODY_Y, W - 2 * MX, BODY_H - (s.caption ? 0.5 : 0));
  }
  if (s.caption) slide.addText(s.caption, { x: MX, y: BODY_END - 0.45, w: W - 2 * MX, h: 0.45, fontSize: 11, color: hex("accent3"), isTextBox: true, margin: 0 });
  addFooterNote(slide, s);
  return slide;
}

function slideCode(pres, s) {
  const slide = pres.addSlide({ masterName: "CONTENT", sectionTitle: s.section });
  addTitle(slide, s.title);
  const sideW = s.points ? 4.3 : 0;
  const cw = W - 2 * MX - (sideW ? sideW + 0.3 : 0);
  if (s.file) slide.addText(s.file, { x: MX, y: BODY_Y - 0.05, w: cw, h: 0.35, fontSize: 11, fontFace: CODE_FONT, color: hex("accent1"), isTextBox: true, margin: 0 });
  addCode(slide, s.code, MX, BODY_Y + 0.3, cw, BODY_H - 0.3, s.codeSize || 11);
  if (s.points) {
    slide.addText("읽는 포인트", { x: W - MX - sideW, y: BODY_Y - 0.05, w: sideW, h: 0.35, fontSize: 13, bold: true, color: hex("accent1"), isTextBox: true, margin: 0 });
    addBulletsBox(slide, s.points, W - MX - sideW, BODY_Y + 0.3, sideW, BODY_H - 0.3, s.pointsSize || 12);   // 포인트가 길면 장표에서 pointsSize 로 줄인다
  }
  addFooterNote(slide, s);
  return slide;
}

// 가로 셰브론 n개 + 아래 설명
function slideProcess(pres, s) {
  const slide = pres.addSlide({ masterName: "CONTENT", sectionTitle: s.section });
  addTitle(slide, s.title);
  const n = s.steps.length;
  const gap = 0.12;
  const cw = (W - 2 * MX - gap * (n - 1)) / n;
  const colors = ["accent1", "accent5", "accent6", "accent2", "accent4", "accent3", "dk2"];
  s.steps.forEach((st, i) => {
    const x = MX + i * (cw + gap);
    // 8칸부터는 칸이 좁아 셰브론(양쪽이 파인 모양) 안에 머리글이 안 들어간다 → 전부 오각형(homePlate)으로
    slide.addText(`${i + 1}. ${st.head}`, { shape: (i === 0 || n > 7) ? pres.ShapeType.homePlate : pres.ShapeType.chevron, x, y: BODY_Y, w: cw, h: 0.95, fill: { color: hex(colors[i % colors.length]) }, line: { color: hex(colors[i % colors.length]), width: 0 }, fontSize: n > 7 ? 10 : n > 5 ? 11 : 13, bold: true, color: hex("lt1"), align: "center", valign: "middle", margin: 4 });   // 8칸이면 머리글을 더 줄인다
    slide.addText(paras(st.lines, { fontSize: n > 7 ? 10 : n > 5 ? 10.5 : 12 }), { x, y: BODY_Y + 1.1, w: cw, h: BODY_H - 1.2, fontSize: n > 7 ? 10 : n > 5 ? 10.5 : 12, color: hex("dk1"), valign: "top", isTextBox: true, margin: 3 });
  });
  addFooterNote(slide, s);
  return slide;
}

// 뱀 모양 흐름: 상자(실험) ◇ 마름모(기준) ● 끝. 한 줄에 perRow 개, 화살표 위에 답
function slideChain(pres, s) {
  const slide = pres.addSlide({ masterName: "CONTENT", sectionTitle: s.section });
  addTitle(slide, s.title);
  const items = s.items;
  const perRow = s.perRow || 4;
  const rows = Math.ceil(items.length / perRow);
  const areaH = BODY_H - (s.bottom ? 1.1 : 0);
  const rowH = areaH / rows;
  const nodeH = Math.min(s.nodeH || 1.25, rowH - 0.45);
  const arrowW = s.arrowW || (perRow >= 4 ? 1.35 : 1.05);
  const nodeW = (W - 2 * MX - arrowW * (perRow - 1)) / perRow;
  items.forEach((it, i) => {
    const r = Math.floor(i / perRow);
    let c = i % perRow;
    const reverse = r % 2 === 1;        // 뱀: 홀수 줄은 오른쪽 → 왼쪽
    if (reverse) c = perRow - 1 - c;
    const x = MX + c * (nodeW + arrowW);
    const y = BODY_Y + r * rowH + (rowH - nodeH) / 2 - 0.1;
    let shape = pres.ShapeType.roundRect, fill = hex("lt2"), line = hex("accent1"), color = hex("dk1"), fs = 11;
    if (it.kind === "q") { shape = pres.ShapeType.diamond; fill = "FFF7E6"; line = hex("accent2"); fs = 10; }      // 기준(판단)
    if (it.kind === "end") { shape = pres.ShapeType.roundRect; fill = hex("accent1"); line = hex("accent1"); color = hex("lt1"); } // 결론
    if (it.kind === "fail") { shape = pres.ShapeType.roundRect; fill = "FEE2E2"; line = hex("accent4"); }           // 실패·원인
    if (it.kind === "in") { shape = pres.ShapeType.roundRect; fill = "F1F5F9"; line = hex("accent3"); }             // 앞 단계에서 들어온 것
    if (it.kind === "do") { shape = pres.ShapeType.roundRect; fill = "EFF6FF"; line = hex("accent5"); }             // 확인 방법(코드·시험)
    if (it.kind === "out") { shape = pres.ShapeType.roundRect; fill = "FFFFFF"; line = hex("accent6"); }            // 결과(숫자)
    const o = { shape, x, y, w: nodeW, h: nodeH, fill: { color: fill }, line: { color: line, width: 1.25 }, fontSize: it.fs || fs, color, align: "center", valign: "middle", margin: it.kind === "q" ? 1 : 4, bold: it.kind === "end" };
    if (shape === pres.ShapeType.roundRect) o.rectRadius = 0.1;
    if (it.label) slide.addText(it.label, { x, y: y - 0.26, w: nodeW, h: 0.24, fontSize: 9, color: line, align: "center", isTextBox: true, margin: 0, valign: "bottom" });
    slide.addText(it.text, o);
    // 다음 항목으로 화살표
    if (i < items.length - 1) {
      const nr = Math.floor((i + 1) / perRow);
      const label = it.answer || "";
      if (nr === r) {
        const ax = reverse ? x - arrowW : x + nodeW;
        slide.addShape(pres.ShapeType.line, { x: ax + 0.05, y: y + nodeH / 2, w: arrowW - 0.1, h: 0, line: { color: hex("accent3"), width: 1.5, endArrowType: "triangle" }, flipH: reverse });
        // 답은 화살표 바로 아래, 화살표 폭 안에서만(옆 상자를 덮지 않게). 길면 글자를 줄인다
        if (label) slide.addText(label, { x: ax + 0.02, y: y + nodeH / 2 + 0.04, w: arrowW - 0.04, h: nodeH / 2 + 0.35, fontSize: emWidth(label) > 30 ? 8 : 8.5, color: hex("accent4"), align: "center", isTextBox: true, margin: 0, valign: "top" });
      } else {
        // 아래로 (같은 열). 답은 화살표 옆, 빈 쪽(오른쪽 끝 열이면 왼쪽, 왼쪽 끝 열이면 오른쪽)에
        const ay = y + nodeH;
        slide.addShape(pres.ShapeType.line, { x: x + nodeW / 2, y: ay + 0.03, w: 0, h: rowH - nodeH - 0.06, line: { color: hex("accent3"), width: 1.5, endArrowType: "triangle" } });
        if (label) {
          const toLeft = !reverse;   // 짝수 줄 끝 = 오른쪽 끝 열 → 왼쪽에 쓴다
          const lw = nodeW / 2 + arrowW - 0.1;
          slide.addText(label, { x: toLeft ? x + nodeW / 2 - lw - 0.06 : x + nodeW / 2 + 0.08, y: ay + 0.02, w: lw, h: rowH - nodeH - 0.05, fontSize: 8.5, color: hex("accent4"), align: toLeft ? "right" : "left", isTextBox: true, margin: 0, valign: "middle" });
        }
      }
    }
  });
  if (s.bottom) {
    slide.addShape(pres.ShapeType.roundRect, { x: MX, y: BODY_Y + areaH + 0.05, w: W - 2 * MX, h: 0.95, fill: { color: "F8FAFC" }, line: { color: "CBD5E1", width: 0.75 }, rectRadius: 0.08 });
    slide.addText(s.bottom, { x: MX + 0.15, y: BODY_Y + areaH + 0.1, w: W - 2 * MX - 0.3, h: 0.85, fontSize: 12, color: hex("dk1"), isTextBox: true, margin: 2, valign: "middle" });
  }
  addFooterNote(slide, s);
  return slide;
}

// 큰 숫자 3~4개 + 아래 설명
function slideKpi(pres, s) {
  const slide = pres.addSlide({ masterName: "CONTENT", sectionTitle: s.section });
  addTitle(slide, s.title);
  const n = s.kpis.length;
  const gap = 0.3;
  const cw = (W - 2 * MX - gap * (n - 1)) / n;
  s.kpis.forEach((k, i) => {
    const x = MX + i * (cw + gap);
    slide.addShape(pres.ShapeType.roundRect, { x, y: BODY_Y, w: cw, h: 2.3, fill: { color: hex("lt2") }, line: { color: hex("accent1"), width: 1 }, rectRadius: 0.12 });
    slide.addText(k.value, { x: x + 0.1, y: BODY_Y + 0.15, w: cw - 0.2, h: 1.2, fontSize: emWidth(k.value) > 8 ? (emWidth(k.value) > 11 ? 22 : 24) : 40, bold: true, color: hex("accent1"), align: "center", valign: "middle", isTextBox: true, margin: 0 });
    slide.addText(k.label, { x: x + 0.1, y: BODY_Y + 1.35, w: cw - 0.2, h: 0.85, fontSize: 12, color: hex("dk1"), align: "center", valign: "top", isTextBox: true, margin: 0 });
  });
  if (s.bullets) addBulletsBox(slide, s.bullets, MX, BODY_Y + 2.55, W - 2 * MX, BODY_H - 2.6, s.fontSize || 13);
  addFooterNote(slide, s);
  return slide;
}

// 카드 격자 (2×2 또는 2×3)
function slideCards(pres, s) {
  const slide = pres.addSlide({ masterName: "CONTENT", sectionTitle: s.section });
  addTitle(slide, s.title);
  const cols = s.cols || (s.cards.length > 4 ? 3 : 2);
  const rows = Math.ceil(s.cards.length / cols);
  const gap = 0.25;
  const cw = (W - 2 * MX - gap * (cols - 1)) / cols;
  const ch = (BODY_H - gap * (rows - 1)) / rows;
  const colors = ["accent1", "accent5", "accent2", "accent6", "accent4", "accent3"];
  s.cards.forEach((c, i) => {
    const x = MX + (i % cols) * (cw + gap);
    const y = BODY_Y + Math.floor(i / cols) * (ch + gap);
    slide.addShape(pres.ShapeType.roundRect, { x, y, w: cw, h: ch, fill: { color: "FFFFFF" }, line: { color: "CBD5E1", width: 1 }, rectRadius: 0.1, shadow: { type: "outer", color: "000000", blur: 3, offset: 1, angle: 45, opacity: 0.12 } });
    slide.addShape(pres.ShapeType.ellipse, { x: x + 0.18, y: y + 0.18, w: 0.42, h: 0.42, fill: { color: hex(colors[i % colors.length]) }, line: { color: hex(colors[i % colors.length]), width: 0 } });
    slide.addText(String(c.icon || i + 1), { x: x + 0.18, y: y + 0.18, w: 0.42, h: 0.42, fontSize: 13, bold: true, color: hex("lt1"), align: "center", valign: "middle", isTextBox: true, margin: 0 });
    slide.addText(c.head, { x: x + 0.7, y: y + 0.15, w: cw - 0.85, h: 0.5, fontSize: 14, bold: true, color: hex("dk1"), isTextBox: true, margin: 0, valign: "middle" });
    slide.addText(paras(c.lines, { fontSize: 11.5 }), { x: x + 0.15, y: y + 0.72, w: cw - 0.3, h: ch - 0.8, fontSize: 11.5, color: hex("dk1"), valign: "top", isTextBox: true, margin: 2 });
  });
  addFooterNote(slide, s);
  return slide;
}

// 번호 붙은 단계(길). 2줄 뱀, 상자 안: 번호 · 제목 · 파일:함수
function slidePath(pres, s) {
  const slide = pres.addSlide({ masterName: "CONTENT", sectionTitle: s.section });
  addTitle(slide, s.title);
  const items = s.stages;
  const perRow = s.perRow || 5;
  const rows = Math.ceil(items.length / perRow);
  const arrowW = 0.5;
  const nodeW = (W - 2 * MX - arrowW * (perRow - 1)) / perRow;
  const areaH = BODY_H - (s.bottom ? 1.0 : 0);
  const rowH = areaH / rows;
  const nodeH = Math.min(1.9, rowH - 0.5);
  const colors = ["accent5", "accent5", "accent1", "accent1", "accent1", "accent6", "accent1", "accent1", "accent2", "accent2"];
  items.forEach((it, i) => {
    const r = Math.floor(i / perRow);
    let c = i % perRow;
    const reverse = r % 2 === 1;
    if (reverse) c = perRow - 1 - c;
    const x = MX + c * (nodeW + arrowW);
    const y = BODY_Y + r * rowH + (rowH - nodeH) / 2 - 0.05;
    const col = hex(it.color || colors[i % colors.length]);
    slide.addShape(pres.ShapeType.roundRect, { x, y, w: nodeW, h: nodeH, fill: { color: "FFFFFF" }, line: { color: col, width: 1.5 }, rectRadius: 0.1 });
    slide.addShape(pres.ShapeType.ellipse, { x: x + 0.1, y: y + 0.1, w: 0.4, h: 0.4, fill: { color: col }, line: { color: col, width: 0 } });
    slide.addText(String(i + 1), { x: x + 0.1, y: y + 0.1, w: 0.4, h: 0.4, fontSize: 12, bold: true, color: hex("lt1"), align: "center", valign: "middle", isTextBox: true, margin: 0 });
    slide.addText(it.head, { x: x + 0.55, y: y + 0.08, w: nodeW - 0.62, h: 0.48, fontSize: 11.5, bold: true, color: hex("dk1"), isTextBox: true, margin: 0, valign: "middle" });
    slide.addText(it.text, { x: x + 0.1, y: y + 0.6, w: nodeW - 0.2, h: nodeH - 1.0, fontSize: 10, color: hex("dk1"), isTextBox: true, margin: 0, valign: "top" });
    slide.addText(it.ref, { x: x + 0.1, y: y + nodeH - 0.42, w: nodeW - 0.2, h: 0.4, fontSize: 8.5, fontFace: CODE_FONT, color: col, isTextBox: true, margin: 0, valign: "bottom" });
    if (i < items.length - 1) {
      const nr = Math.floor((i + 1) / perRow);
      if (nr === r) {
        const ax = reverse ? x - arrowW : x + nodeW;
        slide.addShape(pres.ShapeType.line, { x: ax + 0.04, y: y + nodeH / 2, w: arrowW - 0.08, h: 0, line: { color: hex("accent3"), width: 1.75, endArrowType: "triangle" }, flipH: reverse });
      } else {
        slide.addShape(pres.ShapeType.line, { x: x + nodeW / 2, y: y + nodeH + 0.03, w: 0, h: rowH - nodeH - 0.06, line: { color: hex("accent3"), width: 1.75, endArrowType: "triangle" } });
      }
    }
  });
  if (s.bottom) {
    slide.addText(s.bottom, { x: MX, y: BODY_Y + areaH + 0.05, w: W - 2 * MX, h: 0.9, fontSize: 12, color: hex("dk1"), fill: { color: "F8FAFC" }, line: { color: "CBD5E1", width: 0.75 }, isTextBox: true, margin: 6, valign: "middle" });
  }
  addFooterNote(slide, s);
  return slide;
}

// 전/후 또는 A/B 비교 (가운데 화살표)
function slideCompare(pres, s) {
  const slide = pres.addSlide({ masterName: "CONTENT", sectionTitle: s.section });
  addTitle(slide, s.title);
  const cw = (W - 2 * MX - 1.2) / 2;
  const colors = [hex("accent3"), hex("accent1")];
  [s.left, s.right].forEach((col, i) => {
    const x = MX + i * (cw + 1.2);
    slide.addShape(pres.ShapeType.roundRect, { x, y: BODY_Y, w: cw, h: BODY_H, fill: { color: i === 0 ? "F8FAFC" : hex("lt2") }, line: { color: colors[i], width: 1.25 }, rectRadius: 0.12 });
    slide.addText(col.head, { x: x + 0.2, y: BODY_Y + 0.15, w: cw - 0.4, h: 0.5, fontSize: 17, bold: true, color: colors[i], isTextBox: true, margin: 0 });
    if (col.big) slide.addText(col.big, { x: x + 0.2, y: BODY_Y + 0.7, w: cw - 0.4, h: 1.0, fontSize: 34, bold: true, color: colors[i], isTextBox: true, margin: 0 });
    addBulletsBox(slide, col.bullets, x + 0.15, BODY_Y + (col.big ? 1.8 : 0.75), cw - 0.3, BODY_H - (col.big ? 1.9 : 0.85), 12.5);
  });
  slide.addShape(pres.ShapeType.rightArrow, { x: MX + cw + 0.15, y: BODY_Y + BODY_H / 2 - 0.4, w: 0.9, h: 0.8, fill: { color: hex("accent2") }, line: { color: hex("accent2"), width: 0 } });
  addFooterNote(slide, s);
  return slide;
}

function slideClosing(pres, s) {
  const slide = pres.addSlide({ masterName: "DARK", sectionTitle: s.section });
  slide.addText(s.title, { x: 0.8, y: 1.6, w: W - 1.6, h: 1.2, fontSize: 34, bold: true, color: hex("lt1"), isTextBox: true, margin: 0 });
  slide.addText(paras(s.bullets, { fontSize: 16, color: "CADCD9" }), { x: 0.8, y: 3.0, w: W - 1.6, h: 3.5, fontSize: 16, color: "CADCD9", valign: "top", isTextBox: true, margin: 0 });
  return slide;
}


// ----- 자유 배치 그림(diagram): 도형 + 화살표 + 글. 좌표(인치)는 본문 영역 기준(0,0 = 본문 왼쪽 위, 폭 12.33, 높이 BODY_H) -----
// s.shapes: [{id?, type, x, y, w, h, text, tone?, fs?, bold?, color?, align?}]
//   type: rect round diamond cyl hex ellipse chevron cloud cube doc disk callout arrowR folded wave homePlate
//   tone: mint(기본) blue amber gray red purple dark white  — 채움색/선색 묶음
// s.arrows: [{from: id|{x,y}, to: id|{x,y}, label?, dashed?, tone?, width?, noHead?}]  id 면 상자 가장자리에서 자동으로 잇는다
// s.texts:  [{x, y, w, h, text, fs?, color?, align?, bold?, fill?}]
// s.legend: 아래 설명 상자 글(선택)
const TONES = {
  mint: { fill: "EEF4F3", line: "0F766E", color: "1F2A30" },
  blue: { fill: "EFF6FF", line: "2563EB", color: "1F2A30" },
  amber: { fill: "FFF7E6", line: "F59E0B", color: "1F2A30" },
  gray: { fill: "F1F5F9", line: "475569", color: "1F2A30" },
  red: { fill: "FEE2E2", line: "DC2626", color: "1F2A30" },
  purple: { fill: "F3E8FF", line: "7C3AED", color: "1F2A30" },
  dark: { fill: "0F766E", line: "0F766E", color: "FFFFFF" },
  navy: { fill: "1F2A30", line: "1F2A30", color: "FFFFFF" },
  white: { fill: "FFFFFF", line: "94A3B8", color: "1F2A30" },
  none: { fill: null, line: null, color: "1F2A30" },
};
function shapeOf(pres, type) {
  const m = { rect: pres.ShapeType.rect, round: pres.ShapeType.roundRect, diamond: pres.ShapeType.diamond, cyl: pres.ShapeType.can,
    hex: pres.ShapeType.hexagon, ellipse: pres.ShapeType.ellipse, chevron: pres.ShapeType.chevron, cloud: pres.ShapeType.cloud,
    cube: pres.ShapeType.cube, doc: pres.ShapeType.flowChartDocument, disk: pres.ShapeType.flowChartMagneticDisk,
    callout: pres.ShapeType.wedgeRoundRectCallout, arrowR: pres.ShapeType.rightArrow, arrowD: pres.ShapeType.downArrow,
    folded: pres.ShapeType.flowChartDocument, wave: pres.ShapeType.wave, homePlate: pres.ShapeType.homePlate, plaque: pres.ShapeType.plaque,
    bracket: pres.ShapeType.leftRightArrow, gear: pres.ShapeType.gear6, star: pres.ShapeType.star5, dbl: pres.ShapeType.leftRightArrow };
  return m[type] || pres.ShapeType.roundRect;
}
function slideDiagram(pres, s) {
  const slide = pres.addSlide({ masterName: "CONTENT", sectionTitle: s.section });
  addTitle(slide, s.title);
  const ox = MX, oy = BODY_Y;
  const legendH = s.legend ? 0.75 : 0;
  const byId = {};
  (s.shapes || []).forEach((sh) => {
    const t = TONES[sh.tone || "mint"];
    const o = { x: ox + sh.x, y: oy + sh.y, w: sh.w, h: sh.h, fontSize: sh.fs || 11, color: sh.color || t.color, align: sh.align || "center", valign: sh.valign || "middle", margin: sh.margin == null ? 4 : sh.margin, bold: !!sh.bold, shape: shapeOf(pres, sh.type || "round") };
    if (t.fill) o.fill = { color: t.fill }; else o.fill = { type: "none" };
    if (t.line) o.line = { color: t.line, width: sh.lineW || 1.25, dashType: sh.dashed ? "dash" : "solid" }; else o.line = { color: "FFFFFF", width: 0 };
    if ((sh.type || "round") === "round") o.rectRadius = 0.1;
    if (sh.fontFace) o.fontFace = sh.fontFace;
    if (Array.isArray(sh.text)) { o.valign = sh.valign || "top"; o.align = sh.align || "left"; slide.addText(paras(sh.text, { fontSize: sh.fs || 11 }), o); }
    else slide.addText(sh.text || "", o);
    if (sh.id) byId[sh.id] = sh;
  });
  function anchor(a, other) {
    // a: id 또는 {x,y}. id 면 상대 쪽을 향한 가장자리 가운데
    if (typeof a !== "string") return { x: ox + a.x, y: oy + a.y };
    const sh = byId[a]; if (!sh) throw new Error(`diagram: 모르는 id ${a}`);
    const cx = sh.x + sh.w / 2, cy = sh.y + sh.h / 2;
    let tx, ty;
    if (typeof other === "string") { const o = byId[other]; tx = o.x + o.w / 2; ty = o.y + o.h / 2; } else { tx = other.x; ty = other.y; }
    const dx = tx - cx, dy = ty - cy;
    if (Math.abs(dx) >= Math.abs(dy)) return { x: ox + (dx >= 0 ? sh.x + sh.w : sh.x), y: oy + cy };
    return { x: ox + cx, y: oy + (dy >= 0 ? sh.y + sh.h : sh.y) };
  }
  (s.arrows || []).forEach((ar) => {
    const p1 = anchor(ar.from, ar.to), p2 = anchor(ar.to, ar.from);
    const dx = p2.x - p1.x, dy = p2.y - p1.y;
    const t = TONES[ar.tone || "gray"];
    const o = { x: Math.min(p1.x, p2.x), y: Math.min(p1.y, p2.y), w: Math.abs(dx), h: Math.abs(dy),
      line: { color: ar.color || t.line, width: ar.width || 1.75, dashType: ar.dashed ? "dash" : "solid" } };
    if (!ar.noHead) o.line.endArrowType = "triangle";
    if (ar.bothHeads) o.line.beginArrowType = "triangle";
    if (dx < 0 && dy >= 0) o.flipH = true;
    if (dx >= 0 && dy < 0) o.flipV = true;
    if (dx < 0 && dy < 0) { o.flipH = true; o.flipV = true; }
    slide.addShape(pres.ShapeType.line, o);
    if (ar.label) {
      const lw = ar.labelW || Math.max(1.2, Math.min(3.0, emWidth(ar.label) * 0.085 + 0.3));
      const mx = (p1.x + p2.x) / 2, my = (p1.y + p2.y) / 2;
      const off = ar.labelOff || { x: 0, y: Math.abs(dx) > Math.abs(dy) ? -0.3 : 0 };
      const lx = Math.abs(dx) > Math.abs(dy) ? mx - lw / 2 + off.x : mx + 0.08 + off.x;
      slide.addText(ar.label, { x: lx, y: my - 0.14 + off.y, w: lw, h: 0.28, fontSize: ar.labelFs || 9, color: ar.labelColor || hex("accent4"), fill: { color: "FFFFFF" }, align: Math.abs(dx) > Math.abs(dy) ? "center" : "left", valign: "middle", isTextBox: true, margin: 1 });
    }
  });
  (s.texts || []).forEach((tx) => {
    const o = { x: ox + tx.x, y: oy + tx.y, w: tx.w, h: tx.h, fontSize: tx.fs || 10.5, color: tx.color || hex("dk1"), align: tx.align || "left", valign: tx.valign || "top", isTextBox: true, margin: 2, bold: !!tx.bold };
    if (tx.fill) o.fill = { color: tx.fill };
    if (tx.fontFace) o.fontFace = tx.fontFace;
    if (Array.isArray(tx.text)) slide.addText(paras(tx.text, { fontSize: tx.fs || 10.5 }), o); else slide.addText(tx.text, o);
  });
  if (s.legend) {
    slide.addText(s.legend, { x: MX, y: BODY_END - legendH + 0.05, w: W - 2 * MX, h: legendH - 0.05, fontSize: 11, color: hex("dk1"), fill: { color: "F8FAFC" }, line: { color: "CBD5E1", width: 0.75 }, isTextBox: true, margin: 6, valign: "middle" });
  }
  addFooterNote(slide, s);
  return slide;
}

// ----- 막대 그래프(chart): pptx 원생 차트 + 오른쪽 설명 -----
// s.chart: {categories[], series[{name, values[]}], valTitle?, catTitle?, numFmt?, max?}  s.bullets 오른쪽
function slideChart(pres, s) {
  const slide = pres.addSlide({ masterName: "CONTENT", sectionTitle: s.section });
  addTitle(slide, s.title);
  const bw = s.bulletsW || 4.2;
  const cw = W - 2 * MX - bw - 0.3;
  const data = s.chart.series.map((se) => ({ name: se.name, labels: s.chart.categories, values: se.values }));
  const palette = [hex("accent1"), hex("accent2"), hex("accent5"), hex("accent6")];
  const opts = { x: MX, y: BODY_Y, w: cw, h: BODY_H - (s.caption ? 0.45 : 0),
    barDir: s.chart.horizontal ? "bar" : "col", barGapWidthPct: 60,
    chartColors: palette.slice(0, data.length),
    showTitle: !!s.chart.title, title: s.chart.title || "", titleFontSize: 13, titleColor: hex("dk1"), titleFontFace: "+mn-lt",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 10, dataLabelColor: hex("dk1"), dataLabelFormatCode: s.chart.numFmt || "0.0000", dataLabelFontFace: "+mn-lt",
    catAxisLabelFontSize: 10, catAxisLabelColor: hex("dk1"), catAxisLabelFontFace: "+mn-lt",
    valAxisLabelFontSize: 9, valAxisLabelColor: hex("accent3"), valAxisLabelFontFace: "+mn-lt", valAxisLabelFormatCode: s.chart.numFmt || "0.000",
    valGridLine: { color: "E2E8F0", size: 0.5 }, catGridLine: { style: "none" },
    showLegend: data.length > 1, legendPos: "b", legendFontSize: 10, legendFontFace: "+mn-lt",
    showValAxisTitle: !!s.chart.valTitle, valAxisTitle: s.chart.valTitle || "", valAxisTitleFontSize: 10, valAxisTitleColor: hex("accent3"), valAxisTitleFontFace: "+mn-lt",
    showCatAxisTitle: !!s.chart.catTitle, catAxisTitle: s.chart.catTitle || "", catAxisTitleFontSize: 10, catAxisTitleColor: hex("accent3"), catAxisTitleFontFace: "+mn-lt",
    valAxisMinVal: 0 };
  if (s.chart.max != null) opts.valAxisMaxVal = s.chart.max;
  slide.addChart(pres.ChartType.bar, data, opts);
  if (s.bullets) addBulletsBox(slide, s.bullets, W - MX - bw, BODY_Y, bw, BODY_H, 12);
  if (s.caption) slide.addText(s.caption, { x: MX, y: BODY_END - 0.45, w: cw, h: 0.45, fontSize: 10.5, color: hex("accent3"), isTextBox: true, margin: 0 });
  addFooterNote(slide, s);
  return slide;
}

const KINDS = { title: slideTitle, section: slideSection, bullets: slideBullets, two_col: slideTwoCol, table: slideTable, image: slideImage, code: slideCode, process: slideProcess, chain: slideChain, kpi: slideKpi, cards: slideCards, path: slidePath, compare: slideCompare, closing: slideClosing, diagram: slideDiagram, chart: slideChart };

async function main() {
  const specPath = process.argv[2];
  const outPath = process.argv[3];
  const slides = JSON.parse(fs.readFileSync(specPath, "utf-8"));
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  pres.author = "오문규";
  pres.title = "rt-robot-data-infra — 실시간 제어 · 데이터 인프라 포트폴리오";
  const C = pres.SchemeColor;

  pres.defineSlideMaster({
    title: "CONTENT",
    background: { color: "FFFFFF" },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: MX, y: TITLE_Y, w: W - 2 * MX - 1.0, h: TITLE_H, fontSize: 26, bold: true, color: C.text1, valign: "middle", margin: 0 }, text: "" } },
      { text: { text: "rt-robot-data-infra", options: { x: W - MX - 2.6, y: 7.05, w: 2.0, h: 0.3, fontSize: 9, color: C.accent3, align: "right", margin: 0 } } },
    ],
    slideNumber: { x: W - MX - 0.6, y: 7.05, w: 0.6, h: 0.3, fontSize: 9, color: C.accent3, align: "right" },
  });
  pres.defineSlideMaster({
    title: "DARK",
    background: { color: THEME.colors.dk1 },
    objects: [
      { text: { text: "rt-robot-data-infra", options: { x: W - MX - 2.6, y: 7.05, w: 2.0, h: 0.3, fontSize: 9, color: "9FB3AF", align: "right", margin: 0 } } },
    ],
    slideNumber: { x: W - MX - 0.6, y: 7.05, w: 0.6, h: 0.3, fontSize: 9, color: "9FB3AF", align: "right" },
  });

  let currentSection = null;
  slides.forEach((s, idx) => {
    if (s.section !== currentSection) { pres.addSection({ title: s.section }); currentSection = s.section; }
    const fn = KINDS[s.kind];
    if (!fn) throw new Error(`unknown kind ${s.kind} at slide ${idx + 1}`);
    const slide = fn(pres, s);
    if (!["title", "section", "closing"].includes(s.kind)) addNav(pres, slide, s);
    const noteName = String(idx + 1).padStart(3, "0");
    slide.addNotes(`설명 문서: docs/deck/notes/${noteName}.docx (${s.title})`);
  });
  await pres.writeFile({ fileName: outPath });
  await applyTheme(outPath, THEME);
  console.log(`wrote ${outPath}: ${slides.length} slides`);
}

main().catch((e) => { console.error(e); process.exit(1); });
