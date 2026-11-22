/**
 * Tooltip: a short text on hover and keyboard focus, for a control whose
 * meaning is not in its label (an icon button). Not for anything the user must
 * read: touch has no hover, so the text must also live in the control's
 * `aria-label` or the surrounding copy.
 *
 * The child is wrapped, not replaced: it gets `aria-describedby` pointing at
 * the bubble, which stays in the DOM (hidden visually) so a screen reader reads
 * it on focus. Escape dismisses it. The bubble is positioned, not portalled, so
 * a `DataTable` or any `overflow-hidden` ancestor clips it; put a tooltip at
 * the edge of one and it will be cut.
 */
import {
  cloneElement,
  type FocusEvent,
  type KeyboardEvent,
  type MouseEvent,
  type ReactElement,
  useId,
  useState,
} from 'react';
import { cx } from './cx';

interface TargetProps {
  'aria-describedby'?: string;
  onMouseEnter?: (event: MouseEvent<HTMLElement>) => void;
  onMouseLeave?: (event: MouseEvent<HTMLElement>) => void;
  onFocus?: (event: FocusEvent<HTMLElement>) => void;
  onBlur?: (event: FocusEvent<HTMLElement>) => void;
  onKeyDown?: (event: KeyboardEvent<HTMLElement>) => void;
}

export interface TooltipProps {
  text: string;
  side?: 'top' | 'bottom';
  /** One element that takes `aria-describedby` and mouse, focus and key handlers: a button, a link, an input. */
  children: ReactElement<TargetProps>;
}

const sides = { top: 'bottom-full mb-1.5', bottom: 'top-full mt-1.5' } as const;

export function Tooltip({ text, side = 'top', children }: TooltipProps) {
  const id = useId();
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const open = (hovered || focused) && !dismissed;
  const { props } = children;
  const describedBy = props['aria-describedby'];

  return (
    <span className="relative inline-flex">
      {cloneElement(children, {
        'aria-describedby': describedBy ? `${describedBy} ${id}` : id,
        onMouseEnter: (event) => {
          props.onMouseEnter?.(event);
          setHovered(true);
        },
        onMouseLeave: (event) => {
          props.onMouseLeave?.(event);
          setHovered(false);
          setDismissed(false);
        },
        onFocus: (event) => {
          props.onFocus?.(event);
          setFocused(true);
        },
        onBlur: (event) => {
          props.onBlur?.(event);
          setFocused(false);
          setDismissed(false);
        },
        onKeyDown: (event) => {
          props.onKeyDown?.(event);
          if (event.key === 'Escape' && open) {
            setDismissed(true);
          }
        },
      })}
      <span
        id={id}
        role="tooltip"
        className={cx(
          'pointer-events-none absolute left-1/2 z-50 w-max max-w-[16rem] -translate-x-1/2 rounded-md bg-text-primary px-2 py-1 text-xs font-medium text-text-inverse shadow-lg',
          sides[side],
          open ? 'visible' : 'invisible',
        )}
      >
        {text}
      </span>
    </span>
  );
}
