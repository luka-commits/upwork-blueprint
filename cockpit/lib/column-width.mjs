export const MIN_COLUMN_WIDTH = 56;
export const MAX_COLUMN_WIDTH = 720;
export const clampColumnWidth = width => Math.max(MIN_COLUMN_WIDTH, Math.min(MAX_COLUMN_WIDTH, Math.round(width)));

export function columnWidthForKey(width, key) {
  if (key === 'ArrowLeft') return clampColumnWidth(width - 16);
  if (key === 'ArrowRight') return clampColumnWidth(width + 16);
  if (key === 'Home') return MIN_COLUMN_WIDTH;
  if (key === 'End') return MAX_COLUMN_WIDTH;
  return null;
}
