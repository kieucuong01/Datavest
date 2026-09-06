const HEADING_TRANSLATIONS = {
  'I. Analyst Team Reports': 'I. Báo cáo nhóm phân tích',
  'II. Research Team Decision': 'II. Quyết định của nhóm nghiên cứu',
  'III. Trading Team Plan': 'III. Kế hoạch của nhóm giao dịch',
  'IV. Risk Management Team Decision': 'IV. Quyết định của nhóm quản trị rủi ro',
  'V. Portfolio Manager Decision': 'V. Quyết định của quản lý danh mục',
  'Market Analyst': 'Chuyên gia phân tích thị trường',
  'Sentiment Analyst': 'Chuyên gia phân tích tâm lý',
  'News Analyst': 'Chuyên gia phân tích tin tức',
  'Fundamentals Analyst': 'Chuyên gia phân tích cơ bản',
  'Bull Researcher': 'Nhà nghiên cứu xu hướng tăng',
  'Bear Researcher': 'Nhà nghiên cứu xu hướng giảm',
  'Research Manager': 'Quản lý nghiên cứu',
  Trader: 'Chuyên gia giao dịch',
  'Aggressive Analyst': 'Chuyên gia chủ động',
  'Conservative Analyst': 'Chuyên gia thận trọng',
  'Neutral Analyst': 'Chuyên gia trung lập',
  'Portfolio Manager': 'Quản lý danh mục'
}

function cleanInlineMarkdown (value) {
  return String(value || '')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/__(.*?)__/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .trim()
}

function pushParagraph (blocks, lines) {
  if (!lines.length) return
  const text = cleanInlineMarkdown(lines.join(' '))
  if (text) blocks.push({ type: 'paragraph', text })
  lines.length = 0
}

function pushList (blocks, items) {
  if (!items.length) return
  blocks.push({ type: 'list', items: items.map(cleanInlineMarkdown).filter(Boolean) })
  items.length = 0
}

function parseTableRow (line) {
  const text = String(line || '').trim()
  if (!text.startsWith('|')) return []
  const value = text.replace(/^\|/, '').replace(/\|$/, '')
  return value.split('|').map(cleanInlineMarkdown)
}

function isTableSeparator (row) {
  return row.length > 0 && row.every(cell => /^:?-{3,}:?$/.test(cell.replace(/\s/g, '')))
}

function pushTable (blocks, lines) {
  if (lines.length < 2) {
    if (lines.length) blocks.push({ type: 'paragraph', text: lines[0] })
    lines.length = 0
    return
  }
  const rows = lines.map(parseTableRow).filter(row => row.length)
  lines.length = 0
  if (rows.length < 2) return
  const headers = rows.shift()
  if (isTableSeparator(rows[0] || [])) rows.shift()
  if (!headers.length || !rows.length) return
  blocks.push({
    type: 'table',
    headers,
    rows: rows.map(row => headers.map((_, index) => row[index] || ''))
  })
}

/**
 * Convert the trusted native markdown report to text-only presentation blocks.
 * Keeping it text-only avoids rendering arbitrary HTML from a stored artifact.
 */
export function parseTradingAgentsReport (content) {
  const blocks = []
  const paragraphs = []
  const listItems = []
  const tableLines = []
  const lines = String(content || '').replace(/\r\n?/g, '\n').split('\n')
  let fence = ''
  let code = []
  let nativeGroup = false
  let nativeAnalyst = false

  const flush = () => {
    pushParagraph(blocks, paragraphs)
    pushList(blocks, listItems)
    pushTable(blocks, tableLines)
  }

  for (const rawLine of lines) {
    const line = rawLine.trim()
    const fenceMatch = /^(`{3,}|~{3,})/.exec(line)
    if (fence) {
      if (fenceMatch && fenceMatch[1][0] === fence[0] && fenceMatch[1].length >= fence.length) {
        blocks.push({ type: 'code', text: code.join('\n') })
        fence = ''
        code = []
      } else code.push(rawLine)
      continue
    }
    if (fenceMatch) {
      flush()
      fence = fenceMatch[1]
      continue
    }
    const heading = /^(#{1,6})\s+(.+)$/.exec(line)
    const list = /^(?:[-*+]\s+|\d+[.)]\s+)(.+)$/.exec(line)

    if (!line) {
      flush()
    } else if (/^Generated:\s*/i.test(line)) {
      // The native writer's timestamp may use the container timezone. The
      // modal already shows the run timestamp normalized to Vietnam time.
      flush()
    } else if (heading) {
      flush()
      const text = cleanInlineMarkdown(heading[2])
      let level = heading[1].length
      // Native team/analyst wrappers own their AI-written content, even when
      // the model starts its individual report with another H1 or H2.
      if (level === 2 && /^(I|II|III|IV|V)\. /.test(text) && HEADING_TRANSLATIONS[text]) {
        nativeGroup = true
        nativeAnalyst = false
      } else if (nativeGroup && level === 3 && HEADING_TRANSLATIONS[text]) {
        nativeAnalyst = true
      } else if (nativeGroup) level += nativeAnalyst ? 3 : 2
      blocks.push({
        type: 'heading',
        level,
        text
      })
    } else if (list) {
      pushTable(blocks, tableLines)
      pushParagraph(blocks, paragraphs)
      listItems.push(list[1])
    } else if (line.startsWith('|')) {
      pushParagraph(blocks, paragraphs)
      pushList(blocks, listItems)
      tableLines.push(line)
    } else {
      pushTable(blocks, tableLines)
      pushList(blocks, listItems)
      paragraphs.push(line)
    }
  }
  flush()
  if (fence) blocks.push({ type: 'code', text: code.join('\n') })

  return blocks
}

/**
 * Group flat native markdown blocks into digestible report sections without
 * rendering arbitrary HTML from the stored artifact.
 */
export function groupTradingAgentsReportSections (blocks) {
  const sections = []
  const intro = []
  let title = ''
  const headingStack = []

  const createSection = (block) => ({
    title: block.text,
    level: block.level,
    blocks: [],
    subsections: []
  })

  for (const block of Array.isArray(blocks) ? blocks : []) {
    if (block.type === 'heading' && block.level === 1 && !title) {
      title = block.text
      continue
    }
    if (block.type === 'heading') {
      while (headingStack.length && headingStack[headingStack.length - 1].level >= block.level) headingStack.pop()
      const section = createSection(block)
      const parent = headingStack[headingStack.length - 1]
      if (parent) parent.subsections.push(section)
      else sections.push(section)
      headingStack.push(section)
      continue
    }
    const current = headingStack[headingStack.length - 1]
    if (current) current.blocks.push(block)
    else intro.push(block)
  }

  if (intro.length) {
    sections.unshift({
      title: title || 'Overview',
      level: 1,
      blocks: intro,
      subsections: []
    })
  }

  return { title, sections }
}

export function localizeTradingAgentsHeading (heading, language = 'en-US') {
  const text = String(heading || '').trim()
  if (language !== 'vi-VN') return text
  if (HEADING_TRANSLATIONS[text]) return HEADING_TRANSLATIONS[text]
  if (text.startsWith('Trading Analysis Report:')) {
    return text.replace('Trading Analysis Report:', 'Báo cáo phân tích:')
  }
  if (text.startsWith('Generated:')) {
    return text.replace('Generated:', 'Thời điểm tạo:')
  }
  return text
}
