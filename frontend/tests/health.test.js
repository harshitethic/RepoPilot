import test from 'node:test';
import assert from 'node:assert/strict';
import { ollamaAvailable } from '../src/health.js';

test('reports online for a structured model status', () => {
  assert.equal(ollamaAvailable({ ok: true, ollama: { online: true, models: ['model'] } }), true);
});

test('reports offline for false, absent or unavailable Ollama', () => {
  assert.equal(ollamaAvailable({ ok: true, ollama: { online: false, models: [] } }), false);
  assert.equal(ollamaAvailable({ ok: true, ollama: false }), false);
  assert.equal(ollamaAvailable({ ollama: undefined }), false);
  assert.equal(ollamaAvailable(undefined), false);
  assert.equal(ollamaAvailable(null), false);
});

test('accepts the prior nested frontend fallback and rejects truthy strings', () => {
  assert.equal(ollamaAvailable({ ollama: { online: true } }), true);
  assert.equal(ollamaAvailable({ ollama: { online: false } }), false);
  assert.equal(ollamaAvailable({ ollama: 'true' }), false);
  assert.equal(ollamaAvailable({ ollama: { online: 'true' } }), false);
});
