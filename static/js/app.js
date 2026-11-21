/* The supplied React preview, connected to the same-origin FastAPI service. */
"use strict";
const {useState, useEffect, useRef} = React;
const h = React.createElement;
const buildings = ['전체','학생회관','중앙도서관','진리관','조만식기념관','숭덕경상관','형남공학관','기타'];
const identity = (() => {
  const key = 'campus-find-owner-v1';
  let token;
  try { token = localStorage.getItem(key); } catch (_) { /* Session-only identity below. */ }
  if (!/^[a-f0-9]{64}$/.test(token || '')) {
    token = Array.from(crypto.getRandomValues(new Uint8Array(32)), x => x.toString(16).padStart(2, '0')).join('');
    try { localStorage.setItem(key, token); } catch (_) { /* The page still works without persistent storage. */ }
  }
  return token;
})();
const today = () => new Date().toLocaleDateString('sv-SE');
const labels = {title:'물품 이름',category:'물품 종류',location:'장소',contact:'연락처',author:'작성자',keywords:'키워드',event_date:'날짜'};

async function api(path, options = {}) {
  const headers = new Headers(options.headers);
  headers.set('X-Owner-Token', identity);
  let response;
  try { response = await fetch(path, {...options, headers, cache:'no-store'}); }
  catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error('서버에 연결할 수 없습니다. 연결 상태를 확인한 뒤 다시 시도해 주세요.');
  }
  if (response.status === 204) return null;
  let data;
  try { data = await response.json(); }
  catch (_) { throw new Error('서버 응답을 읽을 수 없습니다. 잠시 후 다시 시도해 주세요.'); }
  if (!response.ok) {
    const detail = data.detail;
    const message = Array.isArray(detail)
      ? detail.map(x => `${labels[x.loc?.[1]] || '입력값'}: ${x.msg}`).join(' / ')
      : (typeof detail === 'string' ? detail : '요청을 처리하지 못했습니다. 다시 시도해 주세요.');
    throw new Error(message);
  }
  return data;
}

function present(item) {
  const building = buildings.slice(1).find(b => item.location === b || item.location.startsWith(b + ' '));
  return {...item, building:building || '기타',
    place:building ? item.location.slice(building.length).trim() : item.location,
    kind:item.report_type === 'lost' ? '분실' : '발견',
    image:item.image_path, icon:'📦',
    date:item.event_date || new Date(item.created_at).toLocaleDateString('sv-SE'),
    dateLabel:item.event_date ? (item.report_type === 'lost' ? '분실일' : '발견일') : '등록일',
  };
}
const button = (text, onClick, className = 'button', props = {}) =>
  h('button', {type:'button', className, onClick, ...props}, text);

function initialReportFields(item = null) {
  const display = item ? present(item) : null;
  return {title:item?.title || '', category:item?.category || '',
    building:display?.building || '학생회관', place:display?.place || '',
    date:item ? (item.event_date || '') : today(), keywords:(item?.keywords || []).join(', '),
    description:item?.description || '', color:item?.color || '', material:item?.material || '',
    contact:item?.contact || '', author:item?.author || '테스트 사용자'};
}

function reportPayload(fields, imagePath, kind, original = null) {
  const previous = original ? initialReportFields(original) : null;
  const unchangedLocation = previous && fields.building === previous.building && fields.place.trim() === previous.place.trim();
  return {
    title:fields.title.trim(), category:fields.category.trim(), color:fields.color.trim() || null,
    material:fields.material.trim() || null, description:fields.description.trim() || null,
    keywords:[...new Set(fields.keywords.split(',').map(x => x.trim()).filter(Boolean))],
    image_path:imagePath,
    location:unchangedLocation ? original.location : (fields.building + ' ' + fields.place.trim()).trim(),
    contact:fields.contact.trim() || null, author:fields.author.trim(), event_date:fields.date || null,
    report_type:kind === '분실' ? 'lost' : 'found', status:original?.status || 'open',
    latitude:original?.latitude ?? null, longitude:original?.longitude ?? null,
  };
}

function ItemCard({item, onOpen}) {
  return h('button', {type:'button', className:'item-card', onClick:() => onOpen(item.id)},
    h('div', {className:'item-image'}, item.image ? h('img', {src:item.image, alt:item.title, loading:'lazy'}) : h('span', {'aria-hidden':true}, item.icon),
      h('span', {className:'status ' + (item.status === 'resolved' ? 'resolved' : item.kind === '분실' ? 'lost' : '')}, item.status === 'resolved' ? '해결 완료' : item.kind === '발견' ? '보관 중' : '찾고 있어요')),
    h('div', {className:'card-copy'}, h('small', null, item.building), h('h3', null, item.title), h('p', null, item.place || item.location),
      h('div', {className:'tags'}, ...item.keywords.slice(0, 3).map((keyword, i) => h('span', {key:i}, '#' + keyword))),
      h('div', {className:'card-bottom'}, h('span', null, item.dateLabel + ' ' + item.date), h('span', null, item.is_mine ? '내 등록' : item.author))));
}

function ReportForm({kind, setKind, onBack, onSaved, notify, onBusy, item = null}) {
  const [fields, setFields] = useState(() => initialReportFields(item));
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState('');
  const [imagePath, setImagePath] = useState(item?.image_path || null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const fileInput = useRef(null);
  useEffect(() => {
    if (!file) { setPreview(imagePath || ''); return; }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file, imagePath]);
  function setPending(value) { setBusy(value); onBusy(Boolean(value)); }
  function field(label, name, type = 'text', props = {}) {
    return h('label', {className:'field'}, label,
      h('input', {name, type, value:fields[name],
        onChange:e => setFields(prev => ({...prev, [name]:e.target.value})),
        onInput:type === 'date' ? e => setFields(prev => ({...prev, [name]:e.target.value})) : undefined,
        ...props}));
  }
  function chooseFile(event) {
    const next = event.target.files?.[0];
    if (!next) return;
    if (!['image/jpeg','image/png','image/webp'].includes(next.type) || next.size > 5 * 1024 * 1024) {
      notify('JPG, PNG, WEBP 형식의 5MB 이하 사진을 선택해 주세요.');
      event.target.value = ''; return;
    }
    setFile(next); setImagePath(null);
  }
  async function analyze() {
    if (!file || busy) return;
    setPending('analyze');
    try {
      const form = new FormData(); form.append('file', file);
      const result = await api('/api/images/analyze', {method:'POST', body:form});
      setImagePath(result.image_path);
      setFields(prev => ({...prev,
        title:prev.title.trim() || result.title, category:prev.category.trim() || result.category,
        color:prev.color.trim() || result.color || '', material:prev.material.trim() || result.material || '',
        description:prev.description.trim() || result.description || '',
        keywords:[...new Set([...prev.keywords.split(',').map(x => x.trim()).filter(Boolean), ...result.keywords])].slice(0,20).join(', '),
      }));
      notify('사진의 특징을 불러왔습니다. 내용을 확인하고 수정한 뒤 등록해 주세요.');
    } catch (error) { notify(error.message + ' 직접 특징을 입력해서 등록할 수도 있습니다.'); }
    finally { setPending(''); }
  }
  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    const keywords = [...new Set(fields.keywords.split(',').map(x => x.trim()).filter(Boolean))];
    if (keywords.length > 20 || keywords.some(x => x.length > 50)) {
      setError('키워드는 각 50자 이내로 최대 20개까지 입력해 주세요.'); return;
    }
    const required = item ? ['title','category','author'] : ['title','category','place','author','contact'];
    if (required.some(name => !fields[name].trim())) {
      setError(item ? '물품 이름, 종류와 작성자를 입력해 주세요.' : '물품 이름, 종류, 위치, 작성자와 연락처를 입력해 주세요.'); return;
    }
    setError(''); setPending('save');
    try {
      let savedImage = imagePath;
      if (file && !savedImage) {
        const form = new FormData(); form.append('file', file);
        savedImage = (await api('/api/images', {method:'POST', body:form})).image_path;
        setImagePath(savedImage);
      }
      const payload = reportPayload(fields, savedImage, kind, item);
      const saved = await api(item ? '/api/items/' + item.id : '/api/items', {
        method:item ? 'PUT' : 'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload),
      });
      onSaved(saved);
    } catch (error) {setError(error.message); notify(error.message);}
    finally { setPending(''); }
  }
  return h('section', {className:'form-section'},
    button(item ? '← 수정 취소' : '← 목록으로', onBack, 'text-button', {disabled:Boolean(busy)}),
    h('div', {className:'eyebrow'}, 'SHARE A LITTLE KINDNESS'),
    h('h1', null, item ? '신고 내용을 수정해 주세요.' : kind === '발견' ? '어떤 물건을 주우셨나요?' : '어떤 물건을 잃어버렸나요?'),
    h('p', {className:'muted'}, item ? '기존 정보를 불러왔습니다. 수정한 내용은 저장 버튼을 누르면 반영됩니다.' : '사진과 특징을 남겨 주세요. * 표시된 항목은 꼭 입력해 주세요.'),
    item && h('p', {className:'muted'}, '현재 상태: ' + (item.status === 'resolved' ? '해결 완료' : '진행 중') + ' · 상태는 상세 화면에서 변경할 수 있어요.'),
    h('div', {className:'chips'}, ...['발견','분실'].map(k => button(k + ' 신고', () => setKind(k), 'chip ' + (kind === k ? 'selected' : ''), {key:k, disabled:Boolean(busy), 'aria-pressed':kind === k}))),
    h('form', {onSubmit:submit, className:'report-layout', 'aria-busy':Boolean(busy)},
      h('div', null,
        h('label', {className:'upload'}, preview ? h('img', {src:preview, alt:'선택한 물품 사진'}) :
          h('div', null, h('strong', null, '＋'), h('p', null, '물품 사진 추가'), h('small', null, 'JPG · PNG · WEBP / 최대 5MB')),
          h('input', {ref:fileInput, type:'file', accept:'image/jpeg,image/png,image/webp', onChange:chooseFile, disabled:Boolean(busy), 'aria-label':'물품 사진 업로드'})),
        h('div', {className:'form-actions'}, button(busy === 'analyze' ? '사진 분석 중…' : 'AI로 특징 채우기', analyze, 'button secondary', {disabled:!file || Boolean(busy)}),
          (file || imagePath) && button('사진 삭제', () => {setFile(null); setImagePath(null); if (fileInput.current) fileInput.current.value = '';}, 'text-button', {disabled:Boolean(busy)})),
        h('p', {className:'photo-note'}, '사진 없이도 직접 입력해서 등록할 수 있어요.'),
        h('div', {className:'info-box', role:'status'}, busy === 'analyze' ? '사진에서 물품의 특징을 확인하고 있어요. 잠시만 기다려 주세요.' :
          item && imagePath === item.image_path && !file ? '기존 사진을 유지합니다. 새 사진을 선택하면 교체할 수 있어요.' :
          imagePath ? '사진이 준비되었습니다. 분석된 내용은 아래에서 자유롭게 수정할 수 있어요.' : '사진을 선택하고 AI 분석을 누르면 물품 종류, 색상과 키워드를 제안해 드려요.')),
      h('div', {className:'form-fields'},
        field('물품 이름 *', 'title', 'text', {required:true, maxLength:100, placeholder:'예: 이어폰 케이스'}),
        h('div', {className:'form-row'}, field('물품 종류 *', 'category', 'text', {required:true, maxLength:50, placeholder:'예: 지갑, 이어폰, 우산'}),
          field((kind === '발견' ? '발견 날짜' : '분실 날짜') + (item ? '' : ' *'), 'date', 'date', {required:!item, max:today()})),
        h('label', {className:'field'}, kind === '발견' ? '발견 건물 *' : '예상 분실 건물 *',
          h('select', {name:'building', 'aria-label':kind === '발견' ? '발견 건물 *' : '예상 분실 건물 *', value:fields.building, onChange:e => setFields(prev => ({...prev, building:e.target.value}))}, ...buildings.slice(1).map(b => h('option', {key:b, value:b}, b)))),
        field('상세 위치' + (item ? '' : ' *'), 'place', 'text', {required:!item, maxLength:item ? 200 : 120, placeholder:'예: 2층 휴게 공간 테이블'}),
        h('div', {className:'form-row'}, field('색상', 'color', 'text', {maxLength:50, placeholder:'예: 검정'}), field('재질', 'material', 'text', {maxLength:100, placeholder:'예: 가죽'})),
        field('키워드', 'keywords', 'text', {maxLength:1000, placeholder:'색상, 재질, 특징 (쉼표로 구분)'}),
        h('label', {className:'field'}, '기타 설명', h('textarea', {name:'description', value:fields.description, onChange:e => setFields(prev => ({...prev, description:e.target.value})), rows:4, maxLength:3000, placeholder:'공개 가능한 특징이나 보관 장소를 적어 주세요.'})),
        h('div', {className:'form-row'}, field('작성자 *', 'author', 'text', {required:true, maxLength:50}), field('연락처' + (item ? '' : ' *'), 'contact', 'text', {required:!item, maxLength:200, placeholder:'연락 가능한 이메일 등'})),
        h('p', {className:'muted'}, '연락처는 물품 상세 화면에 표시됩니다. 공개 가능한 연락용 이메일 등을 입력해 주세요.'),
        error && h('div', {className:'info-box error-box', role:'alert'}, error),
        h('button', {type:'submit', className:'button full', disabled:Boolean(busy)}, busy === 'save' ? '저장 중…' : item ? '수정 내용 저장' : '등록하기 ↗'))));
}

function Detail({item, onClose, onDeleted, onEdit, onUpdated, onBusy, notify}) {
  const dialog = useRef(null);
  const busyRef = useRef(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  busyRef.current = busy;
  useEffect(() => {
    const previousFocus = document.activeElement;
    dialog.current?.querySelector('button')?.focus();
    function keydown(event) {
      if (event.key === 'Escape' && !busyRef.current) onClose();
      if (event.key !== 'Tab') return;
      const nodes = [...dialog.current.querySelectorAll('button:not(:disabled),a[href],input:not(:disabled)')];
      const first = nodes[0], last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) {event.preventDefault(); last?.focus();}
      else if (!event.shiftKey && document.activeElement === last) {event.preventDefault(); first?.focus();}
    }
    document.addEventListener('keydown', keydown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {document.removeEventListener('keydown', keydown); document.body.style.overflow = previousOverflow; previousFocus?.focus();};
  }, []);
  async function remove() {
    if (busy) return;
    setBusy(true); onBusy(true); setError('');
    try { await api('/api/items/' + item.id, {method:'DELETE'}); onDeleted(); }
    catch (error) { setError(error.message); notify(error.message); setBusy(false); }
    finally {onBusy(false);}
  }
  async function changeStatus() {
    if (busy) return;
    setBusy(true); onBusy(true); setError('');
    try {
      const status = item.status === 'resolved' ? 'open' : 'resolved';
      const saved = await api('/api/items/' + item.id + '/status', {
        method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify({status}),
      });
      onUpdated(saved);
      notify(status === 'resolved' ? '해결 완료로 변경했습니다.' : '진행 중으로 되돌렸습니다.');
    } catch (error) {setError(error.message);}
    finally {setBusy(false); onBusy(false);}
  }
  return h('div', {className:'modal-backdrop', onClick:event => {if (event.target === event.currentTarget && !busy) onClose();}},
    h('section', {ref:dialog, className:'modal', role:'dialog', 'aria-modal':true, 'aria-labelledby':'detail-title'},
      button('✕ 닫기', onClose, 'close-button', {disabled:busy}),
      h('div', {className:'detail-image'}, item.image ? h('img', {src:item.image, alt:item.title}) : h('span', {'aria-hidden':true}, item.icon)),
      h('div', {className:'detail-copy'}, h('span', {className:'eyebrow'}, item.kind + ' 신고 · ' + (item.is_mine ? '내 등록' : item.author)),
        h('h2', {id:'detail-title'}, item.title),
        h('span', {className:'report-status ' + item.status, role:'status'}, item.status === 'resolved' ? '해결 완료' : '진행 중'),
        h('dl', null, ...[
          ['장소', item.location], [item.dateLabel, item.date], ['종류', item.category],
          ['특징', item.keywords.join(', ') || '미입력'], ['설명', item.description || '미입력'],
          ['작성자', item.author], ['연락처', item.contact || '등록된 연락처가 없습니다.'],
        ].map(([term, value]) => h('div', {key:term}, h('dt', null, term), h('dd', null, value)))),
        h('div', {className:'info-box'}, '연락처로 문의하고, 공개되지 않은 물품 특징을 확인한 뒤 인계해 주세요.'),
        error && h('div', {className:'info-box error-box', role:'alert'}, error),
        item.is_mine && !confirmDelete && h('div', {className:'dialog-actions'},
          button('신고 수정', () => onEdit(item), 'button secondary', {disabled:busy}),
          button(busy ? '처리 중…' : item.status === 'resolved' ? '진행 중으로 되돌리기' : '해결 완료로 표시', changeStatus, 'button', {disabled:busy})),
        item.is_mine && (confirmDelete ? h('div', null,
          h('p', {className:'muted'}, '이 신고를 삭제할까요? 삭제한 신고는 목록에서 사라집니다.'),
          h('div', {className:'dialog-actions'}, button(busy ? '삭제 중…' : '삭제 확인', remove, 'button danger', {disabled:busy}), button('취소', () => setConfirmDelete(false), 'button secondary', {disabled:busy}))) :
          button('내 등록 삭제', () => setConfirmDelete(true), 'button danger', {disabled:busy})))));
}

function App() {
  const [page, setPage] = useState('home'), [query, setQuery] = useState(''), [building, setBuilding] = useState('전체'), [kind, setKind] = useState('전체');
  const [status, setStatus] = useState(''), [editing, setEditing] = useState(null);
  const [items, setItems] = useState([]), [loading, setLoading] = useState(true), [moreBusy, setMoreBusy] = useState(false), [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState(''), [message, setMessage] = useState(''), [selected, setSelected] = useState(null), [reportKind, setReportKind] = useState('발견');
  const [revision, setRevision] = useState(0), [busy, setBusy] = useState(false);
  const listAbort = useRef(null);
  const viewVersion = useRef(0);
  function params(offset = 0) {
    const value = new URLSearchParams({offset:String(offset), limit:'20'});
    if (status) value.set('status', status);
    if (page === 'mine') value.set('mine', 'true');
    else {
      if (query.trim()) value.set('keyword', query.trim());
      if (building !== '전체') value.set('location', building);
      if (kind !== '전체') value.set('report_type', kind === '분실' ? 'lost' : 'found');
    }
    return value;
  }
  useEffect(() => {
    if (page === 'report') return;
    const controller = new AbortController();
    listAbort.current = controller; viewVersion.current += 1;
    setLoading(true); setMoreBusy(false); setError(''); setItems([]); setHasMore(false);
    const timer = setTimeout(async () => {
      try {
        const result = await api('/api/items?' + params(), {signal:controller.signal});
        if (!controller.signal.aborted) {setItems(result.map(present)); setHasMore(result.length === 20);}
      } catch (err) {if (!controller.signal.aborted) setError(err.message);}
      finally {if (!controller.signal.aborted) setLoading(false);}
    }, page === 'home' && query ? 250 : 0);
    return () => {clearTimeout(timer); controller.abort();};
  }, [page, query, building, kind, status, revision]);
  async function loadMore() {
    if (moreBusy || loading) return;
    const version = viewVersion.current;
    setMoreBusy(true);
    try {
      const result = await api('/api/items?' + params(items.length), {signal:listAbort.current.signal});
      if (version === viewVersion.current) {setItems(prev => [...prev, ...result.map(present).filter(x => !prev.some(y => y.id === x.id))]); setHasMore(result.length === 20);}
    } catch (err) {if (err.name !== 'AbortError' && version === viewVersion.current) setMessage(err.message);}
    finally {if (version === viewVersion.current) setMoreBusy(false);}
  }
  function navigate(next) {if (!busy) {setPage(next); setSelected(null); setEditing(null); setMessage(''); window.scrollTo({top:0});}}
  function report(type) {if (!busy) {setReportKind(type); navigate('report');}}
  async function openItem(id) {
    try {setSelected(present(await api('/api/items/' + id)));}
    catch (err) {setMessage(err.message);}
  }
  function editItem(item) {
    if (busy || !item.is_mine) return;
    setEditing(item); setReportKind(item.report_type === 'lost' ? '분실' : '발견');
    setSelected(null); setPage('report'); setMessage(''); window.scrollTo({top:0});
  }
  function statusFilter() {
    return h('select', {value:status, onChange:e => setStatus(e.target.value), 'aria-label':'처리 상태'},
      h('option', {value:''}, '전체 상태'), h('option', {value:'open'}, '진행 중'), h('option', {value:'resolved'}, '해결 완료'));
  }
  function cards(values) {return h('div', {className:'grid'}, ...values.map(item => h(ItemCard, {key:item.id, item, onOpen:openItem})));}
  const loadingView = loading && h('div', {className:'loading-text', role:'status'}, '물품을 불러오고 있어요…');
  const errorView = error && h('div', {className:'empty error-box', role:'alert'}, error, h('div', null, button('다시 불러오기', () => setRevision(x => x + 1), 'button secondary')));
  const moreView = !loading && !error && hasMore && h('div', {className:'load-more'}, button(moreBusy ? '불러오는 중…' : '더 불러오기', loadMore, 'button secondary', {disabled:moreBusy}));
  return h(React.Fragment, null,
    h('header', {className:'topbar'}, h('div', {className:'bar-inner'},
      button(h(React.Fragment, null, h('span', {className:'brand-icon'}, '↗'), '캠퍼스 찾음'), () => navigate('home'), 'brand', {disabled:busy}),
      h('nav', {'aria-label':'주 메뉴'}, button('분실물 찾기', () => navigate('home'), 'nav ' + (page === 'home' ? 'active' : ''), {disabled:busy}), button('내 정보', () => navigate('mine'), 'nav ' + (page === 'mine' ? 'active' : ''), {disabled:busy})),
      h('span', {className:'demo-label connection-label'}, '우리 캠퍼스의 연결'))),
    h('main', null,
      message && h('div', {className:'notice', role:'status'}, h('span', null, message), button('닫기', () => setMessage(''), 'text-button')),
      page === 'home' && h(React.Fragment, null,
        h('section', {className:'hero'}, h('div', {className:'hero-copy'}, h('div', {className:'eyebrow'}, 'CAMPUS LOST & FOUND'),
          h('h1', null, '잃어버린 물건,', h('br'), '다시 만나는 곳.'), h('p', null, '캠퍼스에서 놓친 소중한 물건.', h('br'), '발견한 마음과 찾는 마음을 연결해요.'),
          h('div', {className:'hero-actions'}, button('＋ 물건을 주웠어요', () => report('발견')), button('물건을 잃어버렸어요 ↗', () => report('분실'), 'button secondary'))),
          h('div', {className:'hero-art', 'aria-hidden':true}, h('span', {className:'orbit orbit-one'}), h('span', {className:'orbit orbit-two'}), h('div', {className:'floating-card float-one'}, '🔑', h('small', null, '여기 있었네요!')), h('div', {className:'floating-card float-two'}, '🎧'), h('div', {className:'round-mark'}, '↗'), h('div', {className:'art-caption'}, 'LOST. FOUND. CONNECTED.'))),
        h('section', {className:'search-area', 'aria-label':'분실물 검색'},
          h('div', {className:'search-input'}, h('span', {'aria-hidden':true}, '⌕'), h('input', {value:query, maxLength:100, onChange:e => setQuery(e.target.value), placeholder:'어떤 물건을 찾고 있나요? 이름, 색상, 장소로 검색', 'aria-label':'물품 검색'}), query && button('지우기', () => setQuery(''), 'text-button')),
          h('div', {className:'filter-label'}, '장소별로 찾아보기'), h('div', {className:'chips'}, ...buildings.map(b => button(b, () => setBuilding(b), 'chip ' + (building === b ? 'selected' : ''), {key:b, 'aria-pressed':building === b})))),
        h('section', {className:'feed'}, h('div', {className:'section-heading'},
          h('div', null, h('span', {className:'eyebrow'}, 'ON CAMPUS'), h('h2', null, '캠퍼스 분실물 ', h('span', {className:'count'}, loading ? '…' : items.length + (hasMore ? '+' : '')))),
          h('div', {className:'feed-filters'},
            h('select', {value:kind, onChange:e => setKind(e.target.value), 'aria-label':'신고 유형'}, ...['전체','발견','분실'].map(k => h('option', {key:k, value:k}, k === '전체' ? '모든 신고' : k + ' 신고'))), statusFilter())),
          h('p', {className:'muted'}, '캠퍼스에서 등록한 분실·습득 신고를 최신순으로 보여 드려요.'), loadingView, errorView,
          !loading && !error && (items.length ? cards(items) : h('div', {className:'empty'}, '아직 등록된 물품이 없거나 검색 결과가 없어요.', h('p', null, '다른 검색어나 장소를 선택하거나 새 신고를 등록해 보세요.'), button('필터 초기화', () => {setQuery(''); setBuilding('전체'); setKind('전체'); setStatus('');}, 'button secondary'))), moreView)),
      page === 'report' && h(ReportForm, {key:editing?.id || 'new', item:editing, kind:reportKind, setKind:setReportKind,
        onBack:() => {if (editing) {setPage('mine'); setSelected(editing); setEditing(null);} else navigate('home');}, notify:setMessage, onBusy:setBusy,
        onSaved:saved => {setPage('mine'); setRevision(x => x + 1); if (editing) setSelected(present(saved)); setEditing(null);
          setMessage(editing ? '수정 내용을 저장했습니다.' : '등록했습니다. 내 정보에서 등록한 물품을 확인할 수 있어요.'); window.scrollTo({top:0});}}),
      page === 'mine' && h('section', {className:'mine'}, h('div', {className:'eyebrow'}, 'MY CAMPUS'), h('h1', null, '내가 연결한 마음들'),
        h('div', {className:'profile'}, h('span', {className:'avatar'}, '나'), h('div', null, h('h2', null, '내 등록 물품'), h('p', null, '이 브라우저에서 등록한 물품입니다. 브라우저 저장 정보를 지우면 내 등록을 구분할 수 없어요.'))),
        h('div', {className:'my-filter'}, h('span', {className:'muted'}, '처리 상태로 보기'), statusFilter()),
        loadingView, errorView, !loading && !error && ['발견','분실'].map(k => h('section', {key:k, className:'my-section'}, h('h2', null, k === '발견' ? '내가 발견한 물품' : '내가 찾는 물품'),
          items.some(item => item.kind === k) ? cards(items.filter(item => item.kind === k)) : h('div', {className:'empty'}, status ? '선택한 상태에 해당하는 물품이 없어요.' : '아직 등록한 물품이 없어요.', h('div', null,
            status ? button('전체 상태 보기', () => setStatus(''), 'button secondary') : button(k + ' 신고하기', () => report(k), 'button secondary'))))), moreView),
      h('footer', null, h('strong', null, '캠퍼스 찾음'), h('span', null, '작은 발견이, 누군가에게는 큰 안심.'), h('small', null, '우리 캠퍼스 분실물 연결 공간'))),
    h('div', {className:'mobile-nav'}, button('⌂ 홈', () => navigate('home'), 'nav ' + (page === 'home' ? 'active' : ''), {disabled:busy}), button('＋ 신고', () => report('발견'), 'nav', {disabled:busy}), button('○ 내 정보', () => navigate('mine'), 'nav ' + (page === 'mine' ? 'active' : ''), {disabled:busy})),
    selected && h(Detail, {key:selected.id, item:selected, onClose:() => setSelected(null), notify:setMessage, onBusy:setBusy, onEdit:editItem,
      onUpdated:saved => {setSelected(present(saved)); setRevision(x => x + 1);},
      onDeleted:() => {setSelected(null); setRevision(x => x + 1); setMessage('등록한 물품을 삭제했습니다.');}}));
}

class AppErrorBoundary extends React.Component {
  constructor(props) {super(props); this.state = {failed:false};}
  static getDerivedStateFromError() {return {failed:true};}
  render() {return this.state.failed ? h('main', null, h('div', {className:'empty', role:'alert'}, '화면을 표시하지 못했습니다. 페이지를 새로고침해 주세요.', h('div', null, button('새로고침', () => window.location.reload())))) : this.props.children;}
}
ReactDOM.createRoot(document.getElementById('root')).render(h(AppErrorBoundary, null, h(App)));
