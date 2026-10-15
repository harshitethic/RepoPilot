/**
 * Normalize the local backend's Ollama health contract.
 *
 * The current backend responds with { ok: true, ollama: boolean };
 * tolerate the original frontend's legacy { ollama: { online: boolean } }
 * shape without interpreting strings or truthy objects as service health.
 */
export function ollamaAvailable(health) {
  return health?.ollama === true || health?.ollama?.online === true;
}
