/**
 * Input and Textarea: native controls, themed. seed, stem and niac each carry
 * their own with a built-in label; here the label, hint and error belong to
 * FormField, which supplies `id` and the aria props to spread on the control:
 *
 *   <FormField label="Name">{(control) => <Input {...control} value={v} onChange={...} />}</FormField>
 *
 * Every native attribute passes through to the input (`id`, `name`,
 * `data-testid`, `aria-*`, `autoComplete`, `inputMode`...), and `ref` is the
 * input's, so react-hook-form's `{...register('name')}` works unchanged.
 *
 * `leftIcon` and `rightIcon` draw an adornment inside the field: a decorative
 * glyph (the wrapper hides it from assistive technology), or, for `rightIcon`, a
 * control such as a show-password button when `rightIconInteractive` is set. The
 * text keeps clear of it.
 */
import type { InputHTMLAttributes, ReactNode, Ref } from 'react';
import { cx } from './cx';

export const controlClass =
  'min-h-10 w-full min-w-0 rounded-lg border border-surface-border bg-surface-raised px-3 py-2 text-sm text-text-primary placeholder:text-text-muted hover:bg-surface-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-primary disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-text-disabled aria-[invalid=true]:border-status-error';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  /** A decorative glyph inside the field, before the text. */
  leftIcon?: ReactNode;
  /** An adornment inside the field, after the text. */
  rightIcon?: ReactNode;
  /** The right adornment is a control (a button): it takes pointer events and is not hidden. */
  rightIconInteractive?: boolean;
  ref?: Ref<HTMLInputElement>;
}

export function Input({
  className,
  type = 'text',
  leftIcon,
  rightIcon,
  rightIconInteractive = false,
  ref,
  ...rest
}: InputProps) {
  const field = (
    <input
      ref={ref}
      type={type}
      className={cx(
        controlClass,
        leftIcon ? 'pl-9' : undefined,
        rightIcon ? 'pr-9' : undefined,
        className,
      )}
      {...rest}
    />
  );
  if (!leftIcon && !rightIcon) {
    return field;
  }
  return (
    <div className="relative w-full">
      {leftIcon ? (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-muted [&>svg]:h-4 [&>svg]:w-4"
        >
          {leftIcon}
        </span>
      ) : null}
      {field}
      {rightIcon ? (
        <span
          {...(rightIconInteractive ? {} : { 'aria-hidden': true })}
          className={cx(
            'absolute right-1.5 top-1/2 -translate-y-1/2 text-text-muted [&>svg]:h-4 [&>svg]:w-4',
            rightIconInteractive ? undefined : 'pointer-events-none right-3',
          )}
        >
          {rightIcon}
        </span>
      ) : null}
    </div>
  );
}
