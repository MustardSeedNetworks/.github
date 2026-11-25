/**
 * StatusPill: a verdict, in the status colours, and nothing else.
 *
 * Status colours mean one of success, warning, error or info, or "cannot say"
 * (`unknown`, neutral). They never label a category: a device type, a protocol
 * or a role is a CategoryChip. niac's device-type pills used the status hues
 * for categories (2026-11-22 audit), which makes a category read as a verdict.
 *
 * The label is required and always shown: colour is never the only signal
 * (WCAG 1.4.1). The text takes the `-strong` token, which clears 4.5:1 on its
 * own wash (UI-FLEET-3); the dot takes the bare hue. `icon` swaps the dot for
 * the tone's glyph, for a pill that has to read at a glance.
 *
 * StatusIndicator is the label-less form for a card header, where the title
 * already says what the status is about: a round glyph (or a dot) that is an
 * image named by `label`, so a screen reader hears "Success" and nothing else.
 * It also knows `loading`, a spinner that holds still when the user asks for no
 * motion. It replaces seed's and niac's `StatusBadge` (icon and dot variants,
 * two sizes). `StatusIcon` and `statusText` are what Card's rows share.
 */
import { CircleCheck, CircleHelp, CircleX, Info, LoaderCircle, TriangleAlert } from 'lucide-react';
import { cx } from './cx';

export type StatusTone = 'success' | 'warning' | 'error' | 'info' | 'unknown';
/** A status plus "a result is on its way". */
export type IndicatorTone = StatusTone | 'loading';

export const statusText: Record<IndicatorTone, string> = {
  success: 'text-status-success-strong',
  warning: 'text-status-warning-strong',
  error: 'text-status-error-strong',
  info: 'text-status-info-strong',
  unknown: 'text-text-secondary',
  loading: 'text-text-secondary',
};

const glyphs = {
  success: CircleCheck,
  warning: TriangleAlert,
  error: CircleX,
  info: Info,
  unknown: CircleHelp,
  loading: LoaderCircle,
} as const;

const tones: Record<StatusTone, { pill: string; dot: string }> = {
  success: { pill: 'bg-status-success/10 text-status-success-strong', dot: 'bg-status-success' },
  warning: { pill: 'bg-status-warning/10 text-status-warning-strong', dot: 'bg-status-warning' },
  error: { pill: 'bg-status-error/10 text-status-error-strong', dot: 'bg-status-error' },
  info: { pill: 'bg-status-info/10 text-status-info-strong', dot: 'bg-status-info' },
  unknown: { pill: 'bg-surface-hover text-text-secondary', dot: 'bg-text-muted' },
};

/** The tone's glyph, decorative: whatever carries it states the tone in words. */
export function StatusIcon({ tone, className }: { tone: IndicatorTone; className?: string }) {
  const Glyph = glyphs[tone];
  return (
    <Glyph
      className={cx(
        'h-4 w-4 shrink-0',
        tone === 'loading' && 'motion-safe:animate-spin',
        className,
      )}
      aria-hidden="true"
    />
  );
}

export interface StatusPillProps {
  tone: StatusTone;
  /** Already translated. */
  label: string;
  /** The tone's glyph in place of the dot. */
  icon?: boolean;
  className?: string;
}

export function StatusPill({ tone, label, icon = false, className }: StatusPillProps) {
  const { pill, dot } = tones[tone];
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium',
        pill,
        className,
      )}
      data-tone={tone}
    >
      {icon ? (
        <StatusIcon tone={tone} className="h-3.5 w-3.5" />
      ) : (
        <span className={cx('h-1.5 w-1.5 shrink-0 rounded-full', dot)} aria-hidden="true" />
      )}
      {label}
    </span>
  );
}

export interface StatusIndicatorProps {
  tone: IndicatorTone;
  /** Accessible name, already translated: "Success", "Loading". */
  label: string;
  /** A round glyph (default) or a small dot. */
  variant?: 'icon' | 'dot';
  size?: 'sm' | 'md';
  className?: string;
}

const indicatorSizes = {
  sm: { icon: 'p-0.5 [&>svg]:h-3.5 [&>svg]:w-3.5', dot: 'h-2 w-2' },
  md: { icon: 'p-1 [&>svg]:h-4 [&>svg]:w-4', dot: 'h-2.5 w-2.5' },
} as const;

export function StatusIndicator({
  tone,
  label,
  variant = 'icon',
  size = 'sm',
  className,
}: StatusIndicatorProps) {
  const wash = tone === 'loading' ? tones.unknown : tones[tone];
  if (variant === 'dot') {
    return (
      <span
        role="img"
        aria-label={label}
        data-tone={tone}
        className={cx(
          'inline-block shrink-0 rounded-full',
          indicatorSizes[size].dot,
          wash.dot,
          className,
        )}
      />
    );
  }
  return (
    <span
      role="img"
      aria-label={label}
      data-tone={tone}
      className={cx(
        'inline-flex shrink-0 items-center justify-center rounded-full',
        indicatorSizes[size].icon,
        wash.pill,
        className,
      )}
    >
      <StatusIcon tone={tone} className="h-auto w-auto" />
    </span>
  );
}
