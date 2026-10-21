// Fonts loaded automatically when the tool opens. Kept to system fonts so
// the page works out of the box with nothing to download or configure.
//
// To compare your own (often non-redistributable) Sinhala fonts by default
// instead of dragging them in each time, see README.md — copy
// default-fonts.local.example.js to default-fonts.local.js and point it at
// a local fonts/ directory; both are gitignored.
const defaultFonts = [
    // Sinhala: the repo's own reference font and one system font (macOS).
    { name: 'Hodipotha', url: '../../resources/Hodipotha-9.ttf', systemFont: false },
    { name: 'Sinhala Sangam MN', url: null, systemFont: true, family: '"Sinhala Sangam MN", "Noto Sans Sinhala", sans-serif' },
    { name: 'Arial', url: null, systemFont: true, family: 'Arial, sans-serif' },
    { name: 'Times New Roman', url: null, systemFont: true, family: 'Times New Roman, serif' },
    { name: 'Helvetica', url: null, systemFont: true, family: 'Helvetica, sans-serif' },
    { name: 'Georgia', url: null, systemFont: true, family: 'Georgia, serif' }
];
