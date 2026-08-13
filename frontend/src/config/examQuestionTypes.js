// Dung chung cho man Ngan hang cau hoi (form dong) va man Lam bai (render theo dang) -
// khop dung 8 dang cua Question.Type (backend exams/models.py).
export const QUESTION_TYPES = [
  { value: 'single', label: 'Chọn 1 đáp án' },
  { value: 'multiple', label: 'Chọn nhiều đáp án' },
  { value: 'truefalse', label: 'Đúng / Sai' },
  { value: 'text_fill', label: 'Điền chữ' },
  { value: 'numeric', label: 'Điền số' },
  { value: 'essay', label: 'Tự luận' },
  { value: 'matching', label: 'Nối cặp' },
  { value: 'dragdrop', label: 'Kéo-thả vào chỗ trống' },
]

export const DIFFICULTIES = [
  { value: 'easy', label: 'Dễ' },
  { value: 'medium', label: 'Trung bình' },
  { value: 'hard', label: 'Khó' },
]

export function typeLabel(type) {
  return QUESTION_TYPES.find((t) => t.value === type)?.label || type
}
