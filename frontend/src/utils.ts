export function formatBytes(bytes: number): string {
  const base = 1000;
  if (bytes < base) return `${bytes} B`;

  const units = ['KB', 'MB', 'GB', 'TB', 'PB'];
  let size = bytes;
  let unitIndex = -1;

  do {
    size /= base;
    unitIndex++;
  } while (size >= base && unitIndex < units.length - 1);

  return `${Number(size.toFixed(1))} ${units[unitIndex]}`;
}