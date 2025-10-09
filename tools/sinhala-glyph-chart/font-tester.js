// font-tester.js
// Sinhala Font Tester - Font management and rendering
// Requires sinhala-definitions.js to be loaded first

// State management
const state = {
  fonts: new Map(), // fontId -> {name, family, file}
  activeFontId: 'system',
  fontSize: 20,
  organizeByVowel: false,
  currentHoverGlyph: null
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
  initializeDropZone();
  initializeControls();
  initializeCollapsibleSections();
  renderContent();
});

// === Font Management ===

function initializeDropZone() {
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');

  // Click to browse
  dropZone.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', (e) => handleFiles(e.target.files));

  // Drag and drop
  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.add('drag-over');
  });

  dropZone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.remove('drag-over');
  });

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.remove('drag-over');
    handleFiles(e.dataTransfer.files);
  });
}

async function handleFiles(files) {
  for (const file of files) {
    if (!file.name.match(/\.(ttf|otf|woff2?)$/i)) {
      alert(`Skipping ${file.name}: Invalid font file format`);
      continue;
    }

    try {
      await loadFont(file);
    } catch (error) {
      console.error(`Error loading ${file.name}:`, error);
      alert(`Failed to load ${file.name}`);
    }
  }
}

async function loadFont(file) {
  const fontId = `font-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  const fontFamily = `CustomFont-${fontId}`;

  const arrayBuffer = await file.arrayBuffer();
  const fontFace = new FontFace(fontFamily, arrayBuffer);

  await fontFace.load();
  document.fonts.add(fontFace);

  state.fonts.set(fontId, {
    name: file.name,
    family: fontFamily,
    file: file
  });

  updateFontUI();

  // If this is the first font, make it active
  if (state.fonts.size === 1) {
    state.activeFontId = fontId;
    updateActiveFont();
  }
}

function removeFont(fontId) {
  const font = state.fonts.get(fontId);
  if (!font) return;

  // Remove from document.fonts
  const fontsToRemove = [];
  for (const fontFace of document.fonts) {
    if (fontFace.family === font.family) {
      fontsToRemove.push(fontFace);
    }
  }
  fontsToRemove.forEach(f => document.fonts.delete(f));

  // Remove from state
  state.fonts.delete(fontId);

  // If this was the active font, switch to system
  if (state.activeFontId === fontId) {
    state.activeFontId = 'system';
    updateActiveFont();
  }

  updateFontUI();
}

function updateFontUI() {
  const fontList = document.getElementById('font-list');
  const fontItems = document.getElementById('font-items');
  const activeSelect = document.getElementById('active-font');

  if (state.fonts.size === 0) {
    fontList.style.display = 'none';
    activeSelect.innerHTML = '<option value="system">System Default</option>';
    return;
  }

  fontList.style.display = 'block';

  // Update font list
  fontItems.innerHTML = '';
  state.fonts.forEach((font, fontId) => {
    const item = document.createElement('div');
    item.className = 'font-item';
    if (fontId === state.activeFontId) {
      item.classList.add('active');
    }

    item.innerHTML = `
      <div class="font-name">${font.name}</div>
      ${fontId === state.activeFontId ? '<span class="badge">Active</span>' : ''}
      <div class="font-actions">
        <button class="button button-secondary" onclick="setActiveFont('${fontId}')">Set Active</button>
        <button class="button button-danger" onclick="removeFont('${fontId}')">Remove</button>
      </div>
    `;

    fontItems.appendChild(item);
  });

  // Update dropdown
  activeSelect.innerHTML = '<option value="system">System Default</option>';
  state.fonts.forEach((font, fontId) => {
    const option = document.createElement('option');
    option.value = fontId;
    option.textContent = font.name;
    if (fontId === state.activeFontId) {
      option.selected = true;
    }
    activeSelect.appendChild(option);
  });
}

function setActiveFont(fontId) {
  state.activeFontId = fontId;
  updateActiveFont();
  updateFontUI();
}

function updateActiveFont() {
  const container = document.getElementById('content-container');

  if (state.activeFontId === 'system') {
    container.style.fontFamily = '';
  } else {
    const font = state.fonts.get(state.activeFontId);
    if (font) {
      container.style.fontFamily = `${font.family}, sans-serif`;
    }
  }
}

// === Collapsible Sections ===

function initializeCollapsibleSections() {
  const fontUploadHeader = document.getElementById('font-upload-header');
  const fontUploadSection = document.getElementById('font-upload-section');

  fontUploadHeader.addEventListener('click', () => {
    fontUploadSection.classList.toggle('collapsed');
  });
}

// === Controls ===

function initializeControls() {
  // Active font dropdown
  document.getElementById('active-font').addEventListener('change', (e) => {
    setActiveFont(e.target.value);
  });

  // Font size control
  const fontSizeInput = document.getElementById('font-size');
  const fontSizeSlider = document.getElementById('font-size-slider');

  fontSizeInput.addEventListener('input', (e) => {
    state.fontSize = parseInt(e.target.value);
    fontSizeSlider.value = e.target.value;
    updateFontSize();
  });

  fontSizeSlider.addEventListener('input', (e) => {
    state.fontSize = parseInt(e.target.value);
    fontSizeInput.value = e.target.value;
    updateFontSize();
  });

  // Organization toggle
  const organizeToggle = document.getElementById('organize-toggle');
  const organizeLabel = document.getElementById('organize-label');

  organizeToggle.addEventListener('change', (e) => {
    state.organizeByVowel = e.target.checked;
    organizeLabel.textContent = state.organizeByVowel ? 'Vowel Mark' : 'Base Letter';
    renderContent();
  });

  // Expand/Collapse all
  document.getElementById('expand-all').addEventListener('click', () => {
    document.querySelectorAll('.section').forEach(section => {
      section.classList.remove('collapsed');
    });
  });

  document.getElementById('collapse-all').addEventListener('click', () => {
    document.querySelectorAll('.section').forEach(section => {
      section.classList.add('collapsed');
    });
  });
}

function updateFontSize() {
  document.querySelectorAll('.glyph-text').forEach(el => {
    el.style.fontSize = `${state.fontSize}pt`;
  });

  // Update grid cell minimum size based on font size
  const minCellSize = Math.max(60, state.fontSize * 1.5 + 20);
  document.querySelectorAll('.section-content').forEach(content => {
    content.style.gridTemplateColumns = `repeat(auto-fill, minmax(${minCellSize}px, 1fr))`;
  });
}

// === Content Rendering ===

function renderContent() {
  const container = document.getElementById('content-container');
  container.innerHTML = '';

  if (state.organizeByVowel) {
    renderByVowelMark(container);
  } else {
    renderByBaseLetter(container);
  }

  updateFontSize();
}

function renderByBaseLetter(container) {
  baseLetters.forEach(baseLetter => {
    const section = createSection(baseLetter, () => {
      const glyphs = [];

      // Add combinations with all vowel marks
      vowelMarks.forEach(mark => {
        glyphs.push(baseLetter + mark);
      });

      // Add combinations with compound signs
      compoundSigns.forEach(sign => {
        if (sign === "ර්‍") {
          // Repaya comes before
          if (!repayaExceptions.has(baseLetter)) {
            glyphs.push(sign + baseLetter);
          }
        } else {
          // Rakaransaya and Yansaya come after
          const exceptionSet = sign === "්‍ර" ? rakaransayaExceptions : yansayaExceptions;
          if (!exceptionSet.has(baseLetter)) {
            glyphs.push(baseLetter + sign);
          }
        }
      });

      return glyphs;
    });

    container.appendChild(section);
  });

  // Add Consonant + Rakaransaya + Vowel Marks section
  renderConsonantRakaransayaVowels(container);
}

function renderByVowelMark(container) {
  const allMarks = [...vowelMarks, ...compoundSigns];

  allMarks.forEach(mark => {
    const displayMark = mark || "(none)";
    const section = createSection(displayMark, () => {
      const glyphs = [];

      baseLetters.forEach(baseLetter => {
        if (compoundSigns.includes(mark)) {
          // Handle compound signs with exceptions
          if (mark === "ර්‍") {
            if (!repayaExceptions.has(baseLetter)) {
              glyphs.push(mark + baseLetter);
            }
          } else {
            const exceptionSet = mark === "්‍ර" ? rakaransayaExceptions : yansayaExceptions;
            if (!exceptionSet.has(baseLetter)) {
              glyphs.push(baseLetter + mark);
            }
          }
        } else {
          // Regular vowel marks
          glyphs.push(baseLetter + mark);
        }
      });

      return glyphs;
    });

    container.appendChild(section);
  });

  // Add Consonant + Rakaransaya + Vowel Marks section
  renderConsonantRakaransayaVowels(container);
}

function renderConsonantRakaransayaVowels(container) {
  // Get all consonants (excluding conjuncts, rakaransaya combinations, and touching clusters)
  const simpleConsonants = consonants;
  const rakaransaya = "්‍ර";

  simpleConsonants.forEach(consonant => {
    // Skip if this consonant is in rakaransaya exceptions
    if (rakaransayaExceptions.has(consonant)) {
      return;
    }

    const baseCombo = consonant + rakaransaya;
    const section = createSection(`${baseCombo} + Vowel Marks`, () => {
      const glyphs = [];

      // Add combinations with all vowel marks
      vowelMarks.forEach(mark => {
        glyphs.push(baseCombo + mark);
      });

      return glyphs;
    });

    container.appendChild(section);
  });
}

function createSection(title, getGlyphs) {
  const section = document.createElement('div');
  section.className = 'section';

  const header = document.createElement('div');
  header.className = 'section-header';
  header.innerHTML = `
    <div class="section-title">${title}</div>
    <div class="section-toggle">▼</div>
  `;

  header.addEventListener('click', () => {
    section.classList.toggle('collapsed');
  });

  const content = document.createElement('div');
  content.className = 'section-content';

  const glyphs = getGlyphs();
  glyphs.forEach(glyph => {
    const cell = createGlyphCell(glyph);
    content.appendChild(cell);
  });

  section.appendChild(header);
  section.appendChild(content);

  return section;
}

function createGlyphCell(glyph) {
  const cell = document.createElement('div');
  cell.className = 'glyph-cell';

  const text = document.createElement('div');
  text.className = 'glyph-text';
  text.textContent = glyph;
  text.style.fontSize = `${state.fontSize}pt`;

  cell.appendChild(text);

  // Click to toggle comparison bar
  cell.addEventListener('click', () => {
    const compBar = document.getElementById('comparison-bar');

    // If clicking the same glyph, toggle off
    if (state.currentHoverGlyph === glyph && compBar.classList.contains('active')) {
      hideComparison();
    } else {
      // Show comparison for this glyph
      showComparison(glyph);
    }
  });

  return cell;
}

// === Comparison Bar ===

function showComparison(glyph) {
  state.currentHoverGlyph = glyph;

  const compBar = document.getElementById('comparison-bar');
  const compContent = document.getElementById('comparison-content');

  compContent.innerHTML = '';

  // Add system font
  const systemItem = document.createElement('div');
  systemItem.className = 'comparison-item';
  if (state.activeFontId === 'system') {
    systemItem.classList.add('active');
  }
  systemItem.innerHTML = `
    <div class="comparison-font-name">System Default</div>
    <div class="comparison-glyph">${glyph}</div>
  `;
  compContent.appendChild(systemItem);

  // Add all loaded fonts
  state.fonts.forEach((font, fontId) => {
    const item = document.createElement('div');
    item.className = 'comparison-item';
    if (fontId === state.activeFontId) {
      item.classList.add('active');
    }

    const glyphEl = document.createElement('div');
    glyphEl.className = 'comparison-glyph';
    glyphEl.textContent = glyph;
    glyphEl.style.fontFamily = `${font.family}, sans-serif`;

    item.innerHTML = `<div class="comparison-font-name">${font.name}</div>`;
    item.appendChild(glyphEl);

    compContent.appendChild(item);
  });

  compBar.classList.add('active');
}

function hideComparison() {
  const compBar = document.getElementById('comparison-bar');
  compBar.classList.remove('active');
  state.currentHoverGlyph = null;
}

// Click outside comparison bar to close it
document.addEventListener('DOMContentLoaded', function() {
  const compBar = document.getElementById('comparison-bar');

  // Close button for comparison bar
  const closeBtn = document.createElement('button');
  closeBtn.textContent = '×';
  closeBtn.style.cssText = `
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    background: none;
    border: none;
    font-size: 1.5rem;
    cursor: pointer;
    color: var(--neutral-600);
    padding: 0.25rem 0.5rem;
  `;
  closeBtn.addEventListener('click', hideComparison);
  compBar.insertBefore(closeBtn, compBar.firstChild);
});

// Make functions globally available
window.setActiveFont = setActiveFont;
window.removeFont = removeFont;
