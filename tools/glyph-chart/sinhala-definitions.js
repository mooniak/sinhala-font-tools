// sinhala-definitions.js
// This file contains all Sinhala letter definitions, combinations and exceptions attested and documented by Pushpananda Ekanayake and Pathum Egodawatta.
// This file can be used independently in other projects

// Original consonants array
const originalConsonants = "කඛගඝඞඟචඡජඣඤඥඦටඨඩඪණඬතථදධනඳපඵබභමඹයරලවශෂසහළෆ".split('');

// Current consonants - will be updated when sort order changes
let consonants = [...originalConsonants];

// Vowel signs and compound signs
const vowelMarks = ["", "ා", "ැ", "ෑ", "ි", "ී", "ු", "ූ", "ෘ", "ෙ", "ේ", "ෛ", "ො", "ෝ", "ෞ", "ෟ", "්"];
const compoundSigns = ["්‍ර", "ර්‍", "්‍ය"];

// Inventory (conjunct + touching-cluster maps) and the shaping-exception sets
// are both generated from the standard's YAML — the single source of truth —
// so they can't drift from it.
// Regenerate with: npm run build && node dist/cli/index.js export-json --format js \
//   -o tools/_generated/lanka-glyph-data.js
//   node tools/_generated/build-shaping-exceptions.js
// Loaded via <script> in the browser (globals LankaGlyphData / LankaShapingExceptions)
// and via require() in Node.
const LankaGlyphData =
  (typeof module !== "undefined" && module.exports)
    ? require("../_generated/lanka-glyph-data.js")
    : (typeof globalThis !== "undefined" ? globalThis : window).LankaGlyphData;

const LankaShapingExceptions =
  (typeof module !== "undefined" && module.exports)
    ? require("../_generated/shaping-exceptions.js")
    : (typeof globalThis !== "undefined" ? globalThis : window).LankaShapingExceptions;

// Define base exceptions for special compound forms
const baseRakaransayaExceptions = [...LankaShapingExceptions.rakaransayaExceptions];

// Generate all rakaransaya exceptions (base + their rakaransaya combinations)
const rakaransayaExceptions = new Set([
  ...baseRakaransayaExceptions,
  ...baseRakaransayaExceptions.map(base => base + "්‍ර")
]);
const repayaExceptions = LankaShapingExceptions.repayaExceptions;
const yansayaExceptions = LankaShapingExceptions.yansayaExceptions;

// Ligated conjunct pairs (keyed by leading Sinhala character)
const conjunctMap = LankaGlyphData.conjunctMap;

// Convert the map to pairs
const conjunctPairs = [];
Object.entries(conjunctMap).forEach(([first, seconds]) => {
  seconds.forEach(second => {
    conjunctPairs.push([first, second]);
  });
});

// Touching consonant clusters (keyed by leading Sinhala character)
const touchingClusterMap = LankaGlyphData.touchingClusterMap;

// Convert the map to pairs
const touchingClusterPairs = [];
Object.entries(touchingClusterMap).forEach(([first, seconds]) => {
  seconds.forEach(second => {
    touchingClusterPairs.push([first, second]);
  });
});

// Function to get conjuncts based on current consonants order
function getConjuncts() {
  return conjunctPairs.map(([c1, c2]) => c1 + "්\u200D" + c2);
}

// Function to get touching clusters
function getTouchingClusters() {
  return touchingClusterPairs.map(([c1, c2]) => c1 + "\u200D්" + c2);
}

// Function to generate rakaransaya combinations
function getRakaransayaCombinations() {
  const rakaransaya = "්‍ර";
  const combinations = [];

  // Add consonant + rakaransaya combinations
  consonants.forEach(c => {
    combinations.push(c + rakaransaya);
  });

  // Add ligated conjunct + rakaransaya combinations
  conjuncts.forEach(c => {
    combinations.push(c + rakaransaya);
  });

  return combinations;
}

// Generate the conjuncts and touching clusters
let conjuncts = getConjuncts();
let touchingClusters = getTouchingClusters();

// Generate rakaransaya combinations
let rakaransayaCombinations = getRakaransayaCombinations();

// Make sure we have consonants first, then conjuncts, then rakaransaya combinations, then touching clusters in the base letters array
let baseLetters = [...consonants, ...conjuncts, ...rakaransayaCombinations, ...touchingClusters];

// Node/CommonJS interop. Ignored in the browser, where `module` is undefined
// (this file is loaded via <script src> and its declarations become globals).
// Lets tools such as generate-glyphnames.js reuse this data without duplicating it.
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    originalConsonants,
    vowelMarks,
    compoundSigns,
    conjunctMap,
    conjunctPairs,
    touchingClusterMap,
    touchingClusterPairs,
    baseRakaransayaExceptions,
    rakaransayaExceptions,
    repayaExceptions,
    yansayaExceptions,
    getConjuncts,
    getTouchingClusters,
  };
}
