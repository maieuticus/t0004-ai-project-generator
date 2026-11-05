import assert from 'node:assert/strict';
import test from 'node:test';
import { incrementCount } from '../dist/counter.js';

test('the preview counter advances one step at a time', () => {
  assert.equal(incrementCount(0), 1);
  assert.equal(incrementCount(incrementCount(1)), 3);
});
