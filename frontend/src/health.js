/** Determine availability from the actual structured API response.
 * Boolean support is retained for compatibility with older local versions.
 */
export function ollamaAvailable(health) {
  return health?.ollama === true || health?.ollama?.online === true;
}
