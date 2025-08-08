// sinhala-sorting.js
// This file contains sorting orders and functions for the Sinhala chart

// Pre-defined sorting orders
const sortingOrders = {
  // Default order - as defined in the original chart
  default: originalConsonants,
  
  // Alphabetical order - sorted by Unicode codepoint
  alphabetical: [...originalConsonants].sort(),
  
  // Frequency order - most commonly used consonants first
  frequency: "කමපබතදනලසයරවජගහඅඉඑටඩණධඝඞඟශෂඣඤඥඦඨඪඬථඳඵභඹළෆ".split(''),
  
  // Phonetic groups - grouped by articulation points and manner
  phonetic: [
    // Velar consonants
    "ක", "ඛ", "ග", "ඝ", "ඞ", "ඟ",
    // Palatal consonants
    "ච", "ඡ", "ජ", "ඣ", "ඤ", "ඥ", "ඦ",
    // Retroflex consonants
    "ට", "ඨ", "ඩ", "ඪ", "ණ", "ඬ",
    // Dental consonants
    "ත", "ථ", "ද", "ධ", "න", "ඳ",
    // Labial consonants
    "ප", "ඵ", "බ", "භ", "ම", "ඹ",
    // Approximants
    "ය", "ර", "ල", "ව",
    // Sibilants
    "ශ", "ෂ", "ස", "හ", "ළ", "ෆ"
  ],
  uMatra:"මවචටථඵහඣණණහඣබඩනසයඞඛඝඨඪඬඹපජෂඦෆරළදලඤඥකතගශඟභ".split(''),

  // Custom order - example of user-defined order
  custom: "මබඩනරසදලකවතපජගහයචටළශෂඞඟථඛඝඣඤඥඦඨඪණඬඳඵභඹෆ".split('')
};

// Apply sorting when button is clicked
document.addEventListener('DOMContentLoaded', function() {
  document.getElementById('apply-sort').addEventListener('click', function() {
    const sortType = document.getElementById('sort-order').value;
    
    // Update consonants based on selected sort type
    if (sortingOrders[sortType]) {
      consonants = [...sortingOrders[sortType]];
      
      // Re-create conjuncts, touching clusters, and baseLetters based on new consonant order
      conjuncts = getConjuncts();
      touchingClusters = getTouchingClusters();
      baseLetters = [...consonants, ...conjuncts, ...touchingClusters];
      
      // Re-render the chart
      renderChart();
    }
  });
});

// In case DOMContentLoaded has already fired
if (document.readyState === "complete" || document.readyState === "interactive") {
  setTimeout(function() {
    const applyButton = document.getElementById('apply-sort');
    if (applyButton && !applyButton.onclick) {
      applyButton.addEventListener('click', function() {
        const sortType = document.getElementById('sort-order').value;
        
        // Update consonants based on selected sort type
        if (sortingOrders[sortType]) {
          consonants = [...sortingOrders[sortType]];
          
          // Re-create conjuncts, touching clusters, and baseLetters based on new consonant order
          conjuncts = getConjuncts();
          touchingClusters = getTouchingClusters();
          baseLetters = [...consonants, ...conjuncts, ...touchingClusters];
          
          // Re-render the chart
          renderChart();
        }
      });
    }
  }, 1);
}