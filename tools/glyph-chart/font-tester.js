// font-tester.js
// Sinhala Font Tester - Font management and rendering
// Requires sinhala-definitions.js to be loaded first

// State management
const state = {
  fonts: new Map(), // fontId -> {name, family, path}
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
  loadSavedState();
  loadSavedFonts();
  renderContent();
  restoreScrollPosition();
});

// Save scroll position before page unload
window.addEventListener('beforeunload', function() {
  saveScrollPosition();
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
      // Ask user to copy font to ./font/ directory
      const fileName = file.name;
      const confirmed = confirm(
        `Please ensure "${fileName}" is copied to the "./font/" directory.\n\n` +
        `The tool will load the font from: ./font/${fileName}\n\n` +
        `Click OK once the file is in place.`
      );

      if (confirmed) {
        await loadFontFromPath(fileName);
      }
    } catch (error) {
      console.error(`Error loading ${file.name}:`, error);
      alert(`Failed to load ${file.name}. Make sure the font file is in the ./font/ directory.`);
    }
  }
}

async function loadFontFromPath(fileName) {
  const fontId = `font-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  const fontFamily = `CustomFont-${fontId}`;
  const fontPath = `./font/${fileName}`;

  // Create CSS @font-face rule with path and cache-busting
  createFontFaceFromPath(fontFamily, fontPath);

  state.fonts.set(fontId, {
    name: fileName,
    family: fontFamily,
    path: fontPath
  });

  // Save to localStorage
  saveFontsToStorage();

  updateFontUI();

  // If this is the first font, make it active
  if (state.fonts.size === 1) {
    state.activeFontId = fontId;
    updateActiveFont();
  }
}

function createFontFaceFromPath(fontFamily, fontPath) {
  // Remove any existing font-face with the same family name
  const existingStyles = document.querySelectorAll(`style[data-font-family="${fontFamily}"]`);
  existingStyles.forEach(style => style.remove());

  // Add cache-busting timestamp to ensure fresh load
  const cacheBustPath = `${fontPath}?v=${Date.now()}`;

  // Create style element with @font-face rule using file path
  const styleElement = document.createElement('style');
  styleElement.setAttribute('data-font-family', fontFamily);
  styleElement.appendChild(document.createTextNode(
    `@font-face { font-family: '${fontFamily}'; src: url('${cacheBustPath}'); }`
  ));
  document.head.appendChild(styleElement);

  console.log(`Loaded font: ${fontFamily} from ${cacheBustPath}`);
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

  // Update localStorage
  saveFontsToStorage();

  updateFontUI();
}

// === LocalStorage Persistence ===

function saveFontsToStorage() {
  const fontsData = [];

  for (const [fontId, font] of state.fonts) {
    fontsData.push({
      id: fontId,
      name: font.name,
      path: font.path
    });
  }

  try {
    localStorage.setItem('sinhala-font-tester-fonts', JSON.stringify(fontsData));
    localStorage.setItem('sinhala-font-tester-active', state.activeFontId);
  } catch (error) {
    console.error('Failed to save to localStorage:', error);
  }
}

function loadSavedFonts() {
  try {
    const fontsDataStr = localStorage.getItem('sinhala-font-tester-fonts');
    const savedActiveFontId = localStorage.getItem('sinhala-font-tester-active');

    if (!fontsDataStr) return;

    const fontsData = JSON.parse(fontsDataStr);

    for (const fontData of fontsData) {
      try {
        // Reload font from saved path
        loadFontFromStorage(fontData.id, fontData.name, fontData.path);
      } catch (error) {
        console.error(`Failed to reload font ${fontData.name}:`, error);
      }
    }

    // Restore active font
    if (savedActiveFontId && (savedActiveFontId === 'system' || state.fonts.has(savedActiveFontId))) {
      state.activeFontId = savedActiveFontId;
      updateActiveFont();
    }

    updateFontUI();
  } catch (error) {
    console.error('Failed to load saved fonts:', error);
    // Clear corrupted data
    localStorage.removeItem('sinhala-font-tester-fonts');
    localStorage.removeItem('sinhala-font-tester-active');
  }
}

function loadFontFromStorage(fontId, fileName, fontPath) {
  const fontFamily = `CustomFont-${fontId}`;

  // Create CSS @font-face rule from path with cache-busting
  createFontFaceFromPath(fontFamily, fontPath);

  state.fonts.set(fontId, {
    name: fileName,
    family: fontFamily,
    path: fontPath
  });
}

// === State Persistence ===

function saveState() {
  try {
    const stateData = {
      fontSize: state.fontSize,
      organizeByVowel: state.organizeByVowel
    };
    localStorage.setItem('sinhala-font-tester-state', JSON.stringify(stateData));
  } catch (error) {
    console.error('Failed to save state:', error);
  }
}

function loadSavedState() {
  try {
    const stateDataStr = localStorage.getItem('sinhala-font-tester-state');
    if (!stateDataStr) return;

    const stateData = JSON.parse(stateDataStr);

    // Restore font size
    if (stateData.fontSize) {
      state.fontSize = stateData.fontSize;
      const fontSizeInput = document.getElementById('font-size');
      const fontSizeSlider = document.getElementById('font-size-slider');
      if (fontSizeInput) fontSizeInput.value = state.fontSize;
      if (fontSizeSlider) fontSizeSlider.value = state.fontSize;
    }

    // Restore organize toggle
    if (stateData.organizeByVowel !== undefined) {
      state.organizeByVowel = stateData.organizeByVowel;
      const organizeToggle = document.getElementById('organize-toggle');
      const organizeLabel = document.getElementById('organize-label');
      if (organizeToggle) organizeToggle.checked = state.organizeByVowel;
      if (organizeLabel) organizeLabel.textContent = state.organizeByVowel ? 'Vowel Mark' : 'Base Letter';
    }
  } catch (error) {
    console.error('Failed to load saved state:', error);
  }
}

function saveScrollPosition() {
  try {
    const scrollData = {
      x: window.scrollX,
      y: window.scrollY
    };
    sessionStorage.setItem('sinhala-font-tester-scroll', JSON.stringify(scrollData));
  } catch (error) {
    console.error('Failed to save scroll position:', error);
  }
}

function restoreScrollPosition() {
  try {
    const scrollDataStr = sessionStorage.getItem('sinhala-font-tester-scroll');
    if (!scrollDataStr) return;

    const scrollData = JSON.parse(scrollDataStr);
    window.scrollTo(scrollData.x, scrollData.y);
  } catch (error) {
    console.error('Failed to restore scroll position:', error);
  }
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

  // Save active font preference
  try {
    localStorage.setItem('sinhala-font-tester-active', state.activeFontId);
  } catch (error) {
    console.error('Failed to save active font preference:', error);
  }
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
    saveState();
  });

  fontSizeSlider.addEventListener('input', (e) => {
    state.fontSize = parseInt(e.target.value);
    fontSizeInput.value = e.target.value;
    updateFontSize();
    saveState();
  });

  // Organization toggle
  const organizeToggle = document.getElementById('organize-toggle');
  const organizeLabel = document.getElementById('organize-label');

  organizeToggle.addEventListener('change', (e) => {
    state.organizeByVowel = e.target.checked;
    organizeLabel.textContent = state.organizeByVowel ? 'Vowel Mark' : 'Base Letter';
    renderContent();
    saveState();
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

  // Update line-height in section content based on font size
  const lineHeight = Math.max(1.5, state.fontSize / 10);
  document.querySelectorAll('.section-content').forEach(content => {
    content.style.lineHeight = lineHeight;
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

  // Create editable glyph element factory
  function createEditableGlyph(text, fontFamily = null, isSystem = false) {
    const glyphEl = document.createElement('div');
    glyphEl.className = 'comparison-glyph';
    glyphEl.contentEditable = 'true';
    glyphEl.textContent = text;
    glyphEl.spellcheck = false;
    if (fontFamily) {
      glyphEl.style.fontFamily = `${fontFamily}, sans-serif`;
    }

    // Sync text changes across all comparison glyphs
    glyphEl.addEventListener('input', (e) => {
      const newText = e.target.textContent;
      state.currentHoverGlyph = newText;

      // Update all other comparison glyphs
      const allGlyphs = compContent.querySelectorAll('.comparison-glyph');
      allGlyphs.forEach(g => {
        if (g !== e.target) {
          g.textContent = newText;
        }
      });
    });

    return glyphEl;
  }

  // Add system font
  const systemItem = document.createElement('div');
  systemItem.className = 'comparison-item';
  if (state.activeFontId === 'system') {
    systemItem.classList.add('active');
  }

  const systemNameEl = document.createElement('div');
  systemNameEl.className = 'comparison-font-name';
  systemNameEl.textContent = 'System Default';

  systemItem.appendChild(systemNameEl);
  systemItem.appendChild(createEditableGlyph(glyph, null, true));
  compContent.appendChild(systemItem);

  // Add all loaded fonts
  state.fonts.forEach((font, fontId) => {
    const item = document.createElement('div');
    item.className = 'comparison-item';
    if (fontId === state.activeFontId) {
      item.classList.add('active');
    }

    const nameEl = document.createElement('div');
    nameEl.className = 'comparison-font-name';
    nameEl.textContent = font.name;

    item.appendChild(nameEl);
    item.appendChild(createEditableGlyph(glyph, font.family));
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
