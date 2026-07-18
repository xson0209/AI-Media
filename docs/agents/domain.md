# Tài liệu domain

File này quy định cách agent đọc tài liệu domain khi tìm hiểu codebase.

## Trước khi phân tích code, đọc các tài liệu này nếu có

- `CONTEXT.md` ở root repo, hoặc
- `CONTEXT-MAP.md` ở root repo nếu tồn tại. File này trỏ tới từng `CONTEXT.md` theo ngữ cảnh.
- `docs/adr/` cho các quyết định kiến trúc liên quan đến vùng code sắp đụng tới.

Nếu các file này chưa tồn tại thì tiếp tục làm việc bình thường, không cần báo lỗi.

## Cấu trúc tài liệu

Repo một ngữ cảnh:

```text
/
├── CONTEXT.md
├── docs/adr/
└── src/
```

Repo nhiều ngữ cảnh:

```text
/
├── CONTEXT-MAP.md
├── docs/adr/
└── src/
    ├── ordering/
    │   ├── CONTEXT.md
    │   └── docs/adr/
    └── billing/
        ├── CONTEXT.md
        └── docs/adr/
```

## Dùng đúng thuật ngữ của project

Khi output nhắc tới một khái niệm domain, dùng đúng thuật ngữ đã được định nghĩa trong `CONTEXT.md`.

Nếu khái niệm chưa có trong glossary, coi đó là tín hiệu: hoặc mình đang tự đặt tên chưa đúng, hoặc project đang thiếu một khái niệm cần được ghi lại.

## Nếu trái với ADR thì phải nói rõ

Nếu đề xuất hoặc thay đổi mâu thuẫn với ADR đã có, phải chỉ ra rõ thay vì âm thầm ghi đè quyết định cũ.
