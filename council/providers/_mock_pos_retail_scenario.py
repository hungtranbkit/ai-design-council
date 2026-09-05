"""MockProvider content for the 10-round extended pipeline: "Phần mềm quản lý
bán hàng (POS) cho tiểu thương Việt Nam" - entirely in Vietnamese, entirely
distinct from the 5-round QR-restaurant/SSH-ops scenarios in mock.py.

Selected by council/providers/mock.py's extended-scenario detector when the
brief text matches MARKERS (see below). Structure mirrors
_mock_ssh_ops_scenario.py's discipline (real per-role content, real
disagreements, real mind changes with before/after/reason, schema-enforced
alternatives and pre-mortem findings) but across all 10 rounds defined in
council/pipeline/orchestrator_extended.py.
"""
from __future__ import annotations

from council.pipeline.schemas import (
    AlternativeProposal,
    ChangedDecision,
    ConsensusItem,
    ConsensusReport,
    ConvergenceReport,
    CrossReview,
    Defense,
    DefenseResponse,
    DevilsAdvocateFinding,
    DevilsAdvocateReport,
    PreMortemFinding,
    ProblemUnderstanding,
    Proposal,
)

SCENARIO_ID = "pos_retail_vn"
MARKERS = ("quản lý bán hàng", "tiểu thương", "pos ")  # matched case-insensitively against the brief text

# ---------------------------------------------------------------------------
# Round 1: Hiểu bài toán & giả định độc lập
# ---------------------------------------------------------------------------

ROUND1 = {
    "product_ba": ProblemUnderstanding(
        role="product_ba",
        interpretation=(
            "Đây là bài toán số hóa quy trình bán hàng thủ công hiện tại của tiểu thương (ghi sổ tay, tính "
            "tiền bằng máy tính bỏ túi), không phải xây một ERP đầy đủ - trọng tâm là tốc độ thao tác và độ "
            "tin cậy, không phải tính năng phong phú."
        ),
        assumptions=[
            "Chủ shop tự vận hành phần mềm, không có nhân viên IT hỗ trợ",
            "Phần lớn giao dịch là tiền mặt hoặc chuyển khoản đơn giản, chưa cần tích hợp cổng thanh toán phức tạp ngay",
        ],
        clarifying_questions=["Quy mô điển hình là 1 cửa hàng hay tiểu thương có thể có 2-3 chi nhánh nhỏ?"],
        uncertainty=["Chưa rõ tỷ lệ tiểu thương sẵn sàng trả phí phần mềm hàng tháng so với mua đứt"],
    ),
    "ux_designer": ProblemUnderstanding(
        role="ux_designer",
        interpretation=(
            "Đối tượng dùng chính không phải dân công nghệ - giao diện phải giống thao tác quen thuộc (bấm "
            "số, chọn món) hơn là một app 'hiện đại' nhiều lớp điều hướng."
        ),
        assumptions=[
            "Chủ shop/thu ngân thao tác trong lúc bận, cần số bước thao tác tối thiểu",
            "Thiết bị phổ biến là điện thoại/máy tính bảng Android giá rẻ, màn hình nhỏ, cấu hình yếu",
        ],
        clarifying_questions=["Có cần hỗ trợ tiếng Anh hay chỉ tiếng Việt cho V1?"],
        uncertainty=[],
    ),
    "architect": ProblemUnderstanding(
        role="architect",
        interpretation=(
            "Bài toán kỹ thuật cốt lõi là offline-first: thiết bị bán hàng phải hoạt động được khi mất mạng, "
            "và đồng bộ đúng khi có mạng trở lại - đây là ràng buộc kiến trúc quan trọng hơn cả lựa chọn công "
            "nghệ cụ thể."
        ),
        assumptions=[
            "Mỗi cửa hàng thường chỉ có 1-2 thiết bị bán hàng, không phải hàng chục thiết bị đồng thời",
            "Mất mạng là tạm thời (vài phút tới vài giờ), không phải vận hành hoàn toàn offline dài hạn",
        ],
        clarifying_questions=[],
        uncertainty=["Chưa rõ tần suất mất mạng thực tế ở khu vực tiểu thương mục tiêu (thành thị vs nông thôn có thể khác nhau nhiều)"],
    ),
    "business_critic": ProblemUnderstanding(
        role="business_critic",
        interpretation=(
            "Đây là thị trường rất nhạy cảm về giá - tiểu thương so sánh phần mềm với 'không dùng gì cả' (sổ "
            "tay), không phải với phần mềm doanh nghiệp khác, nên chi phí phải cực thấp để có lý do chuyển đổi."
        ),
        assumptions=["Khách hàng mục tiêu sẵn sàng trả rất ít, có thể dưới mức đủ trang trải hạ tầng cloud truyền thống"],
        clarifying_questions=["Mô hình kinh doanh là bán phần mềm, bán kèm phần cứng (máy in, đầu quét), hay cả hai?"],
        uncertainty=["Chưa có số liệu về mức giá tối đa tiểu thương chấp nhận trả mỗi tháng"],
    ),
    "qa_security": ProblemUnderstanding(
        role="qa_security",
        interpretation=(
            "Rủi ro bảo mật chính không phải là tấn công từ bên ngoài, mà là gian lận nội bộ (nhân viên thu "
            "ngân) và mất dữ liệu giao dịch - đây là hệ thống xử lý tiền thật, dù quy mô nhỏ."
        ),
        assumptions=["Không phải chủ shop nào cũng tin tưởng tuyệt đối nhân viên thu ngân của mình"],
        clarifying_questions=[],
        uncertainty=[
            "Chưa rõ mức độ tuân thủ hóa đơn điện tử bắt buộc theo quy định hiện hành cho hộ kinh doanh nhỏ - "
            "cần xác nhận với tư vấn pháp lý/thuế, không tự khẳng định chi tiết luật ở đây",
        ],
    ),
    "devils_advocate": ProblemUnderstanding(
        role="devils_advocate",
        interpretation=(
            "Nghi ngờ độc lập: cả bài toán có vẻ đang giả định tiểu thương sẽ chủ động chuyển đổi từ thói "
            "quen ghi sổ tay - đây là giả định hành vi, không phải giả định kỹ thuật, và có thể sai."
        ),
        assumptions=[
            "Giả định (tạm thời, cần kiểm chứng) rằng tiểu thương đủ động lực chuyển đổi nếu sản phẩm đủ đơn giản và rẻ",
        ],
        clarifying_questions=["Có bằng chứng nào cho thấy tiểu thương thực sự muốn chuyển đổi, hay đây là giả định của đội sản phẩm?"],
        uncertainty=["Chưa có dữ liệu thực tế về mức độ sẵn sàng thay đổi thói quen của nhóm khách hàng mục tiêu"],
    ),
}

# ---------------------------------------------------------------------------
# Round 2: Đề xuất giải pháp độc lập
# ---------------------------------------------------------------------------

ROUND2 = {
    "product_ba": Proposal(
        role="product_ba",
        round=2,
        summary=(
            "Phần mềm bán hàng tối giản cho tiểu thương: bán nhanh, quản lý tồn kho cơ bản, xem doanh thu, "
            "gửi/in hóa đơn - ưu tiên tốc độ thao tác hơn tính năng."
        ),
        requirements=[
            "Bán hàng trong tối đa 3 thao tác: chọn sản phẩm (hoặc quét mã vạch) -> xác nhận -> thanh toán",
            "Tự động trừ tồn kho khi bán thành công",
            "Xem doanh thu theo ngày ngay trên màn hình chính",
            "Gửi hóa đơn điện tử qua Zalo/SMS cho khách nếu có số điện thoại",
            "In hóa đơn giấy qua máy in nhiệt Bluetooth cho khách cần hóa đơn giấy",
            "Gợi ý nhập hàng dựa trên lịch sử bán",
        ],
        priority_tags={
            "Bán hàng trong tối đa 3 thao tác: chọn sản phẩm (hoặc quét mã vạch) -> xác nhận -> thanh toán": "MUST",
            "Tự động trừ tồn kho khi bán thành công": "MUST",
            "Xem doanh thu theo ngày ngay trên màn hình chính": "MUST",
            "Gửi hóa đơn điện tử qua Zalo/SMS cho khách nếu có số điện thoại": "SHOULD",
            "In hóa đơn giấy qua máy in nhiệt Bluetooth cho khách cần hóa đơn giấy": "SHOULD",
            "Gợi ý nhập hàng dựa trên lịch sử bán": "COULD",
        },
        decisions=[
            "V1 hỗ trợ cả bán theo sản phẩm có mã vạch (tạp hóa) và bán theo món tự đặt tên (quán ăn/cà phê), không bắt buộc mã vạch",
            "Hóa đơn điện tử qua Zalo/SMS là lựa chọn mặc định được khuyến khích, in giấy là tùy chọn thêm",
        ],
        edge_cases=[
            "Khách trả hàng sau khi đã trừ tồn kho - cần thao tác hoàn trả nhanh",
            "Thu ngân bán nhầm giá - cần sửa được đơn hàng trước khi chốt",
        ],
        risks=[
            "Nếu bắt buộc mã vạch, nhiều quán ăn/cà phê sẽ không dùng được sản phẩm ngay từ đầu",
            "Phụ thuộc số điện thoại khách để gửi hóa đơn điện tử - không phải khách nào cũng cung cấp",
        ],
        assumptions=["Tồn kho chỉ cần chính xác ở mức tương đối, không cần theo dõi lô/hạn sử dụng chi tiết ở V1"],
    ),
    "ux_designer": Proposal(
        role="ux_designer",
        round=2,
        summary="Giao diện bán hàng giống một máy tính tiền vật lý: các nút to, ít lớp điều hướng, không yêu cầu học cách dùng.",
        requirements=[
            "Màn hình bán hàng chính hiển thị danh sách sản phẩm/món dạng lưới nút bấm lớn",
            "Thao tác thanh toán hoàn tất trong 1 màn hình, không chuyển qua nhiều trang",
            "Chữ và nút đủ lớn để thao tác nhanh, kể cả khi đang bận",
            "Có chế độ xem nhanh doanh thu hôm nay ngay khi mở app, không cần tìm trong menu",
        ],
        priority_tags={
            "Màn hình bán hàng chính hiển thị danh sách sản phẩm/món dạng lưới nút bấm lớn": "MUST",
            "Thao tác thanh toán hoàn tất trong 1 màn hình, không chuyển qua nhiều trang": "MUST",
            "Chữ và nút đủ lớn để thao tác nhanh, kể cả khi đang bận": "MUST",
            "Có chế độ xem nhanh doanh thu hôm nay ngay khi mở app, không cần tìm trong menu": "SHOULD",
        },
        decisions=[
            "Ưu tiên giao diện dạng lưới nút bấm (grid) thay vì danh sách cuộn dài, giống bố cục máy tính tiền truyền thống mà chủ shop đã quen",
        ],
        edge_cases=[
            "Menu quán ăn có thể có 50-100 món - cần nhóm theo danh mục để không bị rối",
            "Chủ shop đổi giá sản phẩm giữa ca bán - cần sửa giá nhanh không mất nhiều bước",
        ],
        risks=["Nếu giao diện quá đơn giản, có thể thiếu chỗ cho các trường hợp đặc biệt (giảm giá, combo) khiến thu ngân phải lách bằng cách khác"],
        assumptions=["Phần lớn cửa hàng có dưới 200 mặt hàng/món - danh mục quá lớn không phải trường hợp phổ biến ở V1"],
    ),
    "architect": Proposal(
        role="architect",
        round=2,
        summary=(
            "Kiến trúc local-first: dữ liệu bán hàng lưu ngay trên thiết bị (SQLite cục bộ), đồng bộ định kỳ "
            "lên server trung tâm khi có mạng; server dùng để tổng hợp báo cáo và backup."
        ),
        requirements=[
            "Ứng dụng hoạt động đầy đủ chức năng bán hàng khi không có mạng",
            "Đồng bộ dữ liệu lên server khi có kết nối trở lại, không cần thao tác thủ công",
            "Phát hiện và xử lý xung đột khi 2 thiết bị cùng bán offline rồi đồng bộ (ví dụ cùng trừ tồn kho một sản phẩm)",
        ],
        priority_tags={
            "Ứng dụng hoạt động đầy đủ chức năng bán hàng khi không có mạng": "MUST",
            "Đồng bộ dữ liệu lên server khi có kết nối trở lại, không cần thao tác thủ công": "MUST",
            "Phát hiện và xử lý xung đột khi 2 thiết bị cùng bán offline rồi đồng bộ (ví dụ cùng trừ tồn kho một sản phẩm)": "SHOULD",
        },
        decisions=[
            "Lưu dữ liệu chính (nguồn sự thật) ngay trên thiết bị bán hàng (local-first), server chỉ là bản sao tổng hợp",
            "Đồng bộ định kỳ (polling khi có mạng), không cần WebSocket realtime cho một cửa hàng chỉ có 1-2 thiết bị",
        ],
        edge_cases=["Thiết bị bán hàng bị mất/hỏng trước khi kịp đồng bộ - mất dữ liệu chưa đồng bộ"],
        risks=["Xung đột tồn kho giữa 2 thiết bị offline có thể dẫn tới bán vượt số lượng thực tế còn trong kho"],
        assumptions=["Việc đồng bộ có độ trễ vài phút tới vài giờ là chấp nhận được cho tiểu thương, không cần tức thời"],
    ),
    "business_critic": Proposal(
        role="business_critic",
        round=2,
        summary="Hạ tầng phải tối giản chi phí: ưu tiên local-first để giảm chi phí server, tránh các tính năng tốn kém (thanh toán tích hợp, AI) ở V1.",
        requirements=["Chi phí vận hành server phải đủ thấp để mô hình giá gần như miễn phí hoặc rất rẻ vẫn có lãi"],
        priority_tags={"Chi phí vận hành server phải đủ thấp để mô hình giá gần như miễn phí hoặc rất rẻ vẫn có lãi": "MUST"},
        decisions=[
            "Không tích hợp cổng thanh toán QR (Momo/VNPay) ở V1 - để dành cho V2 khi đã có người dùng thực tế xác nhận nhu cầu",
            "Không làm tính năng AI gợi ý nhập hàng ở V1",
        ],
        edge_cases=[],
        risks=["Nếu để dành thanh toán QR cho V2, có thể mất lợi thế cạnh tranh nếu đối thủ đã tích hợp sẵn"],
        assumptions=["Doanh thu ban đầu đến từ số lượng tiểu thương dùng nhiều, không phải từ tính năng cao cấp"],
        uncertainty=["Chưa rõ mức giá tối đa tiểu thương sẵn sàng trả mỗi tháng - cần khảo sát thực tế trước khi chốt mô hình giá"],
    ),
    "qa_security": Proposal(
        role="qa_security",
        round=2,
        summary="Kiểm soát gian lận nội bộ và bảo vệ dữ liệu giao dịch là ưu tiên bảo mật hàng đầu, không phải chống tấn công từ bên ngoài.",
        requirements=[
            "Mỗi nhân viên thu ngân đăng nhập bằng tài khoản riêng, không dùng chung 1 tài khoản",
            "Ghi lại (audit) mọi giao dịch sửa/hủy đơn hàng sau khi đã tạo, kèm ai thực hiện",
        ],
        priority_tags={
            "Mỗi nhân viên thu ngân đăng nhập bằng tài khoản riêng, không dùng chung 1 tài khoản": "MUST",
            "Ghi lại (audit) mọi giao dịch sửa/hủy đơn hàng sau khi đã tạo, kèm ai thực hiện": "MUST",
        },
        decisions=["Phân quyền tối thiểu 2 cấp: chủ shop (toàn quyền, xem báo cáo) và thu ngân (chỉ bán hàng, không sửa/xóa giao dịch đã chốt)"],
        edge_cases=["Thu ngân hủy đơn hàng sau khi đã thanh toán để lấy lại tiền mặt cho bản thân - cần audit log phát hiện được"],
        risks=[
            "Nếu không có audit log sửa/hủy đơn, thu ngân có thể gian lận mà chủ shop không biết",
            "Hóa đơn điện tử gửi qua Zalo/SMS có thể vô tình gửi nhầm số điện thoại người khác nếu không xác nhận lại",
        ],
        assumptions=[],
        uncertainty=[
            "Chưa rõ chi tiết yêu cầu tuân thủ hóa đơn điện tử theo quy định thuế hiện hành cho hộ kinh doanh nhỏ - "
            "không tự khẳng định, cần xác nhận với chuyên gia thuế/pháp lý trước khi triển khai",
        ],
    ),
    "devils_advocate": Proposal(
        role="devils_advocate",
        round=2,
        summary=(
            "Đề xuất độc lập, mang tính hoài nghi: bộ giải pháp có vẻ đang tối ưu cho 'tiểu thương lý tưởng "
            "có smartphone tốt và mạng ổn định' - cần thiết kế cho trường hợp xấu hơn."
        ),
        requirements=["Phải xác định rõ hành vi của app khi thiết bị dùng là máy cấu hình rất yếu hoặc mạng cực kém, không chỉ 'offline tạm thời'"],
        decisions=["Không nên mặc định rằng mọi tiểu thương đều dùng thiết bị Android tầm trung trở lên"],
        edge_cases=["Thiết bị hết dung lượng lưu trữ do dữ liệu offline tích lũy quá lâu chưa đồng bộ"],
        risks=["Chưa ai đề cập điều gì xảy ra nếu chủ shop đổi điện thoại/mất điện thoại - dữ liệu local-first có nguy cơ mất theo thiết bị"],
        assumptions=["Giả định (tạm thời, cần kiểm chứng) rằng phần lớn thiết bị mục tiêu có ít nhất 2-3GB RAM và bộ nhớ trống hợp lý"],
        uncertainty=["Chưa có dữ liệu về phân khúc thiết bị thực tế của tiểu thương mục tiêu"],
    ),
}

# ---------------------------------------------------------------------------
# Round 3: Phản biện chéo - Yêu cầu / UX / Kinh doanh
# ---------------------------------------------------------------------------

ROUND3: dict[str, dict[str, CrossReview]] = {
    "product_ba": {
        "architect": CrossReview(
            reviewer_role="product_ba",
            target_role="architect",
            round=3,
            agree=["Local-first đúng hướng cho tiểu thương"],
            disagree=[
                "Đồng bộ định kỳ (không realtime) có thể gây nhầm lẫn nếu chủ shop xem báo cáo tổng trên web "
                "trong khi thiết bị bán hàng chưa đồng bộ - cần rõ ràng hơn về độ trễ hiển thị, không chỉ chấp nhận ngầm",
            ],
            missing_requirements=["Chưa có yêu cầu hiển thị rõ trạng thái 'đã đồng bộ' hay 'chưa đồng bộ' cho chủ shop biết"],
            proposed_changes=["Thêm chỉ báo trạng thái đồng bộ rõ ràng trên giao diện, không để ngầm định"],
        ),
        "qa_security": CrossReview(
            reviewer_role="product_ba",
            target_role="qa_security",
            round=3,
            agree=["Đồng ý phân quyền chủ shop/thu ngân và audit log sửa/hủy đơn"],
            proposed_changes=[
                "Xác nhận việc yêu cầu đăng nhập riêng từng nhân viên không làm chậm ca bán hàng đông khách - "
                "cần thao tác đăng nhập cực nhanh (ví dụ mã PIN ngắn thay vì mật khẩu dài)",
            ],
        ),
    },
    "ux_designer": {
        "product_ba": CrossReview(
            reviewer_role="ux_designer",
            target_role="product_ba",
            round=3,
            agree=["Đồng ý giữ cả bán theo mã vạch và bán theo món tự đặt tên"],
            disagree=[
                "Việc gửi hóa đơn điện tử làm 'mặc định khuyến khích' có thể gây thêm bước hỏi số điện thoại "
                "khách trong lúc đông khách - làm chậm đúng thứ mà chính đề xuất này đang cố tối ưu (tốc độ bán hàng)",
            ],
            missing_requirements=["Cần quy định rõ hóa đơn là bước tùy chọn nhanh (bỏ qua bằng 1 chạm), không chặn luồng bán hàng chính"],
            proposed_changes=["Đưa bước hóa đơn (in/gửi) thành tùy chọn sau khi thanh toán xong, có nút 'Bỏ qua' rõ ràng"],
        ),
        "architect": CrossReview(
            reviewer_role="ux_designer",
            target_role="architect",
            round=3,
            agree=["Đồng ý local-first phù hợp trải nghiệm không cần chờ mạng"],
            missing_requirements=[
                "Kiến trúc chưa nói giao diện sẽ hiển thị gì cho người dùng khi xảy ra xung đột đồng bộ tồn "
                "kho - không thể chỉ xử lý ngầm ở backend",
            ],
            proposed_changes=["Cần một màn hình đơn giản thông báo 'có xung đột tồn kho cần xác nhận' thay vì tự động xử lý âm thầm"],
        ),
    },
    "business_critic": {
        "architect": CrossReview(
            reviewer_role="business_critic",
            target_role="architect",
            round=3,
            agree=["Đồng ý local-first giảm chi phí server"],
            disagree=[
                "Xử lý xung đột đồng bộ tồn kho nghe có vẻ là bài toán kỹ thuật phức tạp hơn mức cần thiết cho "
                "một cửa hàng chỉ có 1-2 thiết bị - có thể là over-engineering nếu tần suất xung đột thực tế "
                "chưa được kiểm chứng",
            ],
            risks=["Đầu tư quá nhiều công sức xử lý xung đột hiếm gặp trong khi các yêu cầu cơ bản chưa được đánh giá đủ kỹ"],
            proposed_changes=["Đo lường/ước tính tần suất xung đột thực tế trước khi đầu tư giải pháp phức tạp; V1 có thể chỉ cần cảnh báo đơn giản"],
        ),
        "product_ba": CrossReview(
            reviewer_role="business_critic",
            target_role="product_ba",
            round=3,
            disagree=[
                "Đề xuất 'gợi ý nhập hàng dựa trên lịch sử bán' được gắn COULD nhưng vẫn nằm trong danh sách "
                "requirements chính - nên tách hẳn ra khỏi phạm vi V1 để không tạo kỳ vọng sai",
            ],
            proposed_changes=["Loại hẳn 'gợi ý nhập hàng' khỏi danh sách requirements V1, ghi chú rõ là ý tưởng cho V2 trở đi"],
        ),
    },
}

# ---------------------------------------------------------------------------
# Round 4: Phản biện chéo - Kiến trúc / Bảo mật / Vận hành
# ---------------------------------------------------------------------------

ROUND4: dict[str, dict[str, CrossReview]] = {
    "architect": {
        "ux_designer": CrossReview(
            reviewer_role="architect",
            target_role="ux_designer",
            round=4,
            agree=["Đồng ý bố cục dạng lưới nút bấm phù hợp thao tác nhanh"],
            missing_requirements=[
                "Chưa tính tới việc màn hình xác nhận xung đột tồn kho (UX vừa đề xuất) cần dữ liệu gì từ "
                "backend để hiển thị đúng - cần phối hợp thiết kế cùng lúc",
            ],
            proposed_changes=["Thêm một API trạng thái đồng bộ đơn giản để UI hiển thị chỉ báo 'đã đồng bộ/chưa đồng bộ/có xung đột'"],
        ),
        "business_critic": CrossReview(
            reviewer_role="architect",
            target_role="business_critic",
            round=4,
            disagree=[
                "Cho rằng xử lý xung đột đồng bộ là over-engineering - nhưng nếu không xử lý gì, một sản "
                "phẩm bán vượt tồn kho sẽ khiến chủ shop nhận đơn không thể giao, ảnh hưởng trực tiếp uy tín, "
                "không phải rủi ro lý thuyết",
            ],
            risks=["Bỏ qua hoàn toàn xử lý xung đột có thể gây hậu quả kinh doanh thực tế, không chỉ là vấn đề kỹ thuật thừa"],
            proposed_changes=[
                "Đề xuất mức xử lý tối thiểu: cảnh báo đơn giản khi phát hiện xung đột, không cần tự động hợp "
                "nhất phức tạp - vừa đủ, không over-engineer nhưng cũng không bỏ qua rủi ro",
            ],
        ),
    },
    "qa_security": {
        "product_ba": CrossReview(
            reviewer_role="qa_security",
            target_role="product_ba",
            round=4,
            disagree=[
                "Gửi hóa đơn điện tử qua Zalo/SMS yêu cầu số điện thoại khách - nhưng chưa có yêu cầu nào về "
                "việc lưu trữ/bảo vệ danh sách số điện thoại khách hàng này, đây là dữ liệu cá nhân",
            ],
            missing_requirements=["Cần chính sách rõ ràng về việc lưu và sử dụng số điện thoại khách hàng, không thu thập nhiều hơn mức cần thiết"],
            proposed_changes=["Chỉ lưu số điện thoại khách khi thực sự cần gửi hóa đơn ngay lúc đó, không xây dựng cơ sở dữ liệu khách hàng tập trung ở V1"],
        ),
        "architect": CrossReview(
            reviewer_role="qa_security",
            target_role="architect",
            round=4,
            agree=["Đồng ý local-first giảm rủi ro phụ thuộc mạng"],
            disagree=[
                "Chưa thấy đề cập việc dữ liệu lưu cục bộ trên thiết bị (bao gồm lịch sử giao dịch) có được "
                "bảo vệ nếu thiết bị bị mất/đánh cắp hay không - đây là dữ liệu kinh doanh nhạy cảm",
            ],
            missing_requirements=["Yêu cầu mã hóa hoặc khóa truy cập dữ liệu cục bộ khi thiết bị bị mất"],
            risks=["Thiết bị bán hàng bị mất/đánh cắp làm lộ toàn bộ lịch sử giao dịch và tồn kho của cửa hàng"],
            proposed_changes=["Thêm yêu cầu khóa ứng dụng bằng mã PIN/vân tay và cân nhắc mã hóa dữ liệu cục bộ ở mức cơ bản"],
        ),
    },
    "devils_advocate": {
        "architect": CrossReview(
            reviewer_role="devils_advocate",
            target_role="architect",
            round=4,
            agree=["Local-first là lựa chọn hợp lý"],
            disagree=[
                "Giả định 'mất mạng chỉ tạm thời vài phút tới vài giờ' chưa được kiểm chứng - nếu một khu vực "
                "mất mạng nhiều ngày, toàn bộ dữ liệu chưa đồng bộ có nguy cơ tồn đọng rất lâu mà không ai xử lý",
            ],
            missing_requirements=["Cần định nghĩa hành vi khi dữ liệu chưa đồng bộ tồn đọng quá lâu (ví dụ vài ngày) - có cảnh báo cho chủ shop không?"],
            proposed_changes=["Thêm cảnh báo cho chủ shop khi dữ liệu chưa đồng bộ vượt quá một ngưỡng thời gian nhất định"],
        ),
        "ux_designer": CrossReview(
            reviewer_role="devils_advocate",
            target_role="ux_designer",
            round=4,
            agree=["Bố cục lưới nút bấm dễ dùng"],
            disagree=[
                "Giả định thiết bị có màn hình đủ lớn để hiển thị lưới nút bấm rõ ràng - nhưng nhiều tiểu "
                "thương dùng điện thoại phổ thông màn hình nhỏ, không phải máy tính bảng",
            ],
            missing_requirements=["Cần xác nhận thiết kế hoạt động tốt trên màn hình điện thoại nhỏ (dưới 5.5 inch), không chỉ máy tính bảng"],
            proposed_changes=["Thiết kế ưu tiên thử nghiệm trên màn hình điện thoại phổ thông trước, máy tính bảng là trường hợp mở rộng"],
        ),
    },
}

# ---------------------------------------------------------------------------
# Round 5: Devil's Advocate
# ---------------------------------------------------------------------------

ROUND5_FINDINGS = [
    DevilsAdvocateFinding(
        category="security",
        description=(
            "Không ai định nghĩa điều gì xảy ra nếu chủ shop cần thu hồi quyền truy cập khi nhân viên thu "
            "ngân nghỉ việc - tài khoản/mã PIN cũ có thể vẫn dùng được trên thiết bị cũ nếu không có cơ chế "
            "thu hồi rõ ràng"
        ),
        target_role=None,
        severity="high",
    ),
    DevilsAdvocateFinding(
        category="unnecessary_complexity",
        description=(
            "Xử lý xung đột đồng bộ tồn kho đang được tranh luận giữa 'bỏ qua hoàn toàn' và 'tự động hợp "
            "nhất phức tạp' - nhưng chưa ai đặt câu hỏi mức tối thiểu thực sự cần là gì trước khi implement "
            "bất kỳ phương án nào, dễ dẫn tới xây dư thừa"
        ),
        target_role="architect",
        severity="medium",
    ),
    DevilsAdvocateFinding(
        category="missing_business_case",
        description=(
            "Toàn bộ đề xuất giả định tiểu thương sẽ trả tiền cho phần mềm, nhưng thị trường tương tự (sổ "
            "tay, Excel miễn phí) khiến câu hỏi 'ai trả tiền và trả bao nhiêu' vẫn chưa có câu trả lời cụ thể "
            "- đây là rủi ro mô hình kinh doanh, không chỉ sản phẩm"
        ),
        target_role="business_critic",
        severity="high",
    ),
    DevilsAdvocateFinding(
        category="scalability",
        description=(
            "Đồng bộ định kỳ được thiết kế cho 1-2 thiết bị mỗi cửa hàng - nhưng nếu một tiểu thương phát "
            "triển thành chuỗi 5-10 cửa hàng nhỏ, mô hình local-first hiện tại chưa nói rõ có còn phù hợp "
            "hay cần thiết kế lại từ đầu"
        ),
        target_role="architect",
        severity="medium",
    ),
    DevilsAdvocateFinding(
        category="ux",
        description=(
            "Thiết kế lưới nút bấm được giả định phù hợp mọi trường hợp, nhưng quán trà sữa/cà phê với nhiều "
            "size/topping khác nhau (dễ ra 50-100 lựa chọn) chưa được UX Designer giải quyết cụ thể - đây "
            "không phải trường hợp hiếm ở Việt Nam"
        ),
        target_role="ux_designer",
        severity="medium",
    ),
    DevilsAdvocateFinding(
        category="hidden_assumption",
        description=(
            "Toàn bộ đề xuất giả định ngầm rằng chủ shop có thể tự cài đặt và cấu hình ứng dụng (chọn sản "
            "phẩm, thiết lập máy in Bluetooth) mà không cần hỗ trợ kỹ thuật - đây là giả định lớn chưa được "
            "kiểm chứng với nhóm người dùng thực tế không rành công nghệ"
        ),
        target_role=None,
        severity="high",
    ),
    DevilsAdvocateFinding(
        category="operations",
        description=(
            "Chưa ai định nghĩa quy trình hỗ trợ khi tiểu thương gặp sự cố (mất dữ liệu, lỗi đồng bộ) - với "
            "đối tượng người dùng không rành công nghệ, thiếu kênh hỗ trợ rõ ràng có thể khiến sản phẩm bị "
            "bỏ dùng ngay sau sự cố đầu tiên"
        ),
        target_role=None,
        severity="high",
    ),
]


def build_devils_advocate_report() -> DevilsAdvocateReport:
    return DevilsAdvocateReport(round=5, findings=list(ROUND5_FINDINGS))


# ---------------------------------------------------------------------------
# Round 6: Phương án thay thế
# ---------------------------------------------------------------------------

ROUND6 = {
    "product_ba": AlternativeProposal(
        role="product_ba",
        primary_topic="invoice_delivery_default",
        alternative_option=(
            "Thay vì đặt hóa đơn điện tử qua Zalo/SMS làm mặc định khuyến khích, coi việc hỏi hóa đơn là "
            "bước hoàn toàn tùy chọn, ẩn mặc định, chỉ hiện khi khách yêu cầu"
        ),
        trade_offs=[
            "Giảm thêm 1 bước hỏi trong lúc bán hàng đông khách, tăng tốc độ bán",
            "Có thể giảm cơ hội thu thập số điện thoại khách cho các tính năng marketing sau này",
        ],
        recommendation="prefer_alternative",
        rationale="UX Designer đã chỉ ra việc hỏi hóa đơn mặc định làm chậm luồng chính; ẩn mặc định và chỉ hiện khi cần phù hợp hơn với mục tiêu tốc độ bán hàng của V1.",
    ),
    "ux_designer": AlternativeProposal(
        role="ux_designer",
        primary_topic="grid_layout_for_menu",
        alternative_option=(
            "Với quán có menu lớn (50-100 món, nhiều size/topping), dùng danh sách có tìm kiếm/lọc theo danh "
            "mục thay vì lưới nút bấm phẳng"
        ),
        trade_offs=[
            "Xử lý tốt menu phức tạp nhưng thêm bước tìm kiếm/lọc cho quán đơn giản",
            "Cần thiết kế 2 chế độ hiển thị thay vì 1 giao diện duy nhất, tăng công sức thiết kế",
        ],
        recommendation="depends",
        rationale="Devil's Advocate chỉ ra lưới nút bấm không đủ cho menu phức tạp; nhưng ép mọi quán dùng chế độ lọc phức tạp lại làm chậm các quán đơn giản - cần cả 2 chế độ tùy quy mô menu.",
    ),
    "architect": AlternativeProposal(
        role="architect",
        primary_topic="sync_conflict_handling",
        alternative_option=(
            "Thay vì tự động phát hiện và xử lý xung đột tồn kho, chỉ khóa (lock) một sản phẩm để bán trên "
            "đúng 1 thiết bị tại một thời điểm khi cả 2 thiết bị đều online"
        ),
        trade_offs=[
            "Đơn giản hơn nhiều so với hợp nhất xung đột tự động, giảm rủi ro over-engineering",
            "Không giải quyết được trường hợp cả 2 thiết bị cùng offline - vẫn cần cảnh báo xung đột cho trường hợp đó",
        ],
        recommendation="prefer_alternative",
        rationale="Business Critic và Devil's Advocate đều nghi ngờ mức đầu tư cho xử lý xung đột - khóa đơn giản khi online kèm cảnh báo khi offline là mức tối thiểu hợp lý cho V1.",
    ),
    "business_critic": AlternativeProposal(
        role="business_critic",
        primary_topic="pricing_model",
        alternative_option="Thay vì thu phí thuê bao hàng tháng, miễn phí phần mềm và thu lợi nhuận từ việc bán/cho thuê phần cứng (máy in nhiệt, đầu quét mã vạch)",
        trade_offs=[
            "Giảm rào cản dùng thử cho tiểu thương nhạy cảm về giá, tăng tốc độ áp dụng",
            "Doanh thu phụ thuộc vào việc bán phần cứng, rủi ro nếu tiểu thương đã có sẵn máy in/đầu quét",
        ],
        recommendation="depends",
        rationale="Chưa có đủ dữ liệu (đã đánh dấu uncertainty từ vòng 1) về mức giá tiểu thương chấp nhận trả - cần thử nghiệm cả 2 mô hình trước khi chọn hẳn 1 hướng.",
    ),
    "qa_security": AlternativeProposal(
        role="qa_security",
        primary_topic="employee_authentication",
        alternative_option="Thay vì tài khoản riêng cho từng nhân viên (username/password), dùng mã PIN ngắn riêng cho từng người trên cùng thiết bị dùng chung",
        trade_offs=[
            "Đăng nhập nhanh hơn nhiều trong ca bán hàng đông khách so với nhập mật khẩu đầy đủ",
            "Mã PIN ngắn dễ bị đoán/nhìn lén hơn mật khẩu, cần giới hạn số lần thử sai",
        ],
        recommendation="prefer_alternative",
        rationale="Product/BA đã lo ngại đăng nhập đầy đủ làm chậm ca bán hàng đông khách; mã PIN ngắn kèm giới hạn số lần thử sai cân bằng được tốc độ và bảo mật tối thiểu.",
    ),
    "devils_advocate": AlternativeProposal(
        role="devils_advocate",
        primary_topic="local_first_data_ownership",
        alternative_option=(
            "Thay vì coi dữ liệu trên thiết bị là nguồn sự thật chính (local-first thuần), luôn yêu cầu xác "
            "nhận đồng bộ thành công lên server trước khi coi giao dịch là 'hoàn tất' về mặt kế toán"
        ),
        trade_offs=[
            "Giảm rủi ro mất dữ liệu vĩnh viễn nếu thiết bị hỏng/mất trước khi đồng bộ",
            "Có thể tạo cảm giác 'giao dịch chưa xong' gây khó chịu nếu mạng chậm, đi ngược mục tiêu trải nghiệm mượt",
        ],
        recommendation="depends",
        rationale="Đây là đánh đổi thực sự giữa an toàn dữ liệu và trải nghiệm mượt mà - cần Moderator cân nhắc ở vòng hội tụ/đồng thuận.",
    ),
}

# ---------------------------------------------------------------------------
# Round 7: Bảo vệ & sửa quan điểm
# ---------------------------------------------------------------------------


def _defense_product_ba() -> Defense:
    return Defense(
        role="product_ba",
        round=7,
        responses=[
            DefenseResponse(
                critique_source="ux_designer (round3)",
                critique_summary="Hỏi hóa đơn mặc định làm chậm luồng bán hàng chính",
                stance="revise",
                rationale="Đồng ý; chuyển hóa đơn thành bước tùy chọn ẩn mặc định, chỉ hiện khi khách yêu cầu, như phương án thay thế ở vòng 6.",
            ),
            DefenseResponse(
                critique_source="business_critic (round3)",
                critique_summary="Gợi ý nhập hàng bằng AI nên tách hẳn khỏi requirements V1",
                stance="revise",
                rationale="Đồng ý, loại bỏ khỏi danh sách requirements chính thức, ghi chú là ý tưởng V2.",
            ),
            DefenseResponse(
                critique_source="qa_security (round4)",
                critique_summary="Cần chính sách rõ về lưu số điện thoại khách",
                stance="revise",
                rationale="Đồng ý, chỉ lưu số điện thoại tạm thời cho lần gửi hóa đơn đó, không xây dựng cơ sở dữ liệu khách hàng tập trung.",
            ),
        ],
        changed_decisions=[
            ChangedDecision(
                topic="invoice_delivery_default",
                old_decision="Hóa đơn điện tử qua Zalo/SMS là lựa chọn mặc định được khuyến khích",
                new_decision="Hóa đơn là bước tùy chọn ẩn mặc định, chỉ hiện khi khách yêu cầu, không chặn luồng bán hàng chính",
                reason="UX Designer chỉ ra bước này làm chậm ca bán hàng đông khách",
                triggered_by="ux_designer (round3)",
            ),
            ChangedDecision(
                topic="restock_ai_suggestion_scope",
                old_decision="Gợi ý nhập hàng dựa trên lịch sử bán nằm trong requirements (đánh dấu COULD)",
                new_decision="Loại hẳn khỏi requirements V1, chuyển thành ghi chú ý tưởng cho V2",
                reason="Business Critic chỉ ra việc giữ trong requirements chính tạo kỳ vọng sai về phạm vi V1",
                triggered_by="business_critic (round3)",
            ),
        ],
        final_decisions=[
            "V1 hỗ trợ cả bán theo mã vạch và theo món tự đặt tên",
            "Hóa đơn (in/gửi) là bước tùy chọn sau thanh toán, có nút bỏ qua rõ ràng",
            "Không lưu số điện thoại khách thành cơ sở dữ liệu tập trung, chỉ dùng tạm thời khi gửi hóa đơn",
            "Gợi ý nhập hàng AI không thuộc phạm vi V1",
        ],
    )


def _defense_ux_designer() -> Defense:
    return Defense(
        role="ux_designer",
        round=7,
        responses=[
            DefenseResponse(
                critique_source="devils_advocate (round4)",
                critique_summary="Lưới nút bấm giả định màn hình đủ lớn, chưa tính điện thoại nhỏ",
                stance="revise",
                rationale="Đúng, cần thiết kế và thử nghiệm ưu tiên trên màn hình điện thoại phổ thông trước.",
            ),
            DefenseResponse(
                critique_source="devils_advocate (round5)",
                critique_summary="Menu phức tạp (nhiều size/topping) chưa được giải quyết",
                stance="revise",
                rationale="Đồng ý bổ sung chế độ danh sách có lọc cho menu lớn, giữ lưới nút bấm cho menu đơn giản, như phương án thay thế ở vòng 6.",
            ),
            DefenseResponse(
                critique_source="architect (round4)",
                critique_summary="Cần API trạng thái đồng bộ để UI hiển thị đúng",
                stance="defend",
                rationale="Đây là việc Architect cung cấp dữ liệu; UX chỉ cần đặc tả rõ 3 trạng thái cần hiển thị - không cần UX tự thay đổi quyết định của mình.",
            ),
        ],
        changed_decisions=[
            ChangedDecision(
                topic="screen_size_priority",
                old_decision="Thiết kế mặc định giả định máy tính bảng/màn hình đủ lớn",
                new_decision="Ưu tiên thử nghiệm và tối ưu cho màn hình điện thoại phổ thông (dưới 5.5 inch) trước, máy tính bảng là mở rộng",
                reason="Devil's Advocate chỉ ra giả định màn hình lớn không đúng với nhiều tiểu thương thực tế",
                triggered_by="devils_advocate (round4)",
            ),
            ChangedDecision(
                topic="menu_layout_for_complex_menus",
                old_decision="Một kiểu bố cục lưới nút bấm duy nhất cho mọi quán",
                new_decision="Hai chế độ hiển thị: lưới nút bấm cho menu đơn giản, danh sách có lọc/tìm kiếm cho menu lớn (50-100 món)",
                reason="Devil's Advocate chỉ ra lưới nút bấm không xử lý được menu phức tạp phổ biến ở Việt Nam",
                triggered_by="devils_advocate (round5)",
            ),
        ],
        final_decisions=[
            "Ưu tiên tối ưu cho màn hình điện thoại phổ thông trước",
            "Hai chế độ hiển thị menu tùy quy mô: lưới nút bấm hoặc danh sách có lọc",
            "Hóa đơn là bước tùy chọn sau thanh toán, không chặn luồng chính",
            "Cần 3 trạng thái đồng bộ hiển thị rõ trên giao diện: đã đồng bộ / chưa đồng bộ / có xung đột",
        ],
    )


def _defense_architect() -> Defense:
    return Defense(
        role="architect",
        round=7,
        responses=[
            DefenseResponse(
                critique_source="business_critic (round3)",
                critique_summary="Xử lý xung đột đồng bộ có thể là over-engineering",
                stance="partially_accept",
                rationale="Chấp nhận giảm mức đầu tư: thay tự động hợp nhất phức tạp bằng khóa sản phẩm khi online + cảnh báo đơn giản khi offline, như phương án thay thế ở vòng 6.",
            ),
            DefenseResponse(
                critique_source="qa_security (round4)",
                critique_summary="Dữ liệu cục bộ chưa được bảo vệ nếu thiết bị mất/bị đánh cắp",
                stance="revise",
                rationale="Đúng, đây là lỗ hổng thật; thêm yêu cầu khóa ứng dụng bằng mã PIN/vân tay.",
            ),
            DefenseResponse(
                critique_source="devils_advocate (round4)",
                critique_summary="Dữ liệu chưa đồng bộ có thể tồn đọng rất lâu nếu mất mạng dài ngày",
                stance="revise",
                rationale="Đồng ý; thêm cảnh báo cho chủ shop khi dữ liệu chưa đồng bộ vượt một ngưỡng thời gian nhất định.",
            ),
            DefenseResponse(
                critique_source="devils_advocate (round5)",
                critique_summary="Mô hình local-first chưa rõ có phù hợp khi tiểu thương phát triển thành chuỗi nhiều cửa hàng",
                stance="defend",
                rationale="V1 chỉ nhắm tới 1 cửa hàng đơn lẻ theo đúng phạm vi đề bài; mở rộng thành chuỗi là bài toán kiến trúc khác, để giải quyết ở phiên bản sau.",
            ),
        ],
        changed_decisions=[
            ChangedDecision(
                topic="sync_conflict_handling",
                old_decision="Phát hiện và tự động xử lý xung đột khi 2 thiết bị cùng bán offline",
                new_decision="Khóa sản phẩm để bán trên đúng 1 thiết bị khi cả 2 đang online; khi cả 2 offline, chỉ cảnh báo xung đột cho chủ shop xử lý thủ công, không tự động hợp nhất",
                reason="Business Critic và Devil's Advocate đều nghi ngờ mức đầu tư cho xử lý xung đột tự động phức tạp",
                triggered_by="business_critic (round3), devils_advocate (round6)",
            ),
            ChangedDecision(
                topic="local_device_security",
                old_decision="Không có yêu cầu bảo vệ dữ liệu cục bộ khi mất thiết bị",
                new_decision="Yêu cầu khóa ứng dụng bằng mã PIN/vân tay khi mở app trên thiết bị",
                reason="QA+Security chỉ ra dữ liệu kinh doanh nhạy cảm có thể lộ hoàn toàn nếu mất thiết bị",
                triggered_by="qa_security (round4)",
            ),
            ChangedDecision(
                topic="stale_sync_warning",
                old_decision="Không có cơ chế cảnh báo khi dữ liệu chưa đồng bộ tồn đọng lâu",
                new_decision="Cảnh báo cho chủ shop khi dữ liệu chưa đồng bộ vượt một ngưỡng thời gian nhất định (ví dụ hơn 24 giờ)",
                reason="Devil's Advocate chỉ ra mất mạng dài ngày có thể khiến dữ liệu tồn đọng mà không ai biết",
                triggered_by="devils_advocate (round4)",
            ),
        ],
        final_decisions=[
            "Kiến trúc local-first: dữ liệu chính lưu trên thiết bị, server tổng hợp báo cáo/backup",
            "Khóa sản phẩm khi bán lúc online, cảnh báo thủ công khi xung đột lúc offline - không tự động hợp nhất",
            "Yêu cầu khóa ứng dụng bằng mã PIN/vân tay",
            "Cảnh báo khi dữ liệu chưa đồng bộ tồn đọng quá lâu",
            "V1 chỉ nhắm 1 cửa hàng đơn lẻ, mở rộng chuỗi cửa hàng là bài toán của phiên bản sau",
        ],
    )


def _defense_business_critic() -> Defense:
    return Defense(
        role="business_critic",
        round=7,
        responses=[
            DefenseResponse(
                critique_source="architect (round4)",
                critique_summary="Bỏ qua hoàn toàn xử lý xung đột có thể gây hậu quả kinh doanh thực tế",
                stance="partially_accept",
                rationale="Chấp nhận mức xử lý tối thiểu (khóa khi online + cảnh báo khi offline) mà Architect đã điều chỉnh - đây là mức hợp lý, không phải bỏ qua hoàn toàn cũng không phải tự động hợp nhất phức tạp.",
            ),
            DefenseResponse(
                critique_source="devils_advocate (round5)",
                critique_summary="Chưa có câu trả lời rõ ràng cho câu hỏi ai trả tiền và trả bao nhiêu",
                stance="defend",
                rationale="Đây đúng là câu hỏi còn bỏ ngỏ (đã đánh dấu uncertainty từ vòng 1); Business Critic không có đủ dữ liệu thị trường để tự chốt, cần escalate cho người quyết định ở vòng đồng thuận cuối.",
            ),
        ],
        changed_decisions=[],
        final_decisions=[
            "Không tích hợp thanh toán QR và AI gợi ý nhập hàng ở V1",
            "Chấp nhận mức xử lý xung đột tối thiểu (khóa khi online, cảnh báo khi offline) do Architect đề xuất",
            "Mô hình giá cụ thể (thuê bao vs bán kèm phần cứng) cần escalate cho người quyết định, chưa đủ dữ liệu để tự chốt",
        ],
    )


def _defense_qa_security() -> Defense:
    return Defense(
        role="qa_security",
        round=7,
        responses=[
            DefenseResponse(
                critique_source="product_ba (round3)",
                critique_summary="Xác nhận đăng nhập riêng từng nhân viên không làm chậm ca bán hàng đông khách",
                stance="revise",
                rationale="Chấp nhận chuyển từ tài khoản đầy đủ sang mã PIN ngắn riêng từng người, kèm giới hạn số lần thử sai, như phương án thay thế ở vòng 6.",
            ),
        ],
        changed_decisions=[
            ChangedDecision(
                topic="employee_authentication",
                old_decision="Mỗi nhân viên đăng nhập bằng tài khoản riêng (username/password đầy đủ)",
                new_decision="Mỗi nhân viên dùng mã PIN ngắn riêng trên thiết bị dùng chung, giới hạn số lần thử sai",
                reason="Product/BA chỉ ra đăng nhập đầy đủ làm chậm ca bán hàng đông khách",
                triggered_by="product_ba (round3)",
            ),
        ],
        final_decisions=[
            "Mỗi nhân viên dùng mã PIN ngắn riêng, giới hạn số lần thử sai",
            "Ghi audit log mọi giao dịch sửa/hủy đơn hàng kèm ai thực hiện",
            "Chỉ lưu số điện thoại khách tạm thời khi gửi hóa đơn, không xây dựng cơ sở dữ liệu khách hàng tập trung",
            "Yêu cầu khóa ứng dụng bằng mã PIN/vân tay ở cấp thiết bị (phối hợp với Architect)",
        ],
    )


ROUND7 = {
    "product_ba": _defense_product_ba,
    "ux_designer": _defense_ux_designer,
    "architect": _defense_architect,
    "business_critic": _defense_business_critic,
    "qa_security": _defense_qa_security,
}

# ---------------------------------------------------------------------------
# Round 8: Edge case & Pre-mortem
# ---------------------------------------------------------------------------

ROUND8 = {
    "product_ba": PreMortemFinding(
        role="product_ba",
        failure_scenario="Sau 6 tháng, tiểu thương dùng thử vài ngày rồi quay lại ghi sổ tay vì thấy 'thêm việc' thay vì 'giảm việc'.",
        root_cause="Bước onboarding (nhập sản phẩm ban đầu, thiết lập cửa hàng) tốn nhiều thời gian hơn giá trị nhận được ngay trong tuần đầu, chủ shop bỏ giữa chừng.",
        category="business",
        likelihood="medium",
        impact="high",
    ),
    "ux_designer": PreMortemFinding(
        role="ux_designer",
        failure_scenario="Nhân viên thu ngân từ chối dùng app trong giờ cao điểm vì thao tác vẫn chậm hơn máy tính tiền/máy tính bỏ túi quen thuộc.",
        root_cause="Giao diện tuy đơn giản về thiết kế nhưng số bước thực tế vẫn nhiều hơn thói quen cũ nếu không được tối ưu triệt để.",
        category="operational",
        likelihood="medium",
        impact="high",
    ),
    "architect": PreMortemFinding(
        role="architect",
        failure_scenario="Một cửa hàng mất dữ liệu bán hàng của cả một ngày vì thiết bị hỏng trước khi kịp đồng bộ, chủ shop mất niềm tin hoàn toàn vào phần mềm.",
        root_cause="Local-first không có cơ chế sao lưu tức thời/định kỳ ngắn, chỉ đồng bộ khi có mạng - nếu mạng chậm hoặc thiết bị hỏng đúng lúc, dữ liệu chưa đồng bộ mất vĩnh viễn.",
        category="technical",
        likelihood="low",
        impact="high",
    ),
    "business_critic": PreMortemFinding(
        role="business_critic",
        failure_scenario="Sau 6 tháng, số lượng tiểu thương trả phí quá thấp để duy trì kể cả hạ tầng tối giản, dự án phải dừng.",
        root_cause="Mô hình giá chưa được kiểm chứng với người dùng thật trước khi xây sản phẩm đầy đủ - xây trước, hỏi giá sau.",
        category="business",
        likelihood="medium",
        impact="high",
    ),
    "qa_security": PreMortemFinding(
        role="qa_security",
        failure_scenario="Một nhân viên thu ngân gian lận (hủy đơn sau khi thu tiền mặt) trong nhiều tháng liền mà chủ shop không phát hiện.",
        root_cause="Có audit log nhưng không có ai chủ động xem lại định kỳ - ghi log không đủ, cần cảnh báo chủ động khi phát hiện mẫu hành vi bất thường.",
        category="abuse_case",
        likelihood="medium",
        impact="high",
    ),
    "devils_advocate": PreMortemFinding(
        role="devils_advocate",
        failure_scenario="Sau 6 tháng, sản phẩm vẫn hoạt động tốt về kỹ thuật nhưng gần như không ai dùng vì đối thủ cung cấp giải pháp tương tự miễn phí kèm hỗ trợ trực tiếp tại cửa hàng.",
        root_cause="Toàn bộ tranh luận tập trung vào kỹ thuật và trải nghiệm sản phẩm, nhưng chưa ai phân tích đối thủ cạnh tranh hiện có (kể cả giải pháp phi chính thức) trong quá trình thiết kế.",
        category="business",
        likelihood="medium",
        impact="high",
    ),
}

# ---------------------------------------------------------------------------
# Round 9: Hội tụ (Convergence)
# ---------------------------------------------------------------------------


def build_convergence_report() -> ConvergenceReport:
    return ConvergenceReport(
        round=9,
        unresolved_conflicts=[
            "Business Critic và Devil's Advocate đều xác nhận mô hình giá vẫn chưa chốt được (uncertainty từ vòng 1, chưa giải quyết ở vòng 7)",
            "Chưa có phân tích đối thủ cạnh tranh dù Devil's Advocate chỉ ra đây là rủi ro kinh doanh thực sự ở vòng pre-mortem",
        ],
        decision_dependencies=[
            "Quyết định mức xử lý xung đột đồng bộ (architect, vòng 7) phụ thuộc vào việc chưa có số liệu thực tế về tần suất xung đột - nên coi là giả định cần kiểm chứng sớm sau khi ra mắt",
            "Quyết định phân quyền nhân viên bằng mã PIN (qa_security, vòng 7) phụ thuộc vào việc thiết bị có yêu cầu khóa PIN/vân tay ở cấp ứng dụng (architect, vòng 7) - hai quyết định này phải triển khai cùng lúc để đủ an toàn",
        ],
        remaining_contradictions=[],
        ready_for_consensus=True,
        synthesis_note=(
            "Phần lớn mâu thuẫn kỹ thuật đã được giải quyết qua các vòng bảo vệ/sửa quan điểm; 2 câu hỏi còn "
            "lại (mô hình giá, phân tích đối thủ) là câu hỏi kinh doanh/chiến lược, không phải kỹ thuật, nên "
            "chuyển cho người quyết định ở vòng cuối thay vì council tự quyết."
        ),
    )


# ---------------------------------------------------------------------------
# Round 10: Moderator - Đồng thuận cuối
# ---------------------------------------------------------------------------


def build_consensus_report() -> ConsensusReport:
    items = [
        ConsensusItem(
            topic="pos_flow_scope",
            status="accepted",
            decision="V1 hỗ trợ cả bán theo mã vạch (tạp hóa) và bán theo món tự đặt tên (quán ăn/cà phê), không bắt buộc mã vạch",
            rationale="Không ai phản đối trong suốt 9 vòng; đây là yêu cầu nền tảng để sản phẩm dùng được cho cả 2 nhóm khách hàng mục tiêu nêu trong đề bài.",
            evidence=["product_ba round2: hỗ trợ cả 2 kiểu bán hàng", "không có phản biện nào bác bỏ quyết định này qua các vòng 3-8"],
            implementation_priority="P0",
        ),
        ConsensusItem(
            topic="invoice_as_optional_step",
            status="accepted",
            decision="Hóa đơn (in giấy hoặc gửi điện tử) là bước tùy chọn sau khi thanh toán xong, có nút bỏ qua rõ ràng, không chặn luồng bán hàng chính",
            rationale="UX Designer chỉ ra cụ thể việc hỏi hóa đơn mặc định làm chậm ca bán hàng đông khách; Product/BA sửa quyết định ngay ở vòng 7 - đây là mind change có bằng chứng rõ ràng, không phải ý kiến số đông.",
            evidence=["ux_designer round3: hỏi hóa đơn mặc định làm chậm luồng chính", "product_ba round7: sửa thành bước tùy chọn có nút bỏ qua"],
            implementation_priority="P0",
        ),
        ConsensusItem(
            topic="sync_conflict_handling",
            status="accepted",
            decision="Khóa sản phẩm để bán trên đúng 1 thiết bị khi cả 2 đang online; khi cả 2 offline, chỉ cảnh báo xung đột cho chủ shop xử lý thủ công, không tự động hợp nhất phức tạp",
            rationale=(
                "Đây là điểm hội tụ giữa 3 lập luận khác nhau: Business Critic lo ngại over-engineering, "
                "Architect ban đầu muốn tự động hợp nhất, Devil's Advocate chỉ ra bỏ qua hoàn toàn cũng có "
                "rủi ro kinh doanh - mức tối thiểu này thỏa cả 3 lo ngại, không phải thỏa hiệp majority vote "
                "mà là phương án khả thi nhất sau khi cân nhắc bằng chứng từng bên"
            ),
            evidence=[
                "business_critic round3: nghi ngờ over-engineering",
                "architect round7: giảm mức đầu tư xuống khóa + cảnh báo",
                "devils_advocate round6 (alternative): đề xuất chính phương án khóa khi online",
            ],
            implementation_priority="P0",
        ),
        ConsensusItem(
            topic="local_device_security",
            status="accepted",
            decision="Yêu cầu khóa ứng dụng bằng mã PIN/vân tay khi mở app trên thiết bị, cộng với mã PIN ngắn riêng cho từng nhân viên thu ngân",
            rationale="QA+Security chỉ ra cụ thể rủi ro lộ toàn bộ dữ liệu kinh doanh nếu mất thiết bị; Architect chấp nhận ngay ở vòng 7 vì đây là lỗ hổng thật, không phải lý thuyết.",
            evidence=["qa_security round4: dữ liệu cục bộ chưa được bảo vệ nếu mất thiết bị", "architect round7: thêm yêu cầu khóa PIN/vân tay"],
            implementation_priority="P0",
        ),
        ConsensusItem(
            topic="menu_layout_flexibility",
            status="accepted",
            decision="Hai chế độ hiển thị menu: lưới nút bấm cho menu đơn giản, danh sách có lọc/tìm kiếm cho menu lớn; ưu tiên tối ưu cho màn hình điện thoại phổ thông trước máy tính bảng",
            rationale="Devil's Advocate chỉ ra 2 giả định sai (màn hình luôn lớn, menu luôn đơn giản) bằng ví dụ cụ thể; UX Designer sửa lại thành 2 chế độ thay vì ép 1 giao diện duy nhất.",
            evidence=[
                "devils_advocate round4: giả định màn hình lớn không đúng thực tế",
                "devils_advocate round5: menu phức tạp chưa được giải quyết",
                "ux_designer round7: thêm 2 chế độ hiển thị",
            ],
            implementation_priority="P1",
        ),
        ConsensusItem(
            topic="v1_scope_exclusions",
            status="accepted",
            decision="Không tích hợp thanh toán QR (Momo/VNPay) và không làm tính năng AI gợi ý nhập hàng ở V1; để dành cho các phiên bản sau",
            rationale="Business Critic đề xuất từ đầu để giữ chi phí/độ phức tạp thấp; không role nào phản đối việc loại các tính năng này khỏi V1 qua suốt 9 vòng, kể cả Devil's Advocate.",
            evidence=["business_critic round2: không tích hợp thanh toán QR và AI ở V1", "product_ba round7: đồng ý loại gợi ý nhập hàng khỏi requirements chính thức"],
            implementation_priority="P2",
        ),
        ConsensusItem(
            topic="pricing_model",
            status="unresolved",
            decision=None,
            rationale=(
                "Đây là câu hỏi mô hình kinh doanh (thuê bao vs bán kèm phần cứng), không phải câu hỏi kỹ "
                "thuật. Business Critic đã đánh dấu uncertainty từ vòng 1 và tiếp tục từ chối tự chốt ở vòng 7 "
                "vì thiếu dữ liệu thị trường thực tế - council không có thẩm quyền hay dữ liệu để tự quyết "
                "định thay cho quyết định kinh doanh này"
            ),
            evidence=[
                "business_critic round1: chưa có số liệu về mức giá tiểu thương chấp nhận",
                "business_critic round7: tiếp tục từ chối tự chốt, đề nghị escalate",
                "convergence round9: xác nhận đây là mâu thuẫn/câu hỏi chưa giải quyết",
            ],
            dissent="Product/BA nghiêng về mô hình bán kèm phần cứng vì giảm rào cản dùng thử, nhưng không có số liệu để khẳng định chắc chắn.",
        ),
        ConsensusItem(
            topic="competitive_analysis",
            status="unresolved",
            decision=None,
            rationale="Devil's Advocate chỉ ra ở vòng pre-mortem rằng chưa ai phân tích đối thủ cạnh tranh trong suốt quá trình thiết kế - đây là khoảng trống nghiên cứu thị trường, không phải quyết định kỹ thuật mà council có thể tự lấp bằng tranh luận nội bộ.",
            evidence=["devils_advocate round8: chưa có phân tích đối thủ cạnh tranh", "convergence round9: xác nhận đây là khoảng trống chưa giải quyết"],
            dissent=None,
        ),
    ]
    summary = (
        "6 chủ đề đạt đồng thuận qua bằng chứng cụ thể từ 9 vòng tranh luận (không phải biểu quyết đa số), "
        "bao gồm nhiều lần đổi ý có ghi rõ before/after/reason; 2 chủ đề còn lại là câu hỏi kinh doanh/thị "
        "trường ngoài thẩm quyền kỹ thuật của council, cần người quyết định."
    )
    return ConsensusReport(round=10, items=items, summary=summary)
