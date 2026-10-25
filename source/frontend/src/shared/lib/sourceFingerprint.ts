/** Компактный отпечаток исходника без хранения полного текста в React state. */

export function fingerprintSource(source: string): string {
  // djb2 + длина: стабилен для сравнения ревизий, O(n), без выделения гигантских строк.
  let hash = 5381;
  for (let index = 0; index < source.length; index += 1) {
    hash = (hash * 33) ^ source.charCodeAt(index);
  }
  return `${source.length}:${(hash >>> 0).toString(16)}`;
}
