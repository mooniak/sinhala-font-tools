// sinhala-chart.js
// This file contains the chart rendering and UI functions
// Requires sinhala-definitions.js to be loaded first

// Chart rendering function
function renderChart() {
  const chart = document.getElementById("chart");
  chart.innerHTML = ''; // Clear existing table

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");

  // Create the first header cell with "Base Letter" text
  const baseLetterHeader = document.createElement("th");
  baseLetterHeader.textContent = "Base Letter";
  headRow.appendChild(baseLetterHeader);

  // Add the rest of the header cells for vowel marks and compound signs
  [...vowelMarks, ...compoundSigns].forEach((mark, i) => {
    const th = document.createElement("th");
    th.textContent = mark || "(none)";
    const btn = document.createElement("button");
    btn.innerHTML = "📋";
    btn.className = "copy-btn";
    btn.onclick = (e) => {
      e.stopPropagation();
      copyColumn(i);
    };
    th.appendChild(btn);
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  chart.appendChild(thead);

  const tbody = document.createElement("tbody");

  // Helper function to determine row type
  function getRowType(base) {
    if (conjuncts.includes(base)) return "ligated-conjunct-row";
    if (rakaransayaCombinations.includes(base)) return "rakaransaya-combination-row";
    if (touchingClusters.includes(base)) return "touching-cluster-row";
    return "consonant-row";
  }

  baseLetters.forEach((base, rowIndex) => {
    const row = document.createElement("tr");
    row.className = getRowType(base);

    const th = document.createElement("th");
    th.textContent = base;
    const btn = document.createElement("button");
    btn.innerHTML = "📋";
    btn.className = "copy-btn";
    btn.onclick = (e) => {
      e.stopPropagation();
      copyRow(rowIndex);
    };
    th.appendChild(btn);
    row.appendChild(th);

    [...vowelMarks, ...compoundSigns].forEach(mark => {
      const td = document.createElement("td");
      let combo = "", skip = false, type = "";
      const showExceptions = document.getElementById('show-exceptions-checkbox').checked;

      if (mark === "්‍ර") {
        if (rakaransayaExceptions.has(base)) {
          if (showExceptions) {
            td.textContent = "×";
            td.style.color = "#ef4444"; // Bright red for exceptions
            td.style.fontWeight = "bold";
            skip = true;
          } else {
            combo = base + mark;
            type = "Compound (Rakaransaya) - Exception";
          }
        } else {
          combo = base + mark;
          type = "Compound (Rakaransaya)";
        }
      } else if (mark === "ර්‍") {
        if (repayaExceptions.has(base)) {
          if (showExceptions) {
            td.textContent = "×";
            td.style.color = "#ef4444"; // Bright red for exceptions
            td.style.fontWeight = "bold";
            skip = true;
          } else {
            combo = mark + base;
            type = "Compound (Repaya) - Exception";
          }
        } else {
          combo = mark + base;
          type = "Compound (Repaya)";
        }
      } else if (mark === "්‍ය") {
        if (yansayaExceptions.has(base)) {
          if (showExceptions) {
            td.textContent = "×";
            td.style.color = "#ef4444"; // Bright red for exceptions
            td.style.fontWeight = "bold";
            skip = true;
          } else {
            combo = base + mark;
            type = "Compound (Yansaya) - Exception";
          }
        } else {
          combo = base + mark;
          type = "Compound (Yansaya)";
        }
      } else {
        combo = base + mark;
        if (conjuncts.includes(base)) {
          type = "Ligated Conjunct + Vowel";
        } else if (rakaransayaCombinations.includes(base)) {
          type = "Rakaransaya Combination + Vowel";
        } else if (touchingClusters.includes(base)) {
          type = "Touching Cluster + Vowel";
        } else {
          type = "Consonant + Vowel";
        }
      }

      if (!skip) {
        const div = document.createElement("div");
        div.className = "combo";

        const span = document.createElement("span");
        span.textContent = combo;
        span.className = "combo-text";

        // Apply direct styling for exceptions when showing the actual characters
        if (!showExceptions &&
          ((mark === "්‍ර" && rakaransayaExceptions.has(base)) ||
            (mark === "ර්‍" && repayaExceptions.has(base)) ||
            (mark === "්‍ය" && yansayaExceptions.has(base)))) {
          span.style.color = "#ef4444";
          span.style.fontWeight = "bold";
        }

        const tooltip = document.createElement("div");
        tooltip.className = "tooltip-box";

        // Format characters for display, add ZWJ label if present
        const chars = [];
        const unicodeParts = [];

        for (const c of combo.split("")) {
          chars.push(`<span class='tooltip-char'>${c}</span>`);

          // Check if character is ZWJ (U+200D)
          if (c === '\u200D') {
            chars[chars.length - 1] = `<span class='tooltip-char'>ZWJ</span>`;
            unicodeParts.push(`<span class='tooltip-unicode'>200D</span>`);
          } else {
            unicodeParts.push(`<span class='tooltip-unicode'>${c.charCodeAt(0).toString(16).toUpperCase().padStart(4, '0')}</span>`);
          }
        }

        tooltip.innerHTML =
          `<span class='tooltip-type'>${type}</span>` +
          `${chars.join(' + ')} <span class='tooltip-equal'>=</span> <span class='tooltip-char'>${combo}</span><br>` +
          `${unicodeParts.join(' + ')}`;

        div.appendChild(span);
        div.appendChild(tooltip);
        td.appendChild(div);
      }

      row.appendChild(td);
    });

    tbody.appendChild(row);
  });

  chart.appendChild(tbody);
}

// Copy utility functions
function copyRow(index) {
  const chart = document.getElementById("chart");
  const row = chart.rows[index + 1];
  const rowType = row.className;
  const combos = [];

  // Get checked options status
  const includeConsonants = document.getElementById('copy-consonants-checkbox').checked;
  const includeLigated = document.getElementById('copy-ligated-checkbox').checked;
  const includeRakaransaya = document.getElementById('copy-rakaransaya-checkbox')?.checked ?? true;
  const includeTouching = document.getElementById('copy-touching-checkbox').checked;

  // Only add to combos if the row type matches checked options
  if ((rowType === 'consonant-row' && includeConsonants) ||
    (rowType === 'ligated-conjunct-row' && includeLigated) ||
    (rowType === 'rakaransaya-combination-row' && includeRakaransaya) ||
    (rowType === 'touching-cluster-row' && includeTouching)) {

    Array.from(row.cells).slice(1).forEach(td => {
      const span = td.querySelector('.combo-text');
      if (span) combos.push(span.textContent);
    });
  }

  if (combos.length > 0) {
    navigator.clipboard.writeText(combos.join(" "));
    alert(`Copied ${combos.length} combinations from this row to clipboard!`);
  } else {
    alert("No combinations selected for copying. Please check filter options in the sidebar.");
  }
}

function copyColumn(index) {
  const chart = document.getElementById("chart");
  const combos = [];

  // Get checked options status
  const includeConsonants = document.getElementById('copy-consonants-checkbox').checked;
  const includeLigated = document.getElementById('copy-ligated-checkbox').checked;
  const includeRakaransaya = document.getElementById('copy-rakaransaya-checkbox')?.checked ?? true;
  const includeTouching = document.getElementById('copy-touching-checkbox').checked;

  Array.from(chart.rows).slice(1).forEach(row => {
    // Only add to combos if the row type matches checked options
    if ((row.className === 'consonant-row' && includeConsonants) ||
      (row.className === 'ligated-conjunct-row' && includeLigated) ||
      (row.className === 'rakaransaya-combination-row' && includeRakaransaya) ||
      (row.className === 'touching-cluster-row' && includeTouching)) {

      const td = row.cells[index + 1];
      const span = td.querySelector('.combo-text');
      if (span) combos.push(span.textContent);
    }
  });

  if (combos.length > 0) {
    navigator.clipboard.writeText(combos.join(" "));
    alert(`Copied ${combos.length} combinations from this column to clipboard!`);
  } else {
    alert("No combinations selected for copying. Please check filter options in the sidebar.");
  }
}

// Function for copying based on selection criteria
function copySelectedCombinations() {
  const chart = document.getElementById("chart");
  const combos = [];

  // Get checked options status
  const includeConsonants = document.getElementById('copy-consonants-checkbox').checked;
  const includeLigated = document.getElementById('copy-ligated-checkbox').checked;
  const includeRakaransaya = document.getElementById('copy-rakaransaya-checkbox')?.checked ?? true;
  const includeTouching = document.getElementById('copy-touching-checkbox').checked;

  // Add combinations based on checked options
  if (includeConsonants) {
    Array.from(chart.querySelectorAll('.consonant-row')).forEach(row => {
      Array.from(row.cells).slice(1).forEach(td => {
        const span = td.querySelector('.combo-text');
        if (span) combos.push(span.textContent);
      });
    });
  }

  if (includeLigated) {
    Array.from(chart.querySelectorAll('.ligated-conjunct-row')).forEach(row => {
      Array.from(row.cells).slice(1).forEach(td => {
        const span = td.querySelector('.combo-text');
        if (span) combos.push(span.textContent);
      });
    });
  }

  if (includeRakaransaya) {
    Array.from(chart.querySelectorAll('.rakaransaya-combination-row')).forEach(row => {
      Array.from(row.cells).slice(1).forEach(td => {
        const span = td.querySelector('.combo-text');
        if (span) combos.push(span.textContent);
      });
    });
  }

  if (includeTouching) {
    Array.from(chart.querySelectorAll('.touching-cluster-row')).forEach(row => {
      Array.from(row.cells).slice(1).forEach(td => {
        const span = td.querySelector('.combo-text');
        if (span) combos.push(span.textContent);
      });
    });
  }

  if (combos.length > 0) {
    navigator.clipboard.writeText(combos.join(" "));
    alert(`Copied ${combos.length} selected combinations to clipboard!`);
  } else {
    alert("No combinations selected for copying. Please check at least one option.");
  }
}

// Functions for specific copy operations
function copyConsonantCombinations() {
  const chart = document.getElementById("chart");
  const combos = [];

  Array.from(chart.querySelectorAll('.consonant-row')).forEach(row => {
    Array.from(row.cells).slice(1).forEach(td => {
      const span = td.querySelector('.combo-text');
      if (span) combos.push(span.textContent);
    });
  });

  navigator.clipboard.writeText(combos.join(" "));
  alert(`Copied ${combos.length} consonant combinations to clipboard!`);
}

function copyLigatedCombinations() {
  const chart = document.getElementById("chart");
  const combos = [];

  Array.from(chart.querySelectorAll('.ligated-conjunct-row')).forEach(row => {
    Array.from(row.cells).slice(1).forEach(td => {
      const span = td.querySelector('.combo-text');
      if (span) combos.push(span.textContent);
    });
  });

  navigator.clipboard.writeText(combos.join(" "));
  alert(`Copied ${combos.length} ligated conjunct combinations to clipboard!`);
}

function copyTouchingCombinations() {
  const chart = document.getElementById("chart");
  const combos = [];

  Array.from(chart.querySelectorAll('.touching-cluster-row')).forEach(row => {
    Array.from(row.cells).slice(1).forEach(td => {
      const span = td.querySelector('.combo-text');
      if (span) combos.push(span.textContent);
    });
  });

  navigator.clipboard.writeText(combos.join(" "));
  alert(`Copied ${combos.length} touching cluster combinations to clipboard!`);
}

function copyAllCombinations() {
  const chart = document.getElementById("chart");
  const combos = [];

  Array.from(chart.rows).slice(1).forEach(row => {
    Array.from(row.cells).slice(1).forEach(td => {
      const span = td.querySelector('.combo-text');
      if (span) combos.push(span.textContent);
    });
  });

  navigator.clipboard.writeText(combos.join(" "));
  alert(`Copied ${combos.length} total combinations to clipboard!`);
}

// UI control functions
function openNav() {
  document.getElementById("mySidebar").classList.add("open");
  document.body.classList.add("sidebar-open");
}

function closeNav() {
  document.getElementById("mySidebar").classList.remove("open");
  document.body.classList.remove("sidebar-open");
}

// Set up collapsible sections in sidebar
function setupCollapsibles() {
  const collapsibles = document.getElementsByClassName("collapsible");
  for (let i = 0; i < collapsibles.length; i++) {
    collapsibles[i].addEventListener("click", function () {
      this.classList.toggle("active");
      const content = this.nextElementSibling;
      if (content.style.maxHeight) {
        content.style.maxHeight = null;
      } else {
        content.style.maxHeight = content.scrollHeight + "px";
      }
    });
  }
}

// Set up click handler for copying cells
document.addEventListener('click', function (e) {
  const target = e.target.closest('td');
  if (!target) return;
  const comboSpan = target.querySelector('.combo-text');
  if (comboSpan) {
    const text = comboSpan.textContent;
    navigator.clipboard.writeText(text).then(() => {
      comboSpan.style.backgroundColor = '#dcfce7';
      setTimeout(() => {
        comboSpan.style.backgroundColor = '';
      }, 500);
    });
  }
});

// Font drag-and-drop
document.body.addEventListener("dragover", (e) => {
  e.preventDefault();
  e.dataTransfer.dropEffect = "copy";
});

document.body.addEventListener("drop", (e) => {
  e.preventDefault();
  const file = e.dataTransfer.files[0];
  if (!file || !file.name.match(/\.(ttf|otf|woff2?)$/i)) {
    alert("Please drop a valid font file (.ttf, .otf, .woff)");
    return;
  }

  const reader = new FileReader();
  reader.onload = function (event) {
    const font = new FontFace("CustomFont", event.target.result);
    font.load().then(function (loadedFont) {
      document.fonts.add(loadedFont);
      document.body.style.fontFamily = "CustomFont, sans-serif";
      alert("Custom font applied!");
    }).catch(() => alert("Failed to load font."));
  };
  reader.readAsArrayBuffer(file);
});

// Initialize event listeners for copy buttons
document.addEventListener('DOMContentLoaded', function () {
  document.getElementById('copy-selected').addEventListener('click', copySelectedCombinations);
  document.getElementById('copy-consonants-btn').addEventListener('click', copyConsonantCombinations);
  document.getElementById('copy-ligated-btn').addEventListener('click', copyLigatedCombinations);
  document.getElementById('copy-touching-btn').addEventListener('click', copyTouchingCombinations);
  document.getElementById('copy-all-btn').addEventListener('click', copyAllCombinations);

  // Add event listener for the show exceptions checkbox
  document.getElementById('show-exceptions-checkbox').addEventListener('change', renderChart);

  // Initialize the chart and collapsible sections
  renderChart();
  setupCollapsibles();
});

// Initialize immediately in case DOMContentLoaded already fired
if (document.readyState === "complete" || document.readyState === "interactive") {
  setTimeout(function () {
    renderChart();
    setupCollapsibles();
  }, 1);
}
