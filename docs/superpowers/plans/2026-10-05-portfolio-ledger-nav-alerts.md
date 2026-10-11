# Portfolio Ledger, NAV, Benchmark and Alerts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Hoàn thiện sổ giao dịch, NAV lịch sử, benchmark và cảnh báo chọn lọc ngay trong trang Danh mục, mỗi phần một commit.

**Architecture:** Tài khoản có ledger là nguồn sự thật cho tiền mặt/vị thế và tách khỏi vị thế thủ công cũ. Snapshot đóng ngày được dựng từ ledger revision và giá raw có nguồn. Tái sử dụng gateway giá, vòng monitor và hộp thông báo hiện tại; không thêm broker, AI pipeline hay dependency.

**Tech Stack:** Python/Flask, PostgreSQL, Decimal, Vue 2, Ant Design Vue, ECharts, pytest, node:test.

**Spec:** `docs/superpowers/specs/2026-10-05-portfolio-ledger-nav-alerts-design.md`

**Status:** Người dùng đã duyệt thiết kế và kế hoạch ngày 2026-10-06; đã hoàn tất local ngày 2026-10-11, gồm bản sửa sau rà soát. Bằng chứng kiểm tra và quyết định triển khai lưu ở `portfolio-execution-ledger.md`.

## Global Constraints

- Ghi nhận thủ công danh mục mua và nắm giữ; thông báo trong ứng dụng. Có nhập CSV.
- VND, USD, USDT là ba đơn vị riêng; không tự coi USDT bằng USD hay cộng thành một NAV khi chưa có FX được kiểm chứng.
- Không sao chép tự động hay xóa vị thế cũ. Không dựng đường lịch sử chỉ bằng quantity hiện tại nhân giá quá khứ.
- Thiếu giá => NAV đầy đủ null. Không vẽ điểm 0, nối qua khoảng trống hay dùng giá ngày tương lai.
- Lợi nhuận đã điều chỉnh dòng tiền là ước tính Modified Dietz; không gọi là TWR chính xác.
- Mọi đọc/ghi/CSV/refresh ràng buộc user_id phía server; mọi ghi dùng transaction và khóa tài khoản.
- Không gửi email/Telegram, deploy hay chạy migration production trong đợt local này.
- Thực hiện trực tiếp trong phiên hiện tại, tuần tự bốn task; không giao code cho subagent.
- Giữ công việc ngoài phạm vi và graph artifacts đang dirty. Chỉ stage file thuộc từng task.

## Review Focus

1. Gửi lại cùng idempotency key với payload khác phải báo conflict, không ghi thêm/đổi giao dịch.
2. Sửa giao dịch cũ làm một lần bán về sau vượt vị thế phải từ chối toàn bộ revision, không để sổ mất cân đối.
3. Cổ tức tiền mặt phải đi vào kết quả đầu tư; raw prices tránh cộng cổ tức hai lần với adjusted prices.
4. Giá phiên trước hợp lệ khi thị trường đóng cửa khác với provider mất dữ liệu; không phát cảnh báo mất giá cuối tuần bình thường.
5. Cooldown không được nuốt thay đổi mới: lưu pending fingerprint để digest sau, đồng thời worker chạy trùng chỉ ghi một thông báo.

## Lệnh kiểm tra dùng chung

Backend, tại `backend/backend_api_python`:

```powershell
$env:PYTHONPATH=(Resolve-Path '.test_deps/Lib/site-packages').Path
& 'C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m pytest tests/test_portfolio_ledger.py tests/test_portfolio_ledger_repository.py tests/test_portfolio_books_routes.py -q -p no:cacheprovider --basetemp=.tmp/portfolio-ledger
```

Frontend, tại `frontend`: `node --test tests/unit/*.test.mjs` và lint các file thay đổi. Dùng Vite local + browser để nghiệm thu Vue thật với dữ liệu giả lập có nhãn; không gọi broker hoặc job AI. Cuối đợt chạy `node node_modules/vite/bin/vite.js build`, `git diff --check`, `./tools/graphify.ps1 update .`.

## Task 1: Sổ giao dịch và tiền mặt

**Files:**
- Create: `backend/backend_api_python/migrations/20261005_portfolio_ledger.sql`.
- Create: `backend/backend_api_python/app/services/portfolio/ledger.py`, `ledger_repository.py`, `books.py`.
- Create: `backend/backend_api_python/app/routes/portfolio_books.py`; register ở `app/openapi/register.py`.
- Modify: `backend/backend_api_python/app/utils/db.py` để nối migration vào bootstrap.
- Create: `frontend/src/api/portfolio-books.js`, `frontend/src/views/mock-portfolio/components/PortfolioBookWorkspace.vue`, `LedgerEntryForm.vue`, `LedgerImport.vue`, `frontend/src/locales/portfolio-books.js`.
- Modify: `frontend/src/views/mock-portfolio/index.vue`, locale composition hiện có để thêm chọn nguồn "Vị thế thủ công / Sổ giao dịch".
- Test: `tests/test_portfolio_ledger.py`, `test_portfolio_ledger_repository.py`, `test_portfolio_books_routes.py`, `tests/unit/portfolioBookLifecycle.test.mjs`.

**Interfaces:**
- `normalize_event(payload: dict, currency: str) -> dict`: canonical market/symbol, Decimal hữu hạn, event UUID, aware timestamp UTC; từ chối thời điểm tương lai.
- `replay_ledger(events: list[dict], cutoff: datetime | None = None) -> dict`: cash, positions(quantity/cost), realizedPnl, income, externalFlows; sắp theo effectiveAt rồi sequence.
- Repository `list_owned(user_id)`, `load_owned(user_id, book_id)`, `mutate(user_id, book_id, expected_revision, request_key, events, replacements)`: row lock `FOR UPDATE`, replay toàn bộ trước commit, trả revision.
- Books service `create`, `opening_preview`, `opening_commit`, `state`, `append`, `revise`, `csv_preview`, `csv_commit`. Constructor nhận repository và clock để kiểm thử.
- Routes `/api/portfolio/books`, `/books/<id>/state`, `/books/<id>/opening/{preview,commit}`, `/books/<id>/entries`, `/books/<id>/entries/<event_id>/revisions`, `/books/<id>/import/{preview,commit}`; GET entries phân trang 50, tối đa 200.
- Request mang `expectedRevision` và `requestKey`; response envelope hiện tại, decimal dạng string. Schema dùng NUMERIC(38,12), timestamps có timezone, unique `(book_id, request_key)` và `(book_id, revision, event_id)`; ownership đọc từ session.
- CSV text UTF-8 trong JSON, tối đa 1 MB/1.000 dòng; cột `eventId,type,effectiveAt,market,symbol,quantity,unitPrice,amount,fee,tax,notes`. Preview không ghi; commit xác minh lại server, all-or-nothing.
- Opening preview đọc ID vị thế thuộc user/cùng currency/long; opening events giữ giá vốn đã khai báo, cash do user nhập. Commit xác minh fingerprint preview để không nhập từ dữ liệu cũ đã thay đổi.

- [x] **Step 1: Viết kiểm tra failing cho số học và abuse cases.**
  Mua 100 x 100 phí 100, mua 100 x 120 phí 100 => cost 22.200, average 111. Bán 50 x 130 phí 50 thuế 20 => realized 880, còn 150, cost 16.650. Cổ tức 200 tăng cash/income, externalFlows không đổi. Test fractional token, NaN/infinity, cash âm, oversell; revision làm giao dịch sau invalid; requestKey payload khác; user B không đọc/ghi được sổ user A.
- [x] **Step 2: Chạy test mới và xác nhận RED do interface chưa có.** Dùng lệnh backend trên, node:test cho lifecycle mới. Không sửa test để bỏ trường hợp yêu cầu.
- [x] **Step 3: Triển khai ledger, repository, service, API, migration và UI.** Unique replay, append audit trail; revision cũ luôn đọc lại được. `PortfolioBookWorkspace` chỉ mount khi chọn sổ, không cộng vị thế legacy vào sổ. CSV có lỗi từng dòng/preview tổng tiền trước nút ghi; UI sửa/hủy tạo revision.
- [x] **Step 4: Xác nhận GREEN.** SQLite-backed SQL fixture cho ownership/idempotency/revision; adapter SQLite chỉ bỏ cú pháp PostgreSQL-specific, thêm kiểm tra migration/bootstrap. Browser: mở sổ VND, deposit/buy/partial sell, CSV lỗi/trùng, đổi sổ khi request cũ chưa xong. Existing portfolio/optimizer tests vẫn qua.
- [x] **Step 5: Commit riêng.** `feat: add owner-scoped portfolio transaction and cash ledger` với đúng file task 1; ghi SHA vào kế hoạch.

## Task 2: NAV lịch sử và lợi nhuận điều chỉnh dòng tiền

**Files:**
- Create: `app/services/portfolio/nav.py`, `history.py`, `tests/test_portfolio_nav.py`, `test_portfolio_history.py` trong backend.
- Modify: `app/services/portfolio/ledger_repository.py`, `books.py`, `app/routes/portfolio_books.py`.
- Create migration `migrations/20261005_portfolio_nav.sql`, nối `app/utils/db.py`.
- Modify: `app/services/portfolio_optimizer/quantdinger_gateway.py`, `market_data.py`: tùy chọn `price_mode`, default optimizer giữ nguyên `total_return` cho VN; NAV yêu cầu raw.
- Modify: `app/services/portfolio_monitor.py` thêm tick checkpoint daily books; worker batching tái sử dụng vòng hiện có.
- Create: `frontend/src/views/mock-portfolio/components/PortfolioNavHistory.vue`, `portfolioHistory.js`, `tests/unit/portfolioHistory.test.mjs`; sửa API/workspace/locale.

**Interfaces:**
- `build_nav_snapshot(events, prices, *, cutoff, ledger_revision) -> dict`: cash, nav|null, valuedNav, coverage, status, positions, captured sources, checksum, externalFlows; prices định danh `(market,symbol,tradeDate)` với mode raw.
- `modified_dietz(begin_nav, end_nav, flows, start_at, end_at) -> dict`: `(end - begin - sum(flow))/(begin + sum(weight*flow))`, `weight=(end_at-flow_at)/(end_at-start_at)`. Trả null nếu bất kỳ external flow tuyệt đối >=10% NAV đầu mà không có valuation tại flow; nêu `large_flow_requires_valuation`. Null khi denominator<=0/invalid/cutoff thiếu.
- `PortfolioHistoryService.refresh(user_id, book_id, start_date, end_date)`: max 366 ngày/request, cutoff trước ngày đang chạy; lock/claim mỗi book/date/revision, abort write nếu revision đổi trong fetch. Snapshot unique `(book_id, day, revision)`, giá và ledger checksum đóng băng.
- `history(user_id, book_id, start_date, end_date)`: mặc định 90 ngày, chỉ revision hiện tại; revision cũ có nhãn superseded, không làm current chart. `mark_dirty_from(day)` từ mutation task 1, không xóa bằng chứng cũ.
- Gateway `fetch_daily(instrument, *, start_date, end_date, price_mode=None)` giữ default cũ; NAV truyền raw, từ chối provider trả mode khác, index không là holding. Snapshot chỉ dùng bar đã hoàn tất, không future lookahead.
- Monitor `refresh_due_books(limit=20)`: tối đa một ngày mới và một ngày cần thử lại/book/tick, durable next_due/lease và hàng đợi retry, retry lease timeout, không chặn monitor cũ bằng backfill dài. Người dùng có nút tạo lại lịch sử trong API riêng, không làm trên GET.
- UI timeframe 1W/1M/YTD/All hoạt động; ECharts `connectNulls:false`; hai nguồn ledger NAV và giá trị phần định giá phân biệt rõ.

- [x] **Step 1: Viết failing tests.** Cash-only 100 -> end150, flow+50 giữa kỳ => return0; end160 => 10/125 cho flow nhỏ hoặc valuation tại flow. Flow20 trên begin100 thiếu flow valuation => return null, reason rõ. Dividend 10 end110, flow0 =>10%. Revision cũ không lên chart, missing price không thành0, adjusted-price input từ chối, future bar bỏ, fractional times và zero denominator giữ null.
- [x] **Step 2: Chạy test NAV/history/gateway và quan sát RED.** Thêm kiểm tra boot migration và existing optimizer VN tests vào cùng nhóm phù hợp.
- [x] **Step 3: Triển khai hàm snapshot/performance, persistence, gateway option, scheduler và chart.** Cash flow tại đúng biên kỳ theo quy ước `(start,end]`; flow đầu kỳ đã trong beginNAV. Không geometric-chain qua gap; sau gap dùng mốc bắt đầu mới có nhãn, không quảng cáo all-time return.
- [x] **Step 4: Xác nhận GREEN và UI.** So độc lập bảng Decimal; giả lập 3 ngày, mất provider ngày giữa, worker claim lặp, sửa CSV lùi ngày đang refresh. Cuối tuần HOSE giữ ngày quote phiên trước và không giả lập phiên giao dịch. Snapshot pipeline/test runtime local phải đi qua hook monitor mới.
- [x] **Step 5: Commit riêng.** `feat: persist provenance-backed daily portfolio NAV and cash-flow-adjusted returns`.

## Task 3: Benchmark cùng kỳ và đơn vị

**Files:**
- Create: `app/services/portfolio/benchmarks.py`, `tests/test_portfolio_benchmarks.py`.
- Modify: `app/services/portfolio/history.py`, `app/routes/portfolio_books.py`, frontend API/`PortfolioNavHistory.vue`/`portfolioHistory.js`/locale.
- Add frontend tests trong `tests/unit/portfolioHistory.test.mjs`.

**Interfaces:**
- `benchmark_registry(currency) -> list[dict]`: VND VNINDEX/VN30 (index points, underlying VND); USDT BTC/USDT; USD XAUUSD. Label price return, baseline selection confirmed by user; no benchmark default for unknown currency.
- `compare_benchmark(nav_points, benchmark_series, *, benchmark_key, currency) -> dict`: đồng bộ ngày hoàn tất, require >=2 điểm hợp lệ; first common date normalize100. Return benchmarkReturn, portfolioReturn|null, excessPctPoints|null, common dates, provider/checksum/priceMode, disclaimer. Portfolio missing segment => không tính excess toàn kỳ.
- API GET `/books/<id>/benchmark?key=&start=&end=` và PUT lựa chọn benchmark trên owned book. Gateway market data raw, bounds366 ngày, cache chỉ chuỗi giá công khai, không cache portfolio theo key thiếu user/revision.

- [x] **Step 1: Viết failing tests.** Benchmark100->110, portfolio100->108 cùng kỳ không flow => excess -2 điểm%; ngày bắt đầu khác phải reset tại giao nhau, benchmark USD cho bookVND từ chối, thiếu đoạn hoặc chỉ1điểm trả null. Cổ tức NAV được tính nhưng price-index label không gọi total return/alpha.
- [x] **Step 2: Xác nhận RED cho module/interface mới.** Chạy test benchmark và frontend alignment; giữ fixtures không dùng giá thị trường hiện tại.
- [x] **Step 3: Triển khai registry, alignment và UI.** Chọn index rõ ràng, biểu đồ100, source/date/method cạnh chart; không biến benchmark thành mã giao dịch. Đổi key chỉ đổi comparison; ledger revision và NAV giữ nguyên.
- [x] **Step 4: Xác nhận GREEN và UI.** Switching benchmark khi response cũ về muộn không ghi đè, same currency/date check server, không nội suy thiếu phiên; chart light/dark/mobile.
- [x] **Step 5: Commit riêng.** `feat: compare portfolio performance with aligned native-currency benchmarks`.

## Task 4: Cảnh báo chọn lọc và digest

**Files:**
- Create: `app/services/portfolio/selective_alerts.py`, `alert_repository.py`, `report_changes.py`; `tests/test_portfolio_selective_alerts.py`, `test_portfolio_alert_repository.py`.
- Create migration `migrations/20261005_portfolio_selective_alerts.sql`, nối bootstrap.
- Modify: `app/services/portfolio_monitor.py`, `app/routes/portfolio_books.py`, `app/services/ai_report_pdf.py` để nhận diện key_risks/invalidation/next_watch của quyết định cuối khi cần.
- Create: `frontend/src/views/mock-portfolio/components/PortfolioAlertPreferences.vue`, `tests/unit/portfolioAlertPreferences.test.mjs`; nối workspace/API/locale.

**Interfaces:**
- `evaluate_selective_alerts(settings, current, previous) -> list[dict]`: loại `allocation`, `data_quality`, `report_change`, `asset_event`; evidence links/date/fingerprint, không thực hiện gửi/AI trong hàm.
- Preferences per owned book: enabled false ban đầu, concentration threshold user chọn 1..100%, data/report/event toggles, digest interval24h mặc định/cooldown tối thiểu6h. Lần đầu bật chỉ baseline và hiện trạng trên UI, không bắn các sự kiện cũ.
- `report_change(previous_report,current_report)`: same asset/kind/locale, completed strictly earlier; đọc final-manager fields qua extractor hiện có, thêm field mapping/test nếu thiếu. Báo thay đổi text, không tự đánh giá điều kiện đã trigger hoặc rủi ro đã hết; sections thiếu không tạo diff.
- `evaluate_due_alerts(limit=20)`: nhận book snapshots revision hiện tại và source reports/events được phép theo watchlist; account-private không đưa ra public. Quote trên phiên đóng hợp lệ không thành data-loss, partial valuation không tính tỷ trọng.
- Repository `claim_transition`, `queue_pending`, `emit_due_digest(user_id)` dưới transaction/row lock. Unique state theo user/book/rule/asset và episode; pending fingerprint không bị overwrite mất thay đổi. Digest chỉ rows sau baseline chưa gửi; insert vào `qd_strategy_notifications` với strategy_id NULL/user_id thật và mark sent cùng transaction.
- Cooldown không gửi lại state không đổi. Recovery một lần; episode mới sau false->true được cảnh báo dù text giống lần trước. Khi tắt, hủy pending và không nhận delivery; worker restart không reset baseline.
- API GET/PUT `/books/<id>/alert-preferences`; notifications dùng route owned `strategy_notifications.py` hiện có. Có source links đọc lại, đánh dấu đã đọc qua API hiện tại; chỉ in-app.

- [x] **Step 1: Viết failing tests.** Threshold vượt/chưa vượt, same fingerprint, recovery/new episode, baseline, pending qua cooldown, concurrent claim chỉ một notice, tắt trong lúc digest, missing/incompatible report không tạo diff, event không có ID/source không tạo notice; user B không thấy payload user A.
- [x] **Step 2: Xác nhận RED ở pure evaluator/repository/API.** Kiểm tra ownership route và migration; không phát email/Telegram thật trong test.
- [x] **Step 3: Triển khai preferences/evaluator/persistence/digest và hook monitor.** Không thêm schedule song song; chọn event IDs/source dates từ bằng chứng đã lưu. Ghi message plain text và payload allowlist, không HTML từ ghi chú/report untrusted.
- [x] **Step 4: Xác nhận GREEN và UI.** Opt-in, đổi ngưỡng/tắt, một digest thay vì nhiều report; fake clock worker hai lần và restart. Verify monitor hook, owned notification GET/mark-read và không bật external channels.
- [x] **Step 5: Commit riêng.** `feat: add opt-in portfolio change alerts with durable dedup and digests`.

## Kết thúc đợt

- [x] Chạy tests tập trung cho cả bốn phần, full frontend unit, changed-file lint, production build; kiểm tra không có paid AI/broker calls ở read/refresh path.
- [x] Kiểm tra browser authenticated với hai user trên DB thử nghiệm nếu có; nếu không, ghi rõ giới hạn và dùng fixture UI + server ownership tests, không gọi đó là production proof.
- [x] Cập nhật Graphify, giữ graph artifacts khỏi commit feature; rà exact staged diff từng commit.
- [x] Báo bốn SHA, kết quả test, migration cần khi release và giới hạn phương pháp tính; không push/deploy nếu chưa được yêu cầu.
