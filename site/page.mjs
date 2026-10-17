// SPDX-FileCopyrightText: 2026 mothue
// SPDX-License-Identifier: AGPL-3.0-only

import { dateInJapan, selectMenus } from './menu.mjs';

const status = document.querySelector('#menu-status');
const current = document.querySelector('#current-menu');
const upcoming = document.querySelector('#upcoming-menu');
const archive = document.querySelector('#archive-list');
const mirror = document.querySelector('#latest-menu');
let state;
let displayedDay;

function period(menu) {
  return `${menu.start_date} 〜 ${menu.end_date}`;
}

function menuLink(menu, label) {
  const link = document.createElement('a');
  link.href = `./${menu.path}`;
  link.textContent = `${label}（${period(menu)}）`;
  return link;
}

function render() {
  if (!state) return;
  const today = dateInJapan();
  displayedDay = today;
  const selection = selectMenus(state.menus, today);
  status.textContent = selection.current
    ? `今日：${today}（日本時間）。今日を含む献立を表示しています。`
    : `今日：${today}（日本時間）。今日を含む献立はまだ取得できていません。保存済みの献立や公式PDFをご確認ください。`;
  current.replaceChildren();
  if (selection.current) current.append(menuLink(selection.current, '今日の献立PDFを開く'));
  upcoming.replaceChildren();
  upcoming.hidden = !selection.upcoming;
  if (selection.upcoming) upcoming.append(menuLink(selection.upcoming, '次の献立PDFを開く'));
  archive.replaceChildren();
  const menus = [...state.menus].sort((a, b) =>
    b.start_date.localeCompare(a.start_date) || Number(b.preferred === true) - Number(a.preferred === true) || b.seq - a.seq);
  for (const menu of menus) {
    const item = document.createElement('li');
    const revised = menu.preferred === false;
    item.append(menuLink(menu, revised ? '献立PDF・差し替え前' : '献立PDF'));
    archive.append(item);
  }
  if (!menus.length) archive.textContent = '保存済みの献立はありません。';
  mirror.replaceChildren(menuLink({ path: state.latest_pdf_path,
    start_date: state.latest_week_start, end_date: state.latest_week_end }, '最後に取得したPDF'));
}

async function refresh() {
  try {
    const response = await fetch('./state.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const next = await response.json();
    if (!Array.isArray(next.menus)) throw new Error('Menu index is missing');
    state = next;
    render();
  } catch (error) {
    if (state) render();
    else status.textContent = '献立一覧を読み込めませんでした。再読み込みするか、公式PDFをご確認ください。';
    console.error('Could not load menu index:', error);
  }
}

await refresh();
// Re-select by today's date even when the source PDF and Actions have not changed.
setInterval(() => {
  if (state && dateInJapan() !== displayedDay) render();
}, 1000);
setInterval(refresh, 5 * 60 * 1000);
window.addEventListener('focus', refresh);
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) void refresh();
});
