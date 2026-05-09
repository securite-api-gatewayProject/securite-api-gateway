const authStatus = document.getElementById('authStatus');
const kongStatus = document.getElementById('kongStatus');
const suricataStatus = document.getElementById('suricataStatus');
const kongConfig = document.getElementById('kongConfig');
const suricataConfig = document.getElementById('suricataConfig');
const suricataAlerts = document.getElementById('suricataAlerts');
const apiResponse = document.getElementById('apiResponse');
const jwtToken = document.getElementById('jwtToken');
const quickStats = document.getElementById('quickStats');
let kongSectionLoaded = false;
let suricataSectionLoaded = false;
let currentSection = 'overview';
let overviewLoading = false;

function pretty(value) {
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2);
}

function readToken() {
  return localStorage.getItem('admin_jwt_token') || '';
}

function saveToken(token) {
  localStorage.setItem('admin_jwt_token', token);
  jwtToken.value = token;
}

function setupNavigation() {
  const buttons = document.querySelectorAll('.nav-link-btn');
  const sections = document.querySelectorAll('.section-panel');

  async function activate(sectionName) {
    currentSection = sectionName;

    buttons.forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.section === sectionName);
    });

    sections.forEach((section) => {
      section.classList.toggle('active', section.id === `section-${sectionName}`);
    });

    if (sectionName === 'kong' && !kongSectionLoaded) {
      await loadKongSection();
    }

    if (sectionName === 'suricata' && !suricataSectionLoaded) {
      await loadSuricataSection();
    }
  }

  buttons.forEach((button) => {
    button.addEventListener('click', async () => activate(button.dataset.section));
  });
}

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  const text = await response.text();
  let body;
  try {
    body = text ? JSON.parse(text) : {};
  } catch {
    body = { raw: text };
  }
  return { response, body };
}

async function loadOverview() {
  if (overviewLoading) {
    return;
  }

  overviewLoading = true;
  const token = readToken();
  if (token) jwtToken.value = token;

  try {
    const { body } = await fetchJSON('/api/status');

    authStatus.textContent = pretty({
      session_user: body.admin_user,
      jwt_cached: Boolean(token),
    });

    kongStatus.textContent = pretty({
      ok: body.kong?.ok,
      services: body.kong?.services_count || 0,
      routes: body.kong?.routes_count || 0,
      plugins: body.kong?.plugins_count || 0,
      error: body.kong?.error,
    });

    suricataStatus.textContent = pretty({
      config_path: body.suricata?.config_path,
      eve_path: body.suricata?.eve_path,
      recent_alerts_count: body.suricata?.recent_alerts_count,
    });

    quickStats.textContent = [
      `Services Kong: ${body.kong?.services_count || 0}`,
      `Routes Kong: ${body.kong?.routes_count || 0}`,
      `Plugins Kong: ${body.kong?.plugins_count || 0}`,
      `Alertes Suricata recentes: ${body.suricata?.recent_alerts_count || 0}`,
      `JWT local cache: ${token ? 'oui' : 'non'}`,
    ].join('\n');
  } catch (error) {
    if (quickStats) {
      quickStats.textContent = 'Erreur de chargement des statistiques';
    }
    apiResponse.textContent = `Unable to load dashboard: ${error.message}`;
  } finally {
    overviewLoading = false;
  }
}

async function loadKongSection() {
  try {
    const { body } = await fetchJSON('/api/kong/config');
    kongConfig.textContent = pretty(body);
    kongSectionLoaded = true;
  } catch (error) {
    kongConfig.textContent = `Unable to load Kong config: ${error.message}`;
  }
}

async function loadSuricataSection() {
  try {
    const [cfg, alerts] = await Promise.all([
      fetchJSON('/api/suricata/config'),
      fetchJSON('/api/suricata/alerts'),
    ]);
    suricataConfig.textContent = cfg.body.content || pretty(cfg.body);
    suricataAlerts.textContent = pretty(alerts.body);
    suricataSectionLoaded = true;
  } catch (error) {
    suricataConfig.textContent = `Unable to load Suricata config: ${error.message}`;
  }
}

async function refreshActiveSection() {
  if (document.hidden) {
    return;
  }

  await loadOverview();

  if (currentSection === 'kong') {
    await loadKongSection();
  }

  if (currentSection === 'suricata') {
    await loadSuricataSection();
  }
}

document.getElementById('loginForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const username = document.getElementById('loginUsername').value;
  const password = document.getElementById('loginPassword').value;

  const { response, body } = await fetchJSON('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });

  if (response.ok && body.access_token) {
    saveToken(body.access_token);
    apiResponse.textContent = pretty({ message: 'JWT loaded from user-service', ...body });
    await loadOverview();
    return;
  }

  apiResponse.textContent = pretty(body);
});

document.getElementById('serviceTestForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const service = document.getElementById('serviceTarget').value;
  const method = document.getElementById('httpMethod').value;
  const path = document.getElementById('requestPath').value.trim();
  const rawBody = document.getElementById('requestBody').value.trim();
  const token = readToken();

  let body = null;
  if (rawBody) {
    try {
      body = JSON.parse(rawBody);
    } catch (error) {
      apiResponse.textContent = `Invalid JSON body: ${error.message}`;
      return;
    }
  }

  const { response, body: responseBody } = await fetchJSON(`/api/test/${service}`, {
    method: 'POST',
    body: JSON.stringify({ path, method, token, body }),
  });

  apiResponse.textContent = pretty({
    http_status: response.status,
    ...responseBody,
  });
});

setupNavigation();
loadOverview();
setInterval(refreshActiveSection, 10000);
