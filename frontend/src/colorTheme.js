// Color theme configuration for Xiquet
// Based on casteller colors: white shirt, black sash, red handkerchief, white pants

export const COLOR_THEMES = {
  white: {
    name: 'Blanc',
    color: '#ffffff',
    image: '/xiquet_images/basic_white.png',
    primary: '#000000', // Black sash
    secondary: '#ffffff', // White shirt
    accent: '#d0282c', // Red handkerchief
    background: '#ffffff',
    text: '#000000',
    textSecondary: '#666666',
    border: '#e0e0e0',
    highlight: '#d0282c'
  },
  green: {
    name: 'Verd',
    color: '#3a9636',
    image: '/xiquet_images/basic_green.png',
    primary: '#000000', // Black sash
    secondary: '#3a9636', // Green shirt
    accent: '#d0282c', // Red handkerchief
    background: '#ffffff',
    text: '#000000',
    textSecondary: '#666666',
    border: '#e0e0e0',
    highlight: '#3a9636'
  },
  yellow: {
    name: 'Groc',
    color: '#e8c62b',
    image: '/xiquet_images/basic_yellow.png',
    primary: '#000000', // Black sash
    secondary: '#e8c62b', // Yellow shirt
    accent: '#d0282c', // Red handkerchief
    background: '#ffffff',
    text: '#000000',
    textSecondary: '#666666',
    border: '#e0e0e0',
    highlight: '#e8c62b'
  },
  red: {
    name: 'Vermell',
    color: '#d0282c',
    image: '/xiquet_images/basic_red.png',
    primary: '#000000', // Black sash
    secondary: '#d0282c', // Red shirt
    accent: '#d0282c', // Red handkerchief (keep red)
    background: '#ffffff',
    text: '#000000',
    textSecondary: '#666666',
    border: '#e0e0e0',
    highlight: '#d0282c'
  },
  blue: {
    name: 'Blau',
    color: '#236ca8',
    image: '/xiquet_images/basic_lightblue.png',
    primary: '#000000', // Black sash
    secondary: '#236ca8', // Blue shirt
    accent: '#d0282c', // Red handkerchief
    background: '#ffffff',
    text: '#000000',
    textSecondary: '#666666',
    border: '#e0e0e0',
    highlight: '#236ca8'
  }
};

// Get color preference from localStorage
export const getColorPreference = () => {
  const saved = localStorage.getItem('xiquet_color_preference');
  return saved && COLOR_THEMES[saved] ? saved : 'white';
};

// Save color preference to localStorage
export const saveColorPreference = (color) => {
  localStorage.setItem('xiquet_color_preference', color);
};

// Get current theme
export const getCurrentTheme = () => {
  const color = getColorPreference();
  return COLOR_THEMES[color];
};

