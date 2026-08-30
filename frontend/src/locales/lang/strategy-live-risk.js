const locale = {
  'trading-assistant.logs.level.all': 'All',
  'trading-assistant.logs.level.info': 'Info',
  'trading-assistant.logs.level.warning': 'Warning',
  'trading-assistant.logs.level.warn': 'Warning',
  'trading-assistant.logs.level.error': 'Error',
  'trading-assistant.logs.level.trade': 'Trade',
  'trading-assistant.logs.level.signal': 'Signal',
  'trading-assistant.logs.autoRefresh': 'Auto refresh',
  'trading-assistant.logs.noLogs': 'No logs',
  'strategyCenter.console.pauseOnly': 'Pause only',
  'strategyCenter.console.pauseConfirm': 'Pause strategy execution and keep its current positions?',
  'strategyCenter.console.stopAndClose': 'Pause and close',
  'strategyCenter.console.stopAndCloseConfirm': 'Pause the strategy and queue reduce-only orders for all positions owned by it?',
  'strategyCenter.console.stopAndCloseQueued': 'Strategy paused and its close orders were queued',
  'strategyCenter.console.pauseSuccess': 'Strategy paused; positions remain open',
  'strategyCenter.console.runtimeStatus': 'Runtime status',
  'strategyCenter.console.financialOverview': 'Capital and risk',
  'strategyCenter.console.strategyCapital': 'Strategy capital',
  'strategyCenter.console.currentEquity': 'Current equity',
  'strategyCenter.console.cumulativeNetPnl': 'Cumulative net P&L',
  'strategyCenter.console.currentExposure': 'Current exposure',
  'strategyCenter.console.currentExposureHint': 'Gross notional value of current positions; this is not invested capital or used margin.',
  'strategyCenter.console.leverage': 'Leverage',
  'strategyCenter.console.performanceOverview': 'Runtime performance',
  'strategyCenter.console.winRateSample': '{wins}/{total} profitable',
  'strategyCenter.console.completedTrades': 'Completed trades',
  'strategyCenter.console.todayPnlEstimated': 'Opening baseline estimated',
  'strategyCenter.console.todayPnlEstimatedHint': 'No equity snapshot was available near local midnight. This value uses the trade ledger as a temporary opening baseline and becomes exact after continuous snapshots cover a day boundary.',
  'strategyCenter.console.netPnlBasis': 'Realized and unrealized P&L, net of recorded fees',
  'strategyCenter.console.liveFinancialUnavailable': 'Live financial metrics are unavailable in notification mode',
  'strategyCenter.console.spotMarket': 'Spot',
  'strategyCenter.console.swapMarket': 'Perpetual',
  'strategyCenter.editor.positionSide': 'Position direction',
  'strategyCenter.editor.positionSideHint': 'Live swap strategies must own exactly one hedge-mode leg.',
  'strategyCenter.editor.positionSideLong': 'Long leg',
  'strategyCenter.editor.positionSideShort': 'Short leg',
  'strategyCenter.editor.positionSideRequired': 'Select the position direction before enabling live execution.',
  'strategyCenter.editor.directionMode': 'Strategy trading capability',
  'strategyCenter.editor.directionLongOnly': 'Long only',
  'strategyCenter.editor.directionShortOnly': 'Short only',
  'strategyCenter.editor.directionBoth': 'Long & short',
  'strategyCenter.editor.directionNeutral': 'Neutral',
  'strategyCenter.editor.directionMode.long_only': 'Long only',
  'strategyCenter.editor.directionMode.short_only': 'Short only',
  'strategyCenter.editor.directionMode.both': 'Long and short',
  'strategyCenter.editor.directionMode.neutral': 'Neutral dual-leg',
  'strategyCenter.editor.directionMode.unknown': 'Not declared',
  'strategyCenter.editor.directionModeDetectedHint': 'Detected from the strategy contract. Strategy signals still decide each order direction.',
  'strategyCenter.editor.directionModeLegacyHint': 'This legacy strategy does not declare its capability. Select a compatibility mode; new strategies should declare direction_mode in metadata.',
  'strategyCenter.editor.directionModeRequired': 'Select a compatibility mode for this legacy swap strategy.',
  'strategyCenter.editor.accountRiskTitle': 'Account-level risk limits',
  'strategyCenter.editor.accountRiskHint': 'Limits apply across all live strategies that share this exchange account.',
  'strategyCenter.editor.accountRiskAutoHint': 'Set a limit to 0 to derive it from strategy capital and leverage.',
  'strategyCenter.editor.maxGrossNotional': 'Maximum gross notional',
  'strategyCenter.editor.maxSymbolGrossNotional': 'Maximum symbol gross notional',
  'strategyCenter.editor.maxMarginEstimate': 'Maximum estimated margin',
  'strategyCenter.editor.maxGrossLeverage': 'Maximum gross leverage',
  'strategyCenter.editor.maxRoundTripFee': 'Maximum round-trip fee estimate',
  'strategyCenter.editor.maxFundingPerInterval': 'Maximum funding per interval',
  'strategyV2.positionSideRequired': 'Select a long or short position direction for this live swap strategy.',
  'strategyV2.positionSideInvalid': 'The selected position direction is invalid.',
  'strategyV2.directionModeRequired': 'This live swap strategy must declare a trading-direction capability.',
  'strategyV2.directionModeInvalid': 'The strategy trading-direction capability is invalid.',
  'strategyV2.directionModeMismatch': 'The selected trading capability conflicts with the strategy contract.',
  'strategyV2.directionModeViolation': 'The order direction exceeds the strategy\'s declared trading capability.',
  'strategyV2.dualDirectionHedgeModeRequired': 'Long-and-short or neutral strategies require hedge mode on the exchange account.',
  'strategyV2.accountRiskInvalid': 'The account risk configuration is invalid.',
  'strategyV2.hedgeModeRequired': 'The exchange account is in one-way mode. Switch it to hedge mode before starting.',
  'strategyV2.hedgeModeUnknown': 'The exchange position mode could not be verified, so live execution was blocked.',
  'strategyV2.liveLegConflict': 'Another live strategy already owns this account, symbol, and direction.',
  'strategyV2.stopClosePartialFailure': 'The strategy was paused, but one or more close orders could not be queued.',
  'strategyV2.paused': 'Strategy paused',
  'strategyV2.stoppedAndCloseQueued': 'Strategy paused and close orders queued',
  'strategyV2.startQueued': 'Strategy start queued; waiting for the execution worker to confirm.',
  'accountRisk.grossNotionalExceeded': 'Account gross notional limit exceeded.',
  'accountRisk.symbolGrossNotionalExceeded': 'Symbol gross notional limit exceeded.',
  'accountRisk.marginEstimateExceeded': 'Estimated account margin limit exceeded.',
  'accountRisk.feeBudgetExceeded': 'Estimated round-trip fee budget exceeded.',
  'accountRisk.fundingBudgetExceeded': 'Estimated funding budget exceeded.',
  'accountRisk.grossLeverageExceeded': 'Account gross leverage limit exceeded.',
  'accountRisk.positionPriceMissing': 'A current position could not be valued, so the opening order was blocked.',
  'accountRisk.proposedPriceMissing': 'The opening order has no usable reference price, so it was blocked.'
  , 'strategyCenter.gridOrders.tab': 'Exchange orders'
  , 'strategyCenter.gridOrders.title': 'Exchange resting grid orders'
  , 'strategyCenter.gridOrders.description': 'Orders are reconciled against the exchange; an exchange order ID is the placement proof.'
  , 'strategyCenter.gridOrders.reconcile': 'Reconcile now'
  , 'strategyCenter.gridOrders.syncFailed': 'Exchange reconciliation failed'
  , 'strategyCenter.gridOrders.open': 'Tracked open orders'
  , 'strategyCenter.gridOrders.verified': 'Verified on exchange'
  , 'strategyCenter.gridOrders.unverified': 'Missing exchange ID'
  , 'strategyCenter.gridOrders.lastSync': 'Last reconciliation'
  , 'strategyCenter.gridOrders.cell': 'Cell'
  , 'strategyCenter.gridOrders.purpose': 'Purpose'
  , 'strategyCenter.gridOrders.side': 'Side'
  , 'strategyCenter.gridOrders.price': 'Price'
  , 'strategyCenter.gridOrders.quantity': 'Quantity'
  , 'strategyCenter.gridOrders.filled': 'Filled'
  , 'strategyCenter.gridOrders.status': 'Status'
  , 'strategyCenter.gridOrders.exchangeOrderId': 'Exchange order ID'
  , 'strategyCenter.gridOrders.updatedAt': 'Updated'
  , 'strategyCenter.gridOrders.notVerified': 'Not verified'
  , 'strategyCenter.gridOrders.empty': 'No exchange resting orders are visible'
  , 'strategyCenter.gridOrders.emptyHint': 'A running grid should normally have resting entries. Reconcile and inspect strategy health before assuming it is active.'
}

const enUSFallback = locale

const zhCN = {
  ...enUSFallback,
  'trading-assistant.logs.level.all': '全部',
  'trading-assistant.logs.level.info': '信息',
  'trading-assistant.logs.level.warning': '警告',
  'trading-assistant.logs.level.warn': '警告',
  'trading-assistant.logs.level.error': '错误',
  'trading-assistant.logs.level.trade': '交易',
  'trading-assistant.logs.level.signal': '信号',
  'trading-assistant.logs.autoRefresh': '自动刷新',
  'trading-assistant.logs.noLogs': '暂无日志',
  'strategyCenter.console.pauseOnly': '仅暂停',
  'strategyCenter.console.pauseConfirm': '暂停策略运行并保留当前持仓吗？',
  'strategyCenter.console.stopAndClose': '暂停并平仓',
  'strategyCenter.console.stopAndCloseConfirm': '暂停策略，并为该策略持有的全部仓位提交只减仓订单吗？',
  'strategyCenter.console.stopAndCloseQueued': '策略已暂停，平仓订单已提交队列',
  'strategyCenter.console.pauseSuccess': '策略已暂停，当前持仓继续保留',
  'strategyCenter.console.runtimeStatus': '运行状态',
  'strategyCenter.console.financialOverview': '资金与风险',
  'strategyCenter.console.strategyCapital': '策略资金',
  'strategyCenter.console.currentEquity': '当前净值',
  'strategyCenter.console.cumulativeNetPnl': '累计净收益',
  'strategyCenter.console.currentExposure': '当前敞口',
  'strategyCenter.console.currentExposureHint': '当前持仓的总名义价值，不等于策略资金或已用保证金。',
  'strategyCenter.console.leverage': '杠杆',
  'strategyCenter.console.performanceOverview': '运行表现',
  'strategyCenter.console.winRateSample': '盈利 {wins} / 已完成 {total}',
  'strategyCenter.console.completedTrades': '已完成交易',
  'strategyCenter.console.todayPnlEstimated': '当日基准为估算',
  'strategyCenter.console.todayPnlEstimatedHint': '用户本地零点附近暂时没有净值快照，当前以交易账本重建日初基准；连续采样跨过下一个零点后将自动转为精确值。',
  'strategyCenter.console.netPnlBasis': '已实现与未实现收益，扣除已记录手续费',
  'strategyCenter.console.liveFinancialUnavailable': '仅通知模式不提供实盘资金指标',
  'strategyCenter.console.spotMarket': '现货',
  'strategyCenter.console.swapMarket': '永续合约',
  'strategyCenter.editor.positionSide': '持仓方向',
  'strategyCenter.editor.positionSideHint': '合约实盘策略必须固定归属一个双向持仓腿。',
  'strategyCenter.editor.positionSideLong': '做多腿',
  'strategyCenter.editor.positionSideShort': '做空腿',
  'strategyCenter.editor.positionSideRequired': '开启实盘前请选择持仓方向。',
  'strategyCenter.editor.directionMode': '策略交易方向能力',
  'strategyCenter.editor.directionLongOnly': '仅做多',
  'strategyCenter.editor.directionShortOnly': '仅做空',
  'strategyCenter.editor.directionBoth': '多空双向',
  'strategyCenter.editor.directionNeutral': '中性双腿',
  'strategyCenter.editor.directionMode.long_only': '仅做多',
  'strategyCenter.editor.directionMode.short_only': '仅做空',
  'strategyCenter.editor.directionMode.both': '多空双向',
  'strategyCenter.editor.directionMode.neutral': '中性双腿',
  'strategyCenter.editor.directionMode.unknown': '未声明',
  'strategyCenter.editor.directionModeDetectedHint': '已从策略契约自动识别；每笔订单的实际方向仍由策略信号决定。',
  'strategyCenter.editor.directionModeLegacyHint': '该旧策略未声明方向能力，请选择兼容模式；新策略应在元数据中声明 direction_mode。',
  'strategyCenter.editor.directionModeRequired': '请为该旧版合约策略选择兼容模式。',
  'strategyCenter.editor.accountRiskTitle': '账户级风险限制',
  'strategyCenter.editor.accountRiskHint': '限制会统计共享同一交易所账户的全部实盘策略。',
  'strategyCenter.editor.accountRiskAutoHint': '数值设为 0 时，将根据策略资金和杠杆自动计算。',
  'strategyCenter.editor.maxGrossNotional': '最大总名义仓位',
  'strategyCenter.editor.maxSymbolGrossNotional': '单标的最大总名义仓位',
  'strategyCenter.editor.maxMarginEstimate': '最大预估保证金',
  'strategyCenter.editor.maxGrossLeverage': '最大总杠杆',
  'strategyCenter.editor.maxRoundTripFee': '最大往返手续费预估',
  'strategyCenter.editor.maxFundingPerInterval': '单周期最大资金费率成本',
  'strategyV2.positionSideRequired': '该合约实盘策略必须选择做多或做空方向。',
  'strategyV2.positionSideInvalid': '持仓方向无效。',
  'strategyV2.directionModeRequired': '该合约实盘策略必须声明交易方向能力。',
  'strategyV2.directionModeInvalid': '策略交易方向能力无效。',
  'strategyV2.directionModeMismatch': '所选交易方向能力与策略契约不一致。',
  'strategyV2.directionModeViolation': '订单方向超出了策略声明的交易方向能力。',
  'strategyV2.dualDirectionHedgeModeRequired': '多空双向或中性策略要求交易所账户开启双向持仓模式。',
  'strategyV2.accountRiskInvalid': '账户风险配置无效。',
  'strategyV2.hedgeModeRequired': '交易所账户处于单向持仓模式，请切换为双向持仓后再启动。',
  'strategyV2.hedgeModeUnknown': '无法确认交易所持仓模式，已阻止实盘启动。',
  'strategyV2.liveLegConflict': '同一账户、标的和方向已有其他实盘策略运行。',
  'strategyV2.stopClosePartialFailure': '策略已暂停，但部分平仓订单未能提交。',
  'strategyV2.paused': '策略已暂停',
  'strategyV2.stoppedAndCloseQueued': '策略已暂停，平仓订单已提交',
  'accountRisk.grossNotionalExceeded': '账户总名义仓位超过限制。',
  'accountRisk.symbolGrossNotionalExceeded': '该标的总名义仓位超过限制。',
  'accountRisk.marginEstimateExceeded': '账户预估保证金超过限制。',
  'accountRisk.feeBudgetExceeded': '预估往返手续费超过预算。',
  'accountRisk.fundingBudgetExceeded': '预估资金费率成本超过预算。',
  'accountRisk.grossLeverageExceeded': '账户总杠杆超过限制。',
  'accountRisk.positionPriceMissing': '当前持仓缺少可用价格，已阻止新增开仓。',
  'accountRisk.proposedPriceMissing': '开仓订单缺少可用参考价格，已阻止提交。'
  , 'strategyCenter.gridOrders.tab': '交易所挂单'
  , 'strategyCenter.gridOrders.title': '交易所常驻网格挂单'
  , 'strategyCenter.gridOrders.description': '挂单会与交易所回读核验；交易所订单号是挂单成功的凭证。'
  , 'strategyCenter.gridOrders.reconcile': '立即核验'
  , 'strategyCenter.gridOrders.syncFailed': '交易所挂单核验失败'
  , 'strategyCenter.gridOrders.open': '跟踪中挂单'
  , 'strategyCenter.gridOrders.verified': '交易所已确认'
  , 'strategyCenter.gridOrders.unverified': '缺少交易所订单号'
  , 'strategyCenter.gridOrders.lastSync': '最近核验'
  , 'strategyCenter.gridOrders.cell': '网格'
  , 'strategyCenter.gridOrders.purpose': '用途'
  , 'strategyCenter.gridOrders.side': '方向'
  , 'strategyCenter.gridOrders.price': '价格'
  , 'strategyCenter.gridOrders.quantity': '数量'
  , 'strategyCenter.gridOrders.filled': '已成交'
  , 'strategyCenter.gridOrders.status': '状态'
  , 'strategyCenter.gridOrders.exchangeOrderId': '交易所订单号'
  , 'strategyCenter.gridOrders.updatedAt': '更新时间'
  , 'strategyCenter.gridOrders.notVerified': '未核验'
  , 'strategyCenter.gridOrders.empty': '没有查到交易所常驻挂单'
  , 'strategyCenter.gridOrders.emptyHint': '运行中的网格通常应存在买入挂单；请先执行核验并检查运行健康，不要默认它正在正常挂单。'
}

const zhTW = {
  ...zhCN,
  'trading-assistant.logs.level.info': '資訊',
  'trading-assistant.logs.level.error': '錯誤',
  'trading-assistant.logs.level.signal': '訊號',
  'trading-assistant.logs.autoRefresh': '自動重新整理',
  'trading-assistant.logs.noLogs': '暫無日誌',
  'strategyCenter.console.pauseOnly': '僅暫停',
  'strategyCenter.console.pauseConfirm': '暫停策略執行並保留目前持倉嗎？',
  'strategyCenter.console.stopAndClose': '暫停並平倉',
  'strategyCenter.console.stopAndCloseConfirm': '暫停策略，並為此策略持有的全部倉位提交只減倉訂單嗎？',
  'strategyCenter.console.pauseSuccess': '策略已暫停，目前持倉繼續保留',
  'strategyCenter.console.runtimeStatus': '執行狀態',
  'strategyCenter.console.financialOverview': '資金與風險',
  'strategyCenter.console.strategyCapital': '策略資金',
  'strategyCenter.console.currentEquity': '目前淨值',
  'strategyCenter.console.cumulativeNetPnl': '累計淨收益',
  'strategyCenter.console.currentExposure': '目前曝險',
  'strategyCenter.console.currentExposureHint': '目前持倉的總名義價值，不等於策略資金或已用保證金。',
  'strategyCenter.console.leverage': '槓桿',
  'strategyCenter.console.performanceOverview': '執行表現',
  'strategyCenter.console.winRateSample': '獲利 {wins} / 已完成 {total}',
  'strategyCenter.console.completedTrades': '已完成交易',
  'strategyCenter.console.todayPnlEstimated': '當日基準為估算',
  'strategyCenter.console.todayPnlEstimatedHint': '使用者本地零點附近暫時沒有淨值快照，目前以交易帳本重建日初基準；連續採樣跨過下一個零點後將自動轉為精確值。',
  'strategyCenter.console.netPnlBasis': '已實現與未實現收益，扣除已記錄手續費',
  'strategyCenter.console.liveFinancialUnavailable': '僅通知模式不提供實盤資金指標',
  'strategyCenter.console.spotMarket': '現貨',
  'strategyCenter.console.swapMarket': '永續合約',
  'strategyCenter.editor.positionSide': '持倉方向',
  'strategyCenter.editor.positionSideLong': '做多腿',
  'strategyCenter.editor.positionSideShort': '做空腿'
}

const ja = {
  ...enUSFallback,
  'trading-assistant.logs.level.all': 'すべて',
  'trading-assistant.logs.level.info': '情報',
  'trading-assistant.logs.level.warning': '警告',
  'trading-assistant.logs.level.warn': '警告',
  'trading-assistant.logs.level.error': 'エラー',
  'trading-assistant.logs.level.trade': '取引',
  'trading-assistant.logs.level.signal': 'シグナル',
  'trading-assistant.logs.autoRefresh': '自動更新',
  'trading-assistant.logs.noLogs': 'ログはありません',
  'strategyCenter.console.pauseOnly': '一時停止のみ',
  'strategyCenter.console.pauseConfirm': 'ポジションを維持したまま戦略を一時停止しますか？',
  'strategyCenter.console.stopAndClose': '停止して決済',
  'strategyCenter.console.stopAndCloseConfirm': '戦略を停止し、保有ポジションに決済注文を送信しますか？',
  'strategyCenter.console.stopAndCloseQueued': '戦略を停止し、決済注文をキューに追加しました',
  'strategyCenter.console.pauseSuccess': '戦略を停止しました。ポジションは維持されます',
  'strategyCenter.editor.positionSide': 'ポジション方向',
  'strategyCenter.editor.positionSideLong': 'ロング',
  'strategyCenter.editor.positionSideShort': 'ショート',
  'strategyV2.hedgeModeRequired': '取引所口座をヘッジモードに切り替えてから開始してください。'
}

const ko = {
  ...enUSFallback,
  'trading-assistant.logs.level.all': '전체',
  'trading-assistant.logs.level.info': '정보',
  'trading-assistant.logs.level.warning': '경고',
  'trading-assistant.logs.level.warn': '경고',
  'trading-assistant.logs.level.error': '오류',
  'trading-assistant.logs.level.trade': '거래',
  'trading-assistant.logs.level.signal': '신호',
  'trading-assistant.logs.autoRefresh': '자동 새로고침',
  'trading-assistant.logs.noLogs': '로그 없음',
  'strategyCenter.console.pauseOnly': '일시 중지만',
  'strategyCenter.console.stopAndClose': '중지 후 청산',
  'strategyCenter.editor.positionSide': '포지션 방향',
  'strategyCenter.editor.positionSideLong': '롱',
  'strategyCenter.editor.positionSideShort': '숏',
  'strategyV2.hedgeModeRequired': '거래소 계정을 헤지 모드로 전환한 후 시작하세요.'
}

const de = {
  ...enUSFallback,
  'trading-assistant.logs.level.all': 'Alle',
  'trading-assistant.logs.level.info': 'Info',
  'trading-assistant.logs.level.warning': 'Warnung',
  'trading-assistant.logs.level.warn': 'Warnung',
  'trading-assistant.logs.level.error': 'Fehler',
  'trading-assistant.logs.level.trade': 'Handel',
  'trading-assistant.logs.level.signal': 'Signal',
  'trading-assistant.logs.autoRefresh': 'Automatisch aktualisieren',
  'trading-assistant.logs.noLogs': 'Keine Protokolle',
  'strategyCenter.console.pauseOnly': 'Nur pausieren',
  'strategyCenter.console.stopAndClose': 'Pausieren und schließen',
  'strategyCenter.editor.positionSide': 'Positionsrichtung',
  'strategyCenter.editor.positionSideLong': 'Long-Seite',
  'strategyCenter.editor.positionSideShort': 'Short-Seite'
}

const fr = {
  ...enUSFallback,
  'trading-assistant.logs.level.all': 'Tous',
  'trading-assistant.logs.level.info': 'Information',
  'trading-assistant.logs.level.warning': 'Avertissement',
  'trading-assistant.logs.level.warn': 'Avertissement',
  'trading-assistant.logs.level.error': 'Erreur',
  'trading-assistant.logs.level.trade': 'Transactions',
  'trading-assistant.logs.level.signal': 'Signal',
  'trading-assistant.logs.autoRefresh': 'Actualisation automatique',
  'trading-assistant.logs.noLogs': 'Aucun journal',
  'strategyCenter.console.pauseOnly': 'Mettre en pause',
  'strategyCenter.console.stopAndClose': 'Pause et clôture',
  'strategyCenter.editor.positionSide': 'Sens de position',
  'strategyCenter.editor.positionSideLong': 'Jambe longue',
  'strategyCenter.editor.positionSideShort': 'Jambe courte'
}

const ru = {
  ...enUSFallback,
  'trading-assistant.logs.level.all': 'Все',
  'trading-assistant.logs.level.info': 'Информация',
  'trading-assistant.logs.level.warning': 'Предупреждение',
  'trading-assistant.logs.level.warn': 'Предупреждение',
  'trading-assistant.logs.level.error': 'Ошибка',
  'trading-assistant.logs.level.trade': 'Сделки',
  'trading-assistant.logs.level.signal': 'Сигнал',
  'trading-assistant.logs.autoRefresh': 'Автообновление',
  'trading-assistant.logs.noLogs': 'Нет журналов',
  'strategyCenter.console.pauseOnly': 'Только пауза',
  'strategyCenter.console.stopAndClose': 'Пауза и закрытие',
  'strategyCenter.editor.positionSide': 'Направление позиции',
  'strategyCenter.editor.positionSideLong': 'Лонг',
  'strategyCenter.editor.positionSideShort': 'Шорт'
}

const vi = {
  ...enUSFallback,
  'trading-assistant.logs.level.all': 'Tất cả',
  'trading-assistant.logs.level.info': 'Thông tin',
  'trading-assistant.logs.level.warning': 'Cảnh báo',
  'trading-assistant.logs.level.warn': 'Cảnh báo',
  'trading-assistant.logs.level.error': 'Lỗi',
  'trading-assistant.logs.level.trade': 'Giao dịch',
  'trading-assistant.logs.level.signal': 'Tín hiệu',
  'trading-assistant.logs.autoRefresh': 'Tự động làm mới',
  'trading-assistant.logs.noLogs': 'Không có nhật ký',
  'strategyCenter.console.pauseOnly': 'Chỉ tạm dừng',
  'strategyCenter.console.stopAndClose': 'Dừng và đóng vị thế',
  'strategyCenter.editor.positionSide': 'Hướng vị thế',
  'strategyCenter.editor.positionSideLong': 'Vị thế mua',
  'strategyCenter.editor.positionSideShort': 'Vị thế bán',
  'strategyCenter.gridOrders.tab': 'Lệnh chờ trên sàn',
  'strategyCenter.gridOrders.title': 'Các lệnh lưới đang chờ trên sàn',
  'strategyCenter.gridOrders.description': 'Lệnh được đối soát với sàn; mã lệnh của sàn là bằng chứng lệnh đã được đặt.',
  'strategyCenter.gridOrders.reconcile': 'Đối soát ngay',
  'strategyCenter.gridOrders.syncFailed': 'Đối soát lệnh trên sàn thất bại',
  'strategyCenter.gridOrders.open': 'Lệnh mở đang theo dõi',
  'strategyCenter.gridOrders.verified': 'Đã xác minh trên sàn',
  'strategyCenter.gridOrders.unverified': 'Thiếu mã lệnh của sàn',
  'strategyCenter.gridOrders.lastSync': 'Lần đối soát gần nhất',
  'strategyCenter.gridOrders.cell': 'Ô lưới',
  'strategyCenter.gridOrders.purpose': 'Mục đích',
  'strategyCenter.gridOrders.side': 'Chiều lệnh',
  'strategyCenter.gridOrders.price': 'Giá',
  'strategyCenter.gridOrders.quantity': 'Số lượng',
  'strategyCenter.gridOrders.filled': 'Đã khớp',
  'strategyCenter.gridOrders.status': 'Trạng thái',
  'strategyCenter.gridOrders.exchangeOrderId': 'Mã lệnh trên sàn',
  'strategyCenter.gridOrders.updatedAt': 'Cập nhật',
  'strategyCenter.gridOrders.notVerified': 'Chưa xác minh',
  'strategyCenter.gridOrders.empty': 'Không thấy lệnh chờ nào trên sàn',
  'strategyCenter.gridOrders.emptyHint': 'Một lưới đang chạy thường phải có lệnh chờ. Hãy đối soát và kiểm tra trạng thái chiến lược trước khi coi là đang hoạt động.',
  'executorStrategies.trigger.grid.title': 'Khớp lệnh chờ trên sàn',
  'executorStrategies.trigger.grid.description': 'Lệnh giới hạn của lưới nằm chờ trên sàn và khớp ngay khi sàn ghép lệnh; không chờ nến đóng.',
  'executorStrategies.trigger.dca.title': 'Thực thi theo lịch thời gian',
  'executorStrategies.trigger.dca.description': 'Lệnh mua chạy theo khoảng thời gian tự nhiên đã cấu hình và không phụ thuộc vào thay đổi của nến.',
  'executorStrategies.trigger.martingale.title': 'Thực thi theo mức giá thời gian thực',
  'executorStrategies.trigger.martingale.description': 'Các mức bổ sung vị thế được kiểm tra theo giá mới thay vì chờ nến đã chọn đóng.',
  'executorStrategies.trigger.layered_martingale.title': 'Thực thi phân tầng theo giá thời gian thực',
  'executorStrategies.trigger.layered_martingale.description': 'Các mức bổ sung theo tầng được kiểm tra theo giá mới; nến đã đóng vẫn là nguồn xác định cho backtest.',
  'executorStrategies.trigger.riskRealtime': 'Kiểm tra rủi ro thời gian thực',
  'executorStrategies.trigger.fillReconciled': 'Đối soát khớp lệnh qua luồng riêng tư và REST'
}

const th = {
  ...enUSFallback,
  'trading-assistant.logs.level.all': 'ทั้งหมด',
  'trading-assistant.logs.level.info': 'ข้อมูล',
  'trading-assistant.logs.level.warning': 'คำเตือน',
  'trading-assistant.logs.level.warn': 'คำเตือน',
  'trading-assistant.logs.level.error': 'ข้อผิดพลาด',
  'trading-assistant.logs.level.trade': 'การซื้อขาย',
  'trading-assistant.logs.level.signal': 'สัญญาณ',
  'trading-assistant.logs.autoRefresh': 'รีเฟรชอัตโนมัติ',
  'trading-assistant.logs.noLogs': 'ไม่มีบันทึก',
  'strategyCenter.console.pauseOnly': 'หยุดชั่วคราวเท่านั้น',
  'strategyCenter.console.stopAndClose': 'หยุดและปิดสถานะ',
  'strategyCenter.editor.positionSide': 'ทิศทางสถานะ',
  'strategyCenter.editor.positionSideLong': 'ฝั่ง Long',
  'strategyCenter.editor.positionSideShort': 'ฝั่ง Short'
}

const ar = {
  ...enUSFallback,
  'trading-assistant.logs.level.all': 'الكل',
  'trading-assistant.logs.level.info': 'معلومات',
  'trading-assistant.logs.level.warning': 'تحذير',
  'trading-assistant.logs.level.warn': 'تحذير',
  'trading-assistant.logs.level.error': 'خطأ',
  'trading-assistant.logs.level.trade': 'الصفقات',
  'trading-assistant.logs.level.signal': 'إشارة',
  'trading-assistant.logs.autoRefresh': 'تحديث تلقائي',
  'trading-assistant.logs.noLogs': 'لا توجد سجلات',
  'strategyCenter.console.pauseOnly': 'إيقاف مؤقت فقط',
  'strategyCenter.console.stopAndClose': 'إيقاف وإغلاق',
  'strategyCenter.editor.positionSide': 'اتجاه المركز',
  'strategyCenter.editor.positionSideLong': 'مركز شراء',
  'strategyCenter.editor.positionSideShort': 'مركز بيع'
}

export default {
  'en-US': locale,
  'zh-CN': zhCN,
  'zh-TW': zhTW,
  'ja-JP': ja,
  'ko-KR': ko,
  'de-DE': de,
  'fr-FR': fr,
  'ru-RU': ru,
  'vi-VN': vi,
  'th-TH': th,
  'ar-SA': ar
}
