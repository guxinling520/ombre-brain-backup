/**
 * diary-to-timeline.mjs
 * Reads diary markdown, parses time entries, generates timeline events.
 * Diary times are Asia/Shanghai (UTC+8), stored as UTC in timeline.
 *
 * Usage: node diary-to-timeline.mjs <date> [date2 ...]
 *   or:  node diary-to-timeline.mjs --all      (process all diary files)
 *   or:  node diary-to-timeline.mjs --missing  (only dates missing from timeline)
 */
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";

// ---------- CONFIG ----------
const CYBERBOSS_DIR = process.env.CYBERBOSS_HOME ||
  path.join(process.env.USERPROFILE || "~", ".cyberboss");
const DIARY_DIR = path.join(CYBERBOSS_DIR, "diary");
const TIMELINE_STATE = path.join(CYBERBOSS_DIR, "timeline", "timeline-state.json");
const TIMELINE_AGENT = "F:/cyberboss_new/cyberboss/node_modules/timeline-for-agent/bin/timeline-for-agent.js";

/** Convert Asia/Shanghai local time (HH:mm) to UTC ISO string for a given date */
function toUTC(date, localTime) {
  const [h, m] = localTime.split(":").map(Number);
  // Local time Asia/Shanghai = UTC+8
  const utcDate = new Date(`${date}T${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:00+08:00`);
  return utcDate.toISOString();
}

// ---------- CATEGORY RULES ----------
const CAT_RULES = [
  // 学习 - 考试/上课
  [/考试|考场|六级|研究生英语|自然辩证法/, "study", "study.course", "evt.learning"],
  [/上课|课$|课堂|茶园生态|茶树遗传|育种/, "study", "study.course", "evt.learning"],
  // 学习 - 复习
  [/复习|背单词|作文模板|翻译|阅读题|背|词汇/, "study", "study.review"],
  [/对答案|估分|整理.*资料/, "study", "study.review"],
  // 饮食
  [/午饭|中饭|晚饭|早餐|早饭|吃饭|拌饭|米线|面条|凉面|盖饭|外卖|食堂|猪脚|窑鸡|烤肉|米粉|水煮蛋|木桶饭/, "life", "life.meal"],
  [/肥牛|金枪鱼|酸菜|玉米|淀粉肠|鸭汤|凉面|桂林米粉|猪肝|可乐|酸梅汤|烤肉/, "life", "life.meal"],
  [/等外卖|点外卖/, "life", "life.meal"],
  // 睡眠
  [/^起床|^醒了/, "rest", "rest.sleep"],
  [/睡觉|睡了|熬夜|^睡$/, "rest", "rest.sleep", "evt.sleep"],
  [/午休|眯一会|趴着|午睡|睡午觉/, "rest", "rest.nap", "evt.nap"],
  [/赖床/, "rest", "rest.idle"],
  // 通勤
  [/回寝室|去工位|到工位|出发去|出发上山|到考场|封路|走去/, "travel", "travel.commute", "evt.commute"],
  [/电动车|撞人/, "travel", "travel.other"],
  // 娱乐
  [/无畏契约|瓦罗兰特|瓦$|打瓦|游戏|打游戏|洛克王国|打了一把/, "entertainment", "entertainment.game"],
  [/吃瓜|刷视频|短视/, "entertainment", "entertainment.social_media"],
  // 运动
  [/健身|跑步|锻炼/, "exercise", "exercise.workout"],
  // 社交
  [/聊天|网友|朋友|闺蜜|萱萱|丁真|aa|梅梅|和堂妹/, "social", "social.chat"],
  [/打电话/, "social", "social.call"],
  // 工作/实验
  [/实验|样品|参数|液相|气相|干燥|晒青|色谱|喷施|EBR|PEG|试剂/, "work", "work.other"],
  [/方案|方法|规程|HPLC/, "work", "work.other"],
  [/整理.*[数据表]|整理.*文献|整理.*实验/, "work", "work.other"],
  // 杂务
  [/打印|跑腿|取快递|充电器|电池/, "life", "life.errand"],
  [/买[东可乐零]|逛|购物|零食|超市|糖巢/, "life", "life.shopping"],
  // 讨论/沟通
  [/讨论|聊到|对样品|黄老师|金老师|导师|课题|方向|周报|综述|文献/, "work", "work.communication"],
  [/汇报|PPT/, "work", "work.other"],
  // 其他
  [/喝茶|太平猴魁/, "life", "life.other"],
  [/吃瓜/, "entertainment", "entertainment.social_media"],
];

function categorize(text) {
  for (const [regex, cat, subcat, en] of CAT_RULES) {
    if (regex.test(text)) return { categoryId: cat, subcategoryId: subcat, eventNodeId: en || "" };
  }
  return { categoryId: "life", subcategoryId: "life.other", eventNodeId: "" };
}

// ---------- PARSING ----------
/**
 * Parse diary text, return array of { start, end, title, note }
 * Times are in local Asia/Shanghai HH:mm format (will be converted to UTC later).
 */
function parseDiary(text) {
  const lines = text.split("\n");
  const sections = [];
  let current = null;

  for (const line of lines) {
    const hdr = line.match(/^##\s*(\d{1,2}):(\d{2})(?:\s+(.*))?$/);
    const namedHdr = line.match(/^##\s+(全天时间轴|今日总结|重大事件|备注|每日timeline|行程总览)/);
    if (hdr || namedHdr) {
      if (current) sections.push(current);
      if (hdr) {
        current = { time: `${hdr[1].padStart(2, "0")}:${hdr[2]}`, title: (hdr[3] || "").trim(), body: [] };
      } else {
        current = { time: "00:00", title: namedHdr[1].trim(), body: [] };
      }
      continue;
    }
    if (current) {
      const trimmed = line.trim();
      if (trimmed) current.body.push(trimmed);
    }
  }
  if (current) sections.push(current);

  // Check if there's a 全天时间轴 section with structured bullets
  const timelineSection = sections.find((s) => s.title.includes("时间轴"));
  if (timelineSection) {
    const events = [];
    for (const line of timelineSection.body) {
      const m = line.match(/^\s*[-*]\s*(\d{1,2}):(\d{2})\s*(?:[-~]\s*(\d{1,2}):(\d{2}))?\s+(.*)$/);
      // Also match numbered list: "1. 08:00-08:30 内容"
      const nm = !m ? line.match(/^\s*\d+[.、]\s*(\d{1,2}):(\d{2})\s*(?:[-~]\s*(\d{1,2}):(\d{2}))?\s+(.*)$/) : null;
      const hit = m || nm;
      if (hit) {
        const sh = hit[1].padStart(2, "0"), sm = hit[2].padStart(2, "0");
        const eh = hit[3] ? hit[3].padStart(2, "0") : sh;
        const em = hit[4] || sm;
        events.push({ start: `${sh}:${sm}`, end: `${eh}:${em}`, title: hit[5].trim(), note: "" });
      }
    }
    // Also look for standalone time entries (both bullet and numbered list formats)
    for (const line of timelineSection.body) {
      const m = line.match(/^\s*(?:[-*]|\d+[.、])\s*(?:~)?(\d{1,2}):(\d{2})\s+(.*)$/);
      if (m && !line.match(/\d{1,2}:\d{2}\s*[-~]\s*\d{1,2}:\d{2}/) && !line.match(/^\s*\d+[.、]\s*\d{1,2}:\d{2}\s*[-~]/)) {
        // standalone time point - will be merged with neighbours
        const h = m[1].padStart(2, "0"), mm = m[2].padStart(2, "0");
        if (!events.some(e => e.start === `${h}:${mm}`)) {
          events.push({ start: `${h}:${mm}`, end: `${h}:${parseInt(mm)+15>59?'59':String(parseInt(mm)+15).padStart(2,'0')}`, title: m[3].trim(), note: "" });
        }
      }
    }
    if (events.length > 0) return events.sort((a,b) => a.start.localeCompare(b.start));
  }

  // Fallback: use section headers as activity markers
  // Skip "check-in" type sections, merge near sections into activities
  const activities = [];
  let i = 0;
  while (i < sections.length) {
    const sec = sections[i];
    // Skip pure check-in entries and content-less tags
    if (/^check-in/i.test(sec.title) || (/^\d/.test(sec.title) && !sec.title) ||
        (!sec.title && sec.body.length === 0)) {
      i++;
      continue;
    }

    let title = sec.title;
    let note = sec.body.filter(b => typeof b === "string").join("。").trim();

    // For sections with empty title, extract from body
    if (!title && note) {
      // First line of body is often the context
      const firstLine = sec.body[0];
      if (typeof firstLine === "string") {
        title = firstLine.replace(/[。，.。\s]/g, "").slice(0, 30) || sec.time + "时段";
      } else {
        title = sec.time + "时段";
      }
    }

    // If title is very short or generic, use body content
    if ((title.length < 3 || title === "check-in") && note) {
      title = note.replace(/[。，.。\s]/g, "").slice(0, 30);
    }

    const endTime = (i + 1 < sections.length) ? sections[i + 1].time : "23:59";
    activities.push({ start: sec.time, end: endTime, title: title || "活动", note });
    i++;
  }

  return activities;
}

// ---------- GENERATE EVENTS ----------
function mergeNeighbourEvents(events) {
  // Merge events with the same title or very short intervals (< 10 min)
  const merged = [];
  for (const evt of events) {
    if (merged.length > 0) {
      const last = merged[merged.length - 1];
      const lastEnd = last.end;
      const gap = timeDiff(lastEnd, evt.start);
      if (gap <= 10 && last.title === evt.title) {
        last.end = evt.end;
        if (evt.note && !last.note.includes(evt.note)) last.note += "; " + evt.note;
        continue;
      }
    }
    merged.push({ ...evt });
  }
  return merged;
}

function timeDiff(a, b) {
  const [ah, am] = a.split(":").map(Number);
  const [bh, bm] = b.split(":").map(Number);
  return (bh * 60 + bm) - (ah * 60 + am);
}

function buildEvents(rawEvents, date) {
  const merged = mergeNeighbourEvents(rawEvents);
  return merged.map((evt, idx) => {
    const cat = categorize(evt.title);
    const startAt = toUTC(date, evt.start);
    const endAt = toUTC(date, evt.end);
    const slug = evt.title.replace(/[\s()【】"",，。]+/g, "").slice(0, 25) || `event${idx}`;
    return {
      id: `fact:${slug}:${startAt.replace(/[:.]/g, "-")}`,
      startAt,
      endAt,
      title: evt.title,
      note: evt.note || "",
      ...cat,
      tags: [],
      confidence: 0.5,
      sourceMessageIds: [],
    };
  });
}

// ---------- FILE IO ----------
function readJSON(fp) { try { return JSON.parse(fs.readFileSync(fp, "utf8")); } catch { return null; } }
function writeJSON(fp, data) { fs.writeFileSync(fp, JSON.stringify(data, null, 2)); }

// ---------- MAIN ----------
async function main() {
  const args = process.argv.slice(2);
  let dates = [];

  if (args.includes("--all") || args.includes("--refresh")) {
    dates = fs.readdirSync(DIARY_DIR)
      .filter((f) => f.match(/^\d{4}-\d{2}-\d{2}\.md$/))
      .map((f) => f.replace(/\.md$/, ""))
      .sort();
  } else if (args.includes("--missing")) {
    const cb = readJSON(TIMELINE_STATE);
    const existing = new Set(Object.keys(cb?.facts || {}));
    dates = fs.readdirSync(DIARY_DIR)
      .filter((f) => f.match(/^\d{4}-\d{2}-\d{2}\.md$/))
      .map((f) => f.replace(/\.md$/, ""))
      .filter((d) => !existing.has(d))
      .sort();
  } else {
    dates = args.filter((a) => !a.startsWith("-"));
  }

  if (dates.length === 0) {
    console.log("Usage: node diary-to-timeline.mjs <date> [date2 ...]");
    console.log("       node diary-to-timeline.mjs --all");
    console.log("       node diary-to-timeline.mjs --missing");
    process.exit(0);
  }

  const cbState = readJSON(TIMELINE_STATE) || { version: 1, timezone: "Asia/Shanghai", taxonomy: { categories: [], eventNodes: [] }, facts: {}, proposals: [] };

  let ok = 0, errs = [];

  for (const date of dates) {
    const diaryPath = path.join(DIARY_DIR, `${date}.md`);
    if (!fs.existsSync(diaryPath)) { errs.push(`${date}: diary not found`); continue; }
    const text = fs.readFileSync(diaryPath, "utf8").trim();
    if (!text) { errs.push(`${date}: empty`); continue; }

    const raw = parseDiary(text);
    if (raw.length === 0) { errs.push(`${date}: no events parsed`); continue; }

    const events = buildEvents(raw, date);
    const dayData = { status: "draft", updatedAt: new Date().toISOString(), source: null, events };
    cbState.facts[date] = dayData;

    ok++;
    const mins = events.reduce((s, e) => s + Math.max(0, Math.round((Date.parse(e.endAt) - Date.parse(e.startAt)) / 60000)), 0);
    console.log(`${date}: ${events.length} events, ${Math.floor(mins / 60)}h${mins % 60}m`);
  }

  writeJSON(TIMELINE_STATE, cbState);
  console.log(`\nSaved: ${ok} days, ${errs.length} errors`);

  // Write sync status for context visibility
  const statusPath = path.join(CYBERBOSS_DIR, "context", ".last-sync.md");
  const statusLines = [
    "# 上次同步状态",
    `同步时间: ${new Date().toISOString()}`,
    `处理天数: ${ok}`,
    `错误数: ${errs.length}`,
    ...(errs.length > 0 ? ["", "## 错误"] : []),
    ...errs.map((e) => `  - ${e}`),
    "",
    "## 各日事件数",
  ];
  for (const date of dates) {
    const day = cbState.facts[date];
    if (day?.events) {
      const mins = day.events.reduce((s, e) => s + Math.max(0, Math.round((Date.parse(e.endAt) - Date.parse(e.startAt)) / 60000)), 0);
      statusLines.push(`  - ${date}: ${day.events.length} events, ${Math.floor(mins / 60)}h${mins % 60}m`);
    }
  }
  statusLines.push("");
  fs.writeFileSync(statusPath, statusLines.join("\n"));

  // Build sites
  for (const date of dates.filter(d => cbState.facts[d])) {
    try {
      execSync(`node "${TIMELINE_AGENT}" write --date "${date}" --json "{}"`, {
        stdio: "pipe", timeout: 15000, windowsHide: true,
        env: { ...process.env, TIMELINE_FOR_AGENT_STATE_DIR: CYBERBOSS_DIR },
      });
    } catch { /* merge mode, fine */ }
  }

  try {
    execSync(`node "${TIMELINE_AGENT}" build`, {
      stdio: "pipe", timeout: 30000, windowsHide: true,
      env: { ...process.env, TIMELINE_FOR_AGENT_STATE_DIR: CYBERBOSS_DIR, TIMELINE_FOR_AGENT_LOCALE: "zh" },
    });
    console.log("Timeline site rebuilt");
  } catch (e) { console.error("Timeline build error:", e.message); }

  if (errs.length) { console.log("\nErrors:"); errs.forEach((e) => console.log("  -", e)); }
}

main().catch(console.error);
