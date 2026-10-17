// SPDX-FileCopyrightText: 2026 mothue
// SPDX-License-Identifier: AGPL-3.0-only

export function dateInJapan(instant = new Date()) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Tokyo', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(instant);
  const value = type => parts.find(part => part.type === type).value;
  return `${value('year')}-${value('month')}-${value('day')}`;
}

export function selectMenus(menus, today = dateInJapan()) {
  const byRevision = (a, b) => Number(b.preferred === true) - Number(a.preferred === true) || b.seq - a.seq;
  const revisions = [...menus].sort(byRevision);
  const current = revisions.find(menu => menu.start_date <= today && today <= menu.end_date) ?? null;
  const upcoming = revisions.filter(menu => menu.start_date > today)
    .sort((a, b) => a.start_date.localeCompare(b.start_date) || byRevision(a, b))[0] ?? null;
  return { current, upcoming };
}
