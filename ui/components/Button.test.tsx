import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Button } from './Button';

afterEach(cleanup);

describe('Button', () => {
  it('defaults to a secondary button that does not submit a form', () => {
    render(<Button>Cancel</Button>);
    const button = screen.getByRole('button', { name: 'Cancel' });
    expect(button.getAttribute('type')).toBe('button');
    expect(button.getAttribute('data-variant')).toBe('secondary');
  });

  it('exposes the variant so one-primary-per-page is queryable', () => {
    render(
      <>
        <Button variant="primary">Save</Button>
        <Button>Cancel</Button>
        <Button variant="destructive">Delete</Button>
      </>,
    );
    expect(document.querySelectorAll('[data-variant="primary"]')).toHaveLength(1);
    expect(document.querySelectorAll('[data-variant="destructive"]')).toHaveLength(1);
  });

  it('styles each variant from tokens: brand fill, raised face, filled danger', () => {
    render(
      <>
        <Button variant="primary">P</Button>
        <Button variant="secondary">S</Button>
        <Button variant="destructive">D</Button>
      </>,
    );
    expect(screen.getByText('P').className).toContain('bg-brand-primary');
    expect(screen.getByText('S').className).toContain('bg-surface-raised');
    expect(screen.getByText('D').className).toContain('bg-status-error');
    expect(screen.getByText('D').className).toContain('text-on-danger');
  });

  it('is visibly disabled, not merely faded, and does not fire', () => {
    const onClick = vi.fn();
    render(
      <Button variant="primary" disabled onClick={onClick}>
        Save
      </Button>,
    );
    const button = screen.getByRole('button', { name: 'Save' }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(button.className).toContain('disabled:bg-surface-sunken');
    expect(button.className).toContain('disabled:text-text-disabled');
    expect(button.className).toContain('disabled:cursor-not-allowed');
    expect(button.className).not.toContain('opacity');
    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it('calls onClick and hides a decorative icon', () => {
    const onClick = vi.fn();
    render(
      <Button onClick={onClick} icon={<svg data-testid="icon" />}>
        Go
      </Button>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Go' }));
    expect(onClick).toHaveBeenCalledOnce();
    expect(screen.getByTestId('icon').parentElement?.getAttribute('aria-hidden')).toBe('true');
  });
});
