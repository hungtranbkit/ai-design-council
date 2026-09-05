# Đề bài: Bảng điều khiển quản lý máy chủ/máy trạm qua SSH

Thiết kế một hệ thống quản lý nhiều máy chủ và máy trạm trong mạng nội bộ/lẫn
remote cho một nhóm kỹ thuật nhỏ. Hệ thống cần tự phát hiện các máy/SSH target
đã từng kết nối, lưu mô tả, trạng thái online/offline, thông tin dự án đang
chạy, và cho phép mở terminal web để thao tác. Một số máy ở LAN, một số qua
tunnel hoặc hostname; cần hỗ trợ nhiều user, phân quyền, audit log, tránh lộ
credential. Sau này có thể gắn AI agent vào từng máy để chạy build/test/deploy.
Mục tiêu V1 là dễ dùng, ổn định, không over-engineer.

Hãy tranh luận kỹ về discovery, bảo mật credential, web terminal, session
lifecycle, role/permission, audit, realtime/polling, dữ liệu lưu ở đâu, và
giới hạn scope V1.
