/**
 * plist.js — minimal writer for Glyphs 3 `CustomFilter*.plist` files.
 *
 * The format (verified against ~/Library/Application Support/Glyphs 3/
 * CustomFilter.plist and GSSidebarItem.h): a top-level <array> of <dict>,
 * each with `name` plus EITHER `list` (array of bare glyph names) OR
 * `predicate` (a plain NSPredicate format string — not an archived object).
 *
 * Glyphs' own list field splits pasted text on WHITESPACE ONLY, which is how
 * list filters end up holding entries like `si_Ba.reph,` or a tokenized `#`
 * comment header. assertCleanName() refuses to emit anything of that shape.
 */

'use strict';

const BAD_NAME = /[\s,;#"'<>&]/;

function assertCleanName(name, filterName) {
  if (typeof name !== 'string' || name === '') {
    throw new Error(`filter "${filterName}": empty glyph name`);
  }
  if (BAD_NAME.test(name)) {
    throw new Error(
      `filter "${filterName}": glyph name ${JSON.stringify(name)} contains ` +
      'whitespace or punctuation — Glyphs would store it as an unmatchable entry'
    );
  }
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/**
 * Nodes are one of:
 *   { name, glyphs: [...] }      list filter
 *   { name, predicate: '…' }     smart filter
 *   { name, children: [node] }   folder — emitted as `subGroup`, the key
 *                                Glyphs itself writes (verified against
 *                                Typotheque's CustomFilter TPTQ *.plist files)
 */
function nodeLines(node, depth) {
  const t = '\t'.repeat(depth);
  const out = [`${t}<dict>`, `${t}\t<key>name</key>`, `${t}\t<string>${esc(node.name)}</string>`];
  if (node.children) {
    out.push(`${t}\t<key>subGroup</key>`, `${t}\t<array>`);
    for (const child of node.children) out.push(...nodeLines(child, depth + 2));
    out.push(`${t}\t</array>`);
  } else if (node.predicate) {
    out.push(`${t}\t<key>predicate</key>`, `${t}\t<string>${esc(node.predicate)}</string>`);
  } else {
    out.push(`${t}\t<key>list</key>`, `${t}\t<array>`);
    for (const g of node.glyphs) {
      assertCleanName(g, node.name);
      out.push(`${t}\t\t<string>${esc(g)}</string>`);
    }
    out.push(`${t}\t</array>`);
  }
  out.push(`${t}</dict>`);
  return out;
}

function toPlist(nodes) {
  const out = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" ' +
      '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">',
    '<plist version="1.0">',
    '<array>',
  ];
  for (const node of nodes) out.push(...nodeLines(node, 1));
  out.push('</array>', '</plist>', '');
  return out.join('\n');
}

module.exports = { toPlist, assertCleanName };
