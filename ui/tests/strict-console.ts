/**
 * Fails any test that writes to console.error or console.warn. A product whose
 * Vitest config turns stderr into an error (stem's `onConsoleLog`) fails its
 * whole unit job on a green suite when a copied test logs an act() warning
 * (.github#288), and the copies cannot be edited there, so the canonical suite
 * must be silent. Local to this repo: it is not copied into products.
 */
import { afterEach, beforeEach, expect } from 'vitest';

const original = { error: console.error, warn: console.warn };
let written: string[] = [];

beforeEach(() => {
  written = [];
  console.error = (...args: unknown[]) => {
    written.push(`console.error: ${args.map(String).join(' ')}`);
  };
  console.warn = (...args: unknown[]) => {
    written.push(`console.warn: ${args.map(String).join(' ')}`);
  };
});

afterEach(() => {
  console.error = original.error;
  console.warn = original.warn;
  expect(written).toEqual([]);
});
