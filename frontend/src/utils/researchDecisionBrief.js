import { extractPortfolioManagerDecisionSummary } from './tradingAgentsReport.js'

const sectionNames = [
  ['supporting', /^(supporting evidence|bằng chứng (ủng hộ|hỗ trợ)|luận điểm ủng hộ)$/iu],
  ['counter', /^(counter evidence|counterarguments|bằng chứng phản biện|luận điểm phản biện)$/iu],
  ['risks', /^(key risks|risks|rủi ro|rủi ro chính|risk control|kiểm soát rủi ro)$/iu],
  ['invalidation', /^(invalidation conditions|thesis invalidation|điều kiện vô hiệu|điều kiện (vô hiệu hóa|bác bỏ) luận điểm)$/iu],
  ['watch', /^(next watch|watchlist|watchlist and scenarios|theo dõi tiếp|danh sách theo dõi( và kịch bản)?)$/iu],
  ['scenarios', /^(scenarios|kịch bản)$/iu],
  ['thesis', /^(investment thesis|luận điểm đầu tư)$/iu]
]

function plain (value) {
  return String(value || '').replace(/\*\*|__|`/gu, '').replace(/\[([^\]]+)\]\([^)]*\)/gu, '$1').replace(/\s+/gu, ' ').trim()
}

function sourceUrl (value) {
  const match = /\[[^\]]+\]\(([^\s)]+)\)|\bhttps?:\/\/[^\s<>)]+/u.exec(value)
  try {
    const url = new URL(match ? (match[1] || match[0]) : '')
    return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? url.href : ''
  } catch (_) { return '' }
}

export function reportBriefIdentity (report) {
  if (report && report.assetKey) return String(report.assetKey)
  let market = String(report && report.market || '').toLowerCase()
  let symbol = String(report && report.symbol || '').toUpperCase()
  if (market === 'gold') market = 'forex'
  if (market === 'forex' && symbol === 'XAU') symbol = 'XAUUSD'
  if (market === 'crypto' && symbol && !symbol.includes('/')) symbol = `${symbol}/USDT`
  return market && symbol ? `${market}:${symbol}` : ''
}

export function reportBriefDate (report) {
  return String(report && (report.effectiveDate || report.analysisDate || report.analysis_date) || '').slice(0, 10)
}

export function comparablePreviousReport (report, previous) {
  const currentDate = reportBriefDate(report)
  const previousDate = reportBriefDate(previous)
  const locale = item => item && (item.locale || item.language) || ''
  const kind = item => item && item.reportKind || 'deep'
  return Boolean(reportBriefIdentity(report) && reportBriefIdentity(report) === reportBriefIdentity(previous) &&
    Number.isFinite(Date.parse(currentDate)) && Number.isFinite(Date.parse(previousDate)) && previousDate < currentDate &&
    locale(report) === locale(previous) && kind(report) === kind(previous))
}

function extract (report) {
  const body = String(report && report.body || '')
  const brief = { ...extractPortfolioManagerDecisionSummary(body), supporting: [], counter: [], risks: [], invalidation: [], watch: [], scenarios: [], thesis: [] }
  let inManager = false
  let section = ''
  let block = null
  function flush () {
    if (block && block.text.trim()) {
      block.sourceUrl = sourceUrl(block.text)
      block.text = plain(block.text)
      brief[section].push(block)
    }
    block = null
  }
  body.replace(/\r/gu, '').split('\n').forEach((raw, index) => {
    const line = raw.trim()
    const heading = /^#{1,6}\s+(.+)$/u.exec(line)
    const clean = plain(heading ? heading[1] : line).replace(/:$/u, '')
    if (/^(?:v\.\s*)?(?:portfolio manager decision|quyết định của quản lý danh mục)$/iu.test(clean)) {
      flush(); inManager = true; section = ''; return
    }
    if (!inManager) return
    if (/^(?:[ivx]+\.\s+)(?:analyst team reports|research team decision|trading team plan|risk management team decision|báo cáo nhóm phân tích|quyết định của nhóm nghiên cứu|kế hoạch của nhóm giao dịch|quyết định của nhóm quản trị rủi ro)$/iu.test(clean)) {
      flush(); inManager = false; section = ''; return
    }
    const field = /^(?:\*\*)?([^:]{2,100}?)(?:\*\*)?\s*:\s*(.*)$/u.exec(line)
    const label = plain(heading ? heading[1] : field ? field[1] : line).replace(/:$/u, '')
    const known = sectionNames.find(([, pattern]) => pattern.test(label))
    if (known) {
      flush(); section = known[0]
      if (field && field[2].trim()) block = { text: field[2], section: label, line: index + 1 }
      return
    }
    if (heading || (field && /^\*\*/u.test(line))) { flush(); section = ''; return }
    if (!section) return
    if (!line) { flush(); return }
    const bullet = /^(?:[-*+]\s+|\d+[.)]\s+)(.+)$/u.exec(line)
    if (bullet) {
      flush(); block = { text: bullet[1], section: label, line: index + 1 }
    } else if (block) block.text += ` ${line}`
    else block = { text: line, section, line: index + 1 }
  })
  flush()
  return brief
}

export function buildResearchDecisionBrief (report, previous = null) {
  const current = extract(report)
  current.comparison = null
  if (comparablePreviousReport(report, previous)) {
    const prior = extract(previous)
    const compare = (before, after) => ({ before, after, changed: before && after ? plain(before).toUpperCase() !== plain(after).toUpperCase() : null })
    const riskComparisonAvailable = Boolean(prior.risks.length && current.risks.length)
    current.comparison = {
      previousDate: reportBriefDate(previous),
      rating: compare(prior.rating, current.rating),
      timeHorizon: compare(prior.timeHorizon, current.timeHorizon),
      riskComparisonAvailable,
      addedRisks: riskComparisonAvailable ? current.risks.filter(item => !prior.risks.some(old => old.text === item.text)) : [],
      removedRisks: riskComparisonAvailable ? prior.risks.filter(item => !current.risks.some(next => next.text === item.text)) : [],
      addedInvalidation: prior.invalidation.length && current.invalidation.length ? current.invalidation.filter(item => !prior.invalidation.some(old => old.text === item.text)) : []
    }
  }
  // Evidence lists are claims quoted from the report, never verified-provider
  // facts or a synthetic probability. Missing sections remain empty.
  return current
}
