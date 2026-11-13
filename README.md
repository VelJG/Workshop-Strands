# Workshop Strands — Trợ lý AI hỗ trợ doanh nghiệp

**Đại học FPT · AI trong doanh nghiệp: Vượt ra ngoài mô hình**

Ứng dụng chạy **một chế độ AI thật** với **Strands Agents SDK**: một router và ba specialist agents trong Strands Graph. **Q&A** gọi `search_policy` để tra embeddings/FAISS từ các ghi chú mẫu và PDF quy trình mật khẩu; **Ticket** gọi `draft_ticket` nhưng chỉ ghi SQLite sau khi người dùng phê duyệt; **Research** dùng vòng agent–tool của Strands để gọi `search_web` qua Tavily rồi tổng hợp câu trả lời có nguồn. Cần OpenAI API key, Tavily API key, internet và ngân sách API; Tavily Search tiêu thụ credits. Phiếu là dữ liệu giả lập; câu hỏi và kho tri thức được gửi tới nhà cung cấp model, truy vấn Research còn được gửi tới Tavily.

## Chạy trên Windows

Mở PowerShell tại thư mục này:

```powershell
python -m pip install -r requirements-live.txt
python -m workshop serve
```

PDF quy trình mật khẩu là dữ liệu cục bộ, không được Git theo dõi. Đặt file tại `data/policies/Information_Technology_Procedure_-_Passwords.pdf` trước khi chạy. Khi clone repo, cần tự cung cấp file PDF này. Bộ lập chỉ mục trích xuất văn bản theo trang, chia chunk có overlap và gắn trang vào nguồn trích dẫn. Bản PDF có thể không phải bản hiện hành; hãy xác minh với thư viện chính sách chính thức trước khi áp dụng.

Trước khi chạy, tạo `.env` từ `.env.example` rồi điền `OPENAI_API_KEY`, `WORKSHOP_CHAT_MODEL`, `WORKSHOP_EMBEDDING_MODEL` và `TAVILY_API_KEY`. Không đưa key vào Git hoặc trình chiếu. Ứng dụng luôn chạy AI thật và dừng với thông báo rõ ràng nếu thiếu cấu hình. Bản sao này **không sao chép key** từ Workshop2.

Timeout mặc định **120 giây cho mỗi node Strands**; có thể đặt `WORKSHOP_RESEARCH_TIMEOUT_SECONDS` từ 10 đến 300 rồi khởi động lại server. Tavily SDK giới hạn riêng lượt tìm kiếm ở 120 giây.

Mở terminal thứ hai, cũng tại thư mục này:

```powershell
python -m workshop demo
```

Hoặc mở **[giao diện chat](http://127.0.0.1:8000/)** trên trình duyệt. Chọn câu hỏi mẫu để xem nguồn tri thức, sau đó thử đề xuất tạo phiếu và nhấn **Phê duyệt** hoặc **Từ chối**. Trang chat chỉ phục vụ chế độ local không có token; khi bật `WORKSHOP_HOSTED=1` hoặc đặt `WORKSHOP_TOKEN`, giao diện không được mở để tránh dùng token người trình bày trong trình duyệt.

Để xuất **sơ đồ kiến trúc** (không gọi OpenAI/Tavily API), chạy `python -m workshop graph`. Lệnh tạo `graph_visualization.png` tại thư mục dự án; bộ dựng ảnh Mermaid có thể cần internet. Sơ đồ mô tả Strands Graph router → specialist và vòng gọi tool bên trong mỗi agent; đây là **sơ đồ kiến trúc**, không phải ảnh tự sinh từ runtime Strands. Approval ticket vẫn do FastAPI xử lý sau khi agent kết thúc.

Thử câu “Tìm trên web hướng dẫn bảo mật VPN mới nhất và dẫn nguồn” để thấy Research Agent cùng các citation. Router dùng model để chọn một trong ba agent; Strands tự quản lý vòng model → tool → model của specialist. Chỉ một lượt Tavily Search được phép thực hiện cho mỗi câu hỏi. Không nhập dữ liệu nội bộ/khách hàng thật vào yêu cầu tìm web.

Lệnh `workshop demo` chạy kịch bản HTTP trên server đang chạy (không chọn chế độ model): health check, FAQ kèm nguồn, từ chối một yêu cầu tạo phiếu, rồi duyệt yêu cầu khác và xác nhận duyệt lại không tạo phiếu trùng. Kịch bản gọi model thật và có thể phát sinh phí API.

Client diễn tập chờ tối đa 180 giây mỗi request vì Strands chạy router rồi specialist; có thể đặt `WORKSHOP_HTTP_TIMEOUT_SECONDS` từ 10 đến 600 trong terminal chạy `workshop demo`.

Có thể thao tác thủ công tại [tài liệu API](http://127.0.0.1:8000/docs). Chỉ sử dụng dữ liệu giả lập; không nhập thông tin khách hàng thật.

## Chạy bằng Docker

Trước tiên dừng máy chủ Python nếu đang dùng cùng cổng.

```powershell
docker compose up --build --wait
python -m workshop demo
docker compose logs --tail 25
docker compose down
```

Compose chỉ mở cổng trên máy local và giữ volume dữ liệu sau khi dừng. Đổi cổng bằng `WORKSHOP_LOCAL_PORT`, đồng thời truyền URL tương ứng qua `--url`. Muốn dùng cơ sở dữ liệu sạch, hãy đặt `WORKSHOP_DB` sang một tệp mới.

## Cấu hình và vận hành AI thật

Chọn model ID được tài khoản cho phép; chat model cần hỗ trợ gọi công cụ và structured output. Không đưa `.env` lên Git hoặc chia sẻ key. Biến môi trường đặt trực tiếp trong tiến trình được ưu tiên hơn `.env`. FAISS lập chỉ mục một lần lúc khởi động; Q&A tool embed câu truy vấn và lấy tối đa ba kết quả. Chỉ mục nằm trong RAM và được tạo lại khi khởi động. Mỗi request tạo Strands Graph và các agent mới để không trộn hội thoại; model provider và index được tái sử dụng. Lỗi provider hiển thị rõ; ứng dụng không fallback sang phản hồi giả lập.

Docker image luôn có thư viện AI thật; Compose đọc `.env` lúc chạy, không đóng gói key vào image.

## Tài liệu và sơ đồ

- [Luồng hệ thống Mermaid](docs/system-flow.mmd).
- [Kiến trúc AWS](docs/aws.md): phương án triển khai tùy chọn; dự án không tự tạo tài nguyên AWS.
- `graph_visualization.png`: sơ đồ Strands Graph và các specialist.
- `Workshop_Enterprise_AI_AWS_Architecture_V3.drawio.png`: sơ đồ kiến trúc AWS.
- `tests/test_workshop.py`: kiểm thử tình huống có kết quả xác định. Cài `requirements-test.txt`, sau đó chạy `python -m unittest discover -s tests -v` từ thư mục dự án.

