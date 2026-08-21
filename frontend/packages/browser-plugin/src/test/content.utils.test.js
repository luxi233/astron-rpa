/** @format */
import { expect, test } from 'vitest';
import { Utils } from '../content/utils';

const {  isNumberStartString, isSupportUrl, isDynamicId } = Utils;

test('isNumberStartString', () => {
  expect(isNumberStartString('123abc')).toBe(true);
  expect(isNumberStartString('abc123')).toBe(false);
})

test('isSupportUrl', () => {
  expect(isSupportUrl('https://www.example.com')).toBe(true);
  expect(isSupportUrl('http://www.example.com')).toBe(true);
  expect(isSupportUrl('ftp://www.example.com')).toBe(true);
  expect(isSupportUrl('file://www.example.com')).toBe(true);
  expect(isSupportUrl('chrome://extensions')).toBe(false);
})

test('isDynamicId rejects pure-number/uuid/long-random ids', () => {
  // 纯数字(递增主键/时间戳)
  expect(isDynamicId('123456')).toBe(true);
  // uuid
  expect(isDynamicId('550e8400-e29b-41d4-a716-446655440000')).toBe(true);
  // 长随机串(>=20 且含数字)
  expect(isDynamicId('item-8f3a2b1c9d0e47f6a5b2')).toBe(true);
  // 动态关键词
  expect(isDynamicId('session-abc')).toBe(true);
  expect(isDynamicId('token-xyz')).toBe(true);
})

test('isDynamicId keeps stable ids containing digits', () => {
  // 含数字但稳定的 id 不再被弃用
  expect(isDynamicId('tab-1')).toBe(false);
  expect(isDynamicId('user-panel')).toBe(false);
  expect(isDynamicId('nav-item-2')).toBe(false);
  // 长语义 id(纯单词)保留
  expect(isDynamicId('customer-order-summary')).toBe(false);
  expect(isDynamicId('')).toBe(false);
})


