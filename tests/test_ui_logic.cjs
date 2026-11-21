const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const {test} = require('node:test');
const vm = require('node:vm');

// Run pure request-building functions with no browser, network, or API key.
const context = vm.createContext({
  React:{createElement:() => ({}), useState(){}, useEffect(){}, useRef(){}, Component:class {}},
  ReactDOM:{createRoot:() => ({render(){}})},
  localStorage:{getItem:() => 'a'.repeat(64)}, document:{getElementById:() => ({})},
});
vm.runInContext(readFileSync(join(__dirname, '../static/js/app.js'), 'utf8'), context);
const plain = value => JSON.parse(JSON.stringify(value));
const original = {
  id:9, title:'원래 지갑', category:'지갑', location:'중앙도서관 2층',
  color:'검정', material:'가죽', keywords:['검정','가죽'], description:'원래 설명',
  image_path:'/static/uploads/123.png', author:'사용자', contact:'test@example.com',
  event_date:'2026-11-16', created_at:'2026-11-17T00:00:00Z', report_type:'found',
  status:'resolved', latitude:0, longitude:126.9,
};

test('editing a title preserves photo, coordinates, date and resolved status', () => {
  const fields = context.initialReportFields(original);
  fields.title = '수정한 지갑';
  const result = plain(context.reportPayload(fields, original.image_path, '발견', original));
  const expected = {...original, title:'수정한 지갑'};
  delete expected.id; delete expected.created_at;
  assert.deepEqual(result, expected);
});

test('editing a report with an unrecognized location does not inject 기타', () => {
  const item = {...original, location:'교외 버스 정류장'};
  const fields = context.initialReportFields(item);
  fields.description = '새 설명';
  assert.equal(context.reportPayload(fields, item.image_path, '발견', item).location, item.location);
  fields.building = '형남공학관'; fields.place = '3층 복도';
  assert.equal(context.reportPayload(fields, item.image_path, '발견', item).location, '형남공학관 3층 복도');
});

test('editing does not invent a missing event date or contact', () => {
  const item = {...original, event_date:null, contact:null};
  const fields = context.initialReportFields(item);
  assert.equal(fields.date, '');
  const result = context.reportPayload(fields, item.image_path, '발견', item);
  assert.equal(result.event_date, null);
  assert.equal(result.contact, null);
});

test('replacing or removing a photo only changes the requested image reference', () => {
  const fields = context.initialReportFields(original);
  const unchanged = plain(context.reportPayload(fields, original.image_path, '발견', original));
  const replaced = plain(context.reportPayload(fields, '/static/uploads/new.png', '발견', original));
  assert.deepEqual(replaced, {...unchanged, image_path:'/static/uploads/new.png'});
  assert.equal(context.reportPayload(fields, null, '발견', original).image_path, null);
});

test('creating a new report starts open without inherited coordinates', () => {
  const fields = context.initialReportFields();
  Object.assign(fields, {title:'우산', category:'우산', place:'1층', contact:'test@example.com', keywords:'파랑, 파랑, 접이식'});
  const result = plain(context.reportPayload(fields, null, '분실'));
  assert.equal(result.status, 'open');
  assert.equal(result.report_type, 'lost');
  assert.equal(result.latitude, null);
  assert.equal(result.longitude, null);
  assert.deepEqual(result.keywords, ['파랑','접이식']);
});

test('new map selection is included in the report request without changing location text', () => {
  const fields = context.initialReportFields();
  Object.assign(fields, {latitude:37.4966, longitude:126.9544, place:'2층 휴게 공간'});
  const result = context.reportPayload(fields, null, '발견');
  assert.equal(result.latitude, 37.4966);
  assert.equal(result.longitude, 126.9544);
  assert.equal(result.location, '학생회관 2층 휴게 공간');
});

test('editing a map point replaces both coordinates and clearing it does not restore the original', () => {
  const fields = context.initialReportFields(original);
  fields.latitude = 37.496; fields.longitude = 126.955;
  const moved = context.reportPayload(fields, original.image_path, '발견', original);
  assert.equal(moved.latitude, fields.latitude);
  assert.equal(moved.longitude, fields.longitude);
  fields.latitude = null; fields.longitude = null;
  const cleared = context.reportPayload(fields, original.image_path, '발견', original);
  assert.equal(cleared.latitude, null);
  assert.equal(cleared.longitude, null);
  assert.equal(cleared.location, original.location);
});
