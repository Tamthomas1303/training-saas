import AppShell from '../components/AppShell'
import BackButton from '../components/BackButton'
import ContentCatalog from '../components/ContentCatalog'

export default function TrainingCatalogPage() {
  return (
    <AppShell>
      <BackButton />
      <h2 style={{ margin: 0 }}>Danh mục nội dung đào tạo</h2>
      <p className="muted-note" style={{ marginTop: 4 }}>Thêm/bớt nội dung đào tạo theo thay đổi vận hành. Nạp sẵn từ Ma_Khoa_Hoc; dùng khi tạo chương trình/đợt.</p>
      <ContentCatalog />
    </AppShell>
  )
}
