"""Production-verified Smart Insights source registry.

The activation set is copied from the last DataVest production runbook. A
source can be production-verified without having a QuantDinger runtime
collector yet; those rows are marked ``IMPORT_ONLY`` and remain visible in
Data Health until their parser is ported and smoke-tested.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


PRODUCTION_VERIFIED_SOURCE_CODES = frozenset(
    {
        "alternative-fng",
        "bis-statistics",
        "bitinfocharts-top-addresses",
        "blockchaincenter-altcoin-season",
        "binance-usdm-derivatives",
        "bybit-derivatives",
        "cbbi-public",
        "cftc-disaggregated",
        "coinglass-liquidation-maxpain",
        "coinglass-margin-borrow",
        "coinmetrics-community",
        "coinshares-weekly",
        "cryptocraft",
        "defillama-chains",
        "defillama-stablecoins",
        "deribit-public-derivatives",
        "farside-btc-etf",
        "farside-eth-etf",
        "farside-sol-etf",
        "fred",
        "gdacs-events",
        "mempool-space",
        "nasa-eonet",
        "openbb-deribit",
        "usgs-earthquakes",
    }
)

UNQUALIFIED_SOURCE_REASONS = MappingProxyType(
    {
        "mempool-btc-large-addresses": "production smoke failed closed with MISSING_WATCHLIST",
        "cftc-legacy": "no independent deployment-network smoke passed",
        "eia-energy": "no successful production publication evidence in the verified runbook",
    }
)


@dataclass(frozen=True, slots=True)
class SourceDefinition:
    code: str
    name: str
    market: str
    collection_mode: str
    urls: tuple[str, ...]
    schedule: str
    freshness_sla_minutes: int
    methodology_version: str
    terms_url: str
    enabled_by_default: bool = False
    activation_mode: str = "IMPORT_ONLY"
    verified_at: str | None = None
    disabled_reason: str | None = None


_VERIFIED_AT = "2026-08-17"
_CRYPTOETF_ASSETS = (
    ("btc", "Bitcoin"), ("eth", "Ethereum"), ("sol", "Solana"), ("xrp", "XRP"),
    ("hyp", "Hyperliquid"), ("doge", "Dogecoin"), ("link", "Chainlink"),
    ("avax", "Avalanche"), ("hbar", "Hedera"), ("ltc", "Litecoin"),
    ("bnb", "BNB"), ("dot", "Polkadot"), ("sui", "Sui"),
)
_CRYPTOETF_SOURCE_CODES = frozenset(f"cryptoetf-{asset}-etf" for asset, _ in _CRYPTOETF_ASSETS)
_RUNTIME_ENABLED_SOURCE_CODES = frozenset({
    *_CRYPTOETF_SOURCE_CODES,
    "xoomar-btc-etf",
    "xoomar-eth-etf",
    "datavest-market-bars",
})
_RUNTIME_CODES = frozenset({
    "alternative-fng",
    "bitinfocharts-top-addresses",
    "blockchaincenter-altcoin-season",
    "binance-usdm-derivatives",
    "bybit-derivatives",
    "cbbi-public",
    "coinmetrics-community",
    "coinglass-liquidation-maxpain",
    "coinglass-margin-borrow",
    "coinshares-weekly",
    *_CRYPTOETF_SOURCE_CODES,
    "defillama-chains",
    "defillama-stablecoins",
    "deribit-public-derivatives",
    "farside-btc-etf",
    "farside-eth-etf",
    "farside-sol-etf",
    "fred",
    "mempool-space",
    "openbb-deribit",
    "xoomar-btc-etf",
    "xoomar-eth-etf",
    "datavest-market-bars",
})


def _source(
    code: str,
    name: str,
    market: str,
    mode: str,
    urls: tuple[str, ...],
    schedule: str,
    methodology: str,
    sla: int,
    terms: str,
) -> SourceDefinition:
    if code in UNQUALIFIED_SOURCE_REASONS:
        return SourceDefinition(
            code,
            name,
            market,
            mode,
            urls,
            schedule,
            sla,
            methodology,
            terms,
            False,
            "DISABLED",
            None,
            UNQUALIFIED_SOURCE_REASONS[code],
        )
    return SourceDefinition(
        code,
        name,
        market,
        mode,
        urls,
        schedule,
        sla,
        methodology,
        terms,
        code in PRODUCTION_VERIFIED_SOURCE_CODES or code in _RUNTIME_ENABLED_SOURCE_CODES,
        "RUNTIME" if code in _RUNTIME_CODES else "IMPORT_ONLY",
        _VERIFIED_AT if code in PRODUCTION_VERIFIED_SOURCE_CODES else None,
        None,
    )


_SOURCE_ROWS = (
    _source("alternative-fng", "Alternative.me Crypto Fear and Greed", "crypto", "API", ("https://api.alternative.me/fng/?limit=0&format=json",), "daily", "alternative-fng-v1", 2880, "https://alternative.me/crypto/fear-and-greed-index/"),
    _source("bis-statistics", "BIS Statistics", "macro", "API", ("https://stats.bis.org/api/v1/data",), "weekly", "bis-statistics-v1", 20160, "https://www.bis.org/terms_conditions.htm"),
    _source("bitinfocharts-top-addresses", "BitInfoCharts Richest Bitcoin Addresses", "crypto", "SCRAPING", ("https://bitinfocharts.com/top-100-richest-bitcoin-addresses.html",), "daily", "bitinfocharts-v2", 2880, "https://bitinfocharts.com/top-100-richest-bitcoin-addresses.html"),
    _source("blockchaincenter-altcoin-season", "BlockchainCenter Altcoin Season Index", "crypto", "SCRAPING", ("https://www.blockchaincenter.net/altcoin-season-index/",), "daily", "blockchaincenter-altseason-v1", 2880, "https://www.blockchaincenter.net/altcoin-season-index/"),
    _source("binance-usdm-derivatives", "Binance USD-M Futures Market Data", "crypto", "API", ("https://fapi.binance.com/",), "daily", "binance-usdm-derivatives-v1", 2880, "https://www.binance.com/en/terms"),
    _source("bybit-derivatives", "Bybit V5 Derivatives Market Data", "crypto", "API", ("https://api.bybit.com/",), "daily", "bybit-derivatives-v1", 2880, "https://www.bybit.com/en/help-center/article/Terms-of-Service"),
    _source("cbbi-public", "Colin Talks Crypto Bitcoin Bull Run Index", "crypto", "SCRAPING", ("https://colintalkscrypto.com/cbbi/", "https://colintalkscrypto.com/cbbi/data/latest.json"), "daily", "cbbi-v1", 2880, "https://colintalkscrypto.com/cbbi/"),
    _source("cftc-disaggregated", "CFTC Disaggregated Commitments of Traders", "gold", "API", ("https://publicreporting.cftc.gov/resource/72hh-3qpy.json", "https://www.cftc.gov/dea/newcot/f_disagg.txt", "https://www.cftc.gov/files/dea/history/"), "weekly", "cftc-disaggregated-v1", 14400, "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm"),
    _source("cftc-legacy", "CFTC Legacy Commitments of Traders", "gold", "API", ("https://publicreporting.cftc.gov/resource/srt6-5q2f.json",), "weekly", "cftc-legacy-v1", 14400, "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm"),
    _source("coinglass-liquidation-maxpain", "CoinGlass Liquidation Max Pain", "crypto", "SCRAPING", ("https://www.coinglass.com/liquidation-maxpain",), "daily", "coinglass-maxpain-v1", 2880, "https://www.coinglass.com/liquidation-maxpain"),
    _source("coinglass-margin-borrow", "CoinGlass Binance USDT Margin Borrow Rates", "crypto", "SCRAPING", ("https://www.coinglass.com/pro/i/MarginFeeChart",), "daily", "coinglass-margin-v1", 2880, "https://www.coinglass.com/pro/i/MarginFeeChart"),
    _source("coinmetrics-community", "Coin Metrics Community API", "crypto", "API", ("https://community-api.coinmetrics.io/v4/timeseries/asset-metrics",), "daily", "coinmetrics-v1", 2880, "https://coinmetrics.io/terms-of-use/"),
    _source("coinshares-weekly", "CoinShares Digital Asset Fund Flows", "crypto", "SCRAPING", ("https://coinshares.com/insights/research-data/",), "weekly", "coinshares-v1", 10080, "https://coinshares.com/insights/research-data/"),
    *(_source(f"cryptoetf-{asset}-etf", f"CryptoETF {name} ETF Flows", "crypto", "API", (f"https://api.cryptoetf.today/api/v1/flows/{asset}",), "daily", "cryptoetf-v1", 2880, "https://cryptoetf.today/en/api") for asset, name in _CRYPTOETF_ASSETS),
    _source("cryptocraft", "CryptoCraft Economic Calendar", "macro", "SCRAPING", ("https://www.cryptocraft.com/calendar?week=this", "https://www.cryptocraft.com/calendar?week=next"), "calendar", "cryptocraft-v1", 120, "https://www.cryptocraft.com/legal.php"),
    _source("defillama-chains", "DefiLlama Chains", "crypto", "API", ("https://api.llama.fi/v2/chains",), "daily", "defillama-chains-v1", 1440, "https://defillama.com/about"),
    _source("defillama-stablecoins", "DefiLlama Stablecoins", "crypto", "API", ("https://stablecoins.llama.fi/stablecoincharts/all",), "daily", "defillama-stablecoins-v1", 2880, "https://defillama.com/about"),
    _source("datavest-market-bars", "DataVest Market Data Gateway", "all", "INTERNAL_ADAPTER", ("https://github.com/kieucuong01/Datavest",), "every-6-hours", "datavest-market-bars-v1", 720, "https://github.com/kieucuong01/Datavest"),
    _source("deribit-public-derivatives", "Deribit Public Derivatives Market Data", "crypto", "API", ("https://www.deribit.com/api/v2/",), "daily", "deribit-public-derivatives-v1", 2880, "https://www.deribit.com/pages/information/terms-of-service"),
    _source("eia-energy", "U.S. EIA Energy", "macro", "API", ("https://api.eia.gov/v2/",), "daily", "eia-energy-v1", 11520, "https://www.eia.gov/about/copyrights_reuse.php"),
    _source("farside-btc-etf", "Farside Bitcoin ETF Flows", "crypto", "SCRAPING", ("https://farside.co.uk/btc/",), "daily", "farside-btc-v1", 2880, "https://farside.co.uk/btc/"),
    _source("farside-eth-etf", "Farside Ethereum ETF Flows", "crypto", "SCRAPING", ("https://farside.co.uk/eth/",), "daily", "farside-eth-v1", 2880, "https://farside.co.uk/eth/"),
    _source("farside-sol-etf", "Farside Solana ETF Flows", "crypto", "SCRAPING", ("https://farside.co.uk/sol/",), "daily", "farside-sol-v1", 2880, "https://farside.co.uk/sol/"),
    _source("fred", "Federal Reserve Economic Data", "macro", "API", ("https://fred.stlouisfed.org/graph/fredgraph.csv",), "daily", "fred-v1", 4320, "https://fred.stlouisfed.org/legal/"),
    _source("gdacs-events", "GDACS Events", "macro", "API", ("https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH",), "daily", "gdacs-events-v1", 360, "https://www.gdacs.org/About/legal.aspx"),
    _source("mempool-btc-large-addresses", "mempool.space BTC Large Addresses", "crypto", "API", ("https://mempool.space/api/address/", "https://mempool.space/api/blocks/tip/height"), "daily", "mempool-btc-large-addresses-v1", 2880, "https://mempool.space/about"),
    _source("mempool-space", "mempool.space", "crypto", "API", ("https://mempool.space/api/v1/fees/recommended", "https://mempool.space/api/mempool", "https://mempool.space/api/v1/mining/hashrate/3y", "https://mempool.space/api/blocks/tip/height"), "daily", "mempool-v1", 1440, "https://mempool.space/about"),
    _source("nasa-eonet", "NASA EONET", "macro", "API", ("https://eonet.gsfc.nasa.gov/api/v3/events",), "daily", "nasa-eonet-v1", 360, "https://www.nasa.gov/nasa-brand-center/images-and-media/"),
    _source("openbb-deribit", "OpenBB Deribit", "crypto", "API", ("https://docs.openbb.co/odp/python/extensions/providers",), "daily", "openbb-deribit-v1", 1440, "https://docs.openbb.co/odp/python/faqs/license"),
    _source("usgs-earthquakes", "USGS Earthquakes", "macro", "API", ("https://earthquake.usgs.gov/fdsnws/event/1/query",), "daily", "usgs-earthquakes-v1", 360, "https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits"),
    _source("xoomar-btc-etf", "Xoomar Bitcoin ETF Flow Estimate", "crypto", "API", ("https://xoomar.com/api/markets/etf-flows?asset=btc&days=90",), "daily", "xoomar-etf-v1", 2880, "https://xoomar.com/markets/api/etf-flows"),
    _source("xoomar-eth-etf", "Xoomar Ethereum ETF Flow Estimate", "crypto", "API", ("https://xoomar.com/api/markets/etf-flows?asset=eth&days=90",), "daily", "xoomar-etf-v1", 2880, "https://xoomar.com/markets/api/etf-flows"),
)

SOURCES = MappingProxyType({source.code: source for source in _SOURCE_ROWS})


def source_for_code(code: str) -> SourceDefinition:
    try:
        return SOURCES[code]
    except KeyError as exc:
        raise ValueError("unknown_data_source") from exc


def production_source_codes(*, enabled_only: bool = True) -> tuple[str, ...]:
    rows = (source for source in SOURCES.values() if not enabled_only or source.enabled_by_default)
    return tuple(sorted(source.code for source in rows))


__all__ = [
    "PRODUCTION_VERIFIED_SOURCE_CODES",
    "SOURCES",
    "SourceDefinition",
    "UNQUALIFIED_SOURCE_REASONS",
    "production_source_codes",
    "source_for_code",
]
