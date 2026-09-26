import { createContext, useContext } from 'react';

export const ThemeModeContext = createContext({ toggle: () => {}, mode: 'light' });

export function useThemeMode() {
  return useContext(ThemeModeContext);
}