const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../static/app.js'), 'utf8');
const context = vm.createContext({});
// Execute the original pure helper declarations, without starting the browser UI.
vm.runInContext(source.slice(source.indexOf('function escapeHtml('), source.indexOf('function getPath(')), context);
test('HTML escaping', () => assert.equal(context.escapeHtml('<script>"&'), '&lt;script&gt;&quot;&amp;'));
test('URL protocol filtering', () => {
  assert.equal(context.safeUrl('javascript:alert(1)'), '');
  assert.equal(context.safeUrl('https://example.invalid/file'), '');
  assert.equal(context.safeUrl('/media/uploads/a.png'), '/media/uploads/a.png');
});
test('Color validation', () => {
  assert.equal(context.safeColor('#abcdef'), '#abcdef');
  assert.equal(context.safeColor('url(x)'), '#111111');
});
test('Timecode parsing', () => {
  assert.equal(context.parseTimecode('01:02.500'), 62.5);
  assert.equal(context.parseTimecode('1:99'), null);
  assert.equal(context.parseTimecode('garbage'), null);
});
test('Duration and limits', () => {
  assert.equal(context.formatDuration(62.5, true), '01:02.500');
  assert.equal(context.clamp(-1, 0, 20), 0);
});
