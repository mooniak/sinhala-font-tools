/*
 * The generated test texts obey their own grapheme sets, and generation is deterministic.
 *   node --test tools/test-generator/test/make-test-texts.test.js     (about 30 s)
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { execFileSync } = require("child_process");

const G = require("../graphemes.js");
const Presets = require("../presets.js");

const ROOT = path.join(__dirname, "..");
const have = fs.existsSync(path.join(ROOT, "data/words.txt"));
const gen = (out) => execFileSync("node", [path.join(ROOT, "make-test-texts.js"), "--out", out], { stdio: "pipe" });

test("generated test texts: inside each preset's set, clean, deterministic", { skip: !have && "data/ not built", timeout: 180000 }, () => {
  const a = fs.mkdtempSync(path.join(os.tmpdir(), "tt-a-"));
  const b = fs.mkdtempSync(path.join(os.tmpdir(), "tt-b-"));
  gen(a); gen(b);
  const files = fs.readdirSync(a).sort();
  assert.ok(files.includes("stages.md") && files.includes("levels.md") && files.includes("targeted-rakar.md"));
  files.forEach((f) => assert.strictEqual(fs.readFileSync(path.join(a, f), "utf8"), fs.readFileSync(path.join(b, f), "utf8"), f + " differs between runs"));

  const presets = Presets.build(JSON.parse(fs.readFileSync(path.join(ROOT, "../design-stages/stages.json"), "utf8")));
  const check = (file, heading, items) => {
    const body = fs.readFileSync(path.join(a, file), "utf8");
    const start = body.indexOf("## " + heading);
    assert.ok(start >= 0, heading + " missing from " + file);
    const next = body.indexOf("\n## ", start + 3);
    const sec = body.slice(start, next < 0 ? undefined : next);
    const set = new Set(G.parseList(items.join(" ")).graphemes);
    const bad = new Set();
    sec.split("\n").filter((l) => /^(TEMPLATES|TEXT|SENTENCES|INVENTED) : /.test(l)).forEach((l) => {
      G.segment(l.replace(/^\w+ : /, "")).forEach((x) => {
        if (x.sinhala && G.availability({ g: x.g, parts: x.parts }, set, true) === "") bad.add(x.g);
      });
    });
    assert.deepStrictEqual([...bad], [], heading + " uses graphemes outside its set");
    assert.ok(!sec.includes("<!--"), "stray comment in " + heading);
  };
  presets.stages.forEach((st) => check("stages.md", "Stage " + st.n + " — " + st.name, st.items));
  presets.levels.forEach((lv) => check("levels.md", lv.label + " (level " + lv.n + ")", lv.items));

  // targeted files: only real, Latin-free, non-empty sentences; rakar file really has rakar
  const rakar = fs.readFileSync(path.join(a, "targeted-rakar.md"), "utf8").split("\n").filter((l) => l && !/^(---|##|[a-z_]+:)/.test(l));
  assert.ok(rakar.length >= 30);
  rakar.forEach((l) => assert.ok(l.includes("්‍ර"), "no rakar in: " + l));
  fs.readdirSync(a).filter((f) => f.startsWith("targeted-")).forEach((f) => {
    const sentences = fs.readFileSync(path.join(a, f), "utf8").split("---")[2].split("\n").filter((l) => l && !l.startsWith("##"));
    assert.ok(sentences.length > 0, f + " is empty");
    sentences.forEach((l) => assert.ok(!/[A-Za-z]/.test(l), f + " has Latin text: " + l));
  });
});
