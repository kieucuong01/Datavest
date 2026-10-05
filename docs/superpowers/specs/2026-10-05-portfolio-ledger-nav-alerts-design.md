# Sổ giao dịch, NAV lịch sử, benchmark và cảnh báo chọn lọc

Trạng thái: người dùng đã duyệt thiết kế ngày 05/10/2026; chưa triển khai.

## Mục tiêu và phạm vi 80/20

Hoàn thiện trang Danh mục hiện tại để nhà đầu tư ghi lại giao dịch, biết
tiền đang ở đâu, lãi/lỗ đã thực hiện, kết quả đầu tư sau khi tách nạp/rút,
và những thay đổi cần xem lại. Làm tuần tự bốn phần, commit riêng từng phần.

Giả định cho bản đầu: ghi nhận thủ công danh mục mua và nắm giữ; thông báo
trong ứng dụng. Có nhập CSV. VND, USD, USDT là ba đơn vị riêng; không tự coi
USDT bằng USD hay cộng thành một NAV khi chưa có FX được kiểm chứng.
Người dùng đã duyệt bản đầu mua/nắm giữ và thông báo trong ứng dụng.
Thay đổi phạm vi này phải sửa thiết kế trước triển khai; không tự thêm ký quỹ hay broker.

## Hiện trạng đã kiểm tra trong source

- `app/routes/portfolio.py` lưu `qd_manual_positions` theo user. Khi thêm
  cùng mã/nhóm, code xóa rồi chèn vị thế mới; đây không phải sổ giao dịch.
- `portfolio/positions.py` đã phân nhóm tiền tệ, giữ giá thiếu là null.
- `mock-portfolio/index.vue` có các vùng giao dịch, hiệu suất và benchmark,
  nhưng chưa nối dữ liệu lịch sử; realized P&L còn để trống.
- `portfolio_optimizer/quantdinger_gateway.py` và `market_data.py` cung cấp
  chuỗi ngày có nguồn, checksum và thông tin đơn vị/chế độ giá.
- `portfolio_monitor.py` có vòng kiểm tra, gom thông báo theo user và ghi
  `qd_strategy_notifications`. Tái sử dụng lịch chạy và hộp thông báo này.
- `ai_report_pdf.py` đã tách quyết định cuối cùng của Portfolio Manager;
  không cần thêm lượt AI để phát hiện thay đổi nội dung báo cáo.

## Hai cách tích hợp

1. Biến mọi vị thế thủ công hiện tại thành sổ ngay. Ít thành phần hiển thị,
   nhưng thay đổi ngữ nghĩa CRUD và optimizer apply, đồng thời không biết
   tiền mặt/lịch sử ban đầu của người dùng.
2. Thêm tài khoản có sổ ngay trong trang Danh mục, giữ vị thế cũ đọc/sửa
   theo luồng hiện tại cho đến khi người dùng chọn chuyển. Tài khoản có sổ
   lấy vị thế từ giao dịch, không cho sửa trực tiếp quantity/giá vốn.

Chọn cách 2: người dùng tạo sổ mới hoặc chọn vị thế cũ để khởi tạo, xem
trước số dư, nhập tiền mặt rồi xác nhận. Không sao chép tự động hay xóa
vị thế cũ. Chọn rõ nguồn dữ liệu đang xem để tránh tính một vị thế hai lần.
Optimizer apply tiếp tục vào vị thế thủ công; chưa áp dụng thay đổi phân
bổ như thể đã có giao dịch thực hiện trong sổ.

## 1. Sổ giao dịch và tiền mặt

Tài khoản thuộc một user và một tiền tệ. Sổ lưu thời điểm hiệu lực UTC,
ngày hiển thị UTC+7, loại sự kiện, mã/thị trường, quantity, giá, phí, thuế,
số tiền, ghi chú, nguồn nhập và khóa chống gửi trùng.

- Loại sự kiện: số dư đầu kỳ, mua, bán, nạp, rút, cổ tức tiền mặt,
  phí/thuế độc lập và điều chỉnh số lượng có căn cứ (ví dụ chia tách).
- Giá vốn bình quân gia quyền; phí mua vào giá vốn, phí/thuế bán trừ khỏi
  realized P&L. Bán một phần giữ giá vốn của phần còn lại.
- Decimal cho tiền và quantity; từ chối NaN, infinity, số âm không hợp lệ,
  bán vượt số lượng và chi/rút vượt tiền mặt. Không tự cho vay ký quỹ.
- Mua/bán chỉ chuyển đổi tiền mặt và vị thế, không phải external cash flow.
  Cổ tức tiền mặt là thu nhập đầu tư, không phải tiền người dùng nạp.
- Sổ là ghi nhận kinh tế theo ngày giao dịch, không xác nhận tiền/chứng
  khoán đã thanh toán hay lượng tiền được rút tại broker.
- Giữ dấu vết khi sửa/hủy: revision và bản sự kiện trước đó. Giao dịch
  lùi ngày làm vô hiệu snapshot từ ngày đó; không âm thầm giữ NAV cũ.
- CSV có preview lỗi từng dòng, timezone/đơn vị rõ ràng; commit theo batch
  nguyên tử, chống nhập lặp bằng batch ID và khóa dòng. Giới hạn kích thước.
- Số dư đầu kỳ ghi rõ là do người dùng khai báo. Lịch sử bắt đầu từ mốc
  này, không suy diễn các giao dịch hoặc hiệu suất trước mốc.

## 2. NAV theo ngày và hiệu suất

NAV = tiền mặt + giá trị vị thế, theo từng tài khoản/tiền tệ. Tính vị thế
từ ledger tại cutoff; lấy giá đóng cửa ngày đã hoàn tất, lưu nguồn,
tradeDate/observedAt, retrievedAt, priceMode, checksum, ledger revision
và độ phủ định giá cùng snapshot.

- Unique theo tài khoản/ngày/revision; job chạy lặp không nhân đôi điểm.
  Dùng lịch worker hiện có, xử lý từng batch nhỏ và checkpoint.
- Ngày đang diễn ra chỉ là định giá tạm tính, không ghi như phiên đóng.
  Crypto, HOSE và vàng có lịch giá riêng, không giả định cùng phiên.
- Thiếu giá => NAV đầy đủ null, vẫn có giá trị phần đã định giá và coverage.
  Không vẽ điểm 0, nối qua khoảng trống hay dùng giá ngày tương lai.
- Khi thị trường đóng cửa có thể dùng giá phiên trước với nhãn ngày/tuổi
  dữ liệu; giá quá hạn hoặc điều chỉnh không được đối chiếu không tạo
  lợi nhuận chính thức. Thiếu thao tác corporate action => nêu gap.
- Không dựng đường lịch sử chỉ bằng quantity hiện tại nhân giá quá khứ.
  Backfill chỉ dùng ledger đã có và chuỗi giá lịch sử có provenance.
- Hiệu suất bản đầu dùng Modified Dietz với trọng số thời gian của nạp/rút
  giữa hai định giá. Nhãn rõ là lợi nhuận đã điều chỉnh dòng tiền, ước tính;
  không gọi là TWR chính xác. Không tính khi NAV đầu/cuối thiếu, vốn bình
  quân không dương hoặc dòng tiền lớn khiến khoảng định giá không đủ tin cậy.
- Cộng dồn hình học chỉ các đoạn hợp lệ, cùng revision và không có gap;
  mất đoạn => hiển thị chưa đủ dữ liệu cho toàn kỳ. Có ít nhất hai mốc NAV.

Đối chiếu phương pháp với [GIPS Handbook for Firms](https://www.gipsstandards.org/standards/gips-standards-for-firms/gips-standards-handbook-for-firms/):
định giá tại mỗi external cash flow cho TWR chính xác hơn Modified Dietz.
Sản phẩm không tuyên bố tuân thủ/chứng nhận GIPS.

## 3. Benchmark cùng kỳ, cùng tiền tệ

- VND: VNINDEX mặc định, VN30 tùy chọn; USDT: BTC/USDT; USD: XAUUSD.
  Người dùng chọn/chấp nhận benchmark; không coi là mức phù hợp cho mọi
  chiến lược hoặc benchmark tổng lợi nhuận khi chỉ có price index.
- Hai đường chuẩn hóa từ 100 tại cùng ngày bắt đầu. Chỉ so sánh ngày có
  NAV hợp lệ và benchmark hợp lệ; không lấp dữ liệu cuối tuần bằng nội suy.
- Excess return là chênh lệch điểm phần trăm, không gọi là alpha.
  Nêu portfolio có/không bao gồm cổ tức và benchmark là price return.
- Đổi benchmark không đổi ledger/NAV và không phát sinh lượt AI.
  Nguồn, kỳ so sánh và giới hạn chất lượng luôn hiện cạnh biểu đồ.
- Không có benchmark cùng tiền tệ/đơn vị => unavailable, không dùng FX giả.

## 4. Cảnh báo có chọn lọc

Người dùng chọn bật và ngưỡng riêng. Vòng monitor kiểm tra dữ liệu đã có,
không gọi AI cho mỗi lần kiểm tra. Lưu trạng thái bền vững theo user/rule/
tài sản, fingerprint đầu vào, trạng thái lần trước và lần thông báo.

- Vượt tỷ trọng: ngưỡng người dùng đặt, chỉ kiểm tra khi NAV/giá đủ mới.
- Mất/chậm dữ liệu: báo lần chuyển trạng thái; phục hồi có thể báo một lần.
- Báo cáo mới có thay đổi rủi ro/điều kiện vô hiệu: so kỳ trước cùng mã,
  loại/ngôn ngữ, trích trực tiếp quyết định cuối cùng. Gọi đúng là thay đổi
  nội dung, không tuyên bố điều kiện đã xảy ra hay rủi ro đã hết.
- Sự kiện mới của mã trong vị thế/watchlist: chỉ dữ liệu có định danh,
  nguồn/ngày, trong cửa sổ thời gian; không cảnh báo suy đoán từ văn bản.
- Chống trùng bằng unique fingerprint; cooldown và digest theo user.
  Trạng thái không đổi không gửi lại toàn bộ báo cáo. Nội dung thiếu/khác
  ngôn ngữ không tự trở thành cảnh báo thay đổi luận điểm.
- Khởi tạo baseline không bắn loạt cảnh báo cũ. Worker đồng thời chỉ một
  lần claim được sự kiện. Có nút tắt, đánh dấu đã đọc và xem dữ kiện gốc.
- Bản đầu chỉ hộp thông báo trong ứng dụng. Email/Telegram chỉ thêm khi
  người dùng chọn kênh/đích và kiểm tra delivery bằng nội dung đã đồng ý.

## Dữ liệu, quyền và tích hợp

Các bảng mới: tài khoản, ledger/revisions, daily snapshots, alert settings
và alert state/events. Giá/benchmark dùng cache nguồn thị trường hiện có.
Mọi SELECT/UPDATE/DELETE/CSV/refresh đều ràng buộc user_id phía server.
Không lấy user_id từ payload; báo cáo công khai không nhận bối cảnh danh mục.
API vẫn dùng envelope hiện tại. Giới hạn query theo ngày, pagination và batch;
không trả path storage, secrets hoặc nội dung lỗi DB. Ghi chú hiển thị như text.

Migrations được nối vào quy trình boot/init chuẩn và kiểm thử riêng. Deploy
và chạy migration production là bước sau, không thực hiện trong đợt code local.

## Nghiệm thu và thứ tự commit

1. **Ledger**: mua thêm, bán một phần, phí/thuế/cổ tức, nạp/rút, sửa lùi ngày,
   CSV trùng, số dư âm, precision và quyền chéo user; UI nhập/xem sổ.
2. **NAV**: bảng tính độc lập; chỉ nạp tiền không thành lợi nhuận; thiếu giá,
   ngày nghỉ, future bar, revision cũ và chạy job trùng; UI chart có gap.
3. **Benchmark**: cùng ngày/tiền tệ/giá cơ sở; reset 100, đổi benchmark,
   không có chuỗi đủ kỳ; nhãn price return và excess rõ ràng.
4. **Alerts**: vượt/ngừng vượt ngưỡng, missing/recovery, cùng fingerprint,
   cooldown, concurrent claim, baseline, report khác locale và tắt thông báo.

Mỗi phần qua test số học/quyền/trạng thái cần thiết và kiểm tra UI local rồi
commit riêng. Sau bốn phần: build, lint, Graphify update và authenticated
smoke khi có runtime kiểm thử. Chứng cứ local phải tách khỏi delivery hoặc
dữ liệu thật trên production.
