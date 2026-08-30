/**
 * Render in-app notifications from payload.display with legacy fallbacks.
 */

const DASH = '-'

function stripHtml (input) {
  if (!input) return ''
  return String(input)
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/p>/gi, '\n')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/\s+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .replace(/[ \t]{2,}/g, ' ')
    .trim()
}

function escapeHtml (text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function tx (t, key, fallback, params = {}) {
  let value = ''
  try {
    value = t(key, params)
  } catch (e) {
    value = ''
  }
  return value && value !== key ? value : fallback
}

function parseLegacyLoginNickname (item) {
  const msg = stripHtml((item && item.message) || '')
  const zh = msg.match(/账号\s+(\S+)\s+于/)
  if (zh) return zh[1]
  const en = msg.match(/Account\s+(\S+)\s+signed/i)
  if (en) return en[1]
  return DASH
}

function displayOf (item) {
  const p = item && item.payload
  if (p && p.display) return p.display

  const st = (item && item.signal_type) || ''
  if (st === 'profile_test' || (p && p.event === 'qd.profile_test')) {
    return { template: 'profile.test', params: {} }
  }
  if (st === 'indicator_signal' || (p && (p.event === 'qd.indicator_signal' || p.kind === 'indicator_signal'))) {
    const payload = p || {}
    const indicator = payload.indicator || {}
    const instrument = payload.instrument || {}
    const sig = payload.signal || {}
    const alert = payload.alert || {}
    return {
      template: 'indicator.signal',
      params: {
        indicatorName: indicator.name || payload.indicator_name || item.title || '',
        indicatorId: indicator.id || payload.indicator_id || '',
        market: instrument.market || payload.market || '',
        symbol: instrument.symbol || payload.symbol || item.symbol || '',
        symbolName: instrument.name || payload.symbol_name || '',
        timeframe: instrument.timeframe || payload.timeframe || '',
        signalType: sig.type || payload.signal_type || '',
        signalLabel: sig.label || payload.label || '',
        signalSide: sig.side || '',
        price: sig.price != null ? String(sig.price) : (payload.price != null ? String(payload.price) : ''),
        signalBarTime: sig.bar_time || sig.barTime || '',
        notifyBarTime: sig.notify_bar_time || sig.notifyBarTime || payload.timestamp_display || '',
        taskId: alert.task_id || payload.task_id || ''
      }
    }
  }
  if (st === 'security_login' || (p && p.event === 'security.login')) {
    let reasonKey = 'unknown'
    if (p && p.is_new_device && p.is_new_region) reasonKey = 'both'
    else if (p && p.is_new_device) reasonKey = 'newDevice'
    else if (p && p.is_new_region) reasonKey = 'newRegion'
    else if ((item.title || '').includes('New device')) reasonKey = 'newDevice'
    else if ((item.title || '').includes('New region')) reasonKey = 'newRegion'

    const det = (p && p.details) || {}
    return {
      template: 'security.login',
      params: {
        nickname: (p && (p.nickname || det.nickname)) || parseLegacyLoginNickname(item),
        action: (p && p.action) || det.action || '',
        provider: det.provider || (p && p.provider) || '',
        device: (p && p.device) || det.device_label || '',
        location: (p && p.location) || det.location || '',
        ip: (p && (p.ip || p.ip_address)) || DASH,
        reasonKey
      }
    }
  }
  if (p && p.event === 'qd.signal') {
    const strategy = p.strategy || {}
    const instrument = p.instrument || {}
    const sig = p.signal || {}
    const order = p.order || {}
    const trace = p.trace || {}
    return {
      template: 'signal.trade',
      params: {
        strategyName: strategy.name || '',
        strategyId: strategy.id || 0,
        symbol: instrument.symbol || item.symbol || '',
        signalType: sig.type || st || '',
        action: (sig.action || '').toUpperCase(),
        side: (sig.side || '').toUpperCase(),
        price: order.ref_price != null ? String(order.ref_price) : '',
        stake: order.stake_amount != null ? String(order.stake_amount) : '',
        pendingOrderId: trace.pending_order_id || '',
        mode: trace.mode || '',
        timestampDisplay: p.timestamp_display || '',
        timeLabel: p.time_label || ''
      }
    }
  }
  return null
}

function loginReasonLabel (reasonKey, t) {
  const map = {
    newDevice: ['notice.event.login.reason.newDevice', 'New device'],
    newRegion: ['notice.event.login.reason.newRegion', 'New region'],
    both: ['notice.event.login.reason.both', 'New device & region'],
    unknown: ['notice.event.login.reason.unknown', 'Unusual sign-in']
  }
  const pair = map[reasonKey || 'unknown'] || map.unknown
  return tx(t, pair[0], pair[1])
}

function loginMethodLabel (params, t) {
  const action = (params.action || '').trim()
  const provider = (params.provider || 'OAuth').trim()
  if (action === 'login_via_code') {
    return tx(t, 'notice.event.login.method.code', 'Email code login')
  }
  if (action === 'oauth_login') {
    return tx(t, 'notice.event.login.method.oauth', `${provider} login`, { provider })
  }
  return tx(t, 'notice.event.login.method.password', 'Password login')
}

function metricHtml (label, value, extraClass = '') {
  return `
    <div class="qd-notice-card__metric ${extraClass}">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value || DASH)}</strong>
    </div>`
}

function renderIndicatorSignal (p, t, { html = false } = {}) {
  const side = String(p.signalSide || '').toLowerCase()
  const sideClass = ['buy', 'sell', 'watch'].includes(side) ? side : 'neutral'
  const indicatorName = p.indicatorName || 'Indicator'
  const signalLabel = p.signalLabel || p.signalType || 'Signal'
  const symbolText = [p.symbol || '', p.symbolName || ''].filter(Boolean).join(' / ') || DASH
  const title = tx(t, 'notice.event.indicatorSignal.title', 'Indicator signal: {name}', { name: indicatorName })
  const labels = {
    kicker: tx(t, 'notice.event.indicatorSignal.kicker', 'Indicator signal'),
    indicator: tx(t, 'notice.event.indicatorSignal.field.indicator', 'Indicator'),
    signal: tx(t, 'notice.event.indicatorSignal.field.signal', 'Signal'),
    symbol: tx(t, 'notice.event.indicatorSignal.field.symbol', 'Symbol'),
    timeframe: tx(t, 'notice.event.indicatorSignal.field.timeframe', 'Timeframe'),
    price: tx(t, 'notice.event.indicatorSignal.field.price', 'Trigger price'),
    signalBar: tx(t, 'notice.event.indicatorSignal.field.signalBar', 'Signal candle'),
    notifyBar: tx(t, 'notice.event.indicatorSignal.field.notifyBar', 'Notification candle'),
    note: tx(t, 'notice.event.indicatorSignal.note', 'Confirmed on a closed candle and delivered on the next candle.')
  }
  const rows = [
    [labels.indicator, indicatorName],
    [labels.signal, signalLabel],
    [labels.symbol, symbolText],
    [labels.timeframe, p.timeframe || DASH],
    [labels.price, p.price || DASH],
    [labels.signalBar, p.signalBarTime || DASH],
    [labels.notifyBar, p.notifyBarTime || DASH]
  ]
  if (!html) {
    return {
      title,
      message: rows.map(([label, value]) => `${label}: ${value}`).concat(labels.note).join('\n')
    }
  }
  const message = `
    <div class="qd-notice-card qd-notice-card--indicator qd-notice-card--${sideClass}">
      <div class="qd-notice-card__hero">
        <div>
          <div class="qd-notice-card__kicker">${escapeHtml(labels.kicker)}</div>
          <div class="qd-notice-card__title">${escapeHtml(indicatorName)}</div>
        </div>
        <div class="qd-notice-card__chip">${escapeHtml(signalLabel)}</div>
      </div>
      <div class="qd-notice-card__grid">
        ${metricHtml(labels.symbol, symbolText)}
        ${metricHtml(labels.timeframe, p.timeframe || DASH)}
        ${metricHtml(labels.price, p.price || DASH, 'is-price')}
        ${metricHtml(labels.signalBar, p.signalBarTime || DASH)}
        ${metricHtml(labels.notifyBar, p.notifyBarTime || DASH)}
      </div>
      <div class="qd-notice-card__note">${escapeHtml(labels.note)}</div>
    </div>`
  return { title, message }
}

function renderSignalTrade (p, t, { html = false } = {}) {
  const action = String(p.action || '').trim().toUpperCase()
  const side = String(p.side || '').trim().toUpperCase()
  const title = tx(t, 'notice.event.signal.title', 'QD Signal | {symbol} | {action} {side}', {
    symbol: p.symbol || DASH,
    action: action || DASH,
    side
  }).replace(/\s+/g, ' ').trim()
  const labels = {
    kicker: tx(t, 'notice.event.signal.kicker', 'Strategy signal'),
    strategy: tx(t, 'notice.event.signal.field.strategy', 'Strategy'),
    symbol: tx(t, 'notice.event.signal.field.symbol', 'Symbol'),
    signal: tx(t, 'notice.event.signal.field.signal', 'Signal'),
    price: tx(t, 'notice.event.signal.field.price', 'Reference price'),
    stake: tx(t, 'notice.event.signal.field.stake', 'Stake'),
    pending: tx(t, 'notice.event.signal.field.pending', 'Pending order'),
    mode: tx(t, 'notice.event.signal.field.mode', 'Mode'),
    time: p.timeLabel || tx(t, 'notice.event.signal.timeLabel', 'Time')
  }
  const strategy = `${p.strategyName || DASH}${p.strategyId ? ` (#${p.strategyId})` : ''}`
  const rows = [
    [labels.strategy, strategy],
    [labels.symbol, p.symbol || DASH],
    [labels.signal, p.signalType || DASH]
  ]
  if (p.price) rows.push([labels.price, p.price])
  if (p.stake) rows.push([labels.stake, p.stake])
  if (p.pendingOrderId) rows.push([labels.pending, p.pendingOrderId])
  if (p.mode) rows.push([labels.mode, p.mode])
  if (p.timestampDisplay) rows.push([labels.time, p.timestampDisplay])
  if (!html) {
    return { title, message: rows.map(([label, value]) => `${label}: ${value}`).join('\n') }
  }
  const sideClass = side === 'SHORT' || action === 'CLOSE' || action === 'SELL' ? 'sell' : (side === 'LONG' || action === 'BUY' || action === 'OPEN' ? 'buy' : 'neutral')
  const message = `
    <div class="qd-notice-card qd-notice-card--signal qd-notice-card--${sideClass}">
      <div class="qd-notice-card__hero">
        <div>
          <div class="qd-notice-card__kicker">${escapeHtml(labels.kicker)}</div>
          <div class="qd-notice-card__title">${escapeHtml(p.symbol || DASH)}</div>
        </div>
        <div class="qd-notice-card__chip">${escapeHtml([action, side].filter(Boolean).join(' ') || p.signalType || 'Signal')}</div>
      </div>
      <div class="qd-notice-card__grid">
        ${rows.map(([label, value], index) => metricHtml(label, value, index === 0 ? 'is-wide' : '')).join('')}
      </div>
    </div>`
  return { title, message }
}

function renderSecurityLogin (p, t, { html = false } = {}) {
  const reason = loginReasonLabel(p.reasonKey, t)
  const title = tx(t, 'notice.event.login.title', 'QuantDinger login alert - {reason}', { reason })
  const rows = [
    [tx(t, 'notice.event.login.field.account', 'Account'), p.nickname || DASH],
    [tx(t, 'notice.event.login.field.method', 'Method'), loginMethodLabel(p, t)],
    [tx(t, 'notice.event.login.field.device', 'Device'), p.device || DASH],
    [tx(t, 'notice.event.login.field.location', 'Location'), p.location || DASH],
    [tx(t, 'notice.event.login.field.ip', 'IP'), p.ip || DASH]
  ]
  const footer = tx(t, 'notice.event.login.footer', 'If this was not you, change your password immediately and review exchange API permissions.')
  if (!html) {
    return { title, message: rows.map(([label, value]) => `${label}: ${value}`).concat(footer).join('\n') }
  }
  const message = `
    <div class="qd-notice-card qd-notice-card--security qd-notice-card--watch">
      <div class="qd-notice-card__hero">
        <div>
          <div class="qd-notice-card__kicker">${escapeHtml(tx(t, 'notice.type.securityLogin', 'Login alert'))}</div>
          <div class="qd-notice-card__title">${escapeHtml(reason)}</div>
        </div>
        <div class="qd-notice-card__chip">${escapeHtml(tx(t, 'notice.event.login.severity', 'Review'))}</div>
      </div>
      <div class="qd-notice-card__grid">
        ${rows.map(([label, value]) => metricHtml(label, value)).join('')}
      </div>
      <div class="qd-notice-card__note">${escapeHtml(footer)}</div>
    </div>`
  return { title, message }
}

function renderProfileTest (t, { html = false } = {}) {
  const title = tx(t, 'notice.event.profileTest.title', 'QuantDinger notification test')
  const body = tx(t, 'notice.event.profileTest.body', 'This is a test message from Profile notification settings. If you see this, the channel is configured correctly.')
  if (!html) return { title, message: body }
  const message = `
    <div class="qd-notice-card qd-notice-card--test qd-notice-card--neutral">
      <div class="qd-notice-card__hero">
        <div>
          <div class="qd-notice-card__kicker">${escapeHtml(tx(t, 'notice.type.profileTest', 'Test notification'))}</div>
          <div class="qd-notice-card__title">${escapeHtml(title)}</div>
        </div>
        <div class="qd-notice-card__chip">OK</div>
      </div>
      <div class="qd-notice-card__note">${escapeHtml(body)}</div>
    </div>`
  return { title, message }
}

function renderFromDisplay (item, t, { html = false } = {}) {
  const d = displayOf(item)
  if (!d || !d.template) return null
  const p = d.params || {}

  if (d.template === 'security.login') return renderSecurityLogin(p, t, { html })
  if (d.template === 'profile.test') return renderProfileTest(t, { html })
  if (d.template === 'indicator.signal') return renderIndicatorSignal(p, t, { html })
  if (d.template === 'signal.trade') return renderSignalTrade(p, t, { html })
  return null
}

export function noticeTitle (item, t) {
  const rendered = renderFromDisplay(item, t)
  if (rendered && rendered.title) return rendered.title
  return (item && item.title) || ''
}

export function noticeMessage (item, t, { html = false } = {}) {
  const rendered = renderFromDisplay(item, t, { html })
  if (rendered && rendered.message) return rendered.message
  const raw = (item && item.message) || ''
  if (html) {
    if (raw.includes('<div class="qd-report">') || raw.includes('<style>')) {
      return raw
    }
    if (/<[a-z][\s\S]*>/i.test(raw)) {
      return raw
    }
    return escapeHtml(raw).replace(/\n/g, '<br>')
  }
  return stripHtml(raw)
}

export function noticePreview (item, t, maxLen = 80) {
  const text = noticeMessage(item, t, { html: false })
  if (!text) return ''
  const oneLine = text.replace(/\s*\n+\s*/g, ' / ')
  return oneLine.length > maxLen ? `${oneLine.substring(0, maxLen)}...` : oneLine
}

export function noticeMessageHtml (item, t) {
  const raw = (item && item.message) || ''
  if (raw.includes('<div class="qd-report">') || raw.includes('<style>')) {
    return raw
  }
  const rendered = renderFromDisplay(item, t, { html: true })
  if (rendered && rendered.message) {
    return rendered.message
  }
  if (/<[a-z][\s\S]*>/i.test(raw)) {
    return raw
  }
  return escapeHtml(stripHtml(raw)).replace(/\n/g, '<br>')
}

export function noticeTypeLabel (signalType, t) {
  const map = {
    ai_monitor: ['notice.type.aiMonitor', 'AI Monitor'],
    price_alert: ['notice.type.priceAlert', 'Price Alert'],
    signal: ['notice.type.signal', 'Trade Signal'],
    buy: ['notice.type.buy', 'Buy Signal'],
    sell: ['notice.type.sell', 'Sell Signal'],
    hold: ['notice.type.hold', 'Hold Suggestion'],
    trade: ['notice.type.trade', 'Trade Execution'],
    indicator_signal: ['notice.type.indicatorSignal', 'Indicator Signal'],
    security_login: ['notice.type.securityLogin', 'Login Alert'],
    profile_test: ['notice.type.profileTest', 'Test Notification']
  }
  const pair = map[signalType] || ['notice.type.notification', 'Notification']
  return tx(t, pair[0], pair[1])
}
