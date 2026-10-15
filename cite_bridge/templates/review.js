// ---- 画面に依らない部分。DOM に触れない。tests/test_review_js.py が node で動かす
// 保存済みの入力（localStorage の文字列。古いものから順）を一つにまとめる。後のものが優先する。読めなければ空
function mergeStored(raws) {
  try {
    const merged = {decisions: {}, confirms: []};
    for (const raw of raws) {
      const s = JSON.parse(raw || '{}');
      if (s.by) merged.by = s.by;
      if (s.foldDone !== undefined) merged.foldDone = s.foldDone;
      Object.assign(merged.decisions, s.decisions || {});
      merged.confirms.push(...(s.confirms || []));
    }
    return merged;
  } catch (e) { return {}; }
}
// 判断した後に本文か根拠（候補なら候補の中身）が変わったものは、入力を戻さない（見直してもらう）
function isStale(d, c) {
  if (c.candidate) return d.cfp !== c.cfp;
  return !!(d.fingerprint && (d.fingerprint !== c.fingerprint || d.evidence !== c.evidence));
}
// 画面の入力から一件の判断を作る。判断した時点の指紋を持たせ、apply が食い違いを断れるようにする
function makeDecision(c, action, note, remark) {
  return c.candidate
    ? {cand: true, action, note, cfp: c.cfp}
    : {action, note, remark, fingerprint: c.fingerprint, evidence: c.evidence};
}
// 差し戻しと却下には理由が要る。理由の無い id を返す
function missingReasons(decisions) {
  return Object.entries(decisions)
    .filter(([id, d]) => (d.action === 'send_back' || d.action === 'reject') && !d.note)
    .map(([id]) => id);
}
// 判断ファイルの内容（cite-bridge-decisions/1）。判断も確認も無ければ null
function buildOutput(s, D, byId, nowIso) {
  const confirms = [];
  for (const e of s.confirms) {
    const c = D.citations.find(c => e in c.excerpts);
    if (c) confirms.push({id: e, fingerprint: c.excerpts[e]});
    else if (D.orphans && e in D.orphans) confirms.push({id: e, fingerprint: D.orphans[e]});  // どの引用にも使われていない抜き書き
  }
  const ds = Object.entries(s.decisions);
  const out = {format: 'cite-bridge-decisions/1', manuscript: D.manuscript, generated: D.generated, by: s.by.trim(),
    saved: nowIso,
    decisions: ds.filter(([id, d]) => !d.cand && (d.action || d.remark)).map(([id, d]) => ({id, action: d.action,
      note: d.note, remark: d.remark || '',
      fingerprint: byId[id].fingerprint, evidence: byId[id].evidence})),
    candidates: ds.filter(([id, d]) => d.cand && d.action).map(([id, d]) => ({id, action: d.action, note: d.note, cfp: byId[id].cfp})),
    confirms};
  if (!out.decisions.length && !out.candidates.length && !out.confirms.length) return null;
  return out;
}
function downloadName(manuscript) {
  return 'decisions_' + manuscript.replace(/[^\w.-]+/g, '_').replace(/\.md$/, '') + '.json';
}

// ---- 画面（DOM に触れる）
if (typeof document !== 'undefined') (function () {
  const D = JSON.parse(document.getElementById('data').textContent);
  const KEY = 'cite-bridge:' + D.manuscript;
  const byId = Object.fromEntries(D.citations.map(c => [c.id, c]));
  const cards = () => [...document.querySelectorAll('article.card')].filter(a => a.offsetParent !== null);
  function load() {
    // 前の版（作った時刻をキーに含めていた）に残っている入力も読む。新しいキーの入力を優先する
    try {
      const keys = Object.keys(localStorage).filter(k => k.startsWith(KEY + ':')).sort();
      return mergeStored([...keys, KEY].map(k => localStorage.getItem(k)));
    } catch (e) { return {}; }
  }
  function store(s) { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) {} }
  function grow(t) { t.style.height = 'auto'; t.style.height = t.scrollHeight + 'px'; }
  function collect() {
    const s = {decisions: {}, confirms: [], by: document.getElementById('by').value,
               foldDone: document.getElementById('foldDone').checked};
    document.querySelectorAll('article.card').forEach(a => {
      const id = a.dataset.id, r = a.querySelector('input[type=radio]:checked');
      const note = a.querySelector('textarea[data-note]').value.trim();
      const rm = a.querySelector('textarea[data-remark]'), remark = rm ? rm.value.trim() : '';
      if ((r && r.value) || note || remark) s.decisions[id] = makeDecision(byId[id], r ? r.value : '', note, remark);
      a.querySelector('.decide').dataset.choice = r ? r.value : '';
    });
    document.querySelectorAll('input[data-confirm]:checked').forEach(c => s.confirms.push(c.dataset.confirm));
    s.confirms = [...new Set(s.confirms)];
    return s;
  }
  function refresh() {
    const s = collect(); store(s);
    const n = Object.values(s.decisions).filter(d => d.action).length;
    document.getElementById('count').textContent = '判断 ' + n + ' 件・要約の確認 ' + s.confirms.length + ' 件';
  }
  function restore() {
    const s = load();
    if (s.by) document.getElementById('by').value = s.by;
    if (s.foldDone) document.getElementById('foldDone').checked = true;
    for (const [id, d] of Object.entries(s.decisions || {})) {
      const a = document.getElementById(id); if (!a || !byId[id]) continue;
      if (isStale(d, byId[id])) continue;
      const r = a.querySelector('input[type=radio][value="' + (d.action || '') + '"]'); if (r) r.checked = true;
      a.querySelector('textarea[data-note]').value = d.note || '';
      const rm = a.querySelector('textarea[data-remark]'); if (rm) rm.value = d.remark || '';
    }
    (s.confirms || []).forEach(e => document.querySelectorAll('input[data-confirm="' + e + '"]').forEach(c => c.checked = true));
  }
  function foldDecided() {
    const on = document.getElementById('foldDone').checked;
    document.querySelectorAll('article.card').forEach(a => {
      const r = a.querySelector('input[type=radio]:checked');
      if (on && r && r.value) a.classList.add('folded');
    });
  }
  document.addEventListener('input', e => {
    if (e.target.matches('textarea')) grow(e.target);
    if (e.target.matches('input[data-confirm]'))  // 同じ根拠が他のカードにもあれば、確認の印をそろえる
      document.querySelectorAll('input[data-confirm="' + e.target.dataset.confirm + '"]').forEach(c => c.checked = e.target.checked);
    refresh();
  });
  document.addEventListener('change', e => { if (e.target.matches('input[type=radio]')) foldDecided(); });
  document.addEventListener('click', e => {
    const b = e.target.closest('.fold'); if (b) b.closest('article').classList.toggle('folded');
  });
  document.addEventListener('toggle', e => {  // 頁の画像は開いたときに入れる（同じ画像を一度だけ持つ）
    const img = e.target.querySelector && e.target.querySelector('img[data-img]');
    if (img && !img.src) img.src = D.images[img.dataset.img];
  }, true);
  document.getElementById('all').addEventListener('change', e => document.body.classList.toggle('pending-only', !e.target.checked));
  document.getElementById('foldDone').addEventListener('change', e => {
    if (!e.target.checked) document.querySelectorAll('article.card.folded').forEach(a => a.classList.remove('folded'));
    foldDecided(); refresh();
  });
  document.addEventListener('keydown', e => {
    if (e.target.matches('input[type=text], textarea, select') || e.ctrlKey || e.metaKey || e.altKey) {
      if (e.key === 'Escape') e.target.blur();
      return;
    }
    const list = cards(); if (!list.length) return;
    let cur = document.activeElement.closest && document.activeElement.closest('article.card');
    let i = cur ? list.indexOf(cur) : -1;
    const go = j => { const a = list[Math.max(0, Math.min(list.length - 1, j))]; a.focus(); a.scrollIntoView({block: 'start'}); };
    if (e.key === 'j') { go(i + 1); e.preventDefault(); return; }
    if (e.key === 'k') { go(i - 1); e.preventDefault(); return; }
    if (!cur) return;
    const v = {'1': 0, '2': 1, '3': 2}[e.key];  // 保留・承認（受け入れ）・差し戻し（却下）の順に並ぶ
    if (v !== undefined) {
      cur.querySelectorAll('input[type=radio]')[v].checked = true; refresh(); foldDecided();
      if (v === 2) cur.querySelector('textarea[data-note]').focus();
      e.preventDefault(); return;
    }
    if (e.key === 'r') { cur.querySelector('textarea[data-note]').focus(); e.preventDefault(); }
    if (e.key === 'm') { const rm = cur.querySelector('textarea[data-remark]'); if (rm) rm.focus(); e.preventDefault(); }
    if (e.key === 'f') { cur.classList.toggle('folded'); e.preventDefault(); }
  });
  document.getElementById('save').addEventListener('click', () => {
    const s = collect();
    if (!s.by.trim()) { alert('判断する者を書く'); return; }
    const missing = missingReasons(s.decisions);
    if (missing.length) { alert('差し戻しと却下には理由が要る: ' + missing.join(', ')); return; }
    const out = buildOutput(s, D, byId, new Date().toISOString());
    if (!out) { alert('判断がまだ無い'); return; }
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify(out, null, 1)], {type: 'application/json'}));
    a.download = downloadName(D.manuscript);
    document.body.appendChild(a); a.click(); a.remove();
  });
  restore(); refresh(); foldDecided();
  document.querySelectorAll('textarea').forEach(grow);
})();

if (typeof module !== 'undefined') module.exports = {mergeStored, isStale, makeDecision, missingReasons, buildOutput, downloadName};
