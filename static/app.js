'use strict';

const APP_NAME = 'Spectoom';
const APP_VERSION = '2.2.2-cloud';
const app = document.getElementById('app');
const toastRoot = document.getElementById('toast-root');
const previewAudio = document.getElementById('preview-audio');

const MODULES = {
  playlist_entry: {
    id: 'playlist_entry',
    label: 'Entrées en playlist',
    singular: 'Entrée en playlist',
    description: 'Annonce tes entrées en playlist sur les différentes plateformes.',
    short: 'Playlist',
    accent: 'mint',
    ratio: '4:5',
    output: '1080 × 1350 · 20 s',
  },
  new_release: {
    id: 'new_release',
    label: 'Nouvelle sortie',
    singular: 'Nouvelle sortie',
    description: 'Annonce un single, un EP ou un album avec un visuel de campagne.',
    short: 'Sortie',
    accent: 'peach',
    ratio: '4:5',
    output: '1080 × 1350 · 20 s',
  },
  youtube_spectrum: {
    id: 'youtube_spectrum',
    label: 'Spectrum YouTube',
    singular: 'Spectrum YouTube',
    description: 'Crée une vidéo musicale 16:9 avec une visualisation audio-réactive.',
    short: 'Spectrum',
    accent: 'lavender',
    ratio: '16:9',
    output: '1920 × 1080 · durée du morceau',
  },
};

const STEPS = {
  playlist_entry: [
    { id: 'track', label: 'Morceau', hint: 'Titre et pochette' },
    { id: 'background', label: 'Fond', hint: 'Image et cadrage' },
    { id: 'playlists', label: 'Playlists', hint: '1 à 6 entrées' },
    { id: 'branding', label: 'Branding', hint: 'Logo et accroche' },
    { id: 'audio', label: 'Audio', hint: 'Extrait de 20 s' },
    { id: 'export', label: 'Aperçu', hint: 'Vérification' },
  ],
  new_release: [
    { id: 'release', label: 'Sortie', hint: 'Single, EP ou album' },
    { id: 'background', label: 'Visuel', hint: 'Image et cadrage' },
    { id: 'template', label: 'Template', hint: 'Direction graphique' },
    { id: 'branding', label: 'Branding', hint: 'Virgin Music' },
    { id: 'audio', label: 'Audio', hint: 'Extrait de 20 s' },
    { id: 'export', label: 'Aperçu', hint: 'Vérification' },
  ],
  youtube_spectrum: [
    { id: 'track', label: 'Morceau', hint: 'Titre et cover' },
    { id: 'background', label: 'Fond', hint: 'Image ou vidéo' },
    { id: 'spectrum', label: 'Spectrum', hint: 'Style et couleurs' },
    { id: 'typography', label: 'Textes', hint: 'Couleurs et logo' },
    { id: 'audio', label: 'Audio', hint: 'Morceau complet' },
    { id: 'export', label: 'Aperçu', hint: 'Vérification' },
  ],
};

const SPECTRUM_STYLES = [
  ['bars', 'Barres'],
  ['mirror', 'Miroir'],
  ['fluid', 'Fluide'],
  ['hill', 'Colline'],
  ['led', 'LED'],
  ['particles', 'Particules'],
];

const DSP_FALLBACKS = {
  spotify: ['/static/platforms/spotify-black.png', '/static/platforms/spotify-white.png'],
  'apple-music': ['/static/platforms/apple-music-black.png', '/static/platforms/apple-music-white.png'],
  deezer: ['/static/platforms/deezer-black.png', '/static/platforms/deezer-white.png'],
  'youtube-music': ['/static/platforms/youtube-music-black.png', '/static/platforms/youtube-music-white.png'],
  boomplay: ['/static/platforms/boomplay-black.png', '/static/platforms/boomplay-white.png'],
  audiomack: ['/static/platforms/audiomack-black.png', '/static/platforms/audiomack-white.png'],
};

const state = {
  user: null,
  config: { app: { name: APP_NAME, version: APP_VERSION }, modules: [], platforms: [], presets: [] },
  projects: [],
  currentProject: null,
  renders: [],
  preview: null,
  view: 'dashboard',
  projectFilter: 'all',
  editorStep: 'track',
  selectedPlaylist: 0,
  search: '',
  modal: null,
  modalType: null,
  modalLockedType: null,
  modalProjectName: '',
  modalError: '',
  creatingProject: false,
  saving: false,
  lastSavedAt: null,
  renderJob: null,
  renderModalHidden: false,
  conversions: [],
  conversionFiles: [],
  conversionJob: null,
  conversionUploading: false,
  health: null,
  waveform: null,
  waveformUrl: '',
  audioStatus: 'idle',
  previewPlaying: false,
};

let saveTimer = null;
let previewTimer = null;
let renderPollTimer = null;
let conversionPollTimer = null;
let waveformRequest = 0;
let audioContext = null;
let analyser = null;
let mediaSource = null;
let spectrumAnimationFrame = null;
let spectrumParticles = [];
let spectrumHistory = [];
let currentAudioObjectUrl = '';

const iconPaths = {
  home: '<path d="M3 11.5 12 4l9 7.5v8a1.5 1.5 0 0 1-1.5 1.5h-5v-6h-5v6h-5A1.5 1.5 0 0 1 3 19.5v-8Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>',
  project: '<path d="M4 6.5h6l2 2h8v10A1.5 1.5 0 0 1 18.5 20h-13A1.5 1.5 0 0 1 4 18.5v-12Z" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M4 10h16" fill="none" stroke="currentColor" stroke-width="1.8"/>',
  library: '<rect x="3" y="4" width="18" height="16" rx="2.5" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="8" cy="9" r="2"/><path d="m4 18 5-5 3 3 3-4 5 6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>',
  render: '<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="m10 8 6 4-6 4V8Z"/>',
  brand: '<path d="M12 3a9 9 0 1 0 0 18h1.3a1.7 1.7 0 0 0 0-3.4h-1a1.8 1.8 0 0 1 0-3.6h2.8A5.9 5.9 0 0 0 21 8.1C21 5.3 17 3 12 3Z" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="7.7" cy="9" r="1"/><circle cx="11" cy="6.8" r="1"/><circle cx="15" cy="7.2" r="1"/>',
  settings: '<circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" fill="none" stroke="currentColor" stroke-width="1.35"/>',
  plus: '<path d="M12 5v14M5 12h14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  playlist: '<rect x="4" y="4" width="8" height="8" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/><rect x="12" y="12" width="8" height="8" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M12 8h4a2 2 0 0 1 2 2v2M8 12v4a2 2 0 0 0 2 2h2" fill="none" stroke="currentColor" stroke-width="1.8"/>',
  sparkle: '<path d="M12 2c.8 4.2 3 6.4 7 7-4 .8-6.2 3-7 7-.8-4-3-6.2-7-7 4-.6 6.2-2.8 7-7Z" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M19 15c.4 2 1.5 3.1 3.5 3.5-2 .4-3.1 1.5-3.5 3.5-.4-2-1.5-3.1-3.5-3.5 2-.4 3.1-1.5 3.5-3.5Z"/>',
  spectrum: '<path d="M4 17V9m4 8V5m4 12v-7m4 7V3m4 14v-9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  search: '<circle cx="11" cy="11" r="6.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="m16 16 4 4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
  back: '<path d="m15 18-6-6 6-6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
  save: '<path d="M5 4h12l2 2v14H5V4Z" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M8 4v6h8V4M8 20v-6h8v6" fill="none" stroke="currentColor" stroke-width="1.8"/>',
  download: '<path d="M12 3v12m0 0 4-4m-4 4-4-4M5 20h14" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>',
  duplicate: '<rect x="8" y="8" width="11" height="11" rx="2" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M6 16H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" fill="none" stroke="currentColor" stroke-width="1.7"/>',
  trash: '<path d="M5 7h14M9 7V4h6v3M7 7l1 13h8l1-13" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>',
  edit: '<path d="m4 20 4.2-1 10-10-3.2-3.2-10 10L4 20Z" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="m13.8 7 3.2 3.2" fill="none" stroke="currentColor" stroke-width="1.7"/>',
  more: '<circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/>',
  play: '<path d="m9 7 8 5-8 5V7Z"/>',
  pause: '<path d="M8 7h3v10H8V7Zm5 0h3v10h-3V7Z"/>',
  upload: '<path d="M12 16V4m0 0L8 8m4-4 4 4M5 20h14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
  image: '<rect x="3" y="4" width="18" height="16" rx="2" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="8" cy="9" r="2"/><path d="m4 18 5-5 3 3 3-4 5 6" fill="none" stroke="currentColor" stroke-width="1.7"/>',
  music: '<path d="M9 18V6l10-2v12" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="16.5" cy="16" r="2.5"/>',
  video: '<rect x="3" y="5" width="14" height="14" rx="2" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="m17 10 4-2v8l-4-2" fill="none" stroke="currentColor" stroke-width="1.7"/>',
  check: '<path d="m5 12 4 4L19 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  warning: '<path d="M12 3 2.5 20h19L12 3Z" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M12 9v5m0 3h.01" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  close: '<path d="m7 7 10 10M17 7 7 17" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
  logout: '<path d="M10 4H5v16h5M14 8l4 4-4 4m4-4H9" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>',
  grip: '<path d="M9 6h.01M15 6h.01M9 12h.01M15 12h.01M9 18h.01M15 18h.01" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>',
  chevronLeft: '<path d="m14 6-6 6 6 6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
  chevronRight: '<path d="m10 6 6 6-6 6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
  refresh: '<path d="M20 7v5h-5M4 17v-5h5M18.5 9A7 7 0 0 0 6 6.5L4 9m16 6-2 2.5A7 7 0 0 1 5.5 15" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>',
  convert: '<path d="M7 5h10l-2.5-2.5M17 19H7l2.5 2.5M18.5 7.5A7 7 0 0 1 19 15m-13.5 1.5A7 7 0 0 1 5 9" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
};

function icon(name, size = 20) {
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">${iconPaths[name] || iconPaths.more}</svg>`;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function safeUrl(value) {
  const url = String(value || '');
  if (/^\/(media\/|demo\/|static\/)/.test(url) || /^blob:/.test(url)) return escapeHtml(url);
  return '';
}

function safeColor(value, fallback = '#111111') {
  const color = String(value || '');
  return /^#[0-9a-f]{6}$/i.test(color) ? color : fallback;
}

function uid() {
  return window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function initials(value) {
  return String(value || 'U').split(/\s+/).filter(Boolean).slice(0, 2).map((item) => item[0]).join('').toUpperCase();
}

function formatDate(value) {
  if (!value) return '—';
  try {
    return new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(value));
  } catch {
    return String(value);
  }
}

function formatDateTime(value) {
  if (!value) return '—';
  try {
    return new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(value));
  } catch {
    return String(value);
  }
}

function formatDuration(seconds, precise = false) {
  const safe = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(safe / 60);
  const rest = safe - minutes * 60;
  return precise
    ? `${String(minutes).padStart(2, '0')}:${rest.toFixed(3).padStart(6, '0')}`
    : `${String(minutes).padStart(2, '0')}:${String(Math.floor(rest)).padStart(2, '0')}`;
}

function parseTimecode(value) {
  const raw = String(value || '').trim().replace(',', '.');
  if (/^\d+(\.\d+)?$/.test(raw)) return Number(raw);
  const match = raw.match(/^(\d{1,3}):([0-5]?\d(?:\.\d{1,3})?)$/);
  if (!match) return null;
  return Number(match[1]) * 60 + Number(match[2]);
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, Number(value) || 0));
}

function getPath(object, path) {
  return String(path).split('.').reduce((value, key) => value?.[key], object);
}

function setPath(object, path, value) {
  const parts = String(path).split('.');
  let cursor = object;
  parts.forEach((key, index) => {
    if (index === parts.length - 1) cursor[key] = value;
    else {
      if (cursor[key] == null || typeof cursor[key] !== 'object') cursor[key] = /^\d+$/.test(parts[index + 1]) ? [] : {};
      cursor = cursor[key];
    }
  });
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const request = { credentials: 'same-origin', ...options, headers };
  if (options.json !== undefined) {
    headers['Content-Type'] = 'application/json';
    request.body = JSON.stringify(options.json);
    delete request.json;
  }
  const response = await fetch(path, request);
  const type = response.headers.get('content-type') || '';
  const data = type.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    const error = new Error(data?.error || data?.message || `Erreur ${response.status}`);
    error.status = response.status;
    error.details = data?.details;
    throw error;
  }
  return data;
}

function toast(message, type = 'info', duration = 3600) {
  const node = document.createElement('div');
  node.className = `toast toast-${type}`;
  node.innerHTML = `<span class="toast-dot"></span><span>${escapeHtml(message)}</span>`;
  toastRoot.appendChild(node);
  requestAnimationFrame(() => node.classList.add('is-visible'));
  setTimeout(() => {
    node.classList.remove('is-visible');
    setTimeout(() => node.remove(), 220);
  }, duration);
}

function statusClass(status) {
  const value = String(status || '').toLowerCase();
  if (value.includes('termin')) return 'status-done';
  if (value.includes('rendu') || value.includes('attente')) return 'status-rendering';
  if (value.includes('échec') || value.includes('echec')) return 'status-error';
  if (value.includes('prêt') || value.includes('pret')) return 'status-ready';
  return 'status-draft';
}

function moduleFor(projectOrType) {
  const type = typeof projectOrType === 'string' ? projectOrType : projectOrType?.type;
  return MODULES[type] || MODULES.playlist_entry;
}

function thumbnailUrl(project) {
  return project?.background?.url || project?.track?.coverUrl || '/demo/background.jpg';
}

function projectMeta(project) {
  if (project.type === 'playlist_entry') return `${project.playlistsCount ?? project.playlists?.length ?? 0} playlist${(project.playlistsCount ?? project.playlists?.length ?? 0) > 1 ? 's' : ''} · 20 s`;
  if (project.type === 'new_release') return `${String(project.newRelease?.releaseType || 'single').toUpperCase()} · 20 s`;
  return `${formatDuration(project.audio?.duration || 0)} · 16:9`;
}

function validationFor(project) {
  const errors = [];
  if (!project?.name?.trim()) errors.push(['Projet', 'Nomme le projet.']);
  if (!project?.track?.title?.trim()) errors.push(['Morceau', 'Ajoute le titre.']);
  if (!project?.track?.artist?.trim()) errors.push(['Morceau', 'Ajoute le nom de l’artiste.']);
  const audio = project?.audio || {};
  if (!audio.url) errors.push(['Audio', 'Importe un fichier audio.']);
  if (project?.type !== 'youtube_spectrum' && audio.url && Number(audio.duration || 0) < 20) errors.push(['Audio', 'Le fichier doit durer au moins 20 secondes.']);
  if (project?.type !== 'youtube_spectrum' && Number(audio.start || 0) + 20 > Number(audio.duration || 0) + 0.001) errors.push(['Audio', 'La sélection dépasse le fichier.']);
  if (project?.type === 'playlist_entry') {
    if (!project.track?.coverUrl) errors.push(['Morceau', 'Importe la pochette.']);
    if (!project.background?.url) errors.push(['Fond', 'Importe l’image de fond.']);
    if (!Array.isArray(project.playlists) || project.playlists.length < 1) errors.push(['Playlists', 'Ajoute au moins une playlist.']);
    (project.playlists || []).forEach((item, index) => {
      if (!item.platformId) errors.push(['Playlists', `Playlist ${index + 1} : choisis la plateforme.`]);
      if (!item.title?.trim()) errors.push(['Playlists', `Playlist ${index + 1} : ajoute le titre.`]);
      if (!item.coverUrl) errors.push(['Playlists', `Playlist ${index + 1} : ajoute la cover.`]);
    });
  }
  if (project?.type === 'new_release') {
    if (!project.background?.url) errors.push(['Visuel', 'Importe l’image principale.']);
  }
  if (project?.type === 'youtube_spectrum') {
    if (!project.background?.url && !project.background?.videoUrl && !project.track?.coverUrl) errors.push(['Fond', 'Ajoute une image, une vidéo ou une cover.']);
  }
  return errors;
}

async function loadAppData() {
  const [config, projects] = await Promise.all([api('/api/config'), api('/api/projects')]);
  state.config = config;
  state.projects = projects.projects || [];
}

async function init() {
  bindGlobalEvents();
  previewAudio.addEventListener('timeupdate', onAudioTimeUpdate);
  previewAudio.addEventListener('play', () => {
    state.audioStatus = 'playing';
    state.previewPlaying = true;
    updateAudioButtons();
    syncSpectrumVisualizer(true);
  });
  previewAudio.addEventListener('pause', () => {
    state.audioStatus = 'paused';
    state.previewPlaying = false;
    pauseSpectrumVisualizer();
    updateAudioButtons();
  });
  previewAudio.addEventListener('ended', () => {
    state.audioStatus = 'idle';
    state.previewPlaying = false;
    pauseSpectrumVisualizer();
    updateAudioButtons();
  });
  try {
    const me = await api('/api/me');
    if (me.authenticated) {
      state.user = me.user;
      await loadAppData();
      await routeFromHash(true);
    } else {
      render();
    }
  } catch (error) {
    app.innerHTML = `<div class="fatal-state"><h1>Impossible de démarrer Spectoom</h1><p>${escapeHtml(error.message)}</p><button class="button button-dark" data-action="reload">Réessayer</button></div>`;
  }
}

function bindGlobalEvents() {
  window.addEventListener('hashchange', () => routeFromHash(false));
  document.addEventListener('click', onClick);
  document.addEventListener('input', onInput);
  document.addEventListener('change', onChange);
  document.addEventListener('dragover', (event) => { const zone = event.target.closest('#conversion-dropzone'); if (!zone) return; event.preventDefault(); zone.classList.add('is-dragging'); });
  document.addEventListener('dragleave', (event) => { const zone = event.target.closest('#conversion-dropzone'); if (!zone) return; zone.classList.remove('is-dragging'); });
  document.addEventListener('drop', (event) => { const zone = event.target.closest('#conversion-dropzone'); if (!zone) return; event.preventDefault(); zone.classList.remove('is-dragging'); addConversionFiles(event.dataTransfer?.files); });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && state.modal) {
      state.modal = null;
      state.modalLockedType = null;
      state.modalType = null;
      state.modalProjectName = '';
      state.modalError = '';
      state.creatingProject = false;
      renderPreservingFocus();
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's' && state.currentProject) {
      event.preventDefault();
      saveProject(true);
    }
  });
}

async function routeFromHash(initial = false) {
  if (!state.user) return;
  const hash = location.hash.replace(/^#\/?/, '') || 'dashboard';
  const parts = hash.split('/').filter(Boolean);
  if (parts[0] === 'editor' && parts[1]) {
    const projectId = parts[1];
    const step = parts[2];
    if (!state.currentProject || state.currentProject.id !== projectId) {
      await openProject(projectId, step, { updateHash: false });
      return;
    }
    const steps = STEPS[state.currentProject.type] || STEPS.playlist_entry;
    state.editorStep = steps.some((item) => item.id === step) ? step : steps[0].id;
    state.view = 'editor';
  } else {
    stopSpectrumLoop();
    state.currentProject = null;
    state.preview = null;
    state.view = ['dashboard', 'projects', 'renders', 'library', 'branding', 'conversion', 'settings', 'admin'].includes(parts[0]) ? parts[0] : 'dashboard';
    if (parts[0] === 'projects' && parts[1]) state.projectFilter = parts[1];
    if (state.view === 'renders') await loadAllRenders();
    if (state.view === 'conversion') await loadConversions();
    if (state.view === 'settings') await loadHealth();
  }
  render();
  if (initial && !location.hash) history.replaceState(null, '', '#/dashboard');
}

function go(route) {
  const normalized = route.startsWith('#') ? route : `#/${route.replace(/^\//, '')}`;
  if (location.hash === normalized) routeFromHash(false);
  else location.hash = normalized;
}

async function openProject(projectId, step = null, options = {}) {
  try {
    const response = await api(`/api/projects/${projectId}`);
    state.currentProject = response.project;
    state.currentProject.type ||= 'playlist_entry';
    state.selectedPlaylist = 0;
    const steps = STEPS[state.currentProject.type] || STEPS.playlist_entry;
    state.editorStep = steps.some((item) => item.id === step) ? step : steps[0].id;
    state.view = 'editor';
    state.preview = null;
    await Promise.all([loadProjectRenders(projectId), loadPreview(projectId)]);
    syncAudioSource();
    render();
    if (options.updateHash !== false) history.pushState(null, '', `#/editor/${projectId}/${state.editorStep}`);
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function loadPreview(projectId = state.currentProject?.id) {
  if (!projectId) return;
  const expected = projectId;
  try {
    const response = await api(`/api/projects/${projectId}/preview`);
    if (state.currentProject?.id === expected) {
      state.preview = response.preview;
      refreshPreviewArea();
    }
  } catch (error) {
    console.warn('Preview failed', error);
  }
}

async function loadProjectRenders(projectId) {
  try {
    const response = await api(`/api/projects/${projectId}/renders`);
    state.renders = response.renders || [];
  } catch {
    state.renders = [];
  }
}

async function loadAllRenders() {
  const all = [];
  await Promise.all(state.projects.map(async (project) => {
    try {
      const response = await api(`/api/projects/${project.id}/renders`);
      response.renders?.forEach((render) => all.push({ ...render, project }));
    } catch { /* ignore one inaccessible project */ }
  }));
  all.sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)));
  state.renders = all;
}

async function loadConversions() {
  try {
    const response = await api('/api/conversions');
    state.conversions = response.conversions || [];
    const active = state.conversions.find((item) => !['Terminé', 'Échec'].includes(item.status));
    if (active && state.conversionJob?.id !== active.id) {
      state.conversionJob = active;
      pollConversion(active.id);
    }
  } catch {
    state.conversions = [];
  }
}

async function loadHealth() {
  try { state.health = await api('/api/health'); } catch { state.health = null; }
}

function render() {
  if (!state.user) {
    app.innerHTML = renderLogin();
    return;
  }
  if (state.view === 'editor' && state.currentProject) {
    app.innerHTML = renderEditor();
    hydrateEditor();
    return;
  }
  app.innerHTML = renderAppShell(renderCurrentPage());
}

function renderPreservingFocus() {
  const active = document.activeElement;
  const bind = active?.dataset?.bind;
  const actionKey = active?.dataset?.focusKey;
  const selectionStart = typeof active?.selectionStart === 'number' ? active.selectionStart : null;
  const selectionEnd = typeof active?.selectionEnd === 'number' ? active.selectionEnd : null;
  render();
  const selector = bind ? `[data-bind="${CSS.escape(bind)}"]` : actionKey ? `[data-focus-key="${CSS.escape(actionKey)}"]` : null;
  if (selector) {
    const next = document.querySelector(selector);
    if (next) {
      next.focus({ preventScroll: true });
      if (selectionStart != null && next.setSelectionRange) next.setSelectionRange(selectionStart, selectionEnd);
    }
  }
}

function renderLogin() {
  return `
    <main class="login-layout">
      <section class="login-showcase">
        <div class="login-logo-row">
          <img src="/static/brand/spectoom-black.png?v=${APP_VERSION}" alt="Spectoom" class="login-logo">
          <span class="internal-badge">OUTIL INTERNE</span>
        </div>
        <div class="login-copy">
          <span class="eyebrow">STUDIO VIDÉO MUSICAL</span>
          <h1>Une seule app.<br>Trois façons de raconter la musique.</h1>
          <p>Crée des vidéos d’entrées en playlist, de nouvelles sorties et des spectrums YouTube sans logiciel de montage.</p>
        </div>
        <div class="login-module-strip">
          ${Object.values(MODULES).map((module, index) => `
            <article class="login-module-card module-${module.accent}">
              <span class="login-module-index">0${index + 1}</span>
              <strong>${escapeHtml(module.label)}</strong>
              <small>${escapeHtml(module.output)}</small>
            </article>`).join('')}
        </div>
      </section>
      <section class="login-panel">
        <form class="login-card" data-form="login">
          <div class="login-card-icon">${icon('play', 24)}</div>
          <span class="eyebrow">BIENVENUE</span>
          <h2>Connecte-toi à Spectoom</h2>
          <p>La connexion sert uniquement à conserver tes projets et tes rendus.</p>
          <label class="field">
            <span>Adresse e-mail</span>
            <input class="input" name="email" type="email" autocomplete="email" placeholder="prenom@entreprise.com" required>
          </label>
          <label class="field">
            <span>Mot de passe</span>
            <input class="input" name="password" type="password" autocomplete="current-password" required>
          </label>
          <button class="button button-dark button-large" type="submit">Se connecter ${icon('arrow', 18)}</button>
          <div class="login-demo-note"><strong>Accès interne</strong><span>Utilise les identifiants fournis par l’administrateur Spectoom.</span></div>
        </form>
      </section>
    </main>`;
}

function renderAppShell(content) {
  return `
    <div class="app-shell">
      ${renderSidebar()}
      <main class="main-shell">
        ${renderTopbar()}
        <div class="page-content">${content}</div>
      </main>
      ${renderModal()}
      ${renderPersistentJobs()}
    </div>`;
}

function renderSidebar(compact = false) {
  const current = state.view;
  const navItem = (view, label, iconName, route = view) => `
    <button class="side-link ${current === view ? 'is-active' : ''}" data-action="navigate" data-route="${route}">
      ${icon(iconName, 20)}<span>${escapeHtml(label)}</span>
    </button>`;
  return `
    <aside class="sidebar ${compact ? 'sidebar-compact' : ''}">
      <div class="sidebar-brand">
        <img src="/static/brand/spectoom-black.png?v=${APP_VERSION}" alt="Spectoom">
        ${compact ? `<button class="icon-button" data-action="navigate" data-route="dashboard" aria-label="Retour à l’accueil">${icon('back', 18)}</button>` : ''}
      </div>
      <nav class="sidebar-nav">
        ${navItem('dashboard', 'Accueil', 'home')}
        <button class="side-link side-link-new" data-action="open-create">${icon('plus', 20)}<span>Nouveau projet</span></button>
        <div class="side-section">
          <button class="side-link ${state.projectFilter === 'playlist_entry' && current === 'projects' ? 'is-active' : ''}" data-action="navigate" data-route="projects/playlist_entry">${icon('playlist', 20)}<span>Entrées en playlist</span></button>
          <button class="side-link ${state.projectFilter === 'new_release' && current === 'projects' ? 'is-active' : ''}" data-action="navigate" data-route="projects/new_release">${icon('sparkle', 20)}<span>Nouvelles sorties</span></button>
          <button class="side-link ${state.projectFilter === 'youtube_spectrum' && current === 'projects' ? 'is-active' : ''}" data-action="navigate" data-route="projects/youtube_spectrum">${icon('spectrum', 20)}<span>Spectrum YouTube</span></button>
        </div>
        <div class="side-divider"></div>
        ${navItem('projects', 'Mes projets', 'project')}
        ${navItem('library', 'Bibliothèque', 'library')}
        ${navItem('renders', 'Rendus', 'render')}
        ${navItem('branding', 'Branding', 'brand')}
        ${navItem('conversion', 'Conversion', 'convert')}
        ${navItem('settings', 'Paramètres', 'settings')}
        ${state.user?.role === 'admin' ? navItem('admin', 'Administration', 'settings') : ''}
      </nav>
      <div class="sidebar-user">
        <div class="avatar">${escapeHtml(initials(state.user?.name))}</div>
        <div class="sidebar-user-copy"><strong>${escapeHtml(state.user?.name || 'Utilisateur')}</strong><span>${escapeHtml(state.user?.email || '')}</span></div>
        <button class="icon-button" data-action="logout" aria-label="Se déconnecter">${icon('logout', 18)}</button>
      </div>
    </aside>`;
}

function renderTopbar() {
  return `
    <header class="topbar">
      <div class="topbar-search">${icon('search', 19)}<input type="search" value="${escapeHtml(state.search)}" placeholder="Rechercher un projet, un rendu…" data-action="search"></div>
      <div class="topbar-actions">
        <span class="version-pill">Spectoom ${APP_VERSION}</span>
        <button class="avatar avatar-button" data-action="navigate" data-route="settings">${escapeHtml(initials(state.user?.name))}</button>
      </div>
    </header>`;
}

function renderCurrentPage() {
  if (state.view === 'projects') return renderProjectsPage();
  if (state.view === 'renders') return renderRendersPage();
  if (state.view === 'library') return renderLibraryPage();
  if (state.view === 'branding') return renderBrandingPage();
  if (state.view === 'conversion') return renderConversionPage();
  if (state.view === 'settings') return renderSettingsPage();
  if (state.view === 'admin') return renderAdminPage();
  return renderDashboard();
}

function renderDashboard() {
  const firstName = String(state.user?.name || 'toi').split(' ')[0];
  const recent = filterProjects(state.projects).slice(0, 4);
  return `
    <section class="dashboard-hero">
      <div><span class="eyebrow">TON STUDIO</span><h1>Bonjour ${escapeHtml(firstName)} <span class="wave">👋</span></h1><p>Quelle vidéo veux-tu créer aujourd’hui ?</p></div>
      <button class="button button-dark button-create" data-action="open-create"><span class="button-plus">${icon('plus', 20)}</span>Créer une vidéo${icon('arrow', 18)}</button>
    </section>
    <section class="module-grid">
      ${renderModuleCard('playlist_entry')}
      ${renderModuleCard('new_release')}
      ${renderModuleCard('youtube_spectrum')}
    </section>
    <section class="section-block">
      <div class="section-heading"><div><span class="eyebrow">DERNIÈRE ACTIVITÉ</span><h2>Projets récents</h2></div><button class="text-button" data-action="navigate" data-route="projects">Voir tous les projets ${icon('arrow', 17)}</button></div>
      ${recent.length ? `<div class="project-grid">${recent.map(renderProjectCard).join('')}</div>` : renderEmptyProjects()}
    </section>
    <section class="section-block quick-section">
      <div class="section-heading"><div><span class="eyebrow">RACCOURCIS</span><h2>Ressources rapides</h2></div></div>
      <div class="quick-grid">
        ${renderQuickCard('library', 'Bibliothèque médias', 'Images, audio, logos et fonds', 'library', 'mint')}
        ${renderQuickCard('branding', 'Gérer le branding', 'Spectoom, Virgin Music et DSP', 'brand', 'lavender')}
        ${renderQuickCard('renders', 'Voir mes rendus', 'Historique et téléchargements', 'render', 'peach')}
        ${renderQuickCard('conversion', 'Convertir des médias', 'TIFF, WAV et archives ZIP', 'convert', 'blue')}
        ${renderQuickCard('settings', 'État du studio', 'Moteur vidéo et compte', 'settings', 'lavender')}
      </div>
    </section>`;
}

function renderModuleCard(type) {
  const module = MODULES[type];
  const artwork = type === 'playlist_entry'
    ? `<div class="module-art playlist-art"><img src="/demo/playlist-2.jpg"><img src="/demo/playlist-1.jpg"><img src="/demo/playlist-4.jpg"><span class="floating-dsp"><img src="/static/platforms/spotify-black.png"></span></div>`
    : type === 'new_release'
      ? `<div class="module-art release-art"><span class="new-label">new</span><img src="/demo/new-release-background.jpg"><span class="virgin-mini"><img src="/static/brand/virgin-music-red.png"></span></div>`
      : `<div class="module-art spectrum-art"><img src="/demo/spectrum-cover.jpg"><div class="mini-bars">${Array.from({ length: 18 }, (_, index) => `<i style="height:${20 + ((index * 23) % 54)}%"></i>`).join('')}</div><span class="youtube-dot">▶</span></div>`;
  return `
    <article class="module-card module-${module.accent}">
      <div class="module-card-copy">
        <span class="module-icon">${icon(type === 'playlist_entry' ? 'playlist' : type === 'new_release' ? 'sparkle' : 'spectrum', 25)}</span>
        <h2>${escapeHtml(module.label)}</h2>
        <p>${escapeHtml(module.description)}</p>
        <button class="button button-dark button-small" data-action="create-type" data-type="${type}">Commencer ${icon('arrow', 17)}</button>
      </div>
      ${artwork}
    </article>`;
}

function renderQuickCard(route, title, text, iconName, accent) {
  return `<button class="quick-card quick-${accent}" data-action="navigate" data-route="${route}"><span class="quick-icon">${icon(iconName, 21)}</span><span><strong>${escapeHtml(title)}</strong><small>${escapeHtml(text)}</small></span>${icon('chevronRight', 17)}</button>`;
}

function filterProjects(projects) {
  const query = state.search.trim().toLowerCase();
  return projects.filter((project) => {
    const matchesType = state.projectFilter === 'all' || project.type === state.projectFilter;
    const haystack = `${project.name || ''} ${project.track?.title || ''} ${project.track?.artist || ''}`.toLowerCase();
    return matchesType && (!query || haystack.includes(query));
  });
}

function renderProjectsPage() {
  const projects = filterProjects(state.projects);
  const title = state.projectFilter === 'all' ? 'Tous les projets' : MODULES[state.projectFilter]?.label || 'Mes projets';
  return `
    <section class="page-heading">
      <div><span class="eyebrow">BIBLIOTHÈQUE DE TRAVAIL</span><h1>${escapeHtml(title)}</h1><p>${projects.length} projet${projects.length > 1 ? 's' : ''} enregistré${projects.length > 1 ? 's' : ''}.</p></div>
      <button class="button button-dark" data-action="${state.projectFilter === 'all' ? 'open-create' : 'open-create-context'}" ${state.projectFilter === 'all' ? '' : `data-type="${escapeHtml(state.projectFilter)}"`}>${icon('plus', 18)} Nouveau projet</button>
    </section>
    <div class="filter-row">
      ${[['all', 'Tous'], ['playlist_entry', 'Playlists'], ['new_release', 'Nouvelles sorties'], ['youtube_spectrum', 'Spectrums']].map(([id, label]) => `<button class="filter-chip ${state.projectFilter === id ? 'is-active' : ''}" data-action="filter-projects" data-filter="${id}">${escapeHtml(label)}</button>`).join('')}
    </div>
    ${projects.length ? `<div class="project-grid project-grid-large">${projects.map(renderProjectCard).join('')}</div>` : renderEmptyProjects()}`;
}

function renderProjectCard(project) {
  const module = moduleFor(project);
  const image = safeUrl(thumbnailUrl(project));
  return `
    <article class="project-card" data-project-id="${escapeHtml(project.id)}">
      <button class="project-thumb" data-action="open-project" data-id="${escapeHtml(project.id)}" style="background-image:linear-gradient(180deg,transparent 20%,rgba(7,7,10,.54)),url('${image}')">
        <span class="project-type-badge badge-${module.accent}">${escapeHtml(module.label)}</span>
        <span class="project-thumb-title">${escapeHtml(project.track?.title || project.name || 'Sans titre')}</span>
        ${project.type === 'youtube_spectrum' ? `<span class="thumb-spectrum">${Array.from({ length: 13 }, (_, i) => `<i style="height:${15 + (i * 19) % 60}%"></i>`).join('')}</span>` : ''}
      </button>
      <div class="project-card-body">
        <div class="project-card-title"><div><strong>${escapeHtml(project.name || 'Sans titre')}</strong><span>${escapeHtml(projectMeta(project))}</span></div><button class="icon-button" data-action="open-project" data-id="${escapeHtml(project.id)}">${icon('edit', 17)}</button></div>
        <div class="project-card-footer"><span class="status-pill ${statusClass(project.status)}">${escapeHtml(project.status || 'Brouillon')}</span><span>${formatDate(project.updatedAt)}</span></div>
        <div class="project-card-actions"><button data-action="duplicate-project" data-id="${escapeHtml(project.id)}">${icon('duplicate', 16)} Dupliquer</button><button class="danger-link" data-action="delete-project" data-id="${escapeHtml(project.id)}">${icon('trash', 16)} Supprimer</button></div>
      </div>
    </article>`;
}

function renderEmptyProjects() {
  const lockedType = state.view === 'projects' && state.projectFilter !== 'all' ? state.projectFilter : '';
  return `<div class="empty-state"><span class="empty-icon">${icon('project', 28)}</span><h3>Aucun projet ici</h3><p>Crée une vidéo pour commencer à remplir ton studio.</p><button class="button button-dark" data-action="${lockedType ? 'open-create-context' : 'open-create'}" ${lockedType ? `data-type="${escapeHtml(lockedType)}"` : ''}>${icon('plus', 18)} Créer une vidéo</button></div>`;
}

function renderRendersPage() {
  return `
    <section class="page-heading"><div><span class="eyebrow">EXPORTS</span><h1>Mes rendus</h1><p>Retrouve tous les MP4 générés par Spectoom.</p></div></section>
    ${state.renders.length ? `<div class="render-list">${state.renders.map(renderHistoryRow).join('')}</div>` : `<div class="empty-state"><span class="empty-icon">${icon('render', 28)}</span><h3>Aucun rendu pour le moment</h3><p>Les vidéos terminées apparaîtront ici.</p></div>`}`;
}

function renderHistoryRow(render) {
  const project = render.project || state.projects.find((item) => item.id === render.projectId) || {};
  const module = moduleFor(project.type || render.projectType);
  return `<article class="render-row"><div class="render-row-icon badge-${module.accent}">${icon(project.type === 'youtube_spectrum' ? 'spectrum' : project.type === 'new_release' ? 'sparkle' : 'playlist', 22)}</div><div class="render-row-copy"><strong>${escapeHtml(project.name || render.filename || 'Rendu')}</strong><span>${escapeHtml(module.label)} · ${formatDateTime(render.createdAt)}</span></div><div class="render-progress-mini"><span class="status-pill ${statusClass(render.status)}">${escapeHtml(render.status)}</span>${render.status !== 'Terminé' ? `<div><i style="width:${clamp(render.progress, 0, 100)}%"></i></div>` : ''}</div><div class="render-row-actions">${render.outputUrl ? `<a class="button button-light button-small" href="${safeUrl(render.outputUrl)}?download=1" download>${icon('download', 17)} Télécharger</a>` : ''}<button class="icon-button" data-action="open-project" data-id="${escapeHtml(render.projectId)}">${icon('edit', 17)}</button></div></article>`;
}

function renderLibraryPage() {
  const assets = [];
  state.projects.forEach((project) => {
    const push = (url, label, kind) => { if (url && !assets.some((item) => item.url === url)) assets.push({ url, label, kind }); };
    push(project.background?.url, `${project.name} · fond`, 'image');
    push(project.track?.coverUrl, `${project.track?.title || project.name} · cover`, 'image');
    push(project.audio?.url, `${project.track?.title || project.name} · audio`, 'audio');
    (project.playlists || []).forEach((playlist) => push(playlist.coverUrl, `${playlist.title} · playlist`, 'image'));
  });
  return `<section class="page-heading"><div><span class="eyebrow">MÉDIAS RÉCENTS</span><h1>Bibliothèque</h1><p>Ressources déjà utilisées dans tes projets.</p></div></section>${assets.length ? `<div class="asset-grid">${assets.map((asset) => asset.kind === 'audio' ? `<article class="asset-card asset-audio"><span>${icon('music', 24)}</span><strong>${escapeHtml(asset.label)}</strong><audio controls src="${safeUrl(asset.url)}"></audio></article>` : `<article class="asset-card"><img src="${safeUrl(asset.url)}" alt=""><strong>${escapeHtml(asset.label)}</strong></article>`).join('')}</div>` : renderEmptyProjects()}`;
}

function fontCssFamily(font) {
  if (!font) return 'Arial, Helvetica, sans-serif';
  if (font.url && /^[A-Za-z0-9_-]+$/.test(font.cssFamily || '')) return `'${font.cssFamily}'`;
  return font.cssFamily || 'Arial, Helvetica, sans-serif';
}

function fontFaceRule(font) {
  if (!font?.url || !/^[A-Za-z0-9_-]+$/.test(font.cssFamily || '')) return '';
  const format = String(font.url).toLowerCase().endsWith('.otf') ? 'opentype' : 'truetype';
  return `@font-face{font-family:'${font.cssFamily}';src:url('${safeUrl(font.url)}') format('${format}');font-style:normal;font-weight:100 900;font-display:swap;}`;
}

function selectedProjectFont(project) {
  const id = project?.typography?.fontId || 'spectoom-sans';
  return (state.config.fonts || []).find((font) => font.id === id) || (state.config.fonts || [])[0] || { id: 'spectoom-sans', name: 'Spectoom Sans', cssFamily: 'Arial, Helvetica, sans-serif', url: '' };
}

function renderProjectFontPicker(project) {
  const fonts = state.config.fonts || [];
  const selected = selectedProjectFont(project);
  return `<div class="project-font-picker">
    <label class="field"><span>Police du visuel</span><select class="select" data-action="project-font-select">${fonts.map((font) => `<option value="${escapeHtml(font.id)}" ${selected.id === font.id ? 'selected' : ''}>${escapeHtml(font.name)}${font.builtIn ? '' : ' · ajoutée'}</option>`).join('')}</select><small>La même police est utilisée dans l’aperçu et le MP4.</small></label>
    <label class="button button-light button-full">${icon('plus', 16)} Ajouter une police<input type="file" hidden accept=".ttf,.otf,font/ttf,font/otf" data-upload-kind="font" data-upload-path="typography.fontUrl"></label>
  </div>`;
}

function renderBrandingPage() {
  const fonts = state.config.fonts || [];
  const faceRules = fonts.map(fontFaceRule).filter(Boolean).join('');
  return `
    ${faceRules ? `<style>${faceRules}</style>` : ''}
    <section class="page-heading"><div><span class="eyebrow">IDENTITÉS VISUELLES</span><h1>Branding</h1><p>Les éléments officiels et les polices disponibles dans les générateurs.</p></div></section>
    <div class="brand-grid">
      <article class="brand-card"><div class="brand-preview light"><img src="/static/brand/spectoom-black.png"></div><div><span class="eyebrow">APPLICATION</span><h3>Spectoom</h3><p>Logo noir pour les interfaces claires, blanc pour les fonds sombres.</p></div></article>
      <article class="brand-card"><div class="brand-preview virgin"><img src="/static/brand/virgin-music-red.png"></div><div><span class="eyebrow">NOUVELLES SORTIES</span><h3>Virgin Music Afrique</h3><p>Variantes rouge, blanche et noire intégrées au module Nouvelle sortie.</p></div></article>
      <article class="brand-card brand-card-wide"><div><span class="eyebrow">PLATEFORMES</span><h3>Catalogue DSP</h3><p>Chaque logo possède une variante noire et blanche, avec contraste automatique dans les vidéos.</p></div><div class="dsp-showcase">${state.config.platforms.map((platform) => `<span><img src="${safeUrl(platform.iconBlackUrl || DSP_FALLBACKS[platform.id]?.[0])}" alt="${escapeHtml(platform.name)}"><small>${escapeHtml(platform.name)}</small></span>`).join('')}</div></article>
      <article class="brand-card brand-card-wide font-library-card">
        <div class="font-library-heading"><div><span class="eyebrow">TYPOGRAPHIE</span><h3>Bibliothèque de polices</h3><p>Ajoute des fichiers TTF ou OTF, puis sélectionne-les séparément dans chaque projet.</p></div><label class="button button-dark">${icon('plus', 17)} Ajouter des polices<input type="file" hidden multiple accept=".ttf,.otf,font/ttf,font/otf" data-action="font-library-files"></label></div>
        <div class="font-library-grid">${fonts.map((font) => `<div class="font-library-item"><span class="font-sample" style="font-family:${escapeHtml(fontCssFamily(font))}">Aa</span><div><strong>${escapeHtml(font.name)}</strong><small>${font.builtIn ? 'Police intégrée' : escapeHtml(font.originalName || 'Police personnalisée')}</small></div><span class="font-origin ${font.builtIn ? '' : 'custom'}">${font.builtIn ? 'Système' : 'Ajoutée'}</span></div>`).join('')}</div>
      </article>
    </div>`;
}

function formatFileSize(bytes) {
  const size = Math.max(0, Number(bytes) || 0);
  if (size < 1024) return `${size} o`;
  if (size < 1024 ** 2) return `${(size / 1024).toFixed(1)} Ko`;
  return `${(size / 1024 ** 2).toFixed(size > 100 * 1024 ** 2 ? 0 : 1)} Mo`;
}

function conversionTypeForName(name, mime = '') {
  const lower = String(name || '').toLowerCase();
  const type = String(mime || '').toLowerCase();
  if (type.startsWith('image/') || /\.(jpe?g|png|webp|tiff?)$/.test(lower)) {
    return { id: 'cover_tiff', label: 'Cover → TIFF', hint: '3000 × 3000 · 300 DPI · RVB · LZW' };
  }
  if (type.startsWith('video/') || /\.(mp4|mov|m4v|webm|mkv|avi|mpeg|mpg|mts|m2ts|3gp|ogv|vob|wmv|flv)$/.test(lower)) {
    return { id: 'video_wav', label: 'Vidéo → WAV', hint: 'Extraction audio · 44,1 kHz · 16 bits · stéréo' };
  }
  if (type.startsWith('audio/') || /\.(aa|aac|aax|ac3|adx|aif|aiff|alac|amr|ape|ast|at3|au|caf|dff|dsf|dts|eac3|flac|gsm|hca|m4a|m4b|mka|mp2|mp3|mpc|oga|ogg|oma|opus|ra|ram|snd|spx|tak|tta|voc|wav|wave|wma|wv|xa|xma)$/.test(lower)) {
    return { id: 'audio_wav', label: 'Audio → WAV', hint: '44,1 kHz · 16 bits · stéréo' };
  }
  return { id: 'auto_media', label: 'Détection automatique', hint: 'Spectoom vérifiera le média avec FFmpeg' };
}

function renderConversionPage() {
  const files = state.conversionFiles || [];
  const job = state.conversionJob;
  const active = job && !['Terminé', 'Échec'].includes(job.status);
  const isSingle = files.length === 1;
  const jobIsZip = job?.packageType === 'zip' || Number(job?.fileCount || 0) > 1 || String(job?.filename || '').toLowerCase().endsWith('.zip');
  const jobDownloadLabel = jobIsZip ? 'Télécharger le ZIP' : 'Télécharger le fichier';
  return `<section class="page-heading"><div><span class="eyebrow">OUTILS MÉDIA</span><h1>Conversion</h1><p>Prépare les covers, tous les formats audio et les pistes extraites des vidéos.</p></div></section>
    <div class="conversion-spec-grid">
      <article class="conversion-spec spec-mint"><span>${icon('image', 22)}</span><div><strong>Cover vers TIFF</strong><p>3000 × 3000 px, 300 DPI, RVB 8 bits, 3 canaux, sans alpha, LZW et sans balise ICC 34675.</p></div></article>
      <article class="conversion-spec spec-lavender"><span>${icon('music', 22)}</span><div><strong>Tout audio vers WAV</strong><p>Tout fichier audio reconnu par FFmpeg est converti en PCM WAV, 44,1 kHz, 16 bits et stéréo.</p></div></article>
      <article class="conversion-spec spec-peach"><span>${icon('video', 22)}</span><div><strong>Vidéo vers WAV</strong><p>Extraction de la première piste audio en 44,1 kHz, 16 bits et stéréo.</p></div></article>
    </div>
    <section class="conversion-workspace">
      <label class="conversion-dropzone" id="conversion-dropzone"><input type="file" hidden multiple data-action="conversion-files"><span class="conversion-drop-icon">${icon('upload', 26)}</span><strong>Dépose un ou plusieurs fichiers ici</strong><p>covers, fichiers audio de tout format ou vidéos · maximum 30 fichiers</p><i>Un seul fichier est téléchargé directement. Un lot de plusieurs fichiers produit un ZIP.</i></label>
      <div class="conversion-queue-panel">
        <div class="conversion-panel-heading"><div><span class="eyebrow">SÉLECTION ACTUELLE</span><h2>${files.length} fichier${files.length > 1 ? 's' : ''}</h2></div>${files.length ? `<button class="text-button" data-action="clear-conversion-files">Tout retirer</button>` : ''}</div>
        ${files.length ? `<div class="conversion-file-list">${files.map((file, index) => { const type = conversionTypeForName(file.name, file.type); return `<div class="conversion-file"><span class="conversion-file-icon">${icon(type?.id === 'cover_tiff' ? 'image' : type?.id === 'video_wav' ? 'video' : type?.id === 'audio_wav' ? 'music' : 'convert', 17)}</span><div><strong>${escapeHtml(file.name)}</strong><small>${escapeHtml(type?.label || 'Détection automatique')} · ${formatFileSize(file.size)}</small></div><button class="icon-button" data-action="remove-conversion-file" data-index="${index}" aria-label="Retirer">${icon('close', 15)}</button></div>`; }).join('')}</div>` : `<div class="mini-empty tall">Ajoute un fichier pour un téléchargement direct, ou plusieurs fichiers pour créer un pack ZIP.</div>`}
        <button class="button button-dark button-large button-full" data-action="start-conversion" ${!files.length || state.conversionUploading || active ? 'disabled' : ''}>${state.conversionUploading ? 'Téléversement…' : `${icon('convert', 18)} ${isSingle ? 'Convertir le fichier' : files.length > 1 ? 'Convertir et créer le ZIP' : 'Convertir'}`}</button>
      </div>
    </section>
    ${job ? `<section class="conversion-current ${job.status === 'Terminé' ? 'is-done' : job.status === 'Échec' ? 'is-error' : ''}"><div class="conversion-current-head"><div><span class="eyebrow">DERNIÈRE CONVERSION</span><h2 id="conversion-job-message">${escapeHtml(job.message || job.status)}</h2></div><strong id="conversion-job-percent">${Math.round(job.progress || 0)} %</strong></div><div class="conversion-progress"><i id="conversion-job-progress" style="width:${clamp(job.progress, 0, 100)}%"></i></div><div class="conversion-current-foot"><span>${escapeHtml(job.status)}${job.fileCount ? ` · ${job.currentFile || 0}/${job.fileCount} fichier(s)` : ''}</span>${job.outputUrl ? `<a class="button button-dark button-small" href="${safeUrl(job.outputUrl)}?download=1" download>${icon('download', 16)} ${jobDownloadLabel}</a>` : ''}</div>${job.error ? `<p class="conversion-error">${escapeHtml(job.error)}</p>` : ''}</section>` : ''}
    <section class="section-block"><div class="section-heading"><div><span class="eyebrow">HISTORIQUE</span><h2>Conversions récentes</h2></div></div>${state.conversions.length ? `<div class="conversion-history">${state.conversions.map((item) => { const zip = item.packageType === 'zip' || Number(item.fileCount || 0) > 1 || String(item.filename || '').toLowerCase().endsWith('.zip'); return `<article><span class="conversion-history-icon">${icon(item.status === 'Terminé' ? 'check' : item.status === 'Échec' ? 'warning' : 'convert', 18)}</span><div><strong>${escapeHtml(item.filename || `${item.fileCount || 0} fichier(s)`)}</strong><small>${formatDateTime(item.createdAt)} · ${escapeHtml(item.status)}</small></div><span>${zip ? `${item.fileCount || 0} fichiers · ZIP` : 'Fichier unique'}</span>${item.outputUrl ? `<a class="button button-light button-small" href="${safeUrl(item.outputUrl)}?download=1" download>${icon('download', 15)} ${zip ? 'ZIP' : 'Fichier'}</a>` : ''}</article>`; }).join('')}</div>` : `<div class="mini-empty tall">Aucune conversion enregistrée.</div>`}</section>`;
}

function renderSettingsPage() {
  const health = state.health;
  return `
    <section class="page-heading"><div><span class="eyebrow">CONFIGURATION</span><h1>Paramètres</h1><p>Compte et état de l’installation locale.</p></div></section>
    <div class="settings-grid">
      <article class="settings-card"><span class="settings-icon">${icon('project', 23)}</span><h3>Compte</h3><dl><div><dt>Nom</dt><dd>${escapeHtml(state.user?.name)}</dd></div><div><dt>E-mail</dt><dd>${escapeHtml(state.user?.email)}</dd></div><div><dt>Rôle</dt><dd>${escapeHtml(state.user?.role)}</dd></div></dl><button class="button button-light" data-action="logout">${icon('logout', 17)} Se déconnecter</button></article>
      <article class="settings-card"><span class="settings-icon">${icon('video', 23)}</span><h3>Moteur média</h3>${health ? `<dl><div><dt>Version</dt><dd>${escapeHtml(health.version)}</dd></div><div><dt>FFmpeg</dt><dd><span class="health-dot ${health.ffmpeg ? 'ok' : 'bad'}"></span>${health.ffmpeg ? 'Disponible' : 'Indisponible'}</dd></div><div><dt>FFprobe</dt><dd><span class="health-dot ${health.ffprobe ? 'ok' : 'warn'}"></span>${health.ffprobe ? 'Disponible' : 'Optionnel'}</dd></div><div><dt>Analyse audio</dt><dd><span class="health-dot ${health.mutagen ? 'ok' : 'warn'}"></span>${health.mutagen ? 'Mutagen actif' : 'FFmpeg uniquement'}</dd></div></dl>` : `<p>État indisponible.</p>`}<button class="button button-light" data-action="refresh-health">${icon('refresh', 17)} Actualiser</button></article>
      <article class="settings-card settings-card-wide"><span class="settings-icon">${icon('check', 23)}</span><h3>Fonctionnement interne</h3><p>Spectoom est gratuit. La connexion sert à séparer les projets et conserver l’historique des rendus. Aucun plan premium, paiement ou filigrane commercial n’est appliqué.</p></article>
    </div>`;
}

function renderAdminPage() {
  return `<section class="page-heading"><div><span class="eyebrow">ADMINISTRATION</span><h1>Supervision</h1><p>La gestion avancée reste disponible via les données locales de l’application.</p></div></section><div class="settings-card"><h3>Accès administrateur</h3><p>Cette version unifie les trois générateurs. La supervision détaillée des rendus peut être ajoutée lors de la prochaine itération.</p></div>`;
}

function renderPersistentJobs() {
  const cards = [];
  const renderJob = state.renderJob;
  if (renderJob && state.modal !== 'render' && state.modal !== 'render-done') {
    const done = renderJob.status === 'Terminé';
    const failed = renderJob.status === 'Échec';
    cards.push(`<aside class="persistent-job ${done ? 'is-done' : failed ? 'is-error' : ''}" id="persistent-render-job">
      <div class="persistent-job-icon">${icon(done ? 'check' : failed ? 'warning' : 'render', 19)}</div>
      <div class="persistent-job-copy"><span>${done ? 'MP4 prêt' : failed ? 'Rendu échoué' : 'Export en cours'}</span><strong id="persistent-render-message">${escapeHtml(renderJob.message || renderJob.status || 'Traitement')}</strong><div class="persistent-progress"><i id="persistent-render-progress" style="width:${clamp(renderJob.progress, 0, 100)}%"></i></div></div>
      <strong class="persistent-percent" id="persistent-render-percent">${Math.round(renderJob.progress || 0)} %</strong>
      <div class="persistent-job-actions">${done && renderJob.outputUrl ? `<a class="icon-button" href="${safeUrl(renderJob.outputUrl)}?download=1" download aria-label="Télécharger">${icon('download', 16)}</a>` : !failed ? `<button class="icon-button" data-action="show-render-modal" aria-label="Afficher le rendu">${icon('chevronRight', 16)}</button>` : ''}<button class="icon-button" data-action="dismiss-render-job" aria-label="Masquer">${icon('close', 15)}</button></div>
    </aside>`);
  }
  const conversionJob = state.conversionJob;
  if (conversionJob && !['Terminé', 'Échec'].includes(conversionJob.status) && state.view !== 'conversion') {
    cards.push(`<aside class="persistent-job persistent-conversion" id="persistent-conversion-job">
      <div class="persistent-job-icon">${icon('convert', 19)}</div>
      <div class="persistent-job-copy"><span>Conversion en cours</span><strong id="persistent-conversion-message">${escapeHtml(conversionJob.message || 'Traitement')}</strong><div class="persistent-progress"><i id="persistent-conversion-progress" style="width:${clamp(conversionJob.progress, 0, 100)}%"></i></div></div>
      <strong class="persistent-percent" id="persistent-conversion-percent">${Math.round(conversionJob.progress || 0)} %</strong>
      <div class="persistent-job-actions"><button class="icon-button" data-action="navigate" data-route="conversion" aria-label="Voir la conversion">${icon('chevronRight', 16)}</button></div>
    </aside>`);
  }
  return cards.length ? `<div class="persistent-jobs">${cards.join('')}</div>` : '';
}

function renderModal() {
  if (!state.modal) return '';
  if (state.modal === 'create') {
    const locked = state.modalLockedType ? moduleFor(state.modalLockedType) : null;
    const selected = state.modalType ? moduleFor(state.modalType) : null;
    const selectedIcon = selected?.id === 'playlist_entry' ? 'playlist' : selected?.id === 'new_release' ? 'sparkle' : 'spectrum';
    const lockedIcon = locked?.id === 'playlist_entry' ? 'playlist' : locked?.id === 'new_release' ? 'sparkle' : 'spectrum';
    return `<div class="modal-backdrop" data-action="close-modal"><form class="modal-card create-modal ${locked ? 'create-modal-locked' : ''}" data-form="create-project" role="dialog" aria-modal="true" aria-labelledby="create-project-title"><button type="button" class="modal-close" data-action="close-modal" aria-label="Fermer">${icon('close', 20)}</button><span class="eyebrow">NOUVEAU PROJET</span>${locked ? `<h2 id="create-project-title">Nouveau projet ${escapeHtml(locked.singular.toLowerCase())}</h2><p>Le générateur est déjà défini depuis l’onglet courant.</p><div class="locked-create-type option-${locked.accent}"><span>${icon(lockedIcon, 24)}</span><div><strong>${escapeHtml(locked.label)}</strong><small>${escapeHtml(locked.output)}</small></div>${icon('check', 17)}</div>` : `<h2 id="create-project-title">Quelle vidéo veux-tu créer ?</h2><p>Sélectionne un générateur, puis crée le projet. Le choix actif est clairement encadré.</p><div class="create-options" role="radiogroup" aria-label="Type de vidéo">${Object.values(MODULES).map((module) => `<button type="button" class="create-option ${state.modalType === module.id ? 'is-active' : ''} option-${module.accent}" data-action="select-create-type" data-type="${module.id}" role="radio" aria-checked="${state.modalType === module.id}"><span class="create-option-icon">${icon(module.id === 'playlist_entry' ? 'playlist' : module.id === 'new_release' ? 'sparkle' : 'spectrum', 24)}</span><strong>${escapeHtml(module.label)}</strong><p>${escapeHtml(module.description)}</p><small>${escapeHtml(module.output)}</small><i>${state.modalType === module.id ? icon('check', 16) : ''}</i></button>`).join('')}</div>`}<label class="field"><span>Nom du projet <em>facultatif</em></span><input class="input" id="new-project-name" data-action="new-project-name" value="${escapeHtml(state.modalProjectName || '')}" placeholder="Spectoom proposera un nom par défaut" autocomplete="off"></label>${state.modalError ? `<div class="form-error">${icon('warning', 16)} ${escapeHtml(state.modalError)}</div>` : ''}<button type="submit" class="button button-dark button-large" ${(!locked && !selected) || state.creatingProject ? 'disabled' : ''}>${state.creatingProject ? 'Création…' : `Créer le projet ${icon('arrow', 18)}`}</button>${!locked && !selected ? `<p class="create-help">Choisis d’abord l’un des trois générateurs.</p>` : `<p class="create-help">${icon(selectedIcon, 14)} ${escapeHtml((locked || selected).label)} sera ouvert immédiatement après la création.</p>`}</form></div>`;
  }
  if (state.modal === 'render') {
    const job = state.renderJob || {};
    return `<div class="modal-backdrop"><div class="modal-card render-modal" role="dialog" aria-modal="true"><span class="render-orbit">${icon('render', 30)}</span><span class="eyebrow">RENDU EN COURS</span><h2>${escapeHtml(job.message || 'Préparation de la vidéo')}</h2><p>${state.currentProject?.type === 'youtube_spectrum' ? 'Le spectrum suit la durée complète du morceau. Tu peux masquer cette fenêtre et continuer à naviguer.' : 'Spectoom compose les calques et l’extrait audio de 20 secondes.'}</p><div class="render-progress"><i style="width:${clamp(job.progress, 0, 100)}%"></i></div><strong class="render-percent">${Math.round(job.progress || 0)} %</strong><button class="button button-light" data-action="hide-render-modal">Masquer et continuer</button></div></div>`;
  }
  if (state.modal === 'render-done') {
    const job = state.renderJob || {};
    return `<div class="modal-backdrop"><div class="modal-card render-modal" role="dialog" aria-modal="true"><span class="render-success">${icon('check', 32)}</span><span class="eyebrow">TERMINÉ</span><h2>Ton MP4 est prêt</h2><p>${escapeHtml(job.filename || '')}</p><div class="modal-actions"><a class="button button-dark" href="${safeUrl(job.outputUrl)}?download=1" download>${icon('download', 18)} Télécharger</a><button class="button button-light" data-action="close-modal">Fermer</button></div></div></div>`;
  }
  if (state.modal === 'confirm-delete') {
    const project = state.projects.find((item) => item.id === state.deleteProjectId);
    return `<div class="modal-backdrop" data-action="close-modal"><div class="modal-card confirm-modal"><span class="danger-icon">${icon('trash', 24)}</span><h2>Supprimer ce projet ?</h2><p>« ${escapeHtml(project?.name || 'Projet')} » sera retiré de ta liste. Les MP4 déjà téléchargés sur ton ordinateur ne sont pas affectés.</p><div class="modal-actions"><button class="button button-light" data-action="close-modal">Annuler</button><button class="button button-danger" data-action="confirm-delete">Supprimer</button></div></div></div>`;
  }
  return '';
}

function renderEditor() {
  const project = state.currentProject;
  const module = moduleFor(project);
  const steps = STEPS[project.type] || STEPS.playlist_entry;
  const validation = validationFor(project);
  return `
    <div class="editor-shell module-editor-${module.accent}">
      ${renderSidebar(true)}
      <main class="editor-main">
        <header class="editor-topbar">
          <div class="editor-title-row"><button class="icon-button editor-back" data-action="navigate" data-route="dashboard">${icon('back', 19)}</button><div><div class="editor-project-title"><input value="${escapeHtml(project.name)}" data-bind="name" aria-label="Nom du projet"><span class="edit-pencil">${icon('edit', 15)}</span></div><span class="save-indicator" id="save-indicator">${state.saving ? 'Sauvegarde…' : state.lastSavedAt ? `Sauvegardé à ${new Date(state.lastSavedAt).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}` : 'Sauvegarde automatique'}</span></div></div>
          <div class="editor-actions"><button class="button button-light" data-action="save-now">${icon('save', 17)} Sauvegarder</button><button class="button button-dark" data-action="render-project" ${validation.length ? 'disabled' : ''}>${icon('render', 17)} Générer le MP4 ${icon('arrow', 17)}</button></div>
        </header>
        <nav class="editor-stepper">
          ${steps.map((step, index) => `<button class="editor-step ${state.editorStep === step.id ? 'is-active' : ''} ${stepComplete(project, step.id) ? 'is-complete' : ''}" data-action="editor-step" data-step="${step.id}"><span>${index + 1}</span><div><strong>${escapeHtml(step.label)}</strong><small>${escapeHtml(step.hint)}</small></div></button>`).join('')}
        </nav>
        <section class="editor-workspace ${project.type === 'youtube_spectrum' ? 'workspace-wide-preview' : ''}">
          <aside class="editor-panel editor-panel-left">${renderEditorLeft(project)}</aside>
          <section class="preview-column">${renderEditorPreview(project)}</section>
          <aside class="editor-panel editor-panel-right">${renderEditorInspector(project, validation)}</aside>
        </section>
        ${renderAudioDock(project)}
      </main>
      ${renderModal()}
      ${renderPersistentJobs()}
    </div>`;
}

function stepComplete(project, stepId) {
  if (stepId === 'export') return validationFor(project).length === 0;
  if (stepId === 'audio') return Boolean(project.audio?.url && (project.type === 'youtube_spectrum' || Number(project.audio?.duration || 0) >= 20));
  if (stepId === 'background') return Boolean(project.background?.url || project.background?.videoUrl);
  if (stepId === 'track' || stepId === 'release') return Boolean(project.track?.title && project.track?.artist);
  if (stepId === 'playlists') return Boolean(project.playlists?.length);
  if (stepId === 'branding') return Boolean(project.branding?.logoUrl || project.newRelease?.virginLogoUrl);
  if (stepId === 'template') return Boolean(project.newRelease?.template);
  if (stepId === 'spectrum') return Boolean(project.spectrum?.style);
  if (stepId === 'typography') return true;
  return false;
}

function renderEditorLeft(project) {
  if (project.type === 'playlist_entry') return renderPlaylistStep(project);
  if (project.type === 'new_release') return renderReleaseStep(project);
  return renderSpectrumStep(project);
}

function panelHeader(title, text, iconName = null) {
  return `<div class="panel-heading">${iconName ? `<span>${icon(iconName, 19)}</span>` : ''}<div><h2>${escapeHtml(title)}</h2>${text ? `<p>${escapeHtml(text)}</p>` : ''}</div></div>`;
}

function field(label, path, value, options = {}) {
  const type = options.type || 'text';
  return `<label class="field"><span>${escapeHtml(label)}${options.optional ? ' <em>facultatif</em>' : ''}</span><input class="input" type="${type}" value="${escapeHtml(value ?? '')}" data-bind="${escapeHtml(path)}" ${options.placeholder ? `placeholder="${escapeHtml(options.placeholder)}"` : ''} ${options.min != null ? `min="${options.min}"` : ''} ${options.max != null ? `max="${options.max}"` : ''} ${options.step != null ? `step="${options.step}"` : ''}></label>`;
}

function uploadCard(kind, path, url, title, hint, accept, iconName = 'upload') {
  return `<div class="upload-card ${url ? 'has-file' : ''}">${url && kind !== 'audio' && kind !== 'background-video' ? `<img src="${safeUrl(url)}" alt="">` : `<span class="upload-card-icon">${icon(iconName, 23)}</span>`}<div><strong>${escapeHtml(title)}</strong><small>${escapeHtml(hint)}</small></div><label class="button button-light button-small"><input type="file" hidden accept="${accept}" data-upload-kind="${kind}" data-upload-path="${path}">${url ? 'Remplacer' : 'Importer'}</label></div>`;
}

function rangeField(label, path, value, min, max, step, suffix = '') {
  return `<label class="range-field"><span><strong>${escapeHtml(label)}</strong><output data-output-for="${escapeHtml(path)}">${Number(value).toFixed(step < 1 ? 2 : 0)}${escapeHtml(suffix)}</output></span><input type="range" min="${min}" max="${max}" step="${step}" value="${Number(value)}" data-bind="${escapeHtml(path)}"></label>`;
}

function renderPlaylistStep(project) {
  if (state.editorStep === 'track') {
    return `${panelHeader('Morceau', 'Les informations principales de la vidéo.', 'music')}${field('Titre du morceau', 'track.title', project.track.title, { placeholder: 'Ex. Afro Vibes' })}${field('Artiste principal', 'track.artist', project.track.artist, { placeholder: 'Ex. Tima' })}${field('Collaborations', 'track.guestsText', (project.track.guests || []).join(', '), { optional: true, placeholder: 'Feat., invités…' })}${uploadCard('track-cover', 'track.coverUrl', project.track.coverUrl, 'Pochette du morceau', 'Carrée · 1000 × 1000 px recommandé', 'image/png,image/jpeg,image/webp', 'image')}`;
  }
  if (state.editorStep === 'background') {
    return `${panelHeader('Image de fond', 'Cadre l’artiste dans le format 4:5.', 'image')}${uploadCard('background', 'background.url', project.background.url, 'Visuel principal', 'JPG, PNG ou WebP · 1080 × 1350 px', 'image/png,image/jpeg,image/webp', 'image')}<div class="panel-group"><h3>Cadrage</h3>${rangeField('Position horizontale', 'background.x', project.background.x, 0, 100, 1, '%')}${rangeField('Position verticale', 'background.y', project.background.y, 0, 100, 1, '%')}${rangeField('Zoom', 'background.zoom', project.background.zoom, 1, 2.2, .01, '×')}${rangeField('Voile de lisibilité', 'background.veil', project.background.veil, 0, .85, .01)}</div>`;
  }
  if (state.editorStep === 'playlists') {
    return `${panelHeader('Playlists', 'Ajoute de 1 à 6 entrées pour ce morceau.', 'playlist')}<button class="button button-dark button-full" data-action="add-playlist" ${project.playlists.length >= 6 ? 'disabled' : ''}>${icon('plus', 18)} Ajouter une playlist</button><div class="playlist-list">${project.playlists.length ? project.playlists.map((item, index) => renderPlaylistListItem(item, index)).join('') : `<div class="mini-empty">Aucune playlist ajoutée.</div>`}</div><div class="panel-note">${icon('grip', 17)} Utilise les flèches pour modifier l’ordre d’apparition.</div>`;
  }
  if (state.editorStep === 'branding') {
    return `${panelHeader('Branding', 'Définis l’accroche, la police et le logo du rendu.', 'brand')}<label class="field"><span>Accroche</span><textarea class="textarea" data-bind="branding.tagline" maxlength="80">${escapeHtml(project.branding.tagline || '')}</textarea><small>Deux lignes maximum dans la vidéo.</small></label>${field('Couleur d’accent', 'branding.accent', project.branding.accent, { type: 'color' })}${renderProjectFontPicker(project)}<div class="logo-choice"><button class="logo-option ${project.branding.logoUrl?.includes('spectoom-white') ? 'is-active' : ''}" data-action="set-brand-logo" data-url="/static/brand/spectoom-white.png"><span class="logo-swatch dark"><img src="/static/brand/spectoom-white.png"></span>Blanc</button><button class="logo-option ${project.branding.logoUrl?.includes('spectoom-black') ? 'is-active' : ''}" data-action="set-brand-logo" data-url="/static/brand/spectoom-black.png"><span class="logo-swatch light"><img src="/static/brand/spectoom-black.png"></span>Noir</button></div>${uploadCard('logo', 'branding.logoUrl', '', 'Logo personnalisé', 'PNG, WebP ou SVG transparent', 'image/png,image/webp,image/svg+xml', 'upload')}`;
  }
  if (state.editorStep === 'audio') return `${panelHeader('Extrait audio', 'Importe le morceau puis déplace la fenêtre fixe de 20 secondes.', 'music')}${uploadCard('audio', 'audio.url', project.audio.url, project.audio.url ? 'Fichier audio chargé' : 'Importer le morceau', project.audio.url ? `${formatDuration(project.audio.duration)} · sélection automatique` : 'WAV, MP3, M4A ou AAC · minimum 20 s', 'audio/wav,audio/mpeg,audio/mp4,audio/aac', 'music')}<div class="panel-note panel-note-accent">${icon('play', 17)} Le son démarre automatiquement dès que tu déplaces la sélection.</div>`;
  return renderExportPanel(project);
}

function renderPlaylistListItem(item, index) {
  const platform = state.config.platforms.find((entry) => entry.id === item.platformId) || {};
  const iconUrl = platform.iconBlackUrl || DSP_FALLBACKS[item.platformId]?.[0];
  return `<button class="playlist-list-item ${state.selectedPlaylist === index ? 'is-selected' : ''}" data-action="select-playlist" data-index="${index}"><span class="playlist-grip">${icon('grip', 16)}</span><img class="playlist-list-cover" src="${safeUrl(item.coverUrl || '/demo/playlist-1.jpg')}" alt=""><span class="playlist-list-dsp"><img src="${safeUrl(iconUrl)}" alt=""></span><span><strong>${escapeHtml(item.title || `Playlist ${index + 1}`)}</strong><small>${escapeHtml(platform.name || 'Plateforme')}</small></span><i>${icon('chevronRight', 16)}</i></button>`;
}

function renderReleaseStep(project) {
  const release = project.newRelease || {};
  if (state.editorStep === 'release') {
    return `${panelHeader('Nouvelle sortie', 'Renseigne le contenu de la campagne.', 'sparkle')}<div class="segmented segmented-three">${[['single', 'Single'], ['ep', 'EP'], ['album', 'Album']].map(([id, label]) => `<button class="${release.releaseType === id ? 'is-active' : ''}" data-action="set-release-type" data-value="${id}">${label}</button>`).join('')}</div>${field('Titre de la sortie', 'track.title', project.track.title, { placeholder: 'Ex. Éclat' })}${field('Nom de l’artiste', 'track.artist', project.track.artist, { placeholder: 'Ex. Tima' })}${uploadCard('track-cover', 'track.coverUrl', project.track.coverUrl, 'Cover officielle', 'Utilisée dans le template Artwork', 'image/png,image/jpeg,image/webp', 'image')}`;
  }
  if (state.editorStep === 'background') {
    return `${panelHeader('Visuel principal', 'Choisis une photo ou un artwork plein cadre.', 'image')}${uploadCard('background', 'background.url', project.background.url, 'Image de campagne', 'Format vertical recommandé · minimum 720 × 900 px', 'image/png,image/jpeg,image/webp', 'image')}<div class="panel-group"><h3>Cadrage</h3>${rangeField('Position horizontale', 'background.x', project.background.x, 0, 100, 1, '%')}${rangeField('Position verticale', 'background.y', project.background.y, 0, 100, 1, '%')}${rangeField('Zoom', 'background.zoom', project.background.zoom, 1, 2.2, .01, '×')}${rangeField('Voile', 'background.veil', project.background.veil, 0, .75, .01)}</div>`;
  }
  if (state.editorStep === 'template') {
    return `${panelHeader('Template', 'Deux compositions adaptées aux nouvelles sorties.', 'sparkle')}<div class="template-options"><button class="template-option ${release.template === 'editorial' ? 'is-active' : ''}" data-action="set-release-template" data-value="editorial"><span class="template-preview editorial-template"><i>new</i><b>single</b><strong>TITRE<br><small>ARTISTE</small></strong></span><div><strong>Portrait éditorial</strong><small>Photo plein cadre et titrage asymétrique.</small></div></button><button class="template-option ${release.template === 'artwork' ? 'is-active' : ''}" data-action="set-release-template" data-value="artwork"><span class="template-preview artwork-template"><i></i><strong>TITRE</strong></span><div><strong>Artwork central</strong><small>Cover mise en avant et titre centré.</small></div></button></div>`;
  }
  if (state.editorStep === 'branding') {
    return `${panelHeader('Virgin Music', 'Choisis la variante du logo et la police du visuel.', 'brand')}<div class="virgin-options">${[['red', '/static/brand/virgin-music-red.png'], ['white', '/static/brand/virgin-music-white.png'], ['black', '/static/brand/virgin-music-black.png']].map(([tone, url]) => `<button class="virgin-option ${release.virginLogoTone === tone ? 'is-active' : ''} tone-${tone}" data-action="set-virgin-logo" data-tone="${tone}" data-url="${url}"><span><img src="${url}"></span><strong>${tone === 'red' ? 'Rouge' : tone === 'white' ? 'Blanc' : 'Noir'}</strong></button>`).join('')}</div><div class="panel-note">${icon('sparkle', 17)} Le libellé supérieur du rendu est fixé à « new ».</div>${field('Disponibilité', 'newRelease.availability', release.availability || 'Disponible maintenant')}${renderProjectFontPicker(project)}`;
  }
  if (state.editorStep === 'audio') return `${panelHeader('Extrait audio', 'La vidéo utilisera exactement 20 secondes du morceau.', 'music')}${uploadCard('audio', 'audio.url', project.audio.url, project.audio.url ? 'Fichier audio chargé' : 'Importer le morceau', project.audio.url ? `${formatDuration(project.audio.duration)} · extrait de 20 s` : 'WAV, MP3, M4A ou AAC', 'audio/wav,audio/mpeg,audio/mp4,audio/aac', 'music')}<div class="panel-note panel-note-accent">${icon('play', 17)} Déplace le curseur : la nouvelle plage est lue immédiatement.</div>`;
  return renderExportPanel(project);
}

function renderSpectrumStep(project) {
  const spectrum = project.spectrum || {};
  if (state.editorStep === 'track') {
    return `${panelHeader('Morceau', 'Ces informations apparaissent dans la vidéo YouTube.', 'music')}${field('Titre du morceau', 'track.title', project.track.title, { placeholder: 'Ex. Midnight' })}${field('Nom de l’artiste', 'track.artist', project.track.artist, { placeholder: 'Ex. CED' })}${uploadCard('track-cover', 'track.coverUrl', project.track.coverUrl, 'Cover du morceau', 'Carrée · haute définition recommandée', 'image/png,image/jpeg,image/webp', 'image')}`;
  }
  if (state.editorStep === 'background') {
    return `${panelHeader('Fond 16:9', 'Une image ou une vidéo en boucle derrière le spectrum.', 'video')}${uploadCard('background', 'background.url', project.background.url, 'Image de fond', 'JPG, PNG ou WebP · 1920 × 1080 recommandé', 'image/png,image/jpeg,image/webp', 'image')}${uploadCard('background-video', 'background.videoUrl', project.background.videoUrl, 'Vidéo de fond', 'MP4, MOV, M4V ou WebM · boucle automatique', 'video/mp4,video/quicktime,video/webm', 'video')}<label class="field"><span>Animation du fond</span><select class="select" data-bind="spectrum.backgroundAnimation"><option value="static" ${spectrum.backgroundAnimation === 'static' ? 'selected' : ''}>Statique</option><option value="pulse" ${spectrum.backgroundAnimation === 'pulse' ? 'selected' : ''}>Pulsation douce</option><option value="drift" ${spectrum.backgroundAnimation === 'drift' ? 'selected' : ''}>Zoom et dérive</option></select></label>${rangeField('Voile de lisibilité', 'background.veil', project.background.veil, .12, .82, .01)}`;
  }
  if (state.editorStep === 'spectrum') {
    return `${panelHeader('Style du spectrum', 'La visualisation réagit au morceau en temps réel.', 'spectrum')}<div class="spectrum-style-grid">${SPECTRUM_STYLES.map(([id, label]) => `<button class="spectrum-style ${spectrum.style === id ? 'is-active' : ''}" data-action="set-spectrum-style" data-value="${id}"><span class="style-icon style-${id}">${renderMiniSpectrum(id)}</span><strong>${label}</strong></button>`).join('')}</div><div class="panel-group"><h3>Palette</h3><div class="color-row">${['colorA', 'colorB', 'colorC'].map((key, index) => `<label><span>Couleur ${index + 1}</span><input type="color" value="${safeColor(spectrum[key], ['#8b5cf6', '#22d3ee', '#f472b6'][index])}" data-bind="spectrum.${key}"></label>`).join('')}</div>${rangeField('Sensibilité', 'spectrum.sensitivity', spectrum.sensitivity || 1, .55, 2, .01, '×')}</div>`;
  }
  if (state.editorStep === 'typography') {
    const showLogo = project.branding?.showLogo === true;
    return `${panelHeader('Textes et identité', 'Ajuste la police, les couleurs et le logo facultatif.', 'brand')}<div class="color-row color-row-two"><label><span>Titre</span><input type="color" value="${safeColor(spectrum.titleColor, '#ffffff')}" data-bind="spectrum.titleColor"></label><label><span>Artiste</span><input type="color" value="${safeColor(spectrum.artistColor, '#d9d6e7')}" data-bind="spectrum.artistColor"></label></div>${renderProjectFontPicker(project)}<label class="toggle-card"><input type="checkbox" data-bind="branding.showLogo" ${showLogo ? 'checked' : ''}><span class="toggle-control"><i></i></span><span><strong>Afficher un logo dans la vidéo</strong><small>Désactivé par défaut. Aucun logo Spectoom n’est ajouté automatiquement.</small></span></label>${showLogo ? `<div class="logo-choice"><button class="logo-option ${project.branding.logoUrl?.includes('spectoom-white') ? 'is-active' : ''}" data-action="set-brand-logo" data-url="/static/brand/spectoom-white.png"><span class="logo-swatch dark"><img src="/static/brand/spectoom-white.png"></span>Logo blanc</button><button class="logo-option ${project.branding.logoUrl?.includes('spectoom-black') ? 'is-active' : ''}" data-action="set-brand-logo" data-url="/static/brand/spectoom-black.png"><span class="logo-swatch light"><img src="/static/brand/spectoom-black.png"></span>Logo noir</button></div>${uploadCard('logo', 'branding.logoUrl', '', 'Logo personnalisé', 'PNG, WebP ou SVG', 'image/png,image/webp,image/svg+xml', 'upload')}` : `<div class="panel-note">${icon('check', 17)} Aucun logo ne sera affiché dans l’aperçu ni dans le MP4.</div>`}`;
  }
  if (state.editorStep === 'audio') return `${panelHeader('Morceau complet', 'Le MP4 aura la même durée que le fichier audio.', 'music')}${uploadCard('audio', 'audio.url', project.audio.url, project.audio.url ? 'Morceau chargé' : 'Importer le morceau', project.audio.url ? `${formatDuration(project.audio.duration)} · export complet` : 'WAV, MP3, M4A ou AAC', 'audio/wav,audio/mpeg,audio/mp4,audio/aac', 'music')}<div class="panel-note">${icon('video', 17)} Un morceau long produit un rendu long. La progression reste visible dans l’historique.</div>`;
  return renderExportPanel(project);
}

function renderMiniSpectrum(style) {
  if (style === 'hill') return `<svg viewBox="0 0 64 30"><path d="M2 22C10 4 18 28 28 13s18 13 34-4" fill="none" stroke="currentColor" stroke-width="3"/></svg>`;
  return Array.from({ length: style === 'led' ? 14 : 11 }, (_, index) => `<i style="height:${20 + ((index * 31) % 70)}%"></i>`).join('');
}

function renderExportPanel(project) {
  const errors = validationFor(project);
  const module = moduleFor(project);
  return `${panelHeader('Vérifier et exporter', 'Spectoom contrôle le projet avant le rendu.', 'check')}<div class="export-specs"><div><span>Format</span><strong>MP4 · H.264</strong></div><div><span>Canvas</span><strong>${escapeHtml(module.output)}</strong></div><div><span>Audio</span><strong>AAC · 48 kHz</strong></div><div><span>Couleurs</span><strong>Rec.709</strong></div></div>${errors.length ? `<div class="validation-list"><h3>${icon('warning', 18)} ${errors.length} point${errors.length > 1 ? 's' : ''} à corriger</h3>${errors.map(([step, message]) => `<button data-action="jump-validation" data-step-label="${escapeHtml(step)}"><span>${escapeHtml(step)}</span>${escapeHtml(message)}${icon('chevronRight', 15)}</button>`).join('')}</div>` : `<div class="ready-card"><span>${icon('check', 24)}</span><div><strong>Le projet est prêt</strong><p>L’aperçu et les médias requis sont complets.</p></div></div>`}<button class="button button-dark button-full button-large" data-action="render-project" ${errors.length ? 'disabled' : ''}>${icon('render', 18)} Générer le MP4 ${icon('arrow', 18)}</button>`;
}

function renderEditorInspector(project, validation) {
  if (project.type === 'playlist_entry' && state.editorStep === 'playlists') return renderPlaylistInspector(project);
  const module = moduleFor(project);
  const completed = (STEPS[project.type] || []).filter((step) => step.id !== 'export' && stepComplete(project, step.id)).length;
  const total = (STEPS[project.type] || []).length - 1;
  return `${panelHeader('Projet', module.label)}<div class="project-progress-card"><div><strong>${completed}/${total}</strong><span>étapes complètes</span></div><div class="progress-track"><i style="width:${Math.round(completed / total * 100)}%"></i></div></div><div class="inspector-summary"><div><span>Statut</span><strong class="status-pill ${validation.length ? 'status-draft' : 'status-ready'}">${validation.length ? 'Brouillon' : 'Prêt'}</strong></div><div><span>Sortie</span><strong>${escapeHtml(module.output)}</strong></div><div><span>Template</span><strong>${project.type === 'new_release' ? (project.newRelease?.template === 'artwork' ? 'Artwork central' : 'Portrait éditorial') : project.type === 'youtube_spectrum' ? SPECTRUM_STYLES.find(([id]) => id === project.spectrum?.style)?.[1] : `${project.playlists?.length || 0} playlist(s)`}</strong></div></div>${validation.length ? `<div class="inspector-alert"><span>${icon('warning', 18)}</span><div><strong>${validation.length} élément${validation.length > 1 ? 's' : ''} manquant${validation.length > 1 ? 's' : ''}</strong><p>${escapeHtml(validation[0][1])}</p></div></div>` : `<div class="inspector-success"><span>${icon('check', 18)}</span><div><strong>Prêt à rendre</strong><p>Tous les éléments requis sont présents.</p></div></div>`}<div class="render-history-mini"><h3>Derniers rendus</h3>${state.renders.length ? state.renders.slice(0, 3).map((render) => `<div><span class="status-dot ${statusClass(render.status)}"></span><span><strong>${escapeHtml(render.status)}</strong><small>${formatDateTime(render.createdAt)}</small></span>${render.outputUrl ? `<a href="${safeUrl(render.outputUrl)}?download=1" download>${icon('download', 16)}</a>` : ''}</div>`).join('') : `<p>Aucun rendu pour ce projet.</p>`}</div>`;
}

function renderPlaylistInspector(project) {
  const index = clamp(state.selectedPlaylist, 0, Math.max(0, project.playlists.length - 1));
  const item = project.playlists[index];
  if (!item) return `${panelHeader('Playlist sélectionnée', 'Ajoute une playlist pour afficher ses réglages.')}<div class="mini-empty tall">Aucune playlist.</div>`;
  return `${panelHeader('Playlist sélectionnée', `${index + 1} / ${project.playlists.length}`)}<div class="selected-playlist-card"><img src="${safeUrl(item.coverUrl || '/demo/playlist-1.jpg')}" alt=""><div><strong>${escapeHtml(item.title || `Playlist ${index + 1}`)}</strong><span>${escapeHtml(state.config.platforms.find((p) => p.id === item.platformId)?.name || 'Plateforme')}</span></div><button class="icon-button" data-action="remove-playlist" data-index="${index}">${icon('trash', 17)}</button></div>${uploadCard('playlist-cover', `playlists.${index}.coverUrl`, item.coverUrl, 'Image de la playlist', 'Carrée · 640 × 640 px recommandé', 'image/png,image/jpeg,image/webp', 'image')}<label class="field"><span>Plateforme</span><select class="select" data-bind="playlists.${index}.platformId">${state.config.platforms.filter((p) => p.active !== false).map((platform) => `<option value="${platform.id}" ${item.platformId === platform.id ? 'selected' : ''}>${escapeHtml(platform.name)}</option>`).join('')}</select></label>${field('Titre de la playlist', `playlists.${index}.title`, item.title, { placeholder: 'Ex. Afro Hits' })}<div class="field"><span>Icône DSP</span><div class="segmented segmented-three"><button class="${item.iconTone === 'auto' ? 'is-active' : ''}" data-action="set-icon-tone" data-index="${index}" data-value="auto">Auto</button><button class="${item.iconTone === 'white' ? 'is-active' : ''}" data-action="set-icon-tone" data-index="${index}" data-value="white">Blanche</button><button class="${item.iconTone === 'black' ? 'is-active' : ''}" data-action="set-icon-tone" data-index="${index}" data-value="black">Noire</button></div></div><div class="playlist-order-actions"><button class="button button-light button-small" data-action="move-playlist" data-index="${index}" data-direction="-1" ${index === 0 ? 'disabled' : ''}>${icon('chevronLeft', 16)} Avant</button><button class="button button-light button-small" data-action="move-playlist" data-index="${index}" data-direction="1" ${index === project.playlists.length - 1 ? 'disabled' : ''}>Après ${icon('chevronRight', 16)}</button></div>`;
}

function renderEditorPreview(project) {
  const module = moduleFor(project);
  return `<div class="preview-heading"><div><span class="eyebrow">APERÇU ${escapeHtml(module.ratio)}</span><strong>${escapeHtml(module.label)}</strong></div><button class="preview-play" data-action="toggle-audio">${state.audioStatus === 'playing' ? icon('pause', 18) : icon('play', 18)}<span>${state.audioStatus === 'playing' ? 'Pause' : 'Prévisualiser'}</span></button></div><div id="preview-area" class="preview-area ${project.type === 'youtube_spectrum' ? 'preview-landscape' : 'preview-portrait'}">${renderPreviewInner(project)}</div><div class="preview-footer"><span>${icon('check', 14)} Aperçu généré avec le moteur du rendu</span><span>${project.type === 'youtube_spectrum' ? formatDuration(project.audio?.duration || 0) : '00:20'}</span></div>`;
}

function renderPreviewInner(project) {
  if (project.type === 'youtube_spectrum') return renderSpectrumPreview(project);
  if (state.preview?.projectId === project.id) {
    const preview = state.preview;
    const exact = (layer, className, delay = 0) => `<img class="scene-layer ${className}" style="left:${(layer.x / preview.canvasWidth * 100).toFixed(5)}%;top:${(layer.y / preview.canvasHeight * 100).toFixed(5)}%;width:${(layer.width / preview.canvasWidth * 100).toFixed(5)}%;height:${(layer.height / preview.canvasHeight * 100).toFixed(5)}%;--delay:${delay}s" src="${safeUrl(layer.url)}" alt="">`;
    return `<div class="social-scene ${state.previewPlaying ? 'is-playing' : ''}" style="--scene-ratio:${preview.canvasWidth}/${preview.canvasHeight}"><img class="scene-layer scene-background" src="${safeUrl(preview.backgroundUrl)}" alt=""><img class="scene-layer scene-base" src="${safeUrl(preview.baseUrl)}" alt="">${exact(preview.header, 'scene-header', .4)}${(preview.cards || []).map((card, index) => exact(card, 'scene-card', .8 + index * .18)).join('')}${exact(preview.track, 'scene-track', 1.05)}</div>`;
  }
  return `<div class="preview-loading"><span></span><p>Génération de l’aperçu fidèle…</p></div>`;
}

function renderSpectrumPreview(project) {
  const preview = state.preview?.projectId === project.id && state.preview?.type === 'youtube_spectrum' ? state.preview : null;
  if (!preview) return `<div class="preview-loading"><span></span><p>Génération de l’aperçu fidèle…</p></div>`;
  const spectrum = project.spectrum || {};
  const geometry = preview.visualizer || {};
  const canvasWidth = Number(geometry.width || 1100);
  const canvasHeight = Number(geometry.height || (spectrum.style === 'hill' ? 260 : 280));
  const x = Number(geometry.x ?? 650);
  const y = Number(geometry.y ?? 700);
  const alpha = clamp(Number(geometry.alpha ?? .94), 0, 1);
  const backgroundVideo = project.background?.videoUrl
    ? `<video class="spectrum-exact-background" id="spectrum-bg-video" src="${safeUrl(project.background.videoUrl)}" muted loop autoplay playsinline></video>`
    : `<img class="spectrum-exact-background" src="${safeUrl(preview.backgroundUrl)}" alt="">`;
  const visualizer = preview.visualizerVideoUrl
    ? `<video id="spectrum-viz-video" class="spectrum-exact-visualizer" src="${safeUrl(preview.visualizerVideoUrl)}" muted preload="auto" playsinline></video>`
    : `<canvas id="spectrum-canvas" width="${canvasWidth}" height="${canvasHeight}" data-style="${escapeHtml(spectrum.style || 'bars')}"></canvas>`;
  return `<div class="spectrum-exact-scene ${state.previewPlaying ? 'is-playing' : ''}" style="--visual-x:${(x / preview.canvasWidth * 100).toFixed(5)}%;--visual-y:${(y / preview.canvasHeight * 100).toFixed(5)}%;--visual-w:${(canvasWidth / preview.canvasWidth * 100).toFixed(5)}%;--visual-h:${(canvasHeight / preview.canvasHeight * 100).toFixed(5)}%;--visual-alpha:${alpha};--background-animation:${escapeHtml(project.spectrum?.backgroundAnimation || 'static')}">${backgroundVideo}<img class="spectrum-exact-layer spectrum-exact-base" src="${safeUrl(preview.baseUrl)}" alt="">${visualizer}<img class="spectrum-exact-layer spectrum-exact-foreground" src="${safeUrl(preview.foregroundUrl)}" alt=""></div>`;
}

function renderAudioDock(project) {
  const isSpectrum = project.type === 'youtube_spectrum';
  const duration = Number(project.audio?.duration || 0);
  const start = clamp(project.audio?.start || 0, 0, Math.max(0, duration - 20));
  return `<section class="audio-dock"><div class="audio-dock-heading"><div><h2>Audio</h2><p>${isSpectrum ? 'Prévisualise le morceau complet et son animation.' : 'Sélectionne les 20 secondes utilisées dans la vidéo.'}</p></div><label class="button button-light button-small">${icon('upload', 16)} ${project.audio?.url ? 'Remplacer' : 'Importer'}<input type="file" hidden accept="audio/wav,audio/mpeg,audio/mp4,audio/aac" data-upload-kind="audio" data-upload-path="audio.url"></label></div><div class="audio-controls"><button id="audio-play-button" class="audio-play-button" data-action="toggle-audio" ${project.audio?.url ? '' : 'disabled'}>${state.audioStatus === 'playing' ? icon('pause', 22) : icon('play', 22)}</button><div class="audio-time"><strong id="audio-current-time">${formatDuration(isSpectrum ? previewAudio.currentTime : start, true)}</strong><span>/ ${formatDuration(duration, true)}</span></div><div class="waveform-wrap"><canvas id="waveform-canvas"></canvas>${project.audio?.url ? `<input id="audio-range" class="audio-range ${isSpectrum ? 'spectrum-range' : ''}" type="range" min="0" max="${Math.max(0, isSpectrum ? duration : duration - 20)}" step="0.001" value="${isSpectrum ? clamp(previewAudio.currentTime, 0, duration) : start}" data-action="audio-range">` : ''}<div class="selection-label">${isSpectrum ? 'Morceau complet' : '20 secondes'}</div></div>${isSpectrum ? `<div class="audio-time-box"><span>Durée</span><strong>${formatDuration(duration, true)}</strong></div>` : `<div class="audio-time-fields"><label><span>Début</span><input value="${formatDuration(start, true)}" data-action="audio-start-time"></label><label><span>Fin</span><input value="${formatDuration(start + 20, true)}" disabled></label></div>`}</div></section>`;
}

function renderModalOutsideEditor() {
  return renderModal();
}

function hydrateEditor() {
  syncAudioSource();
  requestWaveform();
  if (state.currentProject?.type === 'youtube_spectrum') startSpectrumLoop();
  else stopSpectrumLoop();
}

function syncAudioSource() {
  const url = state.currentProject?.audio?.url || '';
  const absoluteCurrent = previewAudio.getAttribute('src') || '';
  if (url && absoluteCurrent !== url) {
    previewAudio.pause();
    previewAudio.src = url;
    previewAudio.load();
    state.audioStatus = 'idle';
  }
  if (!url && absoluteCurrent) {
    previewAudio.pause();
    previewAudio.removeAttribute('src');
    previewAudio.load();
    state.audioStatus = 'idle';
  }
}

async function ensureAudioGraph() {
  if (!audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)();
  if (!analyser) {
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = clamp(state.currentProject?.spectrum?.smoothing ?? .82, 0, .99);
  }
  if (!mediaSource) {
    mediaSource = audioContext.createMediaElementSource(previewAudio);
    mediaSource.connect(analyser);
    analyser.connect(audioContext.destination);
  }
  if (audioContext.state === 'suspended') await audioContext.resume();
  return analyser;
}

async function toggleAudio() {
  const project = state.currentProject;
  if (!project?.audio?.url) {
    toast('Importe d’abord un fichier audio.', 'warning');
    return;
  }
  try {
    await ensureAudioGraph();
    if (!previewAudio.paused) {
      previewAudio.pause();
      return;
    }
    if (project.type !== 'youtube_spectrum') {
      const start = clamp(project.audio.start || 0, 0, Math.max(0, project.audio.duration - 20));
      if (previewAudio.currentTime < start || previewAudio.currentTime >= start + 20) previewAudio.currentTime = start;
    }
    await previewAudio.play();
  } catch (error) {
    toast(`Lecture impossible : ${error.message}`, 'error');
  }
}

async function playSelectedRange(fromUserGesture = true) {
  const project = state.currentProject;
  if (!project?.audio?.url) return;
  try {
    if (fromUserGesture) await ensureAudioGraph();
    const start = clamp(project.audio.start || 0, 0, Math.max(0, project.audio.duration - 20));
    previewAudio.currentTime = start;
    await previewAudio.play();
  } catch (error) {
    console.warn(error);
    toast('Le navigateur a bloqué la lecture. Clique une fois sur Lecture.', 'warning');
  }
}

function onAudioTimeUpdate() {
  const project = state.currentProject;
  if (!project) return;
  if (project.type !== 'youtube_spectrum' && project.audio?.url) {
    const start = clamp(project.audio.start || 0, 0, Math.max(0, project.audio.duration - 20));
    if (previewAudio.currentTime >= start + 20 || previewAudio.currentTime < start - .05) {
      previewAudio.currentTime = start;
      if (!previewAudio.paused) previewAudio.play().catch(() => {});
    }
  }
  const timeNode = document.getElementById('audio-current-time');
  if (timeNode) timeNode.textContent = formatDuration(previewAudio.currentTime, true);
  const range = document.getElementById('audio-range');
  if (range && project.type === 'youtube_spectrum' && document.activeElement !== range) range.value = String(previewAudio.currentTime);
  if (project.type === 'youtube_spectrum') syncSpectrumVisualizer(false);
  drawWaveform();
}

function updateAudioButtons() {
  document.querySelectorAll('[data-action="toggle-audio"]').forEach((button) => {
    const label = button.querySelector('span');
    button.innerHTML = `${state.audioStatus === 'playing' ? icon('pause', button.classList.contains('audio-play-button') ? 22 : 18) : icon('play', button.classList.contains('audio-play-button') ? 22 : 18)}${label ? `<span>${state.audioStatus === 'playing' ? 'Pause' : 'Prévisualiser'}</span>` : ''}`;
  });
  const scene = document.querySelector('.social-scene');
  scene?.classList.toggle('is-playing', state.audioStatus === 'playing');
  document.querySelector('.spectrum-exact-scene')?.classList.toggle('is-playing', state.audioStatus === 'playing');
}

async function requestWaveform() {
  const project = state.currentProject;
  const url = project?.audio?.url;
  if (!url) {
    state.waveform = null;
    drawWaveform();
    return;
  }
  if (state.waveformUrl === url && state.waveform) {
    drawWaveform();
    return;
  }
  const serial = ++waveformRequest;
  try {
    if (!audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const response = await fetch(url, { credentials: 'same-origin' });
    const buffer = await response.arrayBuffer();
    const decoded = await audioContext.decodeAudioData(buffer.slice(0));
    if (serial !== waveformRequest) return;
    const channel = decoded.getChannelData(0);
    const points = 1400;
    const step = Math.max(1, Math.floor(channel.length / points));
    const peaks = new Float32Array(points);
    for (let i = 0; i < points; i += 1) {
      let peak = 0;
      const start = i * step;
      const end = Math.min(channel.length, start + step);
      for (let j = start; j < end; j += Math.max(1, Math.floor(step / 35))) peak = Math.max(peak, Math.abs(channel[j]));
      peaks[i] = peak;
    }
    state.waveform = peaks;
    state.waveformUrl = url;
    drawWaveform();
  } catch (error) {
    console.warn('Waveform', error);
    state.waveform = null;
    drawWaveform();
  }
}

function drawWaveform() {
  const canvas = document.getElementById('waveform-canvas');
  const project = state.currentProject;
  if (!canvas || !project) return;
  const rect = canvas.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  canvas.width = Math.round(rect.width * dpr);
  canvas.height = Math.round(rect.height * dpr);
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  const width = rect.width;
  const height = rect.height;
  ctx.clearRect(0, 0, width, height);
  const peaks = state.waveform;
  const duration = Math.max(.001, Number(project.audio?.duration || 0));
  const isSpectrum = project.type === 'youtube_spectrum';
  const selectionStart = isSpectrum ? 0 : clamp(project.audio?.start || 0, 0, Math.max(0, duration - 20));
  const selectionEnd = isSpectrum ? previewAudio.currentTime : selectionStart + 20;
  const xStart = selectionStart / duration * width;
  const xEnd = selectionEnd / duration * width;
  if (!isSpectrum) {
    ctx.fillStyle = 'rgba(91, 212, 165, .18)';
    ctx.fillRect(xStart, 0, Math.max(3, xEnd - xStart), height);
    ctx.strokeStyle = 'rgba(31, 162, 112, .8)';
    ctx.lineWidth = 1;
    ctx.strokeRect(xStart + .5, .5, Math.max(2, xEnd - xStart - 1), height - 1);
  }
  const count = peaks?.length || 220;
  const step = width / count;
  for (let index = 0; index < count; index += 1) {
    const peak = peaks ? peaks[index] : .18 + .55 * Math.abs(Math.sin(index * .31)) * Math.abs(Math.cos(index * .07));
    const x = index * step;
    const barHeight = Math.max(2, peak * height * .86);
    const active = isSpectrum ? x <= xEnd : x >= xStart && x <= xEnd;
    ctx.fillStyle = active ? 'rgba(22, 155, 104, .92)' : 'rgba(32, 34, 39, .19)';
    ctx.fillRect(x, (height - barHeight) / 2, Math.max(1, step * .48), barHeight);
  }
  if (isSpectrum) {
    ctx.fillStyle = 'rgba(17, 17, 17, .8)';
    ctx.fillRect(Math.max(0, xEnd - 1), 0, 2, height);
  }
}

function spectrumVisualizerVideo() {
  return document.getElementById('spectrum-viz-video');
}

function pauseSpectrumVisualizer() {
  const video = spectrumVisualizerVideo();
  if (video && !video.paused) video.pause();
}

function syncSpectrumVisualizer(force = false) {
  const video = spectrumVisualizerVideo();
  if (!video || state.currentProject?.type !== 'youtube_spectrum') return;
  const apply = () => {
    const target = clamp(previewAudio.currentTime || 0, 0, Math.max(0, (video.duration || state.currentProject?.audio?.duration || 0) - .02));
    if (force || Math.abs((video.currentTime || 0) - target) > .16) {
      try { video.currentTime = target; } catch (_error) { /* metadata not ready yet */ }
    }
    if (!previewAudio.paused) video.play().catch(() => {});
    else if (!video.paused) video.pause();
  };
  if (video.readyState >= 1) apply();
  else video.addEventListener('loadedmetadata', apply, { once: true });
}

function startSpectrumLoop() {
  stopSpectrumLoop();
  if (spectrumVisualizerVideo()) {
    syncSpectrumVisualizer(true);
    return;
  }
  const loop = () => {
    drawSpectrumCanvas();
    spectrumAnimationFrame = requestAnimationFrame(loop);
  };
  loop();
}

function stopSpectrumLoop() {
  if (spectrumAnimationFrame) cancelAnimationFrame(spectrumAnimationFrame);
  spectrumAnimationFrame = null;
  pauseSpectrumVisualizer();
}

function drawSpectrumCanvas() {
  const canvas = document.getElementById('spectrum-canvas');
  if (!canvas || !state.currentProject || state.currentProject.type !== 'youtube_spectrum') return;
  const ctx = canvas.getContext('2d');
  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);
  const spectrum = state.currentProject.spectrum || {};
  const style = spectrum.style || 'bars';
  const count = analyser?.frequencyBinCount || 128;
  const data = new Uint8Array(count);
  if (analyser && !previewAudio.paused) analyser.getByteFrequencyData(data);
  else for (let i = 0; i < count; i += 1) data[i] = 38 + 68 * Math.abs(Math.sin(performance.now() / 780 + i * .23));
  const sensitivity = clamp(spectrum.sensitivity || 1, .55, 2);
  const colors = [safeColor(spectrum.colorA, '#8b5cf6'), safeColor(spectrum.colorB, '#22d3ee'), safeColor(spectrum.colorC, '#f472b6')];
  const gradient = ctx.createLinearGradient(0, 0, width, 0);
  gradient.addColorStop(0, colors[0]);
  gradient.addColorStop(.52, colors[1]);
  gradient.addColorStop(1, colors[2]);
  ctx.strokeStyle = gradient;
  ctx.fillStyle = gradient;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  const baseY = height / 2;
  if (style === 'bars' || style === 'led' || style === 'mirror') {
    const bars = style === 'led' ? 76 : 82;
    const gap = width / bars;
    const barWidth = Math.max(2, gap * .58);
    for (let i = 0; i < bars; i += 1) {
      const value = data[Math.floor(i / bars * data.length)] / 255;
      const amplitude = Math.max(3, value * height * (style === 'mirror' ? .47 : .44) * sensitivity);
      const x = i * gap + (gap - barWidth) / 2;
      if (style === 'led') {
        const dots = Math.max(1, Math.floor(amplitude / 9));
        for (let d = 0; d < dots; d += 1) {
          ctx.globalAlpha = .45 + d / Math.max(1, dots) * .55;
          ctx.beginPath();
          ctx.arc(x + barWidth / 2, baseY - d * 9, Math.max(1.6, barWidth * .32), 0, Math.PI * 2);
          ctx.fill();
          ctx.beginPath();
          ctx.arc(x + barWidth / 2, baseY + d * 9, Math.max(1.6, barWidth * .32), 0, Math.PI * 2);
          ctx.fill();
        }
      } else {
        ctx.globalAlpha = .92;
        const y = style === 'mirror' ? baseY - amplitude : baseY - amplitude;
        roundRect(ctx, x, y, barWidth, amplitude * 2, Math.min(5, barWidth / 2));
        ctx.fill();
      }
    }
  } else if (style === 'hill' || style === 'fluid') {
    ctx.lineWidth = style === 'fluid' ? 4 : 3;
    ctx.beginPath();
    for (let i = 0; i < 110; i += 1) {
      const value = data[Math.floor(i / 110 * data.length)] / 255;
      const x = i / 109 * width;
      const movement = style === 'fluid' ? Math.sin(i * .21 + performance.now() / 470) * height * .065 : 0;
      const y = baseY - value * height * .39 * sensitivity - movement;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();
    if (style === 'fluid') {
      ctx.globalAlpha = .20;
      ctx.lineWidth = 15;
      ctx.stroke();
    }
  } else if (style === 'particles') {
    if (!spectrumParticles.length || spectrumParticles.some((particle) => particle.maxW !== width || particle.maxH !== height)) {
      spectrumParticles = Array.from({ length: 110 }, () => ({ x: Math.random() * width, y: Math.random() * height, vx: -.45 + Math.random() * .9, vy: -.45 + Math.random() * .9, size: 1 + Math.random() * 3, maxW: width, maxH: height }));
    }
    const energy = data.reduce((sum, value) => sum + value, 0) / data.length / 255;
    ctx.globalAlpha = .52 + energy * .46;
    spectrumParticles.forEach((particle) => {
      particle.x += particle.vx * (1 + energy * 3);
      particle.y += particle.vy * (1 + energy * 3);
      if (particle.x < 0 || particle.x > width || particle.y < 0 || particle.y > height) {
        particle.x = Math.random() * width;
        particle.y = Math.random() * height;
      }
      ctx.beginPath();
      ctx.arc(particle.x, particle.y, particle.size + energy * 3, 0, Math.PI * 2);
      ctx.fill();
    });
  }
  ctx.globalAlpha = 1;
}

function roundRect(ctx, x, y, width, height, radius) {
  const r = Math.min(radius, Math.abs(width) / 2, Math.abs(height) / 2);
  ctx.beginPath();
  ctx.roundRect ? ctx.roundRect(x, y, width, height, r) : ctx.rect(x, y, width, height);
}

function refreshPreviewArea() {
  const area = document.getElementById('preview-area');
  if (!area || !state.currentProject) return;
  area.innerHTML = renderPreviewInner(state.currentProject);
  if (state.currentProject.type === 'youtube_spectrum') startSpectrumLoop();
}

function setSaveIndicator(text, mode = '') {
  const node = document.getElementById('save-indicator');
  if (node) {
    node.textContent = text;
    node.className = `save-indicator ${mode}`;
  }
}

function scheduleSave(options = {}) {
  if (!state.currentProject) return;
  state.saving = true;
  setSaveIndicator('Modifications en cours…', 'is-saving');
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => saveProject(false, options), 650);
}

async function saveProject(showToast = false, options = {}) {
  if (!state.currentProject) return null;
  clearTimeout(saveTimer);
  state.saving = true;
  setSaveIndicator('Sauvegarde…', 'is-saving');
  try {
    const response = await api(`/api/projects/${state.currentProject.id}`, { method: 'PUT', json: { project: state.currentProject } });
    state.currentProject = response.project;
    state.lastSavedAt = Date.now();
    state.saving = false;
    const summaryIndex = state.projects.findIndex((project) => project.id === state.currentProject.id);
    if (summaryIndex >= 0) {
      const old = state.projects[summaryIndex];
      state.projects[summaryIndex] = { ...old, ...state.currentProject, playlistsCount: state.currentProject.playlists?.length || 0 };
    }
    setSaveIndicator(`Sauvegardé à ${new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}`, 'is-saved');
    if (showToast) toast('Projet sauvegardé.', 'success');
    if (state.currentProject.type !== 'youtube_spectrum' || options.forcePreview) {
      clearTimeout(previewTimer);
      previewTimer = setTimeout(() => loadPreview(state.currentProject.id), 80);
    }
    return response.project;
  } catch (error) {
    state.saving = false;
    setSaveIndicator('Échec de la sauvegarde', 'is-error');
    toast(error.message, 'error');
    return null;
  }
}

async function uploadFile(input) {
  const file = input.files?.[0];
  if (!file || !state.currentProject) return;
  const kind = input.dataset.uploadKind;
  const path = input.dataset.uploadPath;
  const form = new FormData();
  form.append('file', file);
  form.append('kind', kind);
  form.append('projectId', state.currentProject.id);
  input.disabled = true;
  toast(`Import de « ${file.name} »…`, 'info', 2200);
  try {
    const response = await api('/api/upload', { method: 'POST', body: form });
    const asset = response.asset;
    if (kind === 'font' && asset.font) {
      const font = asset.font;
      const existing = (state.config.fonts || []).findIndex((item) => item.id === font.id);
      if (existing >= 0) state.config.fonts[existing] = font;
      else state.config.fonts = [...(state.config.fonts || []), font];
      state.currentProject.typography = { fontId: font.id, fontName: font.name, fontUrl: font.url, cssFamily: font.cssFamily };
    } else if (path) {
      setPath(state.currentProject, path, asset.url);
    }
    if (kind === 'audio') {
      state.currentProject.audio.duration = Number(asset.duration || 0);
      state.currentProject.audio.start = 0;
      state.waveform = null;
      state.waveformUrl = '';
      syncAudioSource();
    }
    if (kind === 'background-video') state.currentProject.background.videoUrl = asset.url;
    asset.warnings?.forEach((warning) => toast(warning, 'warning', 5000));
    await saveProject(false, { forcePreview: true });
    renderPreservingFocus();
    if (kind === 'audio') requestWaveform();
    toast(kind === 'font' ? 'Police ajoutée et appliquée au projet.' : 'Média importé.', 'success');
  } catch (error) {
    toast(error.message, 'error', 5200);
  } finally {
    input.disabled = false;
    input.value = '';
  }
}

async function createProject(type) {
  const validType = type && MODULES[type] ? type : null;
  if (!validType || state.creatingProject) {
    state.modalError = 'Choisis le type de vidéo à créer.';
    renderPreservingFocus();
    return;
  }
  const name = String(state.modalProjectName || document.getElementById('new-project-name')?.value || '').trim() || 'Nouveau projet';
  state.creatingProject = true;
  state.modalError = '';
  renderPreservingFocus();
  try {
    const response = await api('/api/projects', { method: 'POST', json: { type: validType, name } });
    state.projects.unshift({ ...response.project, playlistsCount: response.project.playlists?.length || 0 });
    state.modal = null;
    state.modalLockedType = null;
    state.modalType = null;
    state.modalProjectName = '';
    state.creatingProject = false;
    render();
    await openProject(response.project.id);
  } catch (error) {
    state.creatingProject = false;
    state.modalError = error.message || 'Le projet n’a pas pu être créé.';
    renderPreservingFocus();
  }
}

async function duplicateProject(projectId) {
  try {
    const response = await api(`/api/projects/${projectId}/duplicate`, { method: 'POST' });
    state.projects.unshift({ ...response.project, playlistsCount: response.project.playlists?.length || 0 });
    toast('Projet dupliqué.', 'success');
    renderPreservingFocus();
  } catch (error) { toast(error.message, 'error'); }
}

async function deleteProject(projectId) {
  try {
    await api(`/api/projects/${projectId}`, { method: 'DELETE' });
    state.projects = state.projects.filter((project) => project.id !== projectId);
    state.modal = null;
    state.deleteProjectId = null;
    toast('Projet supprimé.', 'success');
    render();
  } catch (error) { toast(error.message, 'error'); }
}

async function renderProject() {
  const project = state.currentProject;
  if (!project) return;
  const errors = validationFor(project);
  if (errors.length) {
    toast(errors[0][1], 'warning');
    return;
  }
  const saved = await saveProject(false, { forcePreview: true });
  if (!saved) return;
  try {
    const response = await api(`/api/projects/${project.id}/render`, { method: 'POST' });
    state.renderJob = response.render;
    state.renderModalHidden = false;
    state.modal = 'render';
    renderPreservingFocus();
    pollRender(response.render.id);
  } catch (error) {
    const details = Array.isArray(error.details) ? error.details.map((item) => item.message).join(' ') : '';
    toast(`${error.message}${details ? ` ${details}` : ''}`, 'error', 6000);
  }
}

function pollRender(renderId) {
  clearInterval(renderPollTimer);
  const poll = async () => {
    try {
      const response = await api(`/api/renders/${renderId}`);
      state.renderJob = response.render;
      updateRenderProgressUI();
      if (response.render.status === 'Terminé') {
        clearInterval(renderPollTimer);
        await Promise.all([loadProjectRenders(response.render.projectId), loadAppData()]);
        if (state.renderModalHidden) {
          state.modal = null;
          toast('Le MP4 est prêt. Tu peux le télécharger depuis la barre de progression.', 'success', 6500);
        } else {
          state.modal = 'render-done';
        }
        renderPreservingFocus();
      } else if (response.render.status === 'Échec') {
        clearInterval(renderPollTimer);
        state.modal = null;
        toast(`Rendu échoué : ${response.render.error || 'erreur inconnue'}`, 'error', 7000);
        renderPreservingFocus();
      }
    } catch (error) {
      console.warn(error);
    }
  };
  poll();
  renderPollTimer = setInterval(poll, 1100);
}

function updateRenderProgressUI() {
  const job = state.renderJob || {};
  const modalTitle = document.querySelector('.render-modal h2');
  const modalBar = document.querySelector('.render-progress i');
  const modalPercent = document.querySelector('.render-percent');
  const persistentMessage = document.getElementById('persistent-render-message');
  const persistentBar = document.getElementById('persistent-render-progress');
  const persistentPercent = document.getElementById('persistent-render-percent');
  if (modalTitle) modalTitle.textContent = job.message || 'Encodage vidéo';
  if (modalBar) modalBar.style.width = `${clamp(job.progress, 0, 100)}%`;
  if (modalPercent) modalPercent.textContent = `${Math.round(job.progress || 0)} %`;
  if (persistentMessage) persistentMessage.textContent = job.message || job.status || 'Traitement';
  if (persistentBar) persistentBar.style.width = `${clamp(job.progress, 0, 100)}%`;
  if (persistentPercent) persistentPercent.textContent = `${Math.round(job.progress || 0)} %`;
}

async function uploadFontLibrary(input) {
  const files = Array.from(input.files || []).filter((file) => /\.(ttf|otf)$/i.test(file.name));
  input.value = '';
  if (!files.length) return toast('Sélectionne un fichier TTF ou OTF.', 'warning');
  let added = 0;
  for (const file of files) {
    const form = new FormData();
    form.append('file', file);
    form.append('kind', 'font');
    try {
      const response = await api('/api/upload', { method: 'POST', body: form });
      if (response.asset?.font) {
        const font = response.asset.font;
        const index = (state.config.fonts || []).findIndex((item) => item.id === font.id);
        if (index >= 0) state.config.fonts[index] = font;
        else state.config.fonts = [...(state.config.fonts || []), font];
        added += 1;
      }
    } catch (error) {
      toast(`${file.name} : ${error.message}`, 'error', 5200);
    }
  }
  if (added) toast(`${added} police${added > 1 ? 's' : ''} ajoutée${added > 1 ? 's' : ''}.`, 'success');
  renderPreservingFocus();
}

function addConversionFiles(fileList) {
  const accepted = [];
  const rejected = [];
  Array.from(fileList || []).forEach((file) => {
    if (!file || !file.name || file.size <= 0) rejected.push(file?.name || 'fichier vide');
    else if (!state.conversionFiles.some((item) => item.name === file.name && item.size === file.size && item.lastModified === file.lastModified)) accepted.push(file);
  });
  const available = Math.max(0, 30 - state.conversionFiles.length);
  state.conversionFiles.push(...accepted.slice(0, available));
  if (accepted.length > available) toast('Un lot est limité à 30 fichiers.', 'warning');
  if (rejected.length) toast(`${rejected.length} fichier(s) vide(s) ou illisible(s) ignoré(s).`, 'warning');
  renderPreservingFocus();
}

async function startConversion() {
  if (!state.conversionFiles.length || state.conversionUploading) return;
  const form = new FormData();
  state.conversionFiles.forEach((file) => form.append('files', file, file.name));
  state.conversionUploading = true;
  renderPreservingFocus();
  try {
    const response = await api('/api/conversions', { method: 'POST', body: form });
    state.conversionJob = response.conversion;
    state.conversionFiles = [];
    state.conversionUploading = false;
    state.conversions = [response.conversion, ...state.conversions.filter((item) => item.id !== response.conversion.id)];
    renderPreservingFocus();
    pollConversion(response.conversion.id);
  } catch (error) {
    state.conversionUploading = false;
    toast(error.message, 'error', 6500);
    renderPreservingFocus();
  }
}

function pollConversion(conversionId) {
  clearInterval(conversionPollTimer);
  const poll = async () => {
    try {
      const response = await api(`/api/conversions/${conversionId}`);
      state.conversionJob = response.conversion;
      const index = state.conversions.findIndex((item) => item.id === response.conversion.id);
      if (index >= 0) state.conversions[index] = response.conversion;
      else state.conversions.unshift(response.conversion);
      updateConversionProgressUI();
      if (['Terminé', 'Échec'].includes(response.conversion.status)) {
        clearInterval(conversionPollTimer);
        if (response.conversion.status === 'Terminé') toast(response.conversion.packageType === 'zip' ? 'Conversion terminée : le ZIP est prêt.' : 'Conversion terminée : le fichier est prêt.', 'success', 6000);
        else toast(`Conversion échouée : ${response.conversion.error || 'erreur inconnue'}`, 'error', 7000);
        renderPreservingFocus();
      }
    } catch (error) {
      console.warn(error);
    }
  };
  poll();
  conversionPollTimer = setInterval(poll, 900);
}

function updateConversionProgressUI() {
  const job = state.conversionJob || {};
  const message = document.getElementById('conversion-job-message');
  const bar = document.getElementById('conversion-job-progress');
  const percent = document.getElementById('conversion-job-percent');
  const persistentMessage = document.getElementById('persistent-conversion-message');
  const persistentBar = document.getElementById('persistent-conversion-progress');
  const persistentPercent = document.getElementById('persistent-conversion-percent');
  if (message) message.textContent = job.message || job.status || 'Traitement';
  if (bar) bar.style.width = `${clamp(job.progress, 0, 100)}%`;
  if (percent) percent.textContent = `${Math.round(job.progress || 0)} %`;
  if (persistentMessage) persistentMessage.textContent = job.message || job.status || 'Traitement';
  if (persistentBar) persistentBar.style.width = `${clamp(job.progress, 0, 100)}%`;
  if (persistentPercent) persistentPercent.textContent = `${Math.round(job.progress || 0)} %`;
}

async function logout() {
  try { await api('/api/logout', { method: 'POST' }); } catch { /* ignore */ }
  previewAudio.pause();
  state.user = null;
  state.projects = [];
  state.currentProject = null;
  state.modal = null;
  history.replaceState(null, '', location.pathname);
  render();
}

async function onClick(event) {
  const target = event.target.closest('[data-action]');
  if (!target) return;
  const action = target.dataset.action;
  if (action === 'reload') return location.reload();
  if (action === 'navigate') return go(target.dataset.route);
  if (action === 'logout') return logout();
  if (action === 'open-create') {
    state.modalLockedType = null; state.modalType = null; state.modalProjectName = ''; state.modalError = ''; state.creatingProject = false; state.modal = 'create'; renderPreservingFocus(); return;
  }
  if (action === 'create-type' || action === 'open-create-context') {
    state.modalLockedType = target.dataset.type; state.modalType = target.dataset.type; state.modalProjectName = ''; state.modalError = ''; state.creatingProject = false; state.modal = 'create'; renderPreservingFocus(); return;
  }
  if (action === 'select-create-type') {
    if (state.modalLockedType) return;
    state.modalType = target.dataset.type; state.modalError = ''; renderPreservingFocus(); return;
  }
  if (action === 'confirm-create') return createProject(state.modalLockedType || state.modalType);
  if (action === 'close-modal') {
    if (target.classList.contains('modal-backdrop') && event.target !== target) return;
    state.modal = null; state.modalLockedType = null; state.modalType = null; state.modalProjectName = ''; state.modalError = ''; state.creatingProject = false; renderPreservingFocus(); return;
  }
  if (action === 'hide-render-modal') { state.renderModalHidden = true; state.modal = null; renderPreservingFocus(); return; }
  if (action === 'show-render-modal') { state.renderModalHidden = false; state.modal = state.renderJob?.status === 'Terminé' ? 'render-done' : 'render'; renderPreservingFocus(); return; }
  if (action === 'dismiss-render-job') { state.renderJob = null; state.renderModalHidden = false; renderPreservingFocus(); return; }
  if (action === 'open-project') return openProject(target.dataset.id);
  if (action === 'duplicate-project') return duplicateProject(target.dataset.id);
  if (action === 'delete-project') { state.deleteProjectId = target.dataset.id; state.modal = 'confirm-delete'; renderPreservingFocus(); return; }
  if (action === 'confirm-delete') return deleteProject(state.deleteProjectId);
  if (action === 'filter-projects') { state.projectFilter = target.dataset.filter; go(`projects/${state.projectFilter}`); return; }
  if (action === 'editor-step') {
    state.editorStep = target.dataset.step;
    history.replaceState(null, '', `#/editor/${state.currentProject.id}/${state.editorStep}`);
    renderPreservingFocus();
    return;
  }
  if (action === 'save-now') return saveProject(true, { forcePreview: true });
  if (action === 'render-project') return renderProject();
  if (action === 'toggle-audio') return toggleAudio();
  if (action === 'add-playlist') {
    if (state.currentProject.playlists.length >= 6) return;
    state.currentProject.playlists.push({ id: uid(), platformId: state.config.platforms[0]?.id || 'spotify', title: '', coverUrl: '', iconTone: 'auto' });
    state.selectedPlaylist = state.currentProject.playlists.length - 1;
    scheduleSave({ forcePreview: true });
    renderPreservingFocus();
    return;
  }
  if (action === 'select-playlist') { state.selectedPlaylist = Number(target.dataset.index); renderPreservingFocus(); return; }
  if (action === 'remove-playlist') {
    state.currentProject.playlists.splice(Number(target.dataset.index), 1);
    state.selectedPlaylist = clamp(state.selectedPlaylist, 0, Math.max(0, state.currentProject.playlists.length - 1));
    scheduleSave({ forcePreview: true }); renderPreservingFocus(); return;
  }
  if (action === 'move-playlist') {
    const index = Number(target.dataset.index); const next = index + Number(target.dataset.direction);
    if (next < 0 || next >= state.currentProject.playlists.length) return;
    const [item] = state.currentProject.playlists.splice(index, 1); state.currentProject.playlists.splice(next, 0, item); state.selectedPlaylist = next;
    scheduleSave({ forcePreview: true }); renderPreservingFocus(); return;
  }
  if (action === 'set-icon-tone') {
    state.currentProject.playlists[Number(target.dataset.index)].iconTone = target.dataset.value;
    scheduleSave({ forcePreview: true }); renderPreservingFocus(); return;
  }
  if (action === 'set-release-type') { state.currentProject.newRelease.releaseType = target.dataset.value; scheduleSave({ forcePreview: true }); renderPreservingFocus(); return; }
  if (action === 'set-release-template') { state.currentProject.newRelease.template = target.dataset.value; scheduleSave({ forcePreview: true }); renderPreservingFocus(); return; }
  if (action === 'set-virgin-logo') { state.currentProject.newRelease.virginLogoTone = target.dataset.tone; state.currentProject.newRelease.virginLogoUrl = target.dataset.url; scheduleSave({ forcePreview: true }); renderPreservingFocus(); return; }
  if (action === 'set-brand-logo') { state.currentProject.branding.logoUrl = target.dataset.url; if (state.currentProject.type === 'youtube_spectrum') state.currentProject.branding.showLogo = true; scheduleSave({ forcePreview: true }); renderPreservingFocus(); return; }
  if (action === 'set-spectrum-style') { state.currentProject.spectrum.style = target.dataset.value; spectrumParticles = []; scheduleSave({ forcePreview: true }); renderPreservingFocus(); return; }
  if (action === 'jump-validation') {
    const label = target.dataset.stepLabel;
    const stepMap = { Projet: 'track', Morceau: state.currentProject.type === 'new_release' ? 'release' : 'track', Audio: 'audio', Fond: 'background', Visuel: 'background', Playlists: 'playlists', Branding: 'branding', Template: 'template', Spectrum: 'spectrum' };
    state.editorStep = stepMap[label] || 'track';
    history.replaceState(null, '', `#/editor/${state.currentProject.id}/${state.editorStep}`); renderPreservingFocus(); return;
  }
  if (action === 'remove-conversion-file') { state.conversionFiles.splice(Number(target.dataset.index), 1); renderPreservingFocus(); return; }
  if (action === 'clear-conversion-files') { state.conversionFiles = []; renderPreservingFocus(); return; }
  if (action === 'start-conversion') return startConversion();
  if (action === 'refresh-health') { await loadHealth(); renderPreservingFocus(); return; }
}

function onInput(event) {
  const target = event.target;
  if (target.dataset.action === 'new-project-name') {
    state.modalProjectName = target.value;
    return;
  }
  if (target.dataset.action === 'search') {
    state.search = target.value;
    const content = document.querySelector('.page-content');
    if (state.view === 'dashboard' || state.view === 'projects') content.innerHTML = renderCurrentPage();
    return;
  }
  if (target.dataset.bind && state.currentProject) {
    const path = target.dataset.bind;
    let value = target.value;
    if (target.type === 'range' || target.type === 'number') value = Number(value);
    if (path === 'track.guestsText') {
      state.currentProject.track.guests = String(value).split(',').map((item) => item.trim()).filter(Boolean);
    } else {
      setPath(state.currentProject, path, value);
    }
    const output = document.querySelector(`[data-output-for="${CSS.escape(path)}"]`);
    if (output) output.textContent = `${Number(value).toFixed(Number(target.step) < 1 ? 2 : 0)}${path.includes('.x') || path.includes('.y') ? '%' : path.includes('zoom') || path.includes('sensitivity') ? '×' : ''}`;
    const needsExactSpectrumPreview = state.currentProject.type === 'youtube_spectrum' && (path.startsWith('track.') || path.startsWith('background.') || path.startsWith('branding.') || path.startsWith('typography.') || path.startsWith('spectrum.titleColor') || path.startsWith('spectrum.artistColor'));
    scheduleSave({ forcePreview: state.currentProject.type !== 'youtube_spectrum' || needsExactSpectrumPreview });
    if (state.currentProject.type === 'youtube_spectrum' && (path.startsWith('spectrum.') || path.startsWith('background.'))) refreshPreviewArea();
  }
  if (target.dataset.action === 'audio-range' && state.currentProject) {
    const value = Number(target.value);
    if (state.currentProject.type === 'youtube_spectrum') {
      previewAudio.currentTime = value;
      if (previewAudio.paused) toggleAudio();
    } else {
      state.currentProject.audio.start = value;
      scheduleSave({ forcePreview: false });
      drawWaveform();
      playSelectedRange(true);
      const startInput = document.querySelector('[data-action="audio-start-time"]');
      if (startInput) startInput.value = formatDuration(value, true);
      const endInput = startInput?.closest('.audio-time-fields')?.querySelector('input[disabled]');
      if (endInput) endInput.value = formatDuration(value + 20, true);
    }
  }
}

function onChange(event) {
  const target = event.target;
  if (target.dataset.action === 'font-library-files') return uploadFontLibrary(target);
  if (target.dataset.action === 'conversion-files') {
    addConversionFiles(target.files);
    target.value = '';
    return;
  }
  if (target.dataset.action === 'project-font-select' && state.currentProject) {
    const font = (state.config.fonts || []).find((item) => item.id === target.value);
    if (!font) return;
    state.currentProject.typography = { fontId: font.id, fontName: font.name, fontUrl: font.url || '', cssFamily: font.cssFamily || 'Arial, Helvetica, sans-serif' };
    scheduleSave({ forcePreview: true });
    renderPreservingFocus();
    return;
  }
  if (target.matches('[data-upload-kind]')) return uploadFile(target);
  if (target.dataset.bind && state.currentProject) {
    const path = target.dataset.bind;
    const value = target.type === 'checkbox' ? target.checked : target.type === 'number' || target.type === 'range' ? Number(target.value) : target.value;
    setPath(state.currentProject, path, value);
    if (path === 'branding.showLogo' && value && !state.currentProject.branding.logoUrl) {
      state.currentProject.branding.logoUrl = '/static/brand/spectoom-white.png';
    }
    const needsExactSpectrumPreview = state.currentProject.type === 'youtube_spectrum' && (path.startsWith('track.') || path.startsWith('background.') || path.startsWith('branding.') || path.startsWith('typography.') || path.startsWith('spectrum.titleColor') || path.startsWith('spectrum.artistColor'));
    scheduleSave({ forcePreview: state.currentProject.type !== 'youtube_spectrum' || needsExactSpectrumPreview });
    renderPreservingFocus();
    return;
  }
  if (target.dataset.action === 'audio-start-time' && state.currentProject) {
    const parsed = parseTimecode(target.value);
    if (parsed == null) { target.value = formatDuration(state.currentProject.audio.start || 0, true); toast('Timecode invalide. Utilise mm:ss.mmm.', 'warning'); return; }
    state.currentProject.audio.start = clamp(parsed, 0, Math.max(0, state.currentProject.audio.duration - 20));
    scheduleSave();
    renderPreservingFocus();
    playSelectedRange(true);
  }
}

document.addEventListener('submit', async (event) => {
  const createForm = event.target.closest('[data-form="create-project"]');
  if (createForm) {
    event.preventDefault();
    await createProject(state.modalLockedType || state.modalType);
    return;
  }
  const form = event.target.closest('[data-form="login"]');
  if (!form) return;
  event.preventDefault();
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  button.textContent = 'Connexion…';
  try {
    const values = new FormData(form);
    const response = await api('/api/login', { method: 'POST', json: { email: values.get('email'), password: values.get('password') } });
    state.user = response.user;
    await loadAppData();
    go('dashboard');
    render();
  } catch (error) {
    toast(error.message, 'error');
    button.disabled = false;
    button.innerHTML = `Se connecter ${icon('arrow', 18)}`;
  }
});

window.addEventListener('resize', () => {
  drawWaveform();
});

init();
