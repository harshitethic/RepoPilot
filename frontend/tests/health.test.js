import test from 'node:test';
import assert from 'node:assert/strict';
import { ollamaAvailable } from '../src/health.js';

test('reports online when the current FastAPI health endpoint returns true', () => {
  assert.equal(ollamaAvailable({ ok: true, ollama: true }), true);
});

test('reports offline for false, absent or unavailable Ollama', () => {
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
