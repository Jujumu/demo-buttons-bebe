const test = require('node:test');
const assert = require('node:assert/strict');
const qs = require('qs');

test('patched qs rejects bracket-comma array limit bypass', () => {
  assert.throws(() => qs.parse('a[]=1,2,3,4', {comma:true,arrayLimit:3,throwOnLimitExceeded:true}), RangeError);
});
test('patched qs safely serializes untrusted constructor.isBuffer', () => {
  const value = qs.parse('x[constructor][isBuffer]=y', {plainObjects:true});
  assert.doesNotThrow(() => qs.stringify(value));
});
test('normal nested and repeated query parsing remains compatible', () => {
  assert.deepEqual(qs.parse('a[b]=hello&x=1&x=2'), {a:{b:'hello'},x:['1','2']});
  assert.equal(qs.stringify({a:'hello world'}), 'a=hello%20world');
});
