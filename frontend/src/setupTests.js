import '@testing-library/jest-dom/vitest';

// jsdom does not implement matchMedia — mock it for ThemeProvider's
// prefers-color-scheme check.
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query) => ({
    matches: false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  }),
});