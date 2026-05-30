/**
 * Validation helpers for sample-ts-lib.
 */
import { capitalize } from "./formatter";

export function isNonEmpty(s: string): boolean {
  return s.trim().length > 0;
}

export function validateLabel(label: string): string {
  if (!isNonEmpty(label)) {
    throw new Error("Label must not be empty");
  }
  return capitalize(label);
}
