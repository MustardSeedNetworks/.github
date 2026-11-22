import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Tooltip } from './Tooltip';

afterEach(cleanup);

const tip = () => (
  <Tooltip text="Delete device">
    <button type="button">x</button>
  </Tooltip>
);

describe('Tooltip', () => {
  it('describes its child with the bubble, which is in the DOM from the start', () => {
    render(tip());
    const button = screen.getByRole('button', { name: 'x' });
    const bubble = screen.getByRole('tooltip');
    expect(button.getAttribute('aria-describedby')).toBe(bubble.id);
    expect(bubble.textContent).toBe('Delete device');
    expect(bubble.className).toContain('invisible');
  });

  it('shows on hover and on keyboard focus, and hides again', () => {
    render(tip());
    const button = screen.getByRole('button');
    const bubble = screen.getByRole('tooltip');
    fireEvent.mouseEnter(button);
    expect(bubble.className).toContain('visible');
    expect(bubble.className).not.toContain('invisible');
    fireEvent.mouseLeave(button);
    expect(bubble.className).toContain('invisible');
    fireEvent.focus(button);
    expect(bubble.className).not.toContain('invisible');
    fireEvent.blur(button);
    expect(bubble.className).toContain('invisible');
  });

  it('is dismissed by Escape until the pointer or focus leaves', () => {
    render(tip());
    const button = screen.getByRole('button');
    const bubble = screen.getByRole('tooltip');
    fireEvent.focus(button);
    fireEvent.keyDown(button, { key: 'Escape' });
    expect(bubble.className).toContain('invisible');
    fireEvent.blur(button);
    fireEvent.focus(button);
    expect(bubble.className).not.toContain('invisible');
  });

  it("keeps the child's own handlers and description", () => {
    const onFocus = vi.fn();
    render(
      <Tooltip text="Tip">
        <button type="button" aria-describedby="other" onFocus={onFocus}>
          x
        </button>
      </Tooltip>,
    );
    const button = screen.getByRole('button');
    fireEvent.focus(button);
    expect(onFocus).toHaveBeenCalledOnce();
    expect(button.getAttribute('aria-describedby')).toMatch(/^other /);
  });
});
