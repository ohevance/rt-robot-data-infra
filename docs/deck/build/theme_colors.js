// 테마 색 써 넣기 — build_deck.js 가 pptx 를 쓴 직후에 한 번 부른다.
//
// 왜 필요한가
//   pptxgenjs 는 테마에 글꼴 둘(제목·본문)만 적고, 색 12칸은 Office 기본 팔레트(파랑·주황)를 그대로 둔다.
//   장표에서 '테마 색'으로 지정한 곳(마스터의 제목 색, 쪽 번호 색 등)이 우리 색으로 보이려면
//   pptx 안의 ppt/theme/theme1.xml 에 있는 색 묶음(<a:clrScheme>)을 우리 색으로 바꿔 써야 한다.
// 하는 일
//   pptx(= ZIP)를 열어 theme1.xml 의 색 묶음을 우리 색 12개로 바꾸고, 테마·색 묶음·글꼴 묶음의 이름을 우리 이름으로 적은 뒤 다시 쓴다.
// 읽는 순서: SLOTS(색 12칸의 이름) → schemeXml(색 묶음 한 덩어리) → applyTheme(열기 → 바꾸기 → 쓰기)
const fs = require("fs");

// 테마 색 12칸. 순서는 OOXML 이 정한 것(어두운 글자 1 · 밝은 바탕 1 · 어두운 2 · 밝은 2 · 강조 1~6 · 링크 · 방문한 링크)
const SLOTS = ["dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6", "hlink", "folHlink"];

// jszip 은 pptxgenjs 가 데리고 오는 라이브러리다. 따로 설치하지 않아도 되게 pptxgenjs 가 있는 곳에서 찾는다
function loadZipLibrary() {
  const pptxgenjsPath = require.resolve("pptxgenjs");
  return require(require.resolve("jszip", { paths: [pptxgenjsPath] }));
}

// XML 속성 값에 넣을 수 있게 & < > " 를 바꾼다 (테마 이름에 쓴다)
function escapeAttribute(text) {
  return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function schemeXml(name, colors) {
  let inner = "";
  for (const slot of SLOTS) {
    const value = String(colors[slot] || "");
    if (!/^[0-9A-Fa-f]{6}$/.test(value)) {
      throw new Error(`테마 색 ${slot} = "${value}" — '#' 없는 16진수 6자리여야 한다 (예: 0F766E)`);
    }
    inner += `<a:${slot}><a:srgbClr val="${value.toUpperCase()}"/></a:${slot}>`;
  }
  return `<a:clrScheme name="${name}">${inner}</a:clrScheme>`;
}

async function applyTheme(pptxPath, theme) {
  const part = "ppt/theme/theme1.xml";      // pptxgenjs 가 쓰는 테마 파일은 이것 하나다
  const zip = await loadZipLibrary().loadAsync(fs.readFileSync(pptxPath));
  const file = zip.file(part);
  if (!file) throw new Error(`${pptxPath} 안에 ${part} 가 없다 — pptxgenjs 가 만든 파일이 아니다`);
  const name = escapeAttribute(theme.name);
  const scheme = schemeXml(name, theme.colors);
  const before = await file.async("string");
  const schemePattern = /<a:clrScheme\b[\s\S]*?<\/a:clrScheme>/;
  if (!schemePattern.test(before)) throw new Error(`${part} 에 <a:clrScheme> 이 없다`);
  // 바꿀 글을 함수로 주는 이유: 문자열로 주면 이름 안의 "$" 가 특수 문자로 읽힌다
  const after = before
    .replace(schemePattern, () => scheme)
    .replace(/(<a:(?:theme|fontScheme)\b[^>]*?\bname=")[^"]*"/g, (whole, head) => `${head}${name}"`);
  zip.file(part, after);
  fs.writeFileSync(pptxPath, await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" }));
}

module.exports = { applyTheme };
