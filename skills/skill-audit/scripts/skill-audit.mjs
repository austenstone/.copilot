#!/usr/bin/env node
import { readFileSync, readdirSync, statSync, existsSync, realpathSync } from "node:fs";
import { join, basename, dirname } from "node:path";
import { homedir } from "node:os";

const withPlugins = process.argv.includes("--plugins");
const ROOTS = [
  join(homedir(), ".copilot/skills"),
  join(homedir(), ".agents/skills"),
  ...(withPlugins ? [join(homedir(), ".copilot/installed-plugins")] : []),
];

const DESC_WARN_CHARS = 600;
const tokens = (s) => Math.ceil(Buffer.byteLength(s, "utf8") / 4);

const findSkillFiles = (dir, out = []) => {
  if (!existsSync(dir)) return out;
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry.startsWith(".")) continue;
    const full = join(dir, entry);
    let st;
    try {
      st = statSync(full);
    } catch {
      continue;
    }
    if (st.isDirectory()) findSkillFiles(full, out);
    else if (entry === "SKILL.md") out.push(full);
  }
  return out;
};

const parseFrontmatter = (text) => {
  const m = text.match(/^---\n([\s\S]*?)\n---/);
  if (!m) return { ok: false };
  const fm = {};
  for (const line of m[1].split("\n")) {
    const kv = line.match(/^(\w[\w-]*):\s*(.*)$/);
    if (kv) fm[kv[1]] = kv[2].replace(/^["']|["']$/g, "").trim();
  }
  return { ok: true, fm, raw: m[1] };
};

const norm = (s) =>
  (s || "")
    .toLowerCase()
    .replace(/[^a-z0-9 ]/g, " ")
    .split(/\s+/)
    .filter(Boolean);

const jaccard = (a, b) => {
  const sa = new Set(a),
    sb = new Set(b);
  if (!sa.size || !sb.size) return 0;
  let inter = 0;
  for (const w of sa) if (sb.has(w)) inter++;
  return inter / (sa.size + sb.size - inter);
};

const skills = [];
const seenReal = new Set();
for (const root of ROOTS) {
  for (const file of findSkillFiles(root)) {
    let real;
    try {
      real = realpathSync(file);
    } catch {
      real = file;
    }
    if (seenReal.has(real)) continue;
    seenReal.add(real);
    const text = readFileSync(file, "utf8");
    const { ok, fm = {} } = parseFrontmatter(text);
    const name = fm.name || basename(dirname(file));
    skills.push({
      file: file.replace(homedir(), "~"),
      name,
      description: fm.description || "",
      validFrontmatter: ok,
      hasName: ok && !!fm.name,
      hasDescription: ok && !!fm.description,
      descTokens: tokens(fm.description || ""),
    });
  }
}

const totalDescTokens = skills.reduce((n, s) => n + s.descTokens, 0);

const invalid = skills.filter((s) => !s.validFrontmatter || !s.hasName || !s.hasDescription);

const byName = new Map();
for (const s of skills) {
  if (!byName.has(s.name)) byName.set(s.name, []);
  byName.get(s.name).push(s);
}
const dupeNames = [...byName.values()].filter((g) => g.length > 1);

const nearDupes = [];
for (let i = 0; i < skills.length; i++) {
  for (let j = i + 1; j < skills.length; j++) {
    if (skills[i].name === skills[j].name) continue;
    const sim = jaccard(norm(skills[i].description), norm(skills[j].description));
    if (sim >= 0.6) nearDupes.push({ a: skills[i].name, b: skills[j].name, sim });
  }
}

const bloated = skills
  .filter((s) => s.description.length > DESC_WARN_CHARS)
  .sort((a, b) => b.description.length - a.description.length);

const out = [];
out.push(`# Skill Audit`);
out.push(``);
out.push(`Scanned ${skills.length} skills across ${ROOTS.length} roots.`);
out.push(`Description budget: ~${totalDescTokens} tokens always loaded.`);
out.push(``);

if (invalid.length) {
  out.push(`## Invalid frontmatter (${invalid.length})`);
  for (const s of invalid) {
    const why = [];
    if (!s.validFrontmatter) why.push("no YAML frontmatter");
    else {
      if (!s.hasName) why.push("missing name");
      if (!s.hasDescription) why.push("missing description");
    }
    out.push(`- ${s.file} — ${why.join(", ")}`);
  }
  out.push(``);
}

if (dupeNames.length) {
  out.push(`## Duplicate names (${dupeNames.length})`);
  for (const g of dupeNames) {
    out.push(`- **${g[0].name}**`);
    for (const s of g) out.push(`  - ${s.file}`);
  }
  out.push(``);
}

if (nearDupes.length) {
  out.push(`## Near-identical descriptions (${nearDupes.length})`);
  for (const d of nearDupes.sort((a, b) => b.sim - a.sim))
    out.push(`- ${d.a} ↔ ${d.b} (${(d.sim * 100).toFixed(0)}% overlap)`);
  out.push(``);
}

if (bloated.length) {
  out.push(`## Bloated descriptions (>${DESC_WARN_CHARS} chars)`);
  for (const s of bloated)
    out.push(`- ${s.name} — ${s.description.length} chars (~${s.descTokens} tokens)`);
  out.push(``);
}

if (!invalid.length && !dupeNames.length && !nearDupes.length && !bloated.length)
  out.push(`No issues found. Clean inventory.`);

console.log(out.join("\n"));
