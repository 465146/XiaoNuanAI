// ── Token 管理 ──
function getToken() {
  return localStorage.getItem('xiaonuan_token');
}

function getUser() {
  const raw = localStorage.getItem('xiaonuan_user');
  return raw ? JSON.parse(raw) : null;
}

function isLoggedIn() {
  return !!getToken();
}

function logout() {
  localStorage.removeItem('xiaonuan_token');
  localStorage.removeItem('xiaonuan_user');
  window.location.href = '/login';
}

// 检查登录态
if (window.location.pathname !== '/login') {
  if (!isLoggedIn()) {
    window.location.href = '/login';
  }
}

// 鉴权 fetch 封装
async function authFetch(url, options = {}) {
  const token = getToken();
  if (!token) {
    window.location.href = '/login';
    throw new Error('未登录');
  }
  const headers = { ...options.headers, 'Authorization': `Bearer ${token}` };
  return fetch(url, { ...options, headers });
}

// 页面加载时显示用户信息
(function initUserBar() {
  const user = getUser();
  if (user) {
    const el = document.getElementById('userDisplay');
    if (el) el.textContent = user.username;
  }
  const logoutBtn = document.getElementById('logoutBtn');
  if (logoutBtn) logoutBtn.addEventListener('click', logout);
})();
