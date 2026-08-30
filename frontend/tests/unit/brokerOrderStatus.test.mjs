import test from 'node:test'
import assert from 'node:assert/strict'

import { brokerOrderStatusColor } from '../../src/utils/brokerOrderStatus.js'

test('neutral terminal order statuses render with the default tag style', () => {
  for (const status of ['canceled', 'cancelled', 'expired', 'done_for_day']) {
    assert.equal(brokerOrderStatusColor(status), undefined)
  }
})

test('order status colors use only valid Ant Design presets', () => {
  assert.equal(brokerOrderStatusColor('filled'), 'green')
  assert.equal(brokerOrderStatusColor('rejected'), 'red')
  assert.equal(brokerOrderStatusColor('partially_filled'), 'blue')
  assert.equal(brokerOrderStatusColor('pending_new'), 'blue')
  assert.equal(brokerOrderStatusColor('unknown'), 'orange')

  const validColors = new Set(['green', 'red', 'blue', 'orange'])
  for (const status of ['filled', 'rejected', 'partially_filled', 'new', 'unknown']) {
    assert.ok(validColors.has(brokerOrderStatusColor(status)))
  }
})
