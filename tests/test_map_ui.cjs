const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const {test} = require('node:test');
const vm = require('node:vm');

// Exercise location callbacks with simulated GPS and map events, never the user's location.
function mountMap(options = {}) {
  const slots = [], pending = [], selections = [], gps = [], markers = [];
  let index = 0, dirty = false, tree, props;
  const element = {addEventListener(){}, removeEventListener(){}};
  const map = {handlers:{}, center:{lat:37.4966, lng:126.9544}, removed:false,
    setView(point){this.center = {lat:point[0], lng:point[1]}; return this;},
    on(name, handler){this.handlers[name] = handler; return this;},
    getZoom:() => 16, getCenter(){return this.center;}, removeLayer(){},
    remove(){this.removed = true;}, invalidateSize(){}};
  const L = {
    map:() => map,
    tileLayer:() => ({on(){return this;}, addTo(){return this;}}),
    circle:() => ({addTo(){return this;}}),
    marker(point, options) {
      const marker = {point, options, handlers:{}, dragging:{enabled:options.draggable,
        enable(){this.enabled = true;}, disable(){this.enabled = false;}},
        setLatLng(value){this.point = value;}, getLatLng(){return {lat:this.point[0], lng:this.point[1]};},
        on(name, handler){this.handlers[name] = handler; return this;}, addTo(){return this;}};
      markers.push(marker); return marker;
    },
  };
  const React = {
    createElement(type, attributes, ...children) {
      if (attributes?.ref && !attributes.ref.current) attributes.ref.current = element;
      return {type, props:attributes || {}, children};
    },
    useRef(value) {const position = index++; return slots[position] ||= {current:value};},
    useState(value) {
      const position = index++;
      if (!(position in slots)) slots[position] = typeof value === 'function' ? value() : value;
      return [slots[position], next => {
        const result = typeof next === 'function' ? next(slots[position]) : next;
        if (!Object.is(slots[position], result)) {slots[position] = result; dirty = true;}
      }];
    },
    useEffect(callback, dependencies) {
      const position = index++, previous = slots[position];
      if (!previous || dependencies.some((value, i) => !Object.is(value, previous.dependencies[i]))) {
        pending.push(() => {previous?.cleanup?.(); slots[position] = {dependencies, cleanup:callback()};});
      }
    },
  };
  const window = {L, isSecureContext:true, ...options.window};
  const navigator = {geolocation:{getCurrentPosition(success, failure){gps.push({success, failure});}}};
  vm.runInNewContext(readFileSync(join(__dirname, '../static/js/campus-map.js'), 'utf8'), {React, window, navigator});
  props = {value:null, onChange(point) {selections.push(point); props.value = point; dirty = true;}, ...options.props};
  function render() {
    let count = 0;
    do {
      dirty = false; index = 0; tree = window.CampusMap(props);
      while (pending.length) pending.shift()();
      if (++count > 20) throw new Error('Repeated renders');
    } while (dirty);
  }
  function nodes(node = tree) {
    if (!node || typeof node !== 'object') return [];
    return [node, ...node.children.flatMap(child => nodes(child))];
  }
  const text = node => typeof node === 'string' ? node : node?.children?.map(text).join('') || '';
  render();
  return {map, gps, markers, selections, render,
    click(label) {const node = nodes().find(node => node.type === 'button' && text(node) === label); assert.ok(node, label); assert.ok(!node.props.disabled); node.props.onClick(); render();},
    event(name, value) {map.handlers[name](value); render();},
    setProps(next) {Object.assign(props, next); render();},
    text:() => text(tree),
    unmount() {for (const slot of slots) slot?.cleanup?.();},
  };
}

const position = {coords:{latitude:37.5, longitude:126.95, accuracy:25}};

test('GPS is requested only on click and returns coordinates and accuracy', () => {
  const ui = mountMap();
  assert.equal(ui.gps.length, 0);
  ui.click('현재 위치 가져오기');
  ui.gps[0].success(position); ui.render();
  assert.equal(ui.selections[0].latitude, 37.5);
  assert.match(ui.text(), /오차 약 25m/);
  assert.equal(ui.markers[0].dragging.enabled, true);
  ui.unmount(); assert.equal(ui.map.removed, true);
});

test('manual click and marker drag win over a delayed GPS response', () => {
  const ui = mountMap();
  ui.click('현재 위치 가져오기');
  ui.event('click', {latlng:{lat:37.49, lng:126.94}});
  ui.gps[0].success(position); ui.render();
  assert.equal(ui.selections.length, 1);
  assert.equal(ui.selections[0].latitude, 37.49);
  ui.click('현재 위치 가져오기');
  const marker = ui.markers[0];
  marker.handlers.dragstart(); marker.point = [37.48, 126.93]; marker.handlers.dragend(); ui.render();
  ui.gps[1].success(position); ui.render();
  assert.equal(ui.selections.length, 2);
  assert.equal(ui.selections[1].latitude, 37.48);
  ui.unmount();
});

test('clearing a point cancels pending GPS and busy state prevents coordinate changes', () => {
  const ui = mountMap({props:{value:{latitude:0, longitude:0}}});
  ui.click('현재 위치 가져오기'); ui.click('지도 위치 제거');
  ui.gps[0].success(position); ui.render();
  assert.deepEqual(ui.selections, [null]);
  ui.setProps({disabled:true}); ui.event('click', {latlng:{lat:1, lng:2}});
  assert.equal(ui.selections.length, 1);
  ui.unmount();
});

test('GPS errors keep the previous point and late callbacks after unmount are ignored', () => {
  const ui = mountMap({props:{value:{latitude:0, longitude:0}}});
  ui.click('현재 위치 가져오기'); ui.gps[0].failure({code:1}); ui.render();
  assert.match(ui.text(), /권한이 거부/);
  assert.match(ui.text(), /위도 0.000000/);
  assert.equal(ui.selections.length, 0);
  ui.click('현재 위치 가져오기'); ui.unmount(); ui.gps[1].success(position);
  assert.equal(ui.selections.length, 0);
});

test('detail maps are read-only and missing Leaflet is handled without accepting late GPS callbacks', () => {
  const detail = mountMap({props:{readOnly:true, value:{latitude:0, longitude:0}}});
  assert.equal(detail.markers[0].dragging.enabled, false);
  assert.equal(detail.gps.length, 0);
  assert.equal(detail.map.handlers.click, undefined);
  detail.unmount();
  const unavailable = mountMap({window:{L:undefined}});
  assert.match(unavailable.text(), /지도 기능을 불러오지 못했습니다/);
  unavailable.click('현재 위치 가져오기'); unavailable.unmount(); unavailable.gps[0].success(position);
  assert.equal(unavailable.selections.length, 0);
});
