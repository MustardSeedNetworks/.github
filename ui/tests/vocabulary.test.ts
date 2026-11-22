/**
 * The canonical components are copied into four products, and jsdom never runs
 * Tailwind: a class one product does not define renders as nothing and every
 * test still passes. This is the check that stands in for compiling the CSS.
 *
 * A class may be a Tailwind utility, one of the shared theme's component
 * classes (`.kicker`, `.figure`, `.panel`, `.target`, never with a variant,
 * which Tailwind does not generate for `@layer components`), or a colour from
 * the token set every product maps: trellis's `@theme` is the floor, so a name
 * that only seed, stem or niac defines (`bg-bg-surface`, `border-border-muted`)
 * fails here. Spacing helpers and type classes that live in a product's own
 * index.css (`gap-tight`, `heading-1`) are refused for the same reason.
 */
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

/** Comments hold apostrophes ("niac's") that would read as string delimiters. */
function withoutComments(text: string): string {
  return text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
}

const COMPONENTS = join(import.meta.dirname, '..', 'components');
const sources = readdirSync(COMPONENTS)
  .filter((file) => /\.tsx?$/.test(file) && !file.endsWith('.test.tsx'))
  .map((file) => ({ file, text: withoutComments(readFileSync(join(COMPONENTS, file), 'utf8')) }));

const COLOR_PREFIX =
  /^(bg|text|border|ring|divide|fill|stroke|outline|from|via|to|shadow|accent|caret|placeholder)-(.+)$/;

const NOT_A_COLOR =
  /^(xs|sm|base|md|lg|xl|\d?xl|left|right|center|justify|start|end|wrap|nowrap|balance|pretty|ellipsis|clip|none|inner|auto|\d+(\.\d+)?|\[.*\]|[tblrxyse]|[tblrxyse]-.*|inherit|current|transparent|solid|dashed|dotted|hidden|collapse|separate|opacity.*|offset-.*)$/;

const TOKEN_COLOR =
  /^(surface-(base|raised|border|hover|sunken|deep)|text-(primary|secondary|muted|disabled|inverse)|status-(success|warning|error|info)(-strong)?|brand-(primary|primary-strong|accent)|on-(brand|danger)|hairline(-strong)?|scrim|knob)$/;

const PRODUCT_LOCAL = [
  /^(heading-[1-4]|body|body-small|body-large|caption|section-title|label|card)$/,
  /^(flex-between|flex-center|animate-slide-in-right|animate-fade-in)$/,
  /^pad-(xs|sm|lg|xl)$/,
  /^-?(gap|p|px|py|pt|pb|pl|pr|m|mx|my|mt|mb|ml|mr|space-x|space-y)-(tight|compact|compact-md|default|comfortable|cell|row|row-lg|content|heading|centered|icon)$/,
];

const SHARED_COMPONENT_CLASSES = [
  'kicker',
  'kicker-accent',
  'figure',
  'panel',
  'panel-hover',
  'target',
];

/** Every whitespace-separated word inside a quoted string or template literal. */
function classTokens(text: string): string[] {
  const words = new Set<string>();
  for (const match of text.matchAll(/(["'`])((?:\\.|(?!\1)[^\\])*)\1/g)) {
    for (const word of (match[2] ?? '').split(/\s+/)) {
      if (/^[a-z!-][\w:./[\]%()-]*$/.test(word) && !word.includes('/*')) {
        words.add(word);
      }
    }
  }
  return [...words];
}

function parts(token: string): { variants: string[]; utility: string } {
  const pieces = token.replace(/^!/, '').split(/:(?![^[]*\])/);
  return { variants: pieces.slice(0, -1), utility: (pieces.at(-1) ?? '').replace(/^-/, '') };
}

describe('canonical component class vocabulary', () => {
  it('finds the component sources', () => {
    expect(sources.length).toBeGreaterThanOrEqual(13);
  });

  for (const { file, text } of sources) {
    describe(file, () => {
      const tokens = classTokens(text);

      it('uses no spacing helper or type class that only some products define', () => {
        const offenders = tokens.filter((token) =>
          PRODUCT_LOCAL.some((pattern) => pattern.test(parts(token).utility)),
        );
        expect(offenders).toEqual([]);
      });

      it('colours only from the token set every product maps', () => {
        const offenders = tokens.filter((token) => {
          const match = COLOR_PREFIX.exec(parts(token).utility);
          if (!match?.[2]) {
            return false;
          }
          const name = match[2].replace(/\/\d+$/, '');
          if (NOT_A_COLOR.test(name) || TOKEN_COLOR.test(name)) {
            return false;
          }
          return /^[a-z]+(-[a-z0-9]+)*$/.test(name);
        });
        expect(offenders).toEqual([]);
      });

      it('puts no variant on a shared component-layer class', () => {
        const offenders = tokens.filter((token) => {
          const { variants, utility } = parts(token);
          return variants.length > 0 && SHARED_COMPONENT_CLASSES.includes(utility);
        });
        expect(offenders).toEqual([]);
      });

      it('gives status-hue text on a status-hue wash the -strong token', () => {
        const offenders = tokens
          .filter((token) =>
            /^text-status-(success|warning|error|info)$/.test(parts(token).utility),
          )
          .filter(() => /bg-status-(success|warning|error|info)\/\d+/.test(text));
        expect(offenders).toEqual([]);
      });
    });
  }

  it('actually catches a product-local colour (the check can fail)', () => {
    const bad = classTokens(`className="bg-bg-surface border-border-muted gap-tight"`);
    expect(bad).toContain('bg-bg-surface');
    expect(COLOR_PREFIX.exec('bg-bg-surface')?.[2]).toBe('bg-surface');
    expect(TOKEN_COLOR.test('bg-surface')).toBe(false);
    expect(PRODUCT_LOCAL.some((pattern) => pattern.test('gap-tight'))).toBe(true);
  });
});
