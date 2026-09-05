# Đề bài: Phần mềm quản lý bán hàng (POS) cho tiểu thương Việt Nam

Thiết kế phần mềm quản lý bán hàng (POS) cho các hộ kinh doanh nhỏ và tiểu
thương tại Việt Nam (quán cà phê, tạp hóa, quán ăn, shop quần áo). Chủ shop
thường không rành công nghệ, cần giao diện cực đơn giản, dùng được trên điện
thoại/máy tính bảng Android giá rẻ, hoạt động ổn khi mạng yếu hoặc mất mạng
tạm thời.

Cần có:
- Quản lý sản phẩm/tồn kho.
- Bán hàng nhanh (chọn món hoặc quét mã vạch).
- In hoặc gửi hóa đơn (máy in nhiệt Bluetooth hoặc gửi qua Zalo/SMS).
- Theo dõi doanh thu theo ngày.
- Hỗ trợ nhiều nhân viên với quyền hạn khác nhau (chủ shop/thu ngân).
- Đồng bộ dữ liệu khi có mạng trở lại.
- Cân nhắc tuân thủ các quy định về hóa đơn điện tử hiện hành.

Ngân sách hạ tầng phải rẻ vì khách hàng mục tiêu chi rất ít cho phần mềm quản
lý. Có thể phát triển thêm tích hợp thanh toán QR (Momo/VNPay/chuyển khoản) và
gợi ý nhập hàng bằng AI sau này.

Mục tiêu V1: đơn giản, ổn định, chi phí thấp, không over-engineer. Hãy tranh
luận kỹ về discovery/onboarding, đồng bộ offline-first, in/gửi hóa đơn, phân
quyền nhân viên, bảo mật giao dịch, chi phí hạ tầng, và giới hạn phạm vi V1.
