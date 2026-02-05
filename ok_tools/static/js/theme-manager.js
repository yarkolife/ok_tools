/*
 * Theme Manager for OK Tools
 * Manages light/dark theme with localStorage saving
 */

const themeGettext = window.gettext || function (str) { return str; };

class ThemeManager {
  constructor() {
    this.STORAGE_KEY = 'ok-tools-theme';
    this.DEFAULT_THEME = 'light';
    this.LIGHT_THEME = 'light';
    this.DARK_THEME = 'dark';
    
    this.init();
  }
  
  /**
   * Initializes the theme manager
   */
  init() {
    // Determine saved theme or use system preferred
    const savedTheme = this.getStoredTheme();
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    const initialTheme = savedTheme || (systemPrefersDark ? this.DARK_THEME : this.LIGHT_THEME);
    this.setTheme(initialTheme, false); // Don't save again if already saved
    
    // Add listener for system changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
      // If user hasn't manually selected theme, update theme based on system
      if (!this.getStoredTheme()) {
        this.setTheme(e.matches ? this.DARK_THEME : this.LIGHT_THEME, false);
      }
    });
    
    // Initialize theme toggle element on page
    this.initThemeToggle();
  }
  
  /**
   * Gets saved theme from localStorage
   * @returns {string|null} Saved theme or null
   */
  getStoredTheme() {
    try {
      return localStorage.getItem(this.STORAGE_KEY);
    } catch (e) {
      console.warn('Could not access localStorage for theme preference:', e);
      return null;
    }
  }
  
  /**
   * Saves selected theme to localStorage
   * @param {string} theme - Theme to save
   */
  storeTheme(theme) {
    try {
      localStorage.setItem(this.STORAGE_KEY, theme);
    } catch (e) {
      console.warn('Could not save theme preference to localStorage:', e);
    }
  }
  
  /**
   * Sets active theme
   * @param {string} theme - Theme to set
   * @param {boolean} save - Whether to save theme to localStorage
   */
  setTheme(theme, save = true) {
    const htmlElement = document.documentElement;
    
    // Remove all possible themes
    htmlElement.removeAttribute('data-theme');
    htmlElement.classList.remove('theme-light', 'theme-dark');
    
    // Set new theme
    if (theme === this.DARK_THEME) {
      htmlElement.setAttribute('data-theme', this.DARK_THEME);
      htmlElement.classList.add('theme-dark');
    } else {
      htmlElement.setAttribute('data-theme', this.LIGHT_THEME);
      htmlElement.classList.add('theme-light');
    }
    
    // Save theme if needed
    if (save) {
      this.storeTheme(theme);
    }
    
    // Dispatch theme change event
    this.dispatchThemeChangeEvent(theme);
  }
  
  /**
   * Toggles between light and dark theme
   */
  toggle() {
    const currentTheme = this.getCurrentTheme();
    const newTheme = currentTheme === this.LIGHT_THEME ? this.DARK_THEME : this.LIGHT_THEME;
    
    this.setTheme(newTheme);
  }
  
  /**
   * Gets current active theme
   * @returns {string} Current theme
   */
  getCurrentTheme() {
    return document.documentElement.getAttribute('data-theme') || this.DEFAULT_THEME;
  }
  
  /**
   * Initializes UI theme toggle element
   */
  initThemeToggle() {
    const themeToggle = document.getElementById('theme-toggle');
    
    if (!themeToggle) {
      // If no specific toggle element exists, you can create it dynamically
      // or just use this method as indication that you need to add element
      console.debug('Theme toggle element with id "theme-toggle" not found.');
      return;
    }
    
    // Set initial button state
    this.updateToggleButton(themeToggle);
    
    // Add click handler
    themeToggle.addEventListener('click', () => {
      this.toggle();
      this.updateToggleButton(themeToggle);
    });
  }
  
  /**
   * Updates theme toggle button state
   * @param {HTMLElement} button - Theme toggle button
   */
  updateToggleButton(button) {
    const currentTheme = this.getCurrentTheme();
    
    // Update text and icon
    const icon = button.querySelector('i') || button.querySelector('svg') || 
                button.querySelector('.theme-icon');
                
    if (icon) {
      // Remove old theme icons
      icon.classList.remove('bi-sun', 'bi-moon', 'bi-circle-half');
      
      // Add icon depending on theme
      if (currentTheme === this.DARK_THEME) {
        icon.classList.add('bi-sun');
        button.setAttribute('aria-label', themeGettext('Switch to light theme'));
      } else {
        icon.classList.add('bi-moon');
        button.setAttribute('aria-label', themeGettext('Switch to dark theme'));
      }
    } else {
      // If no icon, update text
      if (currentTheme === this.DARK_THEME) {
        button.textContent = themeGettext('Light Theme');
      } else {
        button.textContent = themeGettext('Dark Theme');
      }
    }
    
    // Update aria-pressed for toggle buttons
    button.setAttribute('aria-pressed', currentTheme === this.DARK_THEME ? 'false' : 'true');
  }
  
  /**
   * Dispatches theme change event
   * @param {string} theme - New theme
   */
  dispatchThemeChangeEvent(theme) {
    const event = new CustomEvent('themeChange', {
      detail: { theme },
      bubbles: true,
      cancelable: true
    });
    
    document.dispatchEvent(event);
  }
  
  /**
   * Method for programmatically applying theme to elements
   * Can be used for dynamic components
   */
  applyThemeToElements() {
    // Here you can add logic to apply theme to specific elements
    // for example, for custom components that don't use CSS variables
  }
}

// Initialize ThemeManager when DOM loads
document.addEventListener('DOMContentLoaded', () => {
  window.themeManager = new ThemeManager();
});

// Export for use in other modules (if module system is used)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = ThemeManager;
}
