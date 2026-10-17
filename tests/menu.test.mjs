// SPDX-FileCopyrightText: 2026 mothue
// SPDX-License-Identifier: AGPL-3.0-only

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { dateInJapan, selectMenus } from '../site/menu.mjs';

const thisWeek = { seq: 7, start_date: '2026-10-12', end_date: '2026-10-18', path: 'archive/current.pdf' };
const nextWeek = { seq: 8, start_date: '2026-10-19', end_date: '2026-10-25', path: 'archive/next.pdf' };
const menus = [nextWeek, thisWeek];

test('Saturday still shows this week after the next PDF arrives', () => {
  const selection = selectMenus(menus, '2026-10-17');
  assert.equal(selection.current?.path, 'archive/current.pdf');
  assert.equal(selection.upcoming?.path, 'archive/next.pdf');
});

test('Japan midnight switches Sunday to Monday without another fetch', () => {
  const sunday = dateInJapan(new Date('2026-10-18T14:59:59Z'));
  const monday = dateInJapan(new Date('2026-10-18T15:00:00Z'));
  assert.equal(sunday, '2026-10-18');
  assert.equal(monday, '2026-10-19');
  assert.equal(selectMenus(menus, sunday).current?.path, 'archive/current.pdf');
  assert.equal(selectMenus(menus, monday).current?.path, 'archive/next.pdf');
});

test('does not present an old or future menu as current when today is missing', () => {
  assert.equal(selectMenus(menus, '2026-10-26').current, null);
  assert.equal(selectMenus([nextWeek], '2026-10-17').current, null);
});

test('a same-period revision wins regardless of index order', () => {
  const revision = { ...thisWeek, seq: 9, path: 'archive/revised.pdf' };
  assert.equal(selectMenus([revision, nextWeek, thisWeek], '2026-10-17').current?.path,
    'archive/revised.pdf');
});

test('upcoming chooses the nearest period and its latest revision', () => {
  const later = { seq: 10, start_date: '2026-11-02', end_date: '2026-11-08', path: 'later.pdf' };
  const revision = { ...nextWeek, seq: 11, path: 'revision.pdf' };
  assert.equal(selectMenus([later, nextWeek, revision], '2026-10-17').upcoming?.path, 'revision.pdf');
});

test('partial and year-crossing periods follow printed dates', () => {
  const short = { seq: 1, start_date: '2026-09-30', end_date: '2026-10-04', path: 'short.pdf' };
  const newYear = { seq: 2, start_date: '2026-12-28', end_date: '2027-01-03', path: 'newyear.pdf' };
  assert.equal(selectMenus([short], '2026-09-29').current, null);
  assert.equal(selectMenus([short], '2026-09-30').current?.path, 'short.pdf');
  assert.equal(selectMenus([short], '2026-10-05').current, null);
  assert.equal(selectMenus([newYear], '2027-01-01').current?.path, 'newyear.pdf');
});

test('empty index has neither current nor upcoming menu', () => {
  assert.equal(selectMenus([], '2026-10-17').current, null);
  assert.equal(selectMenus([], '2026-10-17').upcoming, null);
});

test('a restored official version wins over a withdrawn revision for current and upcoming', () => {
  const original = { ...thisWeek, preferred: true };
  const withdrawn = { ...thisWeek, seq: 9, preferred: false, path: 'withdrawn.pdf' };
  const versions = [withdrawn, original, nextWeek];
  assert.equal(selectMenus(versions, '2026-10-17').current?.path, 'archive/current.pdf');
  assert.equal(selectMenus(versions, '2026-10-11').upcoming?.path, 'archive/current.pdf');
});
