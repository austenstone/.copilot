#!/usr/bin/env node
import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, basename, dirname } from "node:path";
import { homedir } from "node:os";

const args = process.argv.slice(2);
const targets = args.length ? args : [join(homedir(), ".copilot/skills")];

const findSkillFiles = (p, out = []) => {
  if (!existsSync(p)) return out;
  const st = statSync(p);
  if (st.isFile()) {
    if (basename(p) === "SKILL.md") out.push(p);
    return out;
  }
  for (const entry of readdirSync(p)) {
    if (entry.startsWith(".") || entry === "node_modules") continue;
    findSkillFiles(join(p, entry), out);
  }
  return out;
};

const errors = [];
const warnings = [];
const files = targets.flatMap((t) => findSkillFiles(t));

for (const file of files) {
  const text = readFileSync(file, "utf8");
  const rel = file.replace(homedir(), "~");
  const m = text.match(/^---\n([\s\S]*?)\n---/);
  if (!m) {
    errors.push(`${rel}: missing YAML frontmatter`);
    continue;
  }
  const fm = {};
  for (const line of m[1].split("\n")) {
    const kv = line.match(/^(\w[\w-]*):\s*(.*)$/);
    if (kv) fm[kv[1]] = kv[2].trim();
  }
  if (!fm.name) errors.push(`${rel}: missing 'name' in frontmatter`);
  if (!fm.description) errors.push(`${rel}: missing 'description' in frontmatter`);
  else if (fm.description.replace(/^["']|["']$/g, "").length < 20)
    errors.push(`${rel}: 'description' too short to route reliably`);
  if (fm.name && fm.name !== basename(dirname(file)))
    warnings.push(`${rel}: name '${fm.name}' does not match folder '${basename(dirname(file))}'`);
}

for (const w of warnings) console.error(`  ⚠ ${w}`);

if (errors.length) {
  console.error(`✗ ${errors.length} skill frontmatter issue(s):`);
  for (const e of errors) console.error(`  ${e}`);
  process.exit(1);
}
console.log(`✓ ${files.length} SKILL.md files valid${warnings.length ? ` (${warnings.length} warning)` : ""}`);
