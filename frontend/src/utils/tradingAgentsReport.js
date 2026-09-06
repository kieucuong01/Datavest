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

/**
 * Convert the trusted native markdown report to text-only presentation blocks.
 * Keeping it text-only avoids rendering arbitrary HTML from a stored artifact.
 */
export function parseTradingAgentsReport (content) {
  const blocks = []
  const paragraphs = []
  const listItems = []
  const lines = String(content || '').replace(/\r\n?/g, '\n').split('\n')

  const flush = () => {
    pushParagraph(blocks, paragraphs)
    pushList(blocks, listItems)
  }

  for (const rawLine of lines) {
    const line = rawLine.trim()
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
      blocks.push({
        type: 'heading',
        level: heading[1].length,
        text: cleanInlineMarkdown(heading[2])
      })
    } else if (list) {
      pushParagraph(blocks, paragraphs)
      listItems.push(list[1])
    } else {
      pushList(blocks, listItems)
      paragraphs.push(line)
    }
  }
  flush()

  return blocks
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
