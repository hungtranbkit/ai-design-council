"""MockProvider scenario: "SSH Ops Console" - a Vietnamese-language demo
brief distinct from the QR-restaurant scenario in mock.py. Same structure
(6 role proposals, 12 cross-reviews, 7 Devil's Advocate findings, defenses
with recorded mind changes, a 5-round-5 consensus with unresolved items),
same pydantic schemas, same validation rules - just a different hand-authored
deterministic debate, in Vietnamese, about a self-hosted SSH/host management
console for a small engineering team.

Selected by council/providers/mock.py's scenario detector when the brief
text matches SSH_OPS_MARKERS - see SCENARIO_ID below.
"""
from __future__ import annotations

from council.pipeline.schemas import (
    ChangedDecision,
    ConsensusItem,
    ConsensusReport,
    CrossReview,
    Defense,
    DefenseResponse,
    DevilsAdvocateFinding,
    DevilsAdvocateReport,
    Proposal,
)

SCENARIO_ID = "ssh_ops"
MARKERS = ("ssh", "máy trạm")  # matched case-insensitively against the raw brief text

# ---------------------------------------------------------------------------
# Round 1: Independent proposals
# ---------------------------------------------------------------------------

ROUND1_PRODUCT_BA = Proposal(
    role="product_ba",
    summary=(
        "Hệ thống quản lý tập trung các SSH server/workstation cho một nhóm kỹ thuật nhỏ: "
        "tự phát hiện máy đã từng kết nối, hiển thị trạng thái, cho thao tác qua web terminal, "
        "có phân quyền và audit."
    ),
    requirements=[
        "Tự động phát hiện và liệt kê các SSH target đã từng kết nối từ máy chủ quản lý",
        "Hiển thị trạng thái online/offline theo thời gian thực cho từng máy",
        "Cho phép ghi mô tả (tag, dự án đang chạy) cho từng máy",
        "Mở terminal ngay trên trình duyệt, không cần cài SSH client cục bộ",
        "Hỗ trợ nhiều người dùng với vai trò khác nhau",
    ],
    decisions=[
        "V1 chỉ hỗ trợ giao thức SSH (không VNC/RDP) để giữ phạm vi gọn",
        "Discovery ban đầu dựa trên danh sách máy người dùng khai báo thủ công, có thể học thêm sau",
    ],
    edge_cases=[
        "Máy đổi IP do DHCP khiến hệ thống nhận nhầm là máy mới",
        "Máy tắt nguồn đột ngột giữa một phiên làm việc đang mở",
    ],
    risks=[
        "Người dùng nhầm máy do tên hiển thị trùng nhau giữa các dự án",
        "Onboarding chậm nếu bắt buộc khai báo thủ công từng máy một",
    ],
    assumptions=["Mỗi thành viên trong nhóm đã có quyền SSH hợp lệ tới các máy liên quan"],
)

ROUND1_UX_DESIGNER = Proposal(
    role="ux_designer",
    summary=(
        "Trải nghiệm phải giống việc mở một tab terminal quen thuộc: danh sách máy rõ ràng, "
        "trạng thái dễ nhìn, thao tác nhanh, không cần học lại cách dùng."
    ),
    requirements=[
        "Danh sách máy dạng bảng/card, lọc được theo trạng thái online/offline và theo dự án",
        "Mở terminal trong 1 thao tác, không quá 2 bước bấm",
        "Hiển thị rõ ai khác đang có phiên terminal mở trên cùng một máy, tránh đụng nhau",
        "Giao diện xem được trên điện thoại để kiểm tra nhanh trạng thái (không cần gõ lệnh trên đó)",
    ],
    decisions=["Ưu tiên desktop-first cho thao tác terminal thật sự; mobile chỉ dùng để xem trạng thái"],
    edge_cases=[
        "Terminal bị treo do lệnh chạy lâu (ví dụ tail -f) - cần cách ngắt kết nối rõ ràng cho người dùng",
        "Nhiều tab terminal cùng lúc mở tới cùng một máy",
    ],
    risks=["Người dùng không biết phiên của mình có đang bị ghi lại (audit) hay không nếu giao diện không nói rõ"],
    assumptions=["Người dùng là kỹ sư đã quen thao tác terminal, không cần giao diện 'thân thiện hoá' quá mức"],
)

ROUND1_ARCHITECT = Proposal(
    role="architect",
    summary=(
        "Một service trung tâm quản lý danh sách host (host-registry) và làm proxy terminal qua "
        "WebSocket + PTY; dữ liệu host/dự án lưu trong Postgres; kiểm tra trạng thái bằng heartbeat định kỳ."
    ),
    requirements=[
        "Service quản lý danh sách host (host-registry) và metadata liên quan",
        "Service proxy terminal 2 chiều qua WebSocket, kết nối PTY thật tới host đích qua SSH",
        "Cơ chế heartbeat định kỳ để xác định trạng thái online/offline của từng host",
    ],
    decisions=[
        "Dùng WebSocket cho phiên terminal vì cần gửi input người dùng theo thời gian thực, "
        "không chỉ nhận output một chiều như SSE",
        "Discovery bằng cách để service trung tâm định kỳ thử kết nối SSH tới danh sách host đã khai báo, "
        "kết hợp đọc known_hosts trên máy trung tâm để gợi ý thêm host mới",
    ],
    edge_cases=["Mất kết nối mạng giữa proxy và host đích giữa phiên - cần giữ lại một phần output tối thiểu"],
    risks=["Service proxy trung tâm là điểm chịu tải và điểm lỗi duy nhất cho toàn bộ việc truy cập host"],
    assumptions=["Mọi host đích đều truy cập được qua SSH chuẩn (cổng 22 hoặc qua tunnel), không cần giao thức khác"],
)

ROUND1_BUSINESS_CRITIC = Proposal(
    role="business_critic",
    summary=(
        "Đối tượng dùng là một nhóm kỹ thuật nhỏ nội bộ, nên hạ tầng phải tối giản - không cần "
        "kiến trúc microservices cho vài chục máy chủ."
    ),
    requirements=["Chi phí vận hành hệ thống phải thấp hơn rõ rệt so với giá trị thời gian nó tiết kiệm được"],
    decisions=["Triển khai dạng một service trung tâm gọn (monolith nhẹ) cho V1, không tách nhiều service riêng lẻ"],
    edge_cases=["Nhóm tăng quy mô từ vài máy lên vài chục/vài trăm máy - hệ thống có cần thiết kế lại không"],
    risks=[
        "Đầu tư quá mức cho phân quyền/audit chi tiết trong khi nhóm hiện tại chỉ có vài người tin cậy lẫn nhau",
    ],
    assumptions=["Đối tượng dùng là đội ngũ nội bộ tin cậy, không phải dịch vụ nhiều khách hàng (multi-tenant)"],
)

ROUND1_QA_SECURITY = Proposal(
    role="qa_security",
    summary=(
        "Rủi ro lớn nhất của hệ thống này là rò rỉ credential SSH và audit log chứa dữ liệu nhạy cảm; "
        "phải coi mỗi phiên terminal là một trust boundary thật sự."
    ),
    requirements=[
        "Không bao giờ lưu private key hoặc mật khẩu SSH dạng plaintext trên server trung tâm",
        "Ghi audit log cho mọi lần mở phiên: ai mở, mở tới máy nào, lúc nào",
    ],
    decisions=[
        "Credential SSH phải được mã hoá khi lưu và chỉ giải mã tạm thời trong bộ nhớ lúc mở phiên, "
        "không lưu dạng đọc được ở trạng thái nghỉ",
    ],
    edge_cases=[
        "Người dùng vô tình dán một secret (API key) vào terminal - nếu audit log ghi toàn bộ nội dung gõ "
        "thì secret đó bị lộ ngay trong chính audit log",
    ],
    risks=[
        "Một tài khoản quản trị bị chiếm quyền có thể mở SSH tới toàn bộ hạ tầng nội bộ nếu không giới hạn "
        "phạm vi ảnh hưởng (blast radius)",
    ],
    assumptions=["Server trung tâm chạy trong mạng được kiểm soát, không lộ trực tiếp ra Internet công cộng"],
)

ROUND1_DEVILS_ADVOCATE = Proposal(
    role="devils_advocate",
    summary=(
        "Nghi ngờ độc lập: cả bộ đề xuất có vẻ giả định discovery và việc thiết lập trust SSH đơn giản hơn "
        "thực tế, và chưa ai nói rõ điều gì xảy ra khi một phiên terminal bị rớt kết nối giữa chừng."
    ),
    requirements=[
        "Phải định nghĩa rõ hành vi khi phiên WebSocket rớt giữa chừng: giữ phiên ở server chờ reconnect, "
        "hay huỷ ngay và mất trạng thái",
    ],
    decisions=["Không nên mặc định rằng discovery tự động là đáng tin cậy ngay từ V1"],
    edge_cases=["Máy khởi động lại đúng lúc audit log đang ghi dở một phiên"],
    risks=[
        "Chưa ai đề cập tới quy trình thu hồi quyền truy cập khi một thành viên rời nhóm (credential revocation)",
    ],
    assumptions=[],
    open_questions=["V1 có nên tự làm discovery hoàn toàn tự động, hay chỉ nhận khai báo thủ công và để tự động hoá cho V2?"],
)

ROUND1 = {
    "product_ba": ROUND1_PRODUCT_BA,
    "ux_designer": ROUND1_UX_DESIGNER,
    "architect": ROUND1_ARCHITECT,
    "business_critic": ROUND1_BUSINESS_CRITIC,
    "qa_security": ROUND1_QA_SECURITY,
    "devils_advocate": ROUND1_DEVILS_ADVOCATE,
}

# ---------------------------------------------------------------------------
# Round 2: Cross review
# ---------------------------------------------------------------------------

ROUND2: dict[str, dict[str, CrossReview]] = {
    "product_ba": {
        "architect": CrossReview(
            reviewer_role="product_ba",
            target_role="architect",
            agree=["Cấu trúc host-registry cộng với terminal proxy phù hợp với luồng nghiệp vụ"],
            disagree=[],
            missing_requirements=["Chưa nói khi service proxy chết thì ai được cảnh báo để xử lý kịp thời"],
            risks=[],
            proposed_changes=["Bổ sung yêu cầu cảnh báo vận hành khi service proxy ngừng hoạt động"],
        ),
        "qa_security": CrossReview(
            reviewer_role="product_ba",
            target_role="qa_security",
            agree=["Đồng ý tuyệt đối không lưu credential dạng plaintext"],
            disagree=[],
            missing_requirements=[],
            risks=[],
            proposed_changes=[
                "Cần xác nhận việc mã hoá/giải mã credential không làm chậm đáng kể thao tác mở phiên",
            ],
        ),
    },
    "ux_designer": {
        "product_ba": CrossReview(
            reviewer_role="ux_designer",
            target_role="product_ba",
            agree=["Đồng ý giữ phạm vi V1 chỉ với giao thức SSH"],
            disagree=[
                "Discovery hoàn toàn thủ công sẽ khiến việc onboarding nhóm chậm và trải nghiệm không khác gì "
                "một bảng danh sách máy chép tay",
            ],
            missing_requirements=["Cần ít nhất một cách gợi ý máy tự động, không chỉ nhập tay từng máy"],
            risks=[],
            proposed_changes=["Đề xuất discovery bán tự động: hệ thống gợi ý từ known_hosts, người dùng xác nhận thêm"],
        ),
        "architect": CrossReview(
            reviewer_role="ux_designer",
            target_role="architect",
            agree=["Chọn WebSocket cho terminal 2 chiều là hợp lý"],
            disagree=[],
            missing_requirements=[
                "Chưa thấy kiến trúc hỗ trợ việc hiển thị ai khác đang mở phiên trên cùng một host",
            ],
            risks=[],
            proposed_changes=["Kiến trúc cần lưu trạng thái phiên đang mở theo từng host để phục vụ giao diện này"],
        ),
    },
    "architect": {
        "ux_designer": CrossReview(
            reviewer_role="architect",
            target_role="ux_designer",
            agree=["Yêu cầu hiển thị người đang mở phiên trên máy là hợp lý và khả thi về mặt kỹ thuật"],
            disagree=[],
            missing_requirements=[],
            risks=[],
            proposed_changes=["Thêm một bảng lưu các phiên đang hoạt động (active_sessions) vào thiết kế dữ liệu"],
        ),
        "business_critic": CrossReview(
            reviewer_role="architect",
            target_role="business_critic",
            agree=["Đồng ý không cần kiến trúc microservices cho quy mô này"],
            disagree=[
                "Nhưng gộp toàn bộ logic bảo mật (mã hoá credential, audit) chung với phần còn lại làm tăng "
                "rủi ro nếu phần đó bị lỗi hoặc bị khai thác - nên cô lập riêng phần xử lý credential",
            ],
            missing_requirements=[],
            risks=["Một lỗi ở module giao diện có thể ảnh hưởng tới module xử lý credential nếu chung một tiến trình"],
            proposed_changes=["Tách phần xử lý credential thành một module/tiến trình riêng, phần còn lại vẫn gọn nhẹ"],
        ),
    },
    "business_critic": {
        "architect": CrossReview(
            reviewer_role="business_critic",
            target_role="architect",
            agree=[],
            disagree=[
                "Tách một service mạng riêng cho credential là thêm một thành phần phải triển khai và giám sát "
                "cho một đội chỉ có vài kỹ sư - có thể chưa đáng đánh đổi so với việc cô lập ở mức nhẹ hơn",
            ],
            missing_requirements=[],
            risks=["Chi phí vận hành thêm một service tăng gánh nặng đáng kể cho một đội nhỏ"],
            proposed_changes=[
                "Cô lập phần xử lý credential bằng một tiến trình con trong cùng host thay vì một service mạng riêng",
            ],
        ),
        "product_ba": CrossReview(
            reviewer_role="business_critic",
            target_role="product_ba",
            agree=[],
            disagree=[
                "Coi audit log chỉ ghi lúc mở/đóng phiên là đủ - nếu không ghi lệnh nào được chạy thì không "
                "thể điều tra khi có sự cố xảy ra",
            ],
            missing_requirements=["Yêu cầu về mức độ chi tiết tối thiểu cần có trong audit log để điều tra được sự cố"],
            risks=[],
            proposed_changes=["Ghi rõ audit log cần đủ chi tiết để phục vụ điều tra sự cố, không chỉ ghi thời điểm mở/đóng"],
        ),
    },
    "qa_security": {
        "product_ba": CrossReview(
            reviewer_role="qa_security",
            target_role="product_ba",
            agree=[],
            disagree=[
                "Audit log chỉ ghi lúc mở/đóng phiên không đủ để điều tra sự cố, nhưng ghi toàn bộ nội dung "
                "gõ lại có nguy cơ lộ secret - đây không phải lựa chọn nhị phân, cần một phương án ở giữa",
            ],
            missing_requirements=["Yêu cầu che (redact) các chuỗi giống secret/token trước khi ghi vào audit log"],
            risks=[],
            proposed_changes=["Bổ sung cơ chế phát hiện và che chuỗi giống token/API key trước khi lưu audit log"],
        ),
        "architect": CrossReview(
            reviewer_role="qa_security",
            target_role="architect",
            agree=[],
            disagree=[
                "Kiến trúc chưa nói ai xác thực người dùng trước khi được cấp quyền chọn host - nếu chỉ dựa vào "
                "việc truy cập được server trung tâm thì không có xác thực thực sự",
            ],
            missing_requirements=[
                "Cần một lớp đăng nhập và kiểm tra quyền, tách bạch với việc người dùng có SSH key hay không",
            ],
            risks=["Bất kỳ ai vào được giao diện web sẽ coi như có toàn quyền SSH nếu thiếu lớp xác thực/uỷ quyền riêng"],
            proposed_changes=["Thêm bước đăng nhập và kiểm tra vai trò trước khi cho phép chọn host để mở phiên"],
        ),
    },
    "devils_advocate": {
        "architect": CrossReview(
            reviewer_role="devils_advocate",
            target_role="architect",
            agree=["Lựa chọn WebSocket cho phiên terminal là hợp lý"],
            disagree=[
                "Không có gì đảm bảo việc định kỳ thử kết nối SSH sẽ phát hiện đúng host - nếu host đổi IP hoặc "
                "hostname liên tục thì cơ chế discovery này thất bại âm thầm mà không ai biết",
            ],
            missing_requirements=["Cần cách phát hiện khi discovery thất bại và báo cho người dùng, không để im lặng"],
            risks=[],
            proposed_changes=["Thêm trạng thái 'không xác định được / cần kiểm tra lại' thay vì chỉ online/offline"],
        ),
        "ux_designer": CrossReview(
            reviewer_role="devils_advocate",
            target_role="ux_designer",
            agree=["Yêu cầu mở terminal trong một thao tác là hợp lý"],
            disagree=[
                "Chưa thấy đề cập việc terminal có thể chạy các lệnh phá hoại (rm -rf, reboot) - thiết kế chỉ "
                "tối ưu tốc độ thao tác mà chưa có bước xác nhận nào cho hành động nguy hiểm, trong khi đây là "
                "hệ thống có quyền SSH thật tới nhiều máy chủ",
            ],
            missing_requirements=["Yêu cầu cảnh báo/xác nhận trước khi thực hiện một số lệnh có nguy cơ cao"],
            risks=[],
            proposed_changes=["Ghi nhận việc thiếu cảnh báo cho lệnh nguy hiểm là một rủi ro cần xử lý, không thể bỏ qua"],
        ),
    },
}

# ---------------------------------------------------------------------------
# Round 3: Devil's Advocate - must cover all 7 required categories
# ---------------------------------------------------------------------------

ROUND3_FINDINGS = [
    DevilsAdvocateFinding(
        category="security",
        description=(
            "Đề xuất ban đầu của Product/BA về audit log (chỉ ghi lúc mở/đóng phiên) và phản biện của "
            "QA+Security (cần ghi lệnh nhưng lo ngại lộ secret) vẫn chưa thống nhất - nếu không giải quyết, "
            "đội triển khai audit log kiểu nào cũng có thể sai theo một trong hai hướng"
        ),
        target_role="product_ba",
        severity="high",
    ),
    DevilsAdvocateFinding(
        category="unnecessary_complexity",
        description=(
            "Việc tách phần xử lý credential thành một service/tiến trình riêng đang được đề xuất trước khi có "
            "bằng chứng cụ thể rằng một đội chỉ vài người thực sự cần mức cô lập đó - Business Critic đặt câu "
            "hỏi đúng, nhưng phương án 'tiến trình con cùng host' cũng chưa được chứng minh là đủ an toàn"
        ),
        target_role="architect",
        severity="medium",
    ),
    DevilsAdvocateFinding(
        category="missing_business_case",
        description=(
            "Không ai trong sáu đề xuất đặt câu hỏi hệ thống này có thực sự đáng xây so với việc tiếp tục dùng "
            "một file danh sách SSH cộng với tmux thủ công - chưa có ước tính cụ thể về thời gian nhóm tiết "
            "kiệm được để biện minh cho khoản đầu tư xây dựng và vận hành"
        ),
        target_role="business_critic",
        severity="medium",
    ),
    DevilsAdvocateFinding(
        category="scalability",
        description=(
            "Cơ chế heartbeat định kỳ để kiểm tra online/offline chưa nêu rõ tần suất và số lượng host tối đa "
            "trước khi một service trung tâm duy nhất trở thành điểm nghẽn hiệu năng"
        ),
        target_role="architect",
        severity="medium",
    ),
    DevilsAdvocateFinding(
        category="ux",
        description=(
            "UX Designer yêu cầu hiển thị ai đang mở phiên trên máy nào, nhưng chưa xử lý trường hợp hai người "
            "cùng cần thao tác khẩn cấp trên một host - có chặn nhau hay cho phép mở đồng thời, và ai chịu "
            "trách nhiệm nếu hai người vô tình chạy lệnh xung đột"
        ),
        target_role="ux_designer",
        severity="medium",
    ),
    DevilsAdvocateFinding(
        category="hidden_assumption",
        description=(
            "Toàn bộ sáu đề xuất ngầm giả định rằng server trung tâm luôn được các host đích tin tưởng sẵn "
            "(qua SSH key hoặc agent forwarding có sẵn) - không ai kiểm tra lại giả định này với các máy remote "
            "qua tunnel hoặc hostname lạ, nơi việc thiết lập trust ban đầu khó hơn nhiều so với máy trong LAN"
        ),
        target_role=None,
        severity="high",
    ),
    DevilsAdvocateFinding(
        category="operations",
        description=(
            "Chưa có ai định nghĩa quy trình thu hồi quyền truy cập khi một thành viên rời nhóm - vấn đề đã "
            "được chính Devil's Advocate nêu ở Round 1 nhưng đến giờ vẫn chưa ai trả lời; đây là một lỗ hổng "
            "vận hành thật sự, không chỉ là một lo ngại lý thuyết"
        ),
        target_role="architect",
        severity="high",
    ),
]


def build_devils_advocate_report() -> DevilsAdvocateReport:
    return DevilsAdvocateReport(findings=list(ROUND3_FINDINGS))


# ---------------------------------------------------------------------------
# Round 4: Defense / Revision
# ---------------------------------------------------------------------------


def _defense_product_ba() -> Defense:
    return Defense(
        role="product_ba",
        responses=[
            DefenseResponse(
                critique_source="qa_security (round2)",
                critique_summary="Audit log tối thiểu không đủ để điều tra sự cố, nhưng ghi hết lại lộ secret",
                stance="revise",
                rationale=(
                    "Đồng ý - đây không phải lựa chọn nhị phân; chuyển sang ghi lại lệnh đã chạy nhưng bắt buộc "
                    "che các chuỗi giống secret/token trước khi lưu"
                ),
            ),
            DefenseResponse(
                critique_source="ux_designer (round2)",
                critique_summary="Discovery hoàn toàn thủ công làm chậm việc onboarding nhóm",
                stance="revise",
                rationale="UX Designer đúng - nhóm dễ bỏ cuộc nếu phải khai báo tay từng máy; chấp nhận discovery bán tự động",
            ),
            DefenseResponse(
                critique_source="devils_advocate (round3)",
                critique_summary="Giả định ngầm rằng trust SSH với host remote đã có sẵn",
                stance="defend",
                rationale=(
                    "Đây là giả định hợp lý cho V1: yêu cầu nhóm tự thiết lập SSH key trước khi thêm máy vào "
                    "hệ thống là điều kiện tiên quyết hợp lý, không phải một lỗ hổng của sản phẩm"
                ),
            ),
        ],
        changed_decisions=[
            ChangedDecision(
                topic="audit_logging_scope",
                old_decision="Chỉ ghi audit log lúc mở/đóng phiên, không ghi nội dung lệnh đã chạy",
                new_decision=(
                    "Audit log ghi lại các lệnh đã chạy trong phiên, nhưng tự động che các chuỗi giống "
                    "secret/token trước khi lưu"
                ),
                reason="QA+Security chỉ ra nếu không ghi lệnh thì không điều tra được sự cố, nhưng phải che secret để không tạo rủi ro mới",
                triggered_by="qa_security (round2)",
            ),
            ChangedDecision(
                topic="discovery_mechanism",
                old_decision="Discovery hoàn toàn thủ công, người dùng tự khai báo từng máy một",
                new_decision=(
                    "Discovery bán tự động: hệ thống gợi ý host từ known_hosts, người dùng xác nhận trước khi "
                    "thêm vào danh sách chính thức"
                ),
                reason="UX Designer chỉ ra việc khai báo thủ công quá chậm và không khác gì một bảng danh sách chép tay",
                triggered_by="ux_designer (round2)",
            ),
        ],
        final_decisions=[
            "V1 chỉ hỗ trợ giao thức SSH",
            "Discovery bán tự động (hệ thống gợi ý, người dùng xác nhận)",
            "Audit log ghi lại lệnh đã chạy, tự động che secret trước khi lưu",
        ],
    )


def _defense_ux_designer() -> Defense:
    return Defense(
        role="ux_designer",
        responses=[
            DefenseResponse(
                critique_source="devils_advocate (round2)",
                critique_summary="Thiếu cảnh báo/xác nhận cho các lệnh nguy hiểm",
                stance="partially_accept",
                rationale=(
                    "Không chặn cứng lệnh (chưa đủ độ tin cậy để nhận diện đúng mọi trường hợp ở V1), nhưng "
                    "đồng ý bổ sung cảnh báo đơn giản dựa theo từ khoá cho một số lệnh rủi ro cao"
                ),
            ),
            DefenseResponse(
                critique_source="devils_advocate (round3)",
                critique_summary="Xung đột khi hai người cùng thao tác khẩn cấp trên một máy",
                stance="revise",
                rationale="Đúng là chưa xử lý; cần hiển thị cảnh báo rõ ràng thay vì khoá phiên - tránh làm phức tạp hoá không cần thiết",
            ),
        ],
        changed_decisions=[
            ChangedDecision(
                topic="dangerous_command_warning",
                old_decision="Không có bước xác nhận nào cho hành động nguy hiểm, ưu tiên tốc độ thao tác",
                new_decision=(
                    "Thêm cảnh báo xác nhận đơn giản dựa theo từ khoá (ví dụ rm -rf, reboot, shutdown) trước "
                    "khi thực thi, không chặn nhưng yêu cầu xác nhận thêm một lần"
                ),
                reason="Devil's Advocate chỉ ra hệ thống có quyền SSH thật tới nhiều máy chủ, thiếu xác nhận là rủi ro thật",
                triggered_by="devils_advocate (round2)",
            ),
            ChangedDecision(
                topic="concurrent_session_visibility",
                old_decision="Chỉ hiển thị ai đang mở phiên, không xử lý gì thêm khi có trùng lặp",
                new_decision="Hiển thị cảnh báo rõ ràng khi có người khác đang mở phiên trên cùng máy, không khoá phiên mới",
                reason="Devil's Advocate chỉ ra trường hợp hai người cùng cần thao tác khẩn cấp chưa được xử lý",
                triggered_by="devils_advocate (round3)",
            ),
        ],
        final_decisions=[
            "Ưu tiên desktop-first cho thao tác terminal",
            "Cảnh báo xác nhận theo từ khoá cho lệnh nguy hiểm, không chặn cứng",
            "Hiển thị rõ khi có phiên trùng máy, không khoá phiên mới",
        ],
    )


def _defense_architect() -> Defense:
    return Defense(
        role="architect",
        responses=[
            DefenseResponse(
                critique_source="business_critic (round2)",
                critique_summary="Tách credential thành service riêng là thêm gánh nặng vận hành cho đội nhỏ",
                stance="revise",
                rationale=(
                    "Đồng ý cho V1 - cô lập bằng một tiến trình con trong cùng host thay vì một service mạng "
                    "độc lập, giảm số thành phần phải triển khai và giám sát"
                ),
            ),
            DefenseResponse(
                critique_source="qa_security (round2)",
                critique_summary="Thiếu lớp xác thực người dùng độc lập trước khi cấp quyền chọn host",
                stance="revise",
                rationale="Đúng, đây là lỗ hổng thật; thêm bước đăng nhập và kiểm tra vai trò, tách bạch với việc có SSH key hay không",
            ),
            DefenseResponse(
                critique_source="devils_advocate (round2)",
                critique_summary="Discovery có thể thất bại âm thầm khi host đổi IP/hostname",
                stance="revise",
                rationale="Chấp nhận; thêm trạng thái 'không xác định được' thay vì chỉ online/offline, và cảnh báo khi không xác nhận được một host đã đăng ký",
            ),
            DefenseResponse(
                critique_source="devils_advocate (round3)",
                critique_summary="Chưa rõ giới hạn quy mô của cơ chế heartbeat",
                stance="defend",
                rationale=(
                    "Với quy mô 'nhóm kỹ thuật nhỏ' đã nêu trong đề bài, heartbeat mỗi 30-60 giây cho vài chục "
                    "đến khoảng 200 host là hợp lý và không cần tối ưu thêm ở V1 - ghi nhận đây là giới hạn "
                    "scope rõ ràng thay vì thiết kế lại"
                ),
            ),
        ],
        changed_decisions=[
            ChangedDecision(
                topic="credential_isolation",
                old_decision="Tách phần xử lý credential thành một service mạng riêng",
                new_decision="Cô lập credential trong một tiến trình con cùng host, không tách service mạng riêng",
                reason="Business Critic chỉ ra chi phí vận hành thêm một service cho một đội nhỏ là không tương xứng",
                triggered_by="business_critic (round2)",
            ),
            ChangedDecision(
                topic="user_authentication",
                old_decision="Không có lớp xác thực riêng, dựa vào việc truy cập được server trung tâm",
                new_decision="Thêm bước đăng nhập và kiểm tra vai trò trước khi cho phép chọn host hoặc mở phiên",
                reason="QA+Security chỉ ra nếu thiếu lớp này thì ai vào được giao diện coi như có toàn quyền SSH",
                triggered_by="qa_security (round2)",
            ),
            ChangedDecision(
                topic="host_status_states",
                old_decision="Trạng thái host chỉ có hai giá trị: online/offline",
                new_decision="Thêm trạng thái 'không xác định được / cần kiểm tra lại' khi discovery hoặc heartbeat thất bại",
                reason="Devil's Advocate chỉ ra discovery có thể thất bại âm thầm mà không ai biết",
                triggered_by="devils_advocate (round2)",
            ),
        ],
        final_decisions=[
            "Service trung tâm dạng gọn nhẹ (monolith), WebSocket cho phiên terminal 2 chiều",
            "Credential được cô lập bằng tiến trình con cùng host, không tách service mạng riêng",
            "Có lớp đăng nhập và kiểm tra vai trò trước khi thao tác",
            "Trạng thái host gồm: online / offline / không xác định được",
            "Bảng active_sessions lưu các phiên đang mở theo từng host",
        ],
    )


def _defense_business_critic() -> Defense:
    return Defense(
        role="business_critic",
        responses=[
            DefenseResponse(
                critique_source="architect (round2)",
                critique_summary="Gộp toàn bộ logic bảo mật vào chung một tiến trình làm tăng rủi ro nếu bị lỗi/khai thác",
                stance="partially_accept",
                rationale="Chấp nhận cô lập ở mức tiến trình con (đã được Architect điều chỉnh) thay vì một service mạng độc lập tốn kém hơn",
            ),
            DefenseResponse(
                critique_source="devils_advocate (round3)",
                critique_summary="Chưa có ước tính thời gian nhóm tiết kiệm được để biện minh cho khoản đầu tư",
                stance="defend",
                rationale=(
                    "Đây là câu hỏi hợp lý nhưng thuộc về quyết định đầu tư của tổ chức, không phải điều "
                    "Business Critic có đủ dữ liệu để tự trả lời thay - cần chuyển câu hỏi này cho người quyết định"
                ),
            ),
        ],
        changed_decisions=[],
        final_decisions=[
            "Kiến trúc giữ ở mức một service trung tâm cộng một tiến trình con cô lập credential, không thêm service mạng khác cho V1",
            "Câu hỏi hệ thống này có đáng đầu tư xây hay không cần người quyết định trả lời, không tự đóng ở vòng này",
        ],
    )


def _defense_qa_security() -> Defense:
    return Defense(
        role="qa_security",
        responses=[
            DefenseResponse(
                critique_source="product_ba (round2)",
                critique_summary="Cần xác nhận việc mã hoá/giải mã credential không ảnh hưởng tốc độ mở phiên",
                stance="defend",
                rationale="Giải mã một credential đã mã hoá chỉ tốn vài chục mili-giây, không ảnh hưởng cảm nhận người dùng; giữ nguyên yêu cầu mã hoá bắt buộc",
            ),
        ],
        changed_decisions=[],
        final_decisions=[
            "Không lưu credential SSH dạng plaintext trên server trung tâm",
            "Audit log ghi lại lệnh đã chạy nhưng che secret trước khi lưu",
            "Bắt buộc có lớp đăng nhập và kiểm tra vai trò trước khi mở phiên",
        ],
    )


ROUND4 = {
    "product_ba": _defense_product_ba,
    "ux_designer": _defense_ux_designer,
    "architect": _defense_architect,
    "business_critic": _defense_business_critic,
    "qa_security": _defense_qa_security,
}

# ---------------------------------------------------------------------------
# Round 5: Consensus / Moderator
# ---------------------------------------------------------------------------


def build_consensus_report() -> ConsensusReport:
    items = [
        ConsensusItem(
            topic="credential_storage",
            status="accepted",
            decision=(
                "Không lưu credential SSH dạng plaintext; mã hoá khi lưu, giải mã tạm thời lúc dùng; cô lập "
                "việc xử lý credential trong một tiến trình con riêng cùng host"
            ),
            rationale=(
                "QA+Security đưa bằng chứng cụ thể về rủi ro rò rỉ nếu lưu plaintext, không ai phản đối; "
                "phần 'tiến trình con' là điểm dung hoà giữa yêu cầu cô lập của Architect và giới hạn vận hành "
                "của Business Critic - không phải biểu quyết đa số mà là kết hợp hai lập luận có bằng chứng"
            ),
            evidence=[
                "qa_security round1: không được lưu private key/mật khẩu dạng plaintext",
                "architect round4: cô lập bằng tiến trình con, không service mạng riêng",
                "business_critic round2: phản đối service mạng riêng vì tốn chi phí vận hành",
            ],
        ),
        ConsensusItem(
            topic="discovery_mechanism",
            status="accepted",
            decision=(
                "Discovery bán tự động: hệ thống gợi ý host từ known_hosts, người dùng xác nhận thêm vào "
                "danh sách chính thức; trạng thái host gồm online/offline/không xác định được"
            ),
            rationale=(
                "UX Designer chỉ ra discovery thủ công hoàn toàn làm chậm onboarding, Devil's Advocate chỉ ra "
                "discovery tự động hoàn toàn có thể thất bại âm thầm - phương án bán tự động cộng trạng thái "
                "'không xác định được' giải quyết cả hai lo ngại cùng lúc"
            ),
            evidence=[
                "ux_designer round2: discovery thủ công chậm, giống danh sách chép tay",
                "devils_advocate round2: discovery tự động có thể thất bại âm thầm nếu IP đổi",
                "architect round4: thêm trạng thái không xác định được",
            ],
        ),
        ConsensusItem(
            topic="authentication_and_authorization",
            status="accepted",
            decision=(
                "Bắt buộc có bước đăng nhập và kiểm tra vai trò/quyền trước khi cho phép chọn host hoặc mở "
                "phiên terminal, tách bạch với việc có SSH key hay không"
            ),
            rationale=(
                "QA+Security chỉ ra lỗ hổng cụ thể: nếu thiếu lớp này, bất kỳ ai vào được giao diện web coi "
                "như có toàn quyền SSH - đây là rủi ro nghiêm trọng được Architect thừa nhận và sửa ngay lập tức"
            ),
            evidence=[
                "qa_security round2: thiếu xác thực độc lập là lỗ hổng",
                "architect round4: thêm bước đăng nhập và kiểm tra vai trò",
            ],
        ),
        ConsensusItem(
            topic="audit_logging",
            status="accepted",
            decision="Audit log ghi lại lệnh đã chạy trong phiên, tự động che các chuỗi giống secret/token trước khi lưu",
            rationale=(
                "Giải quyết mâu thuẫn giữa nhu cầu điều tra sự cố (cần ghi lệnh) và rủi ro rò rỉ secret qua "
                "log (không nên ghi hết) - phương án che secret được cả Product/BA và QA+Security chấp nhận "
                "sau khi tranh luận"
            ),
            evidence=[
                "qa_security round2: log tối thiểu không đủ điều tra sự cố nhưng log hết lộ secret",
                "product_ba round4: chấp nhận ghi lệnh có che secret",
            ],
        ),
        ConsensusItem(
            topic="dangerous_command_confirmation",
            status="accepted",
            decision="Cảnh báo xác nhận theo từ khoá (rm -rf, reboot, shutdown...) trước khi thực thi lệnh nguy hiểm, không chặn cứng",
            rationale=(
                "Devil's Advocate chỉ ra hệ thống có quyền SSH thật tới nhiều máy chủ, thiếu xác nhận là rủi "
                "ro thật; UX Designer đồng ý bổ sung mà không làm chậm thao tác thông thường vì chỉ áp dụng "
                "cho một số từ khoá cụ thể"
            ),
            evidence=[
                "devils_advocate round2: thiếu cảnh báo cho lệnh phá hoại",
                "ux_designer round4: thêm cảnh báo theo từ khoá, không chặn cứng",
            ],
        ),
        ConsensusItem(
            topic="realtime_status_updates",
            status="accepted",
            decision="Dùng heartbeat định kỳ (30-60 giây/host) để cập nhật trạng thái, không cần WebSocket push riêng cho việc này ở V1",
            rationale=(
                "Không ai phản đối polling cho việc cập nhật trạng thái máy (khác với terminal cần WebSocket "
                "2 chiều thực sự); Business Critic ủng hộ vì đơn giản, Architect xác nhận đủ đáp ứng quy mô "
                "nhóm nhỏ nêu trong đề bài"
            ),
            evidence=[
                "architect round1: cơ chế heartbeat kiểm tra online/offline",
                "architect round4: heartbeat 30-60 giây cho vài chục đến ~200 host là hợp lý ở V1",
            ],
        ),
        ConsensusItem(
            topic="investment_justification",
            status="unresolved",
            decision=None,
            rationale=(
                "Đây là câu hỏi về giá trị đầu tư (có đáng xây hệ thống này so với quy trình SSH thủ công hiện "
                "tại không), không phải câu hỏi kỹ thuật - Business Critic đúng khi từ chối tự trả lời thay và "
                "escalate lên đây. Council không có đủ thẩm quyền hay dữ liệu để tự quyết định thay cho quyết "
                "định đầu tư của tổ chức"
            ),
            evidence=[
                "devils_advocate round3: chưa có ước tính thời gian tiết kiệm được",
                "business_critic round4: từ chối tự trả lời, đề nghị escalate cho người quyết định",
            ],
            dissent=(
                "Product/BA nghiêng về việc vẫn nên xây vì lợi ích onboarding rõ ràng, nhưng không có số liệu "
                "cụ thể để thuyết phục hoàn toàn"
            ),
        ),
        ConsensusItem(
            topic="user_offboarding_credential_revocation",
            status="unresolved",
            decision=None,
            rationale=(
                "Quy trình thu hồi quyền truy cập khi một thành viên rời nhóm là câu hỏi vận hành/chính sách "
                "nội bộ - ai chịu trách nhiệm thu hồi và trong bao lâu - vượt quá phạm vi kỹ thuật thuần tuý mà "
                "council có thể tự quyết, cần người vận hành thực tế xác nhận quy trình"
            ),
            evidence=[
                "devils_advocate round1: chưa có quy trình thu hồi quyền khi rời nhóm",
                "devils_advocate round3: đây là lỗ hổng vận hành thật, chưa ai trả lời",
            ],
            dissent=(
                "Architect cho rằng có thể giải quyết một phần bằng cách gắn credential vào tài khoản cá nhân "
                "từng người thay vì dùng chung, nhưng chưa đủ để đóng hoàn toàn câu hỏi vận hành này"
            ),
        ),
    ]
    summary = (
        "6 chủ đề đạt đồng thuận qua bằng chứng và tranh luận thực sự (không phải biểu quyết đa số); "
        "2 chủ đề còn lại là câu hỏi đầu tư/vận hành ngoài thẩm quyền kỹ thuật của council, cần người quyết định."
    )
    return ConsensusReport(items=items, summary=summary)
