/**
 * Button: three variants and one disabled look.
 *
 * - primary: the page's one most-likely action. At most one per page; a page
 *   with no single likely action has none.
 * - secondary: everything else.
 * - destructive: anything that deletes or cannot be undone. Filled, never an
 *   outlined or text-only red: a destructive action is styled one way across
 *   the fleet. Pair it with a confirmation.
 *
 * `data-variant` is rendered so "one primary per page" is a queryable fact
 * (`[data-variant="primary"]`) rather than a source grep.
 *
 * Disabled is visibly disabled: a flat sunken face with disabled-text colour
 * and a not-allowed cursor, not just a fade. A fade makes a primary button
 * read as a secondary one. Say why in a `title` or the surrounding copy.
 */
import type { ButtonHTMLAttributes, ReactNode, Ref } from 'react';
import { cx } from './cx';

export type ButtonVariant = 'primary' | 'secondary' | 'destructive';
export type ButtonSize = 'sm' | 'md';

export interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'className'> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** An icon before the label, decorative. */
  icon?: ReactNode;
  className?: string;
  ref?: Ref<HTMLButtonElement>;
}

const base =
  'inline-flex items-center justify-center gap-2 rounded-lg border font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-primary disabled:cursor-not-allowed disabled:border-hairline disabled:bg-surface-sunken disabled:text-text-disabled';

const variants: Record<ButtonVariant, string> = {
  primary:
    'border-transparent bg-brand-primary text-on-brand hover:bg-brand-primary/90 disabled:hover:bg-surface-sunken',
  secondary:
    'border-surface-border bg-surface-raised text-text-primary hover:bg-surface-hover disabled:hover:bg-surface-sunken',
  destructive:
    'border-transparent bg-status-error text-on-danger hover:bg-status-error/90 disabled:hover:bg-surface-sunken',
};

const sizes: Record<ButtonSize, string> = {
  sm: 'min-h-8 px-3 text-xs',
  md: 'min-h-10 px-4 text-sm',
};

export function Button({
  variant = 'secondary',
  size = 'md',
  icon,
  className,
  type = 'button',
  children,
  ref,
  ...rest
}: ButtonProps) {
  return (
    <button
      ref={ref}
      type={type}
      data-variant={variant}
      className={cx(base, variants[variant], sizes[size], className)}
      {...rest}
    >
      {icon ? <span aria-hidden="true">{icon}</span> : null}
      {children}
    </button>
  );
}
