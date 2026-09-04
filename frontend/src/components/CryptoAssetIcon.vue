<template>
  <span
    class="crypto-asset-icon"
    :class="{ 'is-gold': isGoldAsset, 'is-index': isVietnamIndex, 'is-company': isVietnamStock }"
    :style="iconStyle"
    aria-hidden="true"
    :title="normalizedSymbol || undefined"
  >
    <span
      v-if="isVietnamStock && !isVietnamIndex && !logoLoaded"
      class="crypto-asset-icon__fallback"
    >{{ fallbackMark }}</span>
    <img
      v-if="logoUrl"
      :src="logoUrl"
      alt=""
      loading="lazy"
      decoding="async"
      referrerpolicy="no-referrer"
      :class="{ 'is-loaded': logoLoaded }"
      @load="handleLogoLoad"
      @error="handleLogoError"
    >
    <Icon
      v-else-if="iconName"
      :icon="iconName"
      :width="size"
      :height="size"
    />
    <span v-else class="crypto-asset-icon__fallback">{{ fallbackMark }}</span>
  </span>
</template>

<script>
import { Icon } from '@iconify/vue2'

const LOGO_API_BASE = 'https://logos.hunter.io/'
const TICKER_LOGO_API_BASE = 'https://img.loadlogo.com/ticker/'

const CRYPTO_ICON_NAMES = Object.freeze({
  BTC: 'cryptocurrency-color:btc',
  ETH: 'cryptocurrency-color:eth',
  SOL: 'cryptocurrency-color:sol',
  XRP: 'cryptocurrency-color:xrp',
  LINK: 'cryptocurrency-color:link',
  USDT: 'cryptocurrency-color:usdt',
  USDC: 'cryptocurrency-color:usdc',
  BNB: 'cryptocurrency-color:bnb',
  ADA: 'cryptocurrency-color:ada',
  DOGE: 'cryptocurrency-color:doge',
  AVAX: 'cryptocurrency-color:avax',
  DOT: 'cryptocurrency-color:dot',
  LTC: 'cryptocurrency-color:ltc',
  UNI: 'cryptocurrency-color:uni',
  TON: 'cryptocurrency-color:ton',
  TRX: 'cryptocurrency-color:trx',
  ATOM: 'cryptocurrency-color:atom',
  NEAR: 'cryptocurrency-color:near',
  APT: 'cryptocurrency-color:apt',
  OP: 'cryptocurrency-color:op',
  ARB: 'cryptocurrency-color:arb',
  SUI: 'cryptocurrency-color:sui',
  PEPE: 'cryptocurrency-color:pepe',
  SHIB: 'cryptocurrency-color:shib',
  MATIC: 'cryptocurrency-color:matic',
  POL: 'cryptocurrency-color:pol',
  BCH: 'cryptocurrency-color:bch',
  XLM: 'cryptocurrency-color:xlm',
  ALGO: 'cryptocurrency-color:algo',
  FIL: 'cryptocurrency-color:fil',
  ICP: 'cryptocurrency-color:icp',
  ETC: 'cryptocurrency-color:etc',
  XMR: 'cryptocurrency-color:xmr'
})

const VIETNAM_STOCK_DOMAINS = Object.freeze({
  ACB: 'acb.com.vn',
  ANV: 'navico.com.vn',
  BID: 'bidv.com.vn',
  BSR: 'bsr.com.vn',
  BCM: 'becamex.com.vn',
  BMP: 'binhminhplastic.com.vn',
  CTG: 'vietinbank.vn',
  DGC: 'ducgiangchem.vn',
  DGW: 'digiworld.com.vn',
  DIG: 'dic.vn',
  DXG: 'datxanhgroup.vn',
  EIB: 'eximbank.com.vn',
  FPT: 'fpt.com',
  FRT: 'frt.vn',
  FTS: 'fpts.com.vn',
  GAS: 'pvgas.com.vn',
  GMD: 'gemadept.com.vn',
  HAG: 'hagl.com.vn',
  HCM: 'hsc.com.vn',
  HDB: 'hdbank.com.vn',
  HPG: 'hoaphat.com.vn',
  HSG: 'hoasengroup.vn',
  HVN: 'vietnamairlines.com',
  KDC: 'kdc.vn',
  KDH: 'khangdien.com.vn',
  LPB: 'lpbank.com.vn',
  MBB: 'mbbank.com.vn',
  MSN: 'masan.group',
  MWG: 'mwg.vn',
  NKG: 'namkimgroup.vn',
  NLG: 'namlong.com.vn',
  NTP: 'nhuatienphong.com.vn',
  NVL: 'novaland.com.vn',
  OCB: 'ocb.com.vn',
  OIL: 'pvoil.com.vn',
  PDR: 'phatdat.com.vn',
  PLX: 'petrolimex.com.vn',
  PNJ: 'pnj.com.vn',
  POW: 'pvpower.vn',
  PVD: 'pvd.com.vn',
  PVS: 'pvs.com.vn',
  REE: 'ree.com.vn',
  SAB: 'sabeco.com.vn',
  SHB: 'shb.com.vn',
  SSI: 'ssi.com.vn',
  STB: 'sacombank.com.vn',
  TCB: 'techcombank.com',
  TCH: 'hoanghuy.vn',
  TLG: 'thienlonggroup.com',
  TPB: 'tpb.vn',
  VCB: 'vietcombank.com.vn',
  VCI: 'vcsc.com.vn',
  VHC: 'vinhhoan.com',
  VHM: 'vinhomes.vn',
  VIB: 'vib.com.vn',
  VIC: 'vingroup.net',
  VJC: 'vietjetair.com',
  VND: 'vndirect.com.vn',
  VNM: 'vinamilk.com.vn',
  VRE: 'vincom.com.vn',
  VTP: 'viettelpost.com.vn',
  VPB: 'vpbank.com.vn'
})

const VIETNAM_INDEXES = Object.freeze(['VN30', 'VNINDEX', 'VNI'])

function normalizeSymbol (value) {
  let symbol = String(value || '').trim().toUpperCase()
  if (!symbol) return ''

  const separatorIndex = symbol.lastIndexOf(':')
  if (separatorIndex >= 0) symbol = symbol.slice(separatorIndex + 1)
  symbol = symbol.split(/[_-]/u)[0].split('/')[0]
  symbol = symbol.replace(/(?:USDTM|USDT|USDC|USD)$/u, '')
  return symbol.replace(/[^A-Z0-9]/gu, '')
}

export default {
  name: 'CryptoAssetIcon',
  components: { Icon },
  props: {
    symbol: { type: [String, Number], default: '' },
    market: { type: String, default: '' },
    size: { type: Number, default: 28 }
  },
  data () {
    return { logoCandidateIndex: 0, logoFailed: false, logoLoaded: false }
  },
  computed: {
    normalizedSymbol () {
      return normalizeSymbol(this.symbol)
    },
    iconName () {
      if (this.isGoldAsset) return 'fa6-solid:coins'
      if (this.isVietnamIndex) return 'fa6-solid:chart-line'
      return CRYPTO_ICON_NAMES[this.normalizedSymbol] || ''
    },
    isGoldAsset () {
      const market = String(this.market || '').trim().toLowerCase()
      return ['forex', 'gold', 'xau'].includes(market) || this.normalizedSymbol === 'XAU'
    },
    isVietnamStock () {
      const market = String(this.market || '').trim().toLowerCase()
      return ['vn', 'vnstock', 'vietnamstock', 'vietnam-stock'].includes(market)
    },
    isVietnamIndex () {
      return this.isVietnamStock && VIETNAM_INDEXES.includes(this.normalizedSymbol)
    },
    logoCandidates () {
      if (!this.isVietnamStock || this.isVietnamIndex || !this.normalizedSymbol) return []
      const candidates = []
      const domain = VIETNAM_STOCK_DOMAINS[this.normalizedSymbol]
      if (domain) candidates.push(`${LOGO_API_BASE}${domain}`)
      candidates.push(`${TICKER_LOGO_API_BASE}${encodeURIComponent(this.normalizedSymbol)}?size=128&format=png&fallback=404`)
      return candidates
    },
    logoUrl () {
      if (this.logoFailed) return ''
      return this.logoCandidates[this.logoCandidateIndex] || ''
    },
    fallbackMark () {
      return this.normalizedSymbol.slice(0, 3) || '?'
    },
    iconStyle () {
      const dimension = `${this.size}px`
      return { width: dimension, height: dimension }
    }
  },
  watch: {
    symbol () { this.resetLogoState() },
    market () { this.resetLogoState() }
  },
  methods: {
    resetLogoState () {
      this.logoCandidateIndex = 0
      this.logoFailed = false
      this.logoLoaded = false
    },
    handleLogoLoad () {
      this.logoLoaded = true
    },
    handleLogoError () {
      if (this.logoCandidateIndex < this.logoCandidates.length - 1) {
        this.logoCandidateIndex += 1
      } else {
        this.logoFailed = true
      }
    }
  }
}
</script>

<style lang="less" scoped>
.crypto-asset-icon {
  display: inline-grid;
  position: relative;
  flex: 0 0 auto;
  place-items: center;
  overflow: hidden;
  border: 1px solid rgba(36, 83, 198, .14);
  border-radius: 50%;
  background: #f5f8ff;
  color: #2453c6;
  line-height: 1;
  vertical-align: middle;
}

.crypto-asset-icon.is-gold {
  border-color: rgba(188, 137, 24, .28);
  background: #fff8df;
  color: #b77d08;
}

.crypto-asset-icon.is-index {
  border-color: rgba(36, 83, 198, .2);
  background: #eef3ff;
  color: #2453c6;
}

.crypto-asset-icon img {
  display: block;
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  padding: 2px;
  opacity: 0;
  transition: opacity .16s ease;
}

.crypto-asset-icon img.is-loaded {
  opacity: 1;
}

.crypto-asset-icon :deep(svg) {
  display: block;
  max-width: 100%;
  max-height: 100%;
}

.crypto-asset-icon__fallback {
  font-size: .34em;
  font-weight: 800;
  letter-spacing: -.02em;
}
</style>
