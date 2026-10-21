class FontComparison {
    constructor() {
        this.fonts = [];
        this.currentView = 'gallery';
        this.currentIndex = 0;
        this.currentText = 'Ag';
        this.currentSize = 72;
        this.currentSpacing = 0;
        this.tileSpacing = 20;
        this.showFontNames = true;
        this.canvasSize = 200;
        this.faceCount = 0;
        
        this.initializeElements();
        this.loadFromLocalStorage();
        this.attachEventListeners();
        this.loadDefaultFonts();
    }

    initializeElements() {
        this.textInput = document.getElementById('text-input');
        this.sizeSlider = document.getElementById('size-slider');
        this.sizeDisplay = document.getElementById('size-display');
        this.spacingSlider = document.getElementById('spacing-slider');
        this.spacingDisplay = document.getElementById('spacing-display');
        this.tileSpacingSlider = document.getElementById('tile-spacing-slider');
        this.tileSpacingDisplay = document.getElementById('tile-spacing-display');
        this.showNamesCheckbox = document.getElementById('show-names');
        this.dropZone = document.getElementById('drop-zone');
        this.fileInput = document.getElementById('file-input');
        this.fontList = document.getElementById('font-list');
        this.tooltip = document.getElementById('tooltip');
        
        this.galleryContainer = document.getElementById('gallery-container');
        this.thumbnailContainer = document.getElementById('thumbnail-container');
        this.compareContainer = document.getElementById('compare-container');
        
        this.galleryDisplay = document.getElementById('gallery-display');
        this.thumbnailGrid = document.getElementById('thumbnail-grid');
        this.compareGrid = document.getElementById('compare-grid');
        
        this.fontCounter = document.getElementById('font-counter');
        this.prevBtn = document.getElementById('prev-btn');
        this.nextBtn = document.getElementById('next-btn');
        
        this.viewBtns = {
            gallery: document.getElementById('gallery-view'),
            thumbnail: document.getElementById('thumbnail-view'),
            compare: document.getElementById('compare-view')
        };
    }

    attachEventListeners() {
        this.textInput.addEventListener('input', (e) => {
            this.currentText = e.target.value || 'Ag';
            this.saveToLocalStorage();
            this.renderCurrentView();
        });

        this.sizeSlider.addEventListener('input', (e) => {
            this.currentSize = parseInt(e.target.value);
            this.sizeDisplay.textContent = `${this.currentSize}px`;
            this.saveToLocalStorage();
            this.renderCurrentView();
        });

        this.spacingSlider.addEventListener('input', (e) => {
            this.currentSpacing = parseInt(e.target.value);
            this.spacingDisplay.textContent = `${this.currentSpacing}px`;
            this.saveToLocalStorage();
            this.renderCurrentView();
        });

        this.tileSpacingSlider.addEventListener('input', (e) => {
            this.tileSpacing = parseInt(e.target.value);
            this.tileSpacingDisplay.textContent = `${this.tileSpacing}px`;
            this.saveToLocalStorage();
            this.updateTileSpacing();
        });

        this.showNamesCheckbox.addEventListener('change', (e) => {
            this.showFontNames = e.target.checked;
            this.saveToLocalStorage();
            this.renderCurrentView();
        });

        this.dropZone.addEventListener('dragover', this.handleDragOver.bind(this));
        this.dropZone.addEventListener('drop', this.handleDrop.bind(this));
        this.dropZone.addEventListener('click', () => this.fileInput.click());
        
        this.fileInput.addEventListener('change', this.handleFileSelect.bind(this));

        this.prevBtn.addEventListener('click', () => this.navigateGallery(-1));
        this.nextBtn.addEventListener('click', () => this.navigateGallery(1));

        Object.keys(this.viewBtns).forEach(view => {
            this.viewBtns[view].addEventListener('click', () => this.switchView(view));
        });

        document.addEventListener('mousemove', this.handleMouseMove.bind(this));
    }

    loadFromLocalStorage() {
        try {
            const saved = localStorage.getItem('fontComparison');
            if (saved) {
                const data = JSON.parse(saved);
                this.currentText = data.currentText || 'Ag';
                this.currentSize = data.currentSize || 72;
                this.currentSpacing = data.currentSpacing || 0;
                this.tileSpacing = data.tileSpacing || 20;
                this.showFontNames = data.showFontNames !== undefined ? data.showFontNames : true;
                this.currentView = data.currentView || 'gallery';
                
                // Update UI elements
                this.textInput.value = this.currentText;
                this.sizeSlider.value = this.currentSize;
                this.sizeDisplay.textContent = `${this.currentSize}px`;
                this.spacingSlider.value = this.currentSpacing;
                this.spacingDisplay.textContent = `${this.currentSpacing}px`;
                this.tileSpacingSlider.value = this.tileSpacing;
                this.tileSpacingDisplay.textContent = `${this.tileSpacing}px`;
                this.showNamesCheckbox.checked = this.showFontNames;
            }
        } catch (error) {
            console.error('Error loading from localStorage:', error);
        }
    }

    saveToLocalStorage() {
        try {
            const data = {
                currentText: this.currentText,
                currentSize: this.currentSize,
                currentSpacing: this.currentSpacing,
                tileSpacing: this.tileSpacing,
                showFontNames: this.showFontNames,
                currentView: this.currentView
            };
            localStorage.setItem('fontComparison', JSON.stringify(data));
        } catch (error) {
            console.error('Error saving to localStorage:', error);
        }
    }

    updateTileSpacing() {
        const thumbnailGrid = document.getElementById('thumbnail-grid');
        const compareGrid = document.getElementById('compare-grid');
        
        if (thumbnailGrid) {
            thumbnailGrid.style.gap = `${this.tileSpacing}px`;
        }
        if (compareGrid) {
            compareGrid.style.gap = `${this.tileSpacing}px`;
        }
        
        // Update padding for individual font samples
        const samples = document.querySelectorAll('.font-sample');
        samples.forEach(sample => {
            sample.style.padding = `${Math.max(5, this.tileSpacing / 2)}px`;
        });
    }

    // Canvas colours follow the black-and-white palette (../_shared/bw.css), light or dark.
    cssColor(name, fallback) {
        return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
    }

    getCanvasSize() {
        // Dynamic canvas size based on font size
        const baseSize = 200;
        const maxSize = 400;
        const sizeRatio = this.currentSize / 72; // 72px as base
        return Math.min(maxSize, baseSize * Math.max(1, sizeRatio * 0.6));
    }

    handleDragOver(e) {
        e.preventDefault();
        this.dropZone.classList.add('dragover');
    }

    handleDrop(e) {
        e.preventDefault();
        this.dropZone.classList.remove('dragover');
        const files = Array.from(e.dataTransfer.files);
        this.loadFontFiles(files);
    }

    handleFileSelect(e) {
        const files = Array.from(e.target.files);
        this.loadFontFiles(files);
    }

    async loadFontFiles(files) {
        const fontFiles = files.filter(file => 
            file.name.match(/\.(ttf|otf|woff|woff2)$/i)
        );

        for (const file of fontFiles) {
            try {
                const arrayBuffer = await file.arrayBuffer();
                const fontData = await this.registerFont(arrayBuffer, file.name.replace(/\.[^.]+$/, ''));
                fontData.file = file;
                this.fonts.push(fontData);
                this.updateFontList();
                this.renderCurrentView();
            } catch (error) {
                console.error(`Error loading font ${file.name}:`, error);
            }
        }
    }

    // Hand the font to the browser (FontFace) so canvas text goes through the
    // normal text shaper: conjuncts, vowel signs and other OpenType features
    // render as they do on a web page. opentype.js is only used for the
    // display name, and only if it loaded.
    async registerFont(arrayBuffer, fallbackName) {
        let name = fallbackName;
        try {
            if (typeof opentype !== 'undefined') {
                const names = opentype.parse(arrayBuffer).names;
                name = names.fullName?.en || names.fontFamily?.en || fallbackName;
            }
        } catch (e) { /* keep the file name */ }
        const family = `cmp-font-${++this.faceCount}`;
        const face = new FontFace(family, arrayBuffer);
        await face.load();
        document.fonts.add(face);
        return { name, family: `"${family}"`, systemFont: false, loaded: true };
    }

    async loadDefaultFonts() {
        // default-fonts.local.js is optional (gitignored) — merge it in if
        // the page loaded it successfully (see README.md).
        const fontsToLoad = typeof defaultFontsLocal !== 'undefined'
            ? [...defaultFonts, ...defaultFontsLocal]
            : defaultFonts;
        for (const fontData of fontsToLoad) {
            if (fontData.url && !fontData.systemFont) {
                try {
                    const response = await fetch(fontData.url);
                    const loadedFont = await this.registerFont(await response.arrayBuffer(), fontData.name);
                    loadedFont.name = fontData.name;
                    loadedFont.url = fontData.url;
                    this.fonts.push(loadedFont);
                } catch (error) {
                    console.error(`Error loading font ${fontData.name}:`, error);
                }
            } else {
                this.fonts.push(fontData);
            }
        }
        this.updateFontList();
        this.renderCurrentView();
        this.updateTileSpacing();
    }

    updateFontList() {
        this.fontList.innerHTML = '';
        this.fonts.forEach((font, index) => {
            const li = document.createElement('li');
            li.innerHTML = `
                <span>${font.name}</span>
                <button class="remove-font" onclick="fontComparison.removeFont(${index})">×</button>
            `;
            this.fontList.appendChild(li);
        });
        
        this.updateGalleryNavigation();
    }

    removeFont(index) {
        this.fonts.splice(index, 1);
        if (this.currentIndex >= this.fonts.length) {
            this.currentIndex = Math.max(0, this.fonts.length - 1);
        }
        this.updateFontList();
        this.renderCurrentView();
    }

    switchView(view) {
        this.currentView = view;
        
        Object.keys(this.viewBtns).forEach(v => {
            this.viewBtns[v].classList.remove('active');
            document.getElementById(`${v}-container`).classList.remove('active');
        });
        
        this.viewBtns[view].classList.add('active');
        document.getElementById(`${view}-container`).classList.add('active');
        
        this.saveToLocalStorage();
        this.renderCurrentView();
    }

    renderCurrentView() {
        switch (this.currentView) {
            case 'gallery':
                this.renderGallery();
                break;
            case 'thumbnail':
                this.renderThumbnails();
                break;
            case 'compare':
                this.renderCompare();
                break;
        }
    }

    renderGallery() {
        this.galleryDisplay.innerHTML = '';
        if (this.fonts.length === 0) return;

        const font = this.fonts[this.currentIndex];
        const sample = this.createFontSample(font, this.currentSize);
        this.galleryDisplay.appendChild(sample);
        this.updateGalleryNavigation();
    }

    renderThumbnails() {
        this.thumbnailGrid.innerHTML = '';
        this.fonts.forEach(font => {
            const sample = this.createFontSample(font, Math.min(this.currentSize, 64));
            this.thumbnailGrid.appendChild(sample);
        });
        this.updateTileSpacing();
    }

    renderCompare() {
        this.compareGrid.innerHTML = '';
        const compareSize = Math.min(this.currentSize, 96);
        this.fonts.slice(0, 4).forEach(font => {
            const sample = this.createFontSample(font, compareSize);
            this.compareGrid.appendChild(sample);
        });
        this.updateTileSpacing();
    }

    createFontSample(fontData, size) {
        const container = document.createElement('div');
        container.className = 'font-sample';
        container.style.padding = `${Math.max(5, this.tileSpacing / 2)}px`;
        
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        
        const canvasSize = this.getCanvasSize();
        // Text longer than the square tile gets a wider canvas instead of being clipped.
        const width = Math.max(canvasSize, Math.ceil(this.measureText(fontData, size)) + 40);
        const scale = window.devicePixelRatio || 1;
        canvas.width = width * scale;
        canvas.height = canvasSize * scale;
        canvas.style.width = `${width}px`;
        canvas.style.height = `${canvasSize}px`;
        canvas.style.maxWidth = '100%';

        ctx.scale(scale, scale);
        ctx.fillStyle = this.cssColor('--bg', '#ffffff');
        ctx.fillRect(0, 0, width, canvasSize);

        this.renderText(ctx, fontData, size, width, canvasSize);

        const nameDiv = document.createElement('div');
        nameDiv.className = 'font-name';
        nameDiv.textContent = fontData.name;
        nameDiv.style.display = this.showFontNames ? 'block' : 'none';

        container.appendChild(canvas);
        container.appendChild(nameDiv);
        
        container.addEventListener('mouseenter', (e) => this.showTooltip(e, fontData.name));
        container.addEventListener('mouseleave', () => this.hideTooltip());

        return container;
    }

    applyTextStyle(ctx, fontData, size) {
        ctx.font = `${size}px ${fontData.family}, sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        // Letter spacing is applied by the browser, so shaping is untouched.
        if ('letterSpacing' in ctx) ctx.letterSpacing = `${this.currentSpacing}px`;
    }

    measureText(fontData, size) {
        const ctx = document.createElement('canvas').getContext('2d');
        this.applyTextStyle(ctx, fontData, size);
        return ctx.measureText(this.currentText).width;
    }

    renderText(ctx, fontData, size, width, height) {
        this.applyTextStyle(ctx, fontData, size);
        ctx.fillStyle = this.cssColor('--fg', '#000000');
        ctx.fillText(this.currentText, width / 2, height / 2);
    }

    navigateGallery(direction) {
        if (this.fonts.length === 0) return;
        
        this.currentIndex += direction;
        if (this.currentIndex < 0) this.currentIndex = this.fonts.length - 1;
        if (this.currentIndex >= this.fonts.length) this.currentIndex = 0;
        
        this.renderGallery();
    }

    updateGalleryNavigation() {
        if (this.fonts.length === 0) {
            this.fontCounter.textContent = '0 / 0';
            this.prevBtn.disabled = true;
            this.nextBtn.disabled = true;
        } else {
            this.fontCounter.textContent = `${this.currentIndex + 1} / ${this.fonts.length}`;
            this.prevBtn.disabled = false;
            this.nextBtn.disabled = false;
        }
    }

    showTooltip(e, text) {
        this.tooltip.textContent = text;
        this.tooltip.classList.add('show');
        this.updateTooltipPosition(e);
    }

    hideTooltip() {
        this.tooltip.classList.remove('show');
    }

    updateTooltipPosition(e) {
        const rect = this.tooltip.getBoundingClientRect();
        const x = e.clientX + 10;
        const y = e.clientY - rect.height - 10;
        
        this.tooltip.style.left = `${x}px`;
        this.tooltip.style.top = `${y}px`;
    }

    handleMouseMove(e) {
        if (this.tooltip.classList.contains('show')) {
            this.updateTooltipPosition(e);
        }
    }
}

let fontComparison;

document.addEventListener('DOMContentLoaded', () => {
    fontComparison = new FontComparison();
});