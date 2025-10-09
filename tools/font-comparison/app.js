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
                const font = opentype.parse(arrayBuffer);
                
                const fontData = {
                    name: font.names.fullName?.en || font.names.fontFamily?.en || file.name,
                    font: font,
                    file: file,
                    systemFont: false
                };

                this.fonts.push(fontData);
                this.updateFontList();
                this.renderCurrentView();
            } catch (error) {
                console.error(`Error loading font ${file.name}:`, error);
            }
        }
    }

    async loadDefaultFonts() {
        for (const fontData of defaultFonts) {
            if (fontData.url && !fontData.systemFont) {
                try {
                    const response = await fetch(fontData.url);
                    const arrayBuffer = await response.arrayBuffer();
                    const font = opentype.parse(arrayBuffer);
                    
                    const loadedFont = {
                        name: fontData.name,
                        font: font,
                        url: fontData.url,
                        systemFont: false
                    };
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
        const scale = window.devicePixelRatio || 1;
        canvas.width = canvasSize * scale;
        canvas.height = canvasSize * scale;
        canvas.style.width = `${canvasSize}px`;
        canvas.style.height = `${canvasSize}px`;
        
        ctx.scale(scale, scale);
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, canvasSize, canvasSize);

        if (fontData.systemFont) {
            this.renderSystemFont(ctx, fontData, size, canvasSize);
        } else {
            this.renderOpenTypeFont(ctx, fontData, size, canvasSize);
        }

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

    renderSystemFont(ctx, fontData, size, canvasSize) {
        ctx.font = `${size}px ${fontData.family}`;
        ctx.fillStyle = '#000000';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        
        const x = canvasSize / 2;
        const y = canvasSize / 2;
        
        if (this.currentSpacing !== 0) {
            // Manual letter spacing for system fonts
            const chars = Array.from(this.currentText);
            const totalWidth = ctx.measureText(this.currentText).width + (this.currentSpacing * (chars.length - 1));
            let currentX = x - totalWidth / 2;
            
            chars.forEach(char => {
                ctx.fillText(char, currentX, y);
                currentX += ctx.measureText(char).width + this.currentSpacing;
            });
        } else {
            ctx.fillText(this.currentText, x, y);
        }
    }

    renderOpenTypeFont(ctx, fontData, size, canvasSize) {
        const font = fontData.font;
        const x = canvasSize / 2;
        const baseline = canvasSize * 0.6;
        
        try {
            const unitsPerEm = font.unitsPerEm || 1000;
            const scale = size / unitsPerEm;
            
            let totalWidth = 0;
            const chars = Array.from(this.currentText);
            
            chars.forEach((char, index) => {
                const glyph = font.charToGlyph(char);
                if (glyph) {
                    totalWidth += (glyph.advanceWidth || 0) * scale;
                    if (index < chars.length - 1) {
                        totalWidth += this.currentSpacing;
                    }
                }
            });

            let currentX = x - totalWidth / 2;

            chars.forEach((char, index) => {
                const glyph = font.charToGlyph(char);
                if (glyph) {
                    const path = glyph.getPath(currentX, baseline, size);
                    path.fill = '#000000';
                    path.draw(ctx);
                    currentX += (glyph.advanceWidth || 0) * scale;
                    if (index < chars.length - 1) {
                        currentX += this.currentSpacing;
                    }
                }
            });

        } catch (error) {
            console.error('Error rendering font:', error);
            ctx.font = `${size}px Arial`;
            ctx.fillStyle = '#ff0000';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('Error', x, canvasSize / 2);
        }
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