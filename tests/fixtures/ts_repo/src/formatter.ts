/**
 * String formatting utilities for sample-ts-lib.
 */

export function capitalize(s: string): string {
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function truncate(s: string, maxLength: number): string {
  if (s.length <= maxLength) return s;
  return s.slice(0, maxLength) + "...";
}

export class Formatter {
  private prefix: string;

  constructor(prefix: string) {
    this.prefix = prefix;
  }

  format(value: string): string {
    return `${this.prefix}: ${capitalize(value)}`;
  }
}
