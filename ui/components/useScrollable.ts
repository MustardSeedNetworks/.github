/**
 * Whether an element's content outruns its box, kept current as either resizes.
 * A scroller that overflows must be reachable from the keyboard (axe
 * `scrollable-region-focusable`): either it holds something tabbable, or it is
 * itself focusable.
 *
 * - `scrolls`: the content overflows, so the caller gives the region
 *   `tabIndex={0}` and a name (DataTable does, always, so a keyboard user can pan
 *   it with the arrow keys even when it holds buttons).
 * - `needsFocus`: it overflows AND holds nothing tabbable, the minimum a modal
 *   body needs (a long read-only panel).
 *
 * jsdom has no layout, so both are false there unless a test stubs the sizes.
 */
import { type RefObject, useEffect, useRef, useState } from 'react';
import { tabbables } from './useDialog';

export interface Scrollable<T extends HTMLElement> {
  ref: RefObject<T | null>;
  scrolls: boolean;
  needsFocus: boolean;
}

export function useScrollable<T extends HTMLElement>(): Scrollable<T> {
  const ref = useRef<T>(null);
  const [state, setState] = useState({ scrolls: false, needsFocus: false });

  useEffect(() => {
    const { current: element } = ref;
    if (!element) {
      return;
    }
    const measure = () => {
      const scrolls =
        element.scrollWidth > element.clientWidth || element.scrollHeight > element.clientHeight;
      const needsFocus = scrolls && tabbables(element).length === 0;
      setState((previous) =>
        previous.scrolls === scrolls && previous.needsFocus === needsFocus
          ? previous
          : { scrolls, needsFocus },
      );
    };
    measure();
    if (typeof ResizeObserver === 'undefined') {
      return;
    }
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    if (element.firstElementChild) {
      observer.observe(element.firstElementChild);
    }
    return () => observer.disconnect();
  });

  return { ref, ...state };
}
