import { render, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, afterEach, vi } from 'vitest';
import axe from 'axe-core';
import App from '../App';

vi.mock('../api/client', () => ({
  api: vi.fn().mockResolvedValue([]),
}));

afterEach(() => cleanup());

describe('axe-core accessibility', () => {
  it('login page has no critical violations', async () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/login']}>
        <App />
      </MemoryRouter>,
    );
    const results = await axe.run(container, {
      rules: { region: { enabled: false } },
    });
    const critical = results.violations.filter((v) => v.impact === 'critical');
    if (critical.length) {
      console.error('axe critical violations:', JSON.stringify(critical, null, 2));
    }
    expect(critical).toHaveLength(0);
  });
});