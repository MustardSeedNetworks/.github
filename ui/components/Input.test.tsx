import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { FormField } from './FormField';
import { Input } from './Input';
import { Textarea } from './Textarea';

afterEach(cleanup);

describe('Input and Textarea', () => {
  it('render native controls themed from tokens', () => {
    render(
      <>
        <Input aria-label="Name" />
        <Textarea aria-label="Notes" />
      </>,
    );
    const input = screen.getByRole('textbox', { name: 'Name' });
    expect(input.tagName).toBe('INPUT');
    expect(input.className).toContain('bg-surface-raised');
    expect(input.className).toContain('border-surface-border');
    expect(input.className).toContain('min-w-0');
    expect(screen.getByRole('textbox', { name: 'Notes' }).tagName).toBe('TEXTAREA');
  });

  it('take the control props FormField supplies, and flag an error', () => {
    render(
      <FormField label="Name" error="Required">
        {(control) => <Input {...control} />}
      </FormField>,
    );
    const input = screen.getByRole('textbox', { name: 'Name' });
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(input.className).toContain('aria-[invalid=true]:border-status-error');
  });

  it('pass typing through', () => {
    const onChange = vi.fn();
    render(<Input aria-label="Name" onChange={onChange} />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'x' } });
    expect(onChange).toHaveBeenCalledOnce();
  });

  it('defaults the textarea to four rows', () => {
    render(<Textarea aria-label="Notes" />);
    expect(screen.getByRole('textbox').getAttribute('rows')).toBe('4');
  });
});

describe('Input, Select and Textarea pass-through', () => {
  it('passes id, name, data-testid and aria-* to the native control', () => {
    render(
      <>
        <Input id="a" name="a" data-testid="a-input" aria-label="A" aria-describedby="x" />
        <Textarea id="b" name="b" data-testid="b-text" aria-label="B" />
      </>,
    );
    const input = screen.getByTestId('a-input');
    expect(input.id).toBe('a');
    expect(input.getAttribute('name')).toBe('a');
    expect(input.getAttribute('aria-describedby')).toBe('x');
    expect(screen.getByTestId('b-text').getAttribute('name')).toBe('b');
  });

  it('hands ref, name, onChange and onBlur to the control, the shape react-hook-form register() returns', () => {
    const onChange = vi.fn();
    const onBlur = vi.fn();
    let node: HTMLInputElement | null = null;
    const registered = {
      name: 'host',
      onChange,
      onBlur,
      ref: (element: HTMLInputElement | null) => {
        node = element;
      },
    };
    render(<Input aria-label="Host" {...registered} />);
    const input = screen.getByRole('textbox', { name: 'Host' });
    expect(node).toBe(input);
    fireEvent.change(input, { target: { value: 'x' } });
    fireEvent.blur(input);
    expect(onChange).toHaveBeenCalledOnce();
    expect(onBlur).toHaveBeenCalledOnce();
    expect(input.getAttribute('name')).toBe('host');
  });

  it('draws a left and a right adornment inside the field, clear of the text, decorative by default', () => {
    render(
      <Input
        aria-label="Host"
        leftIcon={<svg data-testid="left" />}
        rightIcon={<svg data-testid="right" />}
      />,
    );
    const input = screen.getByRole('textbox');
    expect(input.className).toContain('pl-9');
    expect(input.className).toContain('pr-9');
    expect(screen.getByTestId('left').parentElement?.getAttribute('aria-hidden')).toBe('true');
    expect(screen.getByTestId('right').parentElement?.getAttribute('aria-hidden')).toBe('true');
    expect(screen.getByTestId('right').parentElement?.className).toContain('pointer-events-none');
  });

  it('lets the right adornment be a working control', () => {
    const onClick = vi.fn();
    render(
      <Input
        aria-label="Password"
        type="password"
        rightIconInteractive
        rightIcon={
          <button type="button" aria-label="Show password" onClick={onClick}>
            eye
          </button>
        }
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Show password' }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('renders no wrapper without an adornment', () => {
    const { container } = render(<Input aria-label="Host" />);
    expect(container.firstElementChild?.tagName).toBe('INPUT');
  });
});
