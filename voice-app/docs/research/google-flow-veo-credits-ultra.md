# Google Flow/Veo credits tren Google AI Ultra

Ngay 2026-07-12

## Tra loi ngan bang tieng Viet

Khong co model Veo 3/Veo 3.1 nao duoc Google cong bo la "khong gioi han" sau khi tai khoan Google AI Ultra het Flow credits. Khi het credits trong Google Flow, Google se bao ban khong du credits/da het credits trong thang; cach tiep tuc la doi goi, cho chu ky tinh phi refresh, hoac mua them AI credits neu khu vuc/tai khoan ho tro. Gemini Omni Flash co ghi "available to all users", nhung van co muc tru Google Flow/AI credits moi generation, nen khong phai fallback mien phi vo han.

## Ket luan

- Google Flow can Google Flow credits hoac AI credits de tao noi dung; credits duoc dung chung theo tai khoan tren cac thiet bi. Nguon: [Manage your Google Flow credits](https://support.google.com/flow/answer/16526234).
- Google AI Ultra la goi co han muc cao nhat, nhung van la han muc credits theo thang: Ultra $100 co 10,000 Google Flow credits/thang, Ultra $200 co 25,000 Google Flow credits/thang. Nguon: [Google Flow Help](https://support.google.com/flow/answer/16526234), [Google One AI plans](https://one.google.com/about/google-ai-plans/).
- Khi Flow credits thap, khong du, hoac het trong thang, Google Flow se thong bao cho nguoi dung. Trang quan ly credits khong noi co model nao tiep tuc chay vo han sau khi het credits. Nguon: [Manage your Google Flow credits](https://support.google.com/flow/answer/16526234).
- Sau khi het han muc, Google noi nguoi dung co the doi/nang cap goi hoac mua them AI credits; trang Google One cung noi thanh vien Pro/Ultra co the mua AI credits de co them usage trong Google Flow. Nguon: [Manage your Google Flow credits](https://support.google.com/flow/answer/16526234), [Manage your AI credits with Google One](https://support.google.com/googleone/answer/16287445).
- Credits mien phi hang ngay khong ap dung cho thue bao AI Plus/Pro/Ultra: nguoi khong dang ky goi nhan 50 Flow credits/ngay; neu nang cap len goi tra phi, credits mien phi con lai bi huy ngay va duoc thay bang allocation hang thang cua goi. Nguon: [Manage your Google Flow credits](https://support.google.com/flow/answer/16526234).
- Credits mien phi, khi co, chi dung duoc cho Veo 3.1 Lite/Fast/Quality generations. Dieu nay khong tao ra fallback mien phi cho Ultra sau khi het credits, vi Ultra khong thuoc nhom nhan 50 credits/ngay. Nguon: [Manage your Google Flow credits](https://support.google.com/flow/answer/16526234).
- Gemini Omni Flash trong Flow duoc Google ghi la "available to all users", nhung bang credit costs van tinh phi bang Flow/AI credits: 15/20/25/30 credits cho video 4s/6s/8s/10s, va 40 credits cho edit. Nguon: [Flow models and supported features](https://support.google.com/flow/answer/16352836), [Manage your Google Flow credits](https://support.google.com/flow/answer/16526234).

## Bang chi phi Flow credits moi generation

Theo trang Google Flow Help, chi phi la moi generation, khong phai moi request; mot request co the tao nhieu generation:

| Model trong Flow | Credit cost chinh thuc |
| --- | --- |
| Veo 3.1 Lite | Non-Ultra: 10; Ultra: 5 |
| Veo 3.1 Fast | Non-Ultra: 20; Ultra: 10 |
| Veo 3.1 Quality | Tat ca nguoi dung: 100 |
| Gemini Omni Flash video | 4s: 15; 6s: 20; 8s: 25; 10s: 30 |
| Gemini Omni Flash edit video | 40 |
| 1080p upscaling | Plus/Pro/Ultra: 0; non-subscribers: khong co |
| 4K upscaling | Ultra: 50; non-Ultra: khong co |

Nguon: [Manage your Google Flow credits](https://support.google.com/flow/answer/16526234).

## Phan biet Flow/Google One voi Gemini API

Google One/Flow credits la co che cua ung dung Google Flow va goi Google AI Plus/Pro/Ultra. Day khong giong billing cua Gemini Developer API.

Trong Gemini Developer API pricing, Veo 3.1 Lite/Fast/Standard va Veo 3 deu ghi "Free Tier: Not available" va chi co gia paid tier theo giay video. Nguon: [Gemini Developer API pricing](https://ai.google.dev/gemini-api/docs/pricing). Trang pricing cung ghi Veo 3 API models `veo-3.0-generate-001` va `veo-3.0-fast-generate-001` bi deprecated va shut down vao 2026-06-30, nen voi API nen xem Veo 3.1/GA models thay the. Nguon: [Gemini Developer API pricing](https://ai.google.dev/gemini-api/docs/pricing).

He qua thuc te: neu dang dung Flow bang tai khoan Google AI Ultra, viec het Flow credits khong bien sang API paid tier va cung khong cho Veo API mien phi. Neu dung API rieng, ban can paid tier/billing theo gia API; Google One Ultra credits khong nen duoc hieu la API credits tu dong.

## Tra loi cho cau hoi model fallback

Neu muc tieu la "chon model nao de khong mat credits sau khi credits het", nguon chinh thuc khong xac nhan model nao nhu vay cho video generation. Lua chon re hon trong Flow la Veo 3.1 Lite tren Ultra, vi cost chi 5 credits/generation; nhung khi credits ve 0 thi van khong du credits de tao tiep, tru truong hop tac vu co cost 0 nhu 1080p upscaling cho subscriber, khong phai tao video moi.
