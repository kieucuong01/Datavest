const locale = {
  'brokerAccounts.commandCenterTitle': 'Account Center',
  'brokerAccounts.commandCenterSubtitle': 'Manage brokerage and crypto exchange connections from one workspace.',
  'brokerAccounts.connectionHealth': 'Connection health',
  'brokerAccounts.allHealthy': 'All connected accounts are healthy',
  'brokerAccounts.connections': 'Accounts & connections',
  'brokerAccounts.tradingAccounts': 'Stock brokers',
  'brokerAccounts.cryptoAccounts': 'Crypto exchanges',
  'brokerAccounts.addAccount': 'Add account',
  'brokerAccounts.addCryptoConnection': 'Add crypto exchange',
  'brokerAccounts.cryptoConnectionHint': 'Connect another venue and expand market coverage.',
  'brokerAccounts.connectedCount': '{count} connected',
  'brokerAccounts.cryptoSection.emptyHint': 'Use Add account in the top right to connect your first exchange.'
}

const zhCN = {
  'brokerAccounts.commandCenterTitle': '账户中心',
  'brokerAccounts.commandCenterSubtitle': '统一管理股票券商与加密交易所连接，实时掌握账户状态。',
  'brokerAccounts.connectionHealth': '整体连接状态',
  'brokerAccounts.allHealthy': '已连接账户全部正常',
  'brokerAccounts.connections': '账户与连接',
  'brokerAccounts.tradingAccounts': '股票券商',
  'brokerAccounts.cryptoAccounts': '加密交易所',
  'brokerAccounts.addAccount': '添加账户',
  'brokerAccounts.addCryptoConnection': '添加加密交易所',
  'brokerAccounts.cryptoConnectionHint': '连接更多交易所，覆盖全球市场。',
  'brokerAccounts.connectedCount': '已连接 {count} 个',
  'brokerAccounts.cryptoSection.emptyHint': '请使用右上角“添加账户”连接第一个交易所。'
}

const zhTW = {
  'brokerAccounts.commandCenterTitle': '帳戶中心',
  'brokerAccounts.commandCenterSubtitle': '統一管理股票券商與加密交易所連線，即時掌握帳戶狀態。',
  'brokerAccounts.connectionHealth': '整體連線狀態',
  'brokerAccounts.allHealthy': '已連線帳戶全部正常',
  'brokerAccounts.connections': '帳戶與連線',
  'brokerAccounts.tradingAccounts': '股票券商',
  'brokerAccounts.cryptoAccounts': '加密交易所',
  'brokerAccounts.addAccount': '新增帳戶',
  'brokerAccounts.addCryptoConnection': '新增加密交易所',
  'brokerAccounts.cryptoConnectionHint': '連接更多交易所，覆蓋全球市場。',
  'brokerAccounts.connectedCount': '已連線 {count} 個',
  'brokerAccounts.cryptoSection.emptyHint': '請使用右上角「新增帳戶」連線第一個交易所。'
}

const enUSFallback = locale
const locales = ['ar-SA', 'de-DE', 'fr-FR', 'ja-JP', 'ko-KR', 'ru-RU', 'th-TH', 'vi-VN']

export default locales.reduce((messages, localeName) => {
  messages[localeName] = { ...enUSFallback }
  return messages
}, {
  'en-US': locale,
  'zh-CN': zhCN,
  'zh-TW': zhTW
})
