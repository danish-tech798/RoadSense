'use strict';
const $ = id => document.getElementById(id);
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct = value => Math.max(0, Math.min(100, Number(value) || 0));
const confidence = value => pct(Number(value) * 100).toFixed(1);
const styleClass = value => ['info','warning','mandatory'].includes(value) ? value : 'info';
let activeCatalog = window.SIGN_INFO || {};
let selectedFile = null, previewUrl = null, analyzing = false;
let lastDetections = [], historyEntries = [], lastAlertText = '';
let activeUtterance = null;

function infoFor(entry) {
  return entry.info || activeCatalog[entry.class] || {label:entry.class, icon:'🔹', chip:'SIGN', chip_class:'info'};
}
function showError(message) {
  $('appError').textContent = message || '';
  $('appError').hidden = !message;
}
async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (response.status === 401 || response.redirected && new URL(response.url).pathname === '/login') {
    window.location.assign('/login');
    throw new Error('Your session expired. Sign in again.');
  }
  if (!(response.headers.get('content-type') || '').includes('application/json')) {
    throw new Error('Unexpected server response. Check the VS Code terminal.');
  }
  const data = await response.json();
  if (!response.ok || data.error) throw new Error(data.error || `Request failed (${response.status}).`);
  return data;
}
function loadSafely(task) { task().catch(error => showError(error.message)); }
function setView(name) {
  const target = $('view-' + name);
  if (!target) return;
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  target.classList.add('active');
  document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.view === name));
  const titles = {dashboard:'Dashboard',upload:'Analyze Image',analysis:'AI Analysis',results:'Detection Results',history:'Detection History',analytics:'Analytics',live:'Live Detection',profile:'Profile',settings:'Settings'};
  $('pageTitle').textContent = titles[name] || name;
  window.scrollTo(0, 0);
  if (name === 'dashboard') loadSafely(loadDashboard);
  if (name === 'history') loadSafely(loadHistory);
  if (name === 'analytics') loadSafely(loadAnalytics);
}
function toggleSidebar() { $('sidebar').classList.toggle('open'); $('backdrop').classList.toggle('open'); }
function closeSidebar() { $('sidebar').classList.remove('open'); $('backdrop').classList.remove('open'); }
document.querySelectorAll('.nav-item[data-view]').forEach(item => item.addEventListener('click', () => {setView(item.dataset.view); closeSidebar();}));

// Preferences affect inference and playback; unavailable storage does not prevent use.
let preferences = {};
try { preferences = JSON.parse(localStorage.getItem('roadsense-settings') || '{}'); } catch (_) {}
preferences = preferences && typeof preferences === 'object' ? preferences : {};
const confSlider = $('confSlider');
if (Number(preferences.conf) >= 0.1 && Number(preferences.conf) <= 0.95) confSlider.value = preferences.conf;
if ([640,960,1280].includes(Number(preferences.imgsz))) $('imageSize').value = preferences.imgsz;
if (preferences.voice === 'off') $('voiceEnabled').value = 'off';
$('confValLabel').textContent = confSlider.value;
function saveSettings() {
  preferences = {conf:confSlider.value, imgsz:$('imageSize').value, voice:$('voiceEnabled').value};
  try { localStorage.setItem('roadsense-settings', JSON.stringify(preferences)); } catch (_) {}
}
confSlider.addEventListener('input', () => {$('confValLabel').textContent = confSlider.value; saveSettings();});
$('imageSize').addEventListener('change', saveSettings);
$('voiceEnabled').addEventListener('change', () => {saveSettings(); stopSpeech(); updateVoice();});

// Image upload
$('fileInput').addEventListener('change', event => {if(event.target.files.length) handleFile(event.target.files[0]);});
$('uploadZone').addEventListener('dragover', event => event.preventDefault());
$('uploadZone').addEventListener('drop', event => {event.preventDefault(); if(event.dataTransfer.files.length) handleFile(event.dataTransfer.files[0]);});
function handleFile(file) {
  if (analyzing) {showError('Wait for the current analysis to finish.'); return;}
  if (!['image/jpeg','image/png'].includes(file.type)) {showError('Choose a JPG or PNG image.'); return;}
  if (file.size > 15 * 1024 * 1024) {showError('Choose an image smaller than 15 MB.'); return;}
  resetUpload();
  showError('');
  selectedFile = file;
  previewUrl = URL.createObjectURL(file);
  const img = document.createElement('img');
  img.src = previewUrl; img.alt = 'Selected road image';
  img.onerror = () => {resetUpload(); showError('This image could not be opened. Choose another JPG or PNG.');};
  $('previewImgWrap').replaceChildren(img);
  $('previewFilename').textContent = file.name;
  $('previewWrap').style.display = 'block'; $('uploadZone').style.display = 'none';
}
function resetUpload() {
  if (analyzing) return;
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = null; selectedFile = null;
  $('previewImgWrap').replaceChildren();
  $('previewWrap').style.display = 'none'; $('uploadZone').style.display = 'block'; $('fileInput').value = '';
}
async function runAnalysis() {
  if (!selectedFile || analyzing) return;
  analyzing = true; $('analyzeBtn').disabled = true; showError(''); stopSpeech(); setView('analysis');
  const form = new FormData();
  form.append('image', selectedFile); form.append('conf', confSlider.value); form.append('imgsz', $('imageSize').value);
  try {
    const data = await api('/api/detect', {method:'POST',body:form});
    renderResults(data); setView('results');
  } catch (error) {setView('upload'); showError(error.message);}
  finally {analyzing = false; $('analyzeBtn').disabled = false;}
}
function fillClassFilter(id, entries) {
  const select = $(id), previous = select.value;
  const labels = new Map(entries.map(e => [e.class, infoFor(e).label || e.class]));
  select.replaceChildren(new Option('All classes', ''));
  [...labels].sort((a,b) => a[1].localeCompare(b[1])).forEach(([key,label]) => select.add(new Option(label,key)));
  select.value = labels.has(previous) ? previous : '';
}
function renderResults(data) {
  lastDetections = data.detections || [];
  // The backend PNG already contains boxes. Never draw a second coordinate overlay.
  const img = document.createElement('img');
  img.src = data.annotated_image; img.alt = 'Model predictions with bounding boxes';
  $('resultImgWrap').replaceChildren(img);
  $('resultSummary').textContent = `${lastDetections.length} predicted signs · ${Number(data.elapsed_ms).toFixed(0)} ms · ${data.model || 'YOLOv8'} · ${data.imgsz || 640}px`;
  fillClassFilter('resultClassFilter', lastDetections);
  renderSignCards();
  const flagged = lastDetections.filter(d => ['mandatory','warning'].includes(infoFor(d).chip_class));
  $('resultAlerts').innerHTML = flagged.map(d => {
    const info = infoFor(d);
    return `<div class="alert-box"><div class="alert-label">PREDICTED SIGN</div><div class="alert-text">${escapeHtml(info.label || d.class)} · ${confidence(d.confidence)}% confidence</div></div>`;
  }).join('');
  const labels = [...new Set(lastDetections.map(d => infoFor(d).label || d.class))];
  lastAlertText = labels.length ? `Predicted signs: ${labels.slice(0,12).join('. ')}.${labels.length>12 ? ' More classes are shown on screen.' : ''} Please verify the image.` : '';
  updateVoice();
}
function renderSignCards() {
  const selected = $('resultClassFilter').value;
  const detections = lastDetections.filter(d => !selected || d.class === selected);
  $('signCardsList').innerHTML = detections.map(d => {
    const i = infoFor(d);
    return `<div class="sign-card"><div class="sign-icon-box">${escapeHtml(i.icon || '🔹')}</div><div class="sign-card-body"><div class="sign-card-top"><h4>${escapeHtml(i.label || d.class)}</h4><span class="conf num">${confidence(d.confidence)}%</span></div><p>${escapeHtml(i.meaning || 'Predicted sign category.')}<br>${escapeHtml(i.rule || 'Verify the visible sign.')}</p></div></div>`;
  }).join('') || '<div class="empty-state">No signs detected at this threshold. This does not establish that no signs are present.</div>';
}
$('resultClassFilter').addEventListener('change', renderSignCards);
function updateVoice() {
  const available = Boolean(window.speechSynthesis && window.SpeechSynthesisUtterance);
  const enabled = $('voiceEnabled').value !== 'off';
  $('voiceBtn').disabled = !available || !enabled || !lastAlertText;
  $('voiceStatus').textContent = !available ? 'Voice unavailable in this browser' : !enabled ? 'Voice disabled' : lastAlertText ? 'Read predictions' : 'No predictions to read';
}
function stopSpeech() {
  activeUtterance = null;
  if (window.speechSynthesis) window.speechSynthesis.cancel();
  $('waveform').classList.remove('wf-active');
  updateVoice();
}
function speakAlert() {
  if ($('voiceBtn').disabled) return;
  stopSpeech();
  const utter = new window.SpeechSynthesisUtterance(lastAlertText);
  activeUtterance = utter; utter.lang = 'en-IN'; utter.rate = 0.95;
  $('voiceStatus').textContent = 'Reading predictions…'; $('waveform').classList.add('wf-active');
  const finish = () => {if(activeUtterance === utter) {activeUtterance = null; $('waveform').classList.remove('wf-active'); updateVoice();}};
  utter.onend = finish; utter.onerror = finish;
  window.speechSynthesis.speak(utter);
}
window.addEventListener('beforeunload', () => {if(previewUrl) URL.revokeObjectURL(previewUrl); if(window.speechSynthesis) window.speechSynthesis.cancel();});

// Dynamic classes and truthful model status
async function loadModelInfo() {
  try {
    const data = await api('/api/model-info');
    activeCatalog = data.sign_info || {};
    const count = Object.keys(data.names || {}).length;
    $('modelStatus').textContent = `${count} classes · Ready`;
    $('modelDetails').textContent = `${data.model} · ${count} supported classes. ${count===4 ? 'Original model loaded. Train and install best_india.pt to expand its vocabulary.' : 'Class names come from the loaded checkpoint.'}`;
    if (!preferences.imgsz && [640,960,1280].includes(Number(data.default_imgsz))) $('imageSize').value = data.default_imgsz;
    renderSupportedClasses();
  } catch(error) {
    $('modelStatus').textContent = 'Model unavailable';
    $('modelDetails').textContent = error.message;
    $('supportedClasses').textContent = 'Check the model file and restart Flask.';
  }
}
function renderSupportedClasses() {
  const query = $('classSearch').value.toLowerCase().trim();
  const names = Object.entries(activeCatalog).filter(([key,info]) => `${key} ${info.label || ''}`.toLowerCase().includes(query));
  $('supportedClasses').innerHTML = names.map(([key,info]) => `<span class="class-tag" title="${escapeHtml(key)}">${escapeHtml(info.label || key)}</span>`).join('') || '<span class="help-text">No matching classes.</span>';
}
$('classSearch').addEventListener('input', renderSupportedClasses);
function categoryRows(breakdown) {
  return breakdown.map(b => `<div class="cat-bar"><div class="cat-bar-top"><span>${escapeHtml(b.label || b.class)}</span><span class="num">${pct(b.pct)}%</span></div><div class="cat-bar-track"><div class="cat-bar-fill" style="width:${pct(b.pct)}%"></div></div></div>`).join('') || '<div class="empty-state">No detections recorded yet.</div>';
}
async function loadDashboard() {
  const data = await api('/api/stats');
  $('statImages').textContent = data.total_images; $('statSigns').textContent = data.signs_detected;
  $('statAlerts').textContent = data.safety_alerts; $('statWarnings').textContent = data.warning_signs;
  $('recentList').innerHTML = data.recent.map(r => {
    const i = infoFor(r);
    return `<div class="detect-row"><div class="detect-thumb">${escapeHtml(i.icon || '🔹')}</div><div class="detect-info"><div class="detect-name">${escapeHtml(i.label || r.class)}</div><div class="detect-meta">${escapeHtml(new Date(r.timestamp).toLocaleString())} · ${confidence(r.confidence)}% confidence</div></div><span class="chip ${styleClass(i.chip_class)}">${escapeHtml(i.chip || 'SIGN')}</span></div>`;
  }).join('') || '<div class="empty-state">No detections yet — analyze an image to get started.</div>';
  $('breakdownList').innerHTML = categoryRows(data.breakdown);
}
async function loadHistory() {
  historyEntries = await api('/api/history');
  fillClassFilter('historyClassFilter', historyEntries); renderHistory();
}
function renderHistory() {
  const cls = $('historyClassFilter').value, query = $('historySearch').value.toLowerCase().trim();
  const filtered = historyEntries.filter(e => (!cls || cls === e.class) && `${e.class} ${infoFor(e).label || ''} ${e.timestamp}`.toLowerCase().includes(query));
  $('historyTimeline').innerHTML = filtered.map(e => {
    const i = infoFor(e);
    return `<div class="timeline-item"><div class="timeline-dot"></div><div class="hist-thumb">${escapeHtml(i.icon || '🔹')}</div><div class="hist-card"><div class="hist-main"><h4>${escapeHtml(i.label || e.class)}</h4><div class="hist-meta">${escapeHtml(new Date(e.timestamp).toLocaleString())} · ${escapeHtml(i.chip || 'SIGN')}</div></div><span class="conf num">${confidence(e.confidence)}%</span></div></div>`;
  }).join('') || '<div class="empty-state">No matching detections.</div>';
}
$('historyClassFilter').addEventListener('change', renderHistory);
$('historySearch').addEventListener('input', renderHistory);
async function loadAnalytics() {
  const [stats, entries] = await Promise.all([api('/api/stats'), api('/api/history')]);
  $('categoryBars').innerHTML = categoryRows(stats.breakdown);
  const buckets = {'<70%':0,'70–85%':0,'85–95%':0,'95–100%':0};
  entries.forEach(e => {const n=Number(e.confidence)*100; buckets[n<70?'<70%':n<85?'70–85%':n<95?'85–95%':'95–100%']++;});
  const max = Math.max(...Object.values(buckets),1);
  $('confidenceBars').innerHTML = entries.length ? Object.entries(buckets).map(([label,count]) => `<div class="bar-col"><div class="bar-track"><div class="bar-fill" style="height:${count/max*100}%"></div></div><div class="bar-label num">${count}<br>${escapeHtml(label)}</div></div>`).join('') : '<div class="empty-state">No data yet.</div>';
  const byDay = {};
  entries.forEach(e => {const day=String(e.timestamp).slice(0,10); byDay[day]=(byDay[day]||0)+1;});
  const days = Object.keys(byDay).sort();
  if (!days.length) {$('activityChart').innerHTML='<div class="empty-state">No data yet.</div>'; return;}
  const peak = Math.max(...Object.values(byDay)), W=400,H=100,PAD=10;
  const coords = days.map((day,i) => ({x:days.length>1?PAD+i/(days.length-1)*(W-PAD*2):W/2,y:H-PAD-byDay[day]/peak*(H-PAD*2)}));
  $('activityChart').innerHTML = `<svg class="line-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Daily detection counts"><polyline points="${coords.map(c=>`${c.x},${c.y}`).join(' ')}" fill="none" stroke="#FFB020" stroke-width="2"/>${coords.map(c=>`<circle cx="${c.x}" cy="${c.y}" r="3" fill="#FFB020"/>`).join('')}</svg><div class="activity-labels"><span>${escapeHtml(days[0])}</span><span>${escapeHtml(days[days.length-1])}</span></div><p class="help-text">Peak: ${peak} detections per day · ${days.length} recorded days</p>`;
}
updateVoice();
loadSafely(loadDashboard);
loadModelInfo();
