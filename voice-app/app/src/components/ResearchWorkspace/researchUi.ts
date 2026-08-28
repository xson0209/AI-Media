export function researchStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    draft: 'Bản nháp',
    queued: 'Đang chờ',
    analyzing: 'Đang phân tích',
    researching: 'Đang nghiên cứu',
    ready_for_review: 'Chờ duyệt',
    needs_review: 'Cần xử lý nguồn',
    approved: 'Đã duyệt nguồn',
    archived: 'Đã lưu trữ',
    partial: 'Hoàn tất một phần',
    completed: 'Hoàn tất',
    cancelled: 'Đã hủy',
    failed: 'Có lỗi',
    candidate: 'Ứng viên',
    accepted: 'Đã chọn',
    promoted: 'Đã đưa vào memory',
    rejected: 'Đã bỏ qua',
    recommended: 'Khuyên chọn',
    alternative: 'Phương án khác',
    blocked: 'Cần chỉnh',
    stale: 'Cần chấm lại',
    complete: 'Đủ dữ liệu',
    incomplete: 'Chưa đủ dữ liệu',
  };
  return labels[status] ?? status;
}

export function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => (typeof item === 'string' ? item : JSON.stringify(item)))
    : [];
}

export function numberValue(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}
