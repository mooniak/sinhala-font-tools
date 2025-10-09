// sinhala-definitions.js
// This file contains all Sinhala letter definitions, combinations and exceptions
// This file can be used independently in other projects

// Original consonants array
const originalConsonants = "කඛගඝඞඟචඡජඣඤඥඦටඨඩඪණඬතථදධනඳපඵබභමඹයරලවශෂසහළෆ".split('');

// Current consonants - will be updated when sort order changes
let consonants = [...originalConsonants];

// Vowel signs and compound signs
const vowelMarks = ["", "ා", "ැ", "ෑ", "ි", "ී", "ු", "ූ", "ෘ", "ෙ", "ේ", "ෛ", "ො", "ෝ", "ෞ", "ෟ", "්"];
const compoundSigns = ["්‍ර", "ර්‍", "්‍ය"];

// Define base exceptions for special compound forms
const baseRakaransayaExceptions = ["ඞ", "ඟ", "ඡ", "ජ", "ඤ", "ඥ", "ඨ", "ඪ", "ණ", "ඬ", "ථ", "න", "ඳ", "ඵ", "ඹ", "ය", "ර", "ල", "ළ", "ඞ්‍ග"];

// Generate all rakaransaya exceptions (base + their rakaransaya combinations)
const rakaransayaExceptions = new Set([
  ...baseRakaransayaExceptions,
  ...baseRakaransayaExceptions.map(base => base + "්‍ර")
]);
const repayaExceptions = new Set(["ඤ", "ඬ", "ර", "ක්‍ෂ", "ඞ්‍ග"]);
const yansayaExceptions = new Set(["ඥ", "ඹ", "ඤ්‍ජ"]);

// Ligated conjunct pairs
const conjunctMap = {
  'ක': ['ව', 'ෂ'],
  'ත': ['ථ', 'ව'],
  'න': ['ථ', 'ද', 'ධ', 'ව'],
  'ග': ['ධ'],
  'ට': ['ඨ'],
  'ද': ['ධ', 'ව'],
  'ඞ': ['ග'],
  'ච': ['ච'],
  'ඤ': ['ච', 'ඡ', 'ජ'],
  'ණ': ['ඩ'],
  'බ': ['බ'],
  'ම': ['බ']
};

// Convert the map to pairs
const conjunctPairs = [];
Object.entries(conjunctMap).forEach(([first, seconds]) => {
  seconds.forEach(second => {
    conjunctPairs.push([first, second]);
  });
});

// Touching consonant clusters
const touchingClusterMap = {
  'ක': ['ක', 'ඛ', 'ත', 'ම', 'න'],
  'ග': ['ග', 'ඝ'],
  'ඞ': ['ඞ', 'ක', 'ග', 'ඝ'],
  'ච': ['ච', 'ඡ'],
  'ජ': ['ජ', 'ඣ'],
  'ඤ': ['ච', 'ඤ'],
  'ට': ['ට', 'ඨ'],
  'ඩ': ['ඩ', 'ඪ'],
  'ණ': ['ණ', 'ඩ', 'ඨ', 'හ'],
  'ත': ['ත', 'ථ', 'ම', 'ව'],
  'ද': ['ද', 'ධ', 'ව'],
  'න': ['න', 'ට', 'ත', 'ද', 'ධ', 'ථ', 'ව', 'හ'],
  'ප': ['ප', 'ත', 'ඵ', 'බ', 'ද', 'හ'],
  'බ': ['බ', 'ද', 'භ'],
  'ම': ['ම', 'හ', 'ඵ', 'බ', 'ව', 'ප', 'ද', 'භ'],
  'ල': ['ල', 'ව'],
  'ව': ['හ'],
  'ශ': ['ට'],
  'ස': ['ස', 'ත', 'ව'],
  'හ': ['ම']
};

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
