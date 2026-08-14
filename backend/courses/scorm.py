"""
Nhap goi SCORM (Dot 4/P2, Prompt_Dot4_NhapSCORM.md) - giai nen .zip AN TOAN (chan zip-slip) +
parse imsmanifest.xml (phien ban + file khoi chay + ten) + upload tung file len R2 GIU NGUYEN
cau truc thu muc (de cac tham chieu tuong doi ben trong goi - JS/CSS/anh - van dung), phuc vu
lai qua ScormContentView (same-origin voi trang phat, xem views.py).
"""
import mimetypes
import uuid
import xml.etree.ElementTree as ET
import zipfile

from checklist.storage import StorageError, upload_bytes_at_path

from .models import ScormPackage


class ScormImportError(Exception):
    pass


def _strip_ns(tag):
    return tag.split('}')[-1] if '}' in tag else tag


def _is_safe_member(name):
    """Chan zip-slip: tu choi duong dan tuyet doi hoac co doan '..'. Dung cho MOI entry trong
    zip truoc khi dong den (doc/upload) - xem test_zip_slip_rejected."""
    if not name or name.startswith('/') or name.startswith('\\') or ':' in name:
        return False
    normalized = name.replace('\\', '/')
    return '..' not in normalized.split('/')


def parse_manifest(xml_bytes):
    """Doc imsmanifest.xml -> {version, launch_path, title}. Nem ScormImportError neu khong co
    resource SCO hop le. Phat hien phien ban qua dau hieu namespace/chuoi 'adlcp_v1p3'
    (2004) - khong co thi mac dinh SCORM 1.2 (dau hieu 'adlcp_rootv1p2')."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ScormImportError(f'imsmanifest.xml không đọc được (XML lỗi): {exc}') from exc

    resources = [el for el in root.iter() if _strip_ns(el.tag) == 'resource']
    sco_resource = None
    for el in resources:
        for attr_name, attr_val in el.attrib.items():
            # SCORM 1.2 XSD dung 'scormtype' (thuong), SCORM 2004 XSD dung 'scormType' (hoa T)
            # - so sanh khong phan biet hoa/thuong de khop ca 2.
            if _strip_ns(attr_name).lower() == 'scormtype' and (attr_val or '').strip().lower() == 'sco':
                sco_resource = el
                break
        if sco_resource is not None:
            break
    if sco_resource is None and resources:
        sco_resource = resources[0]  # chi 1 resource, coi nhu do la SCO (goi don gian)
    if sco_resource is None:
        raise ScormImportError('imsmanifest.xml không có <resource> nào (không tìm được SCO)')

    launch_path = sco_resource.attrib.get('href')
    if not launch_path:
        raise ScormImportError('Resource SCO trong imsmanifest.xml thiếu href (file khởi chạy)')

    xml_text = xml_bytes.decode('utf-8', errors='ignore')
    if 'adlcp_v1p3' in xml_text or 'adlcp_v1p4' in xml_text:
        version = ScormPackage.Version.SCORM_2004
    else:
        version = ScormPackage.Version.SCORM_12

    title = ''
    for el in root.iter():
        if _strip_ns(el.tag) == 'title' and (el.text or '').strip():
            title = el.text.strip()
            break

    return {'version': version, 'launch_path': launch_path, 'title': title}


def import_scorm_zip(tenant, lesson, uploaded_by, zip_file):
    """Giai nen zip_file (file upload Django), kiem tra zip-slip cho TAT CA entry, upload len
    R2 duoi 'scorm/<tenant>/<uuid>/', parse manifest, tao/cap nhat ScormPackage cho lesson (1-1
    - upload lai se ghi de goi cu, KHONG xoa file R2 cu - chap nhan duoc o MVP). Nem
    ScormImportError neu file khong hop le (khong phai zip / thieu manifest / duong dan khong
    an toan) - view bat va tra 400."""
    try:
        zf = zipfile.ZipFile(zip_file)
    except zipfile.BadZipFile as exc:
        raise ScormImportError('File không phải .zip hợp lệ') from exc

    names = [n for n in zf.namelist() if not n.endswith('/')]
    for name in names:
        if not _is_safe_member(name):
            raise ScormImportError(f'Gói SCORM có đường dẫn không an toàn: {name}')

    manifest_name = next((n for n in names if n.lower() == 'imsmanifest.xml'), None)
    if manifest_name is None:
        raise ScormImportError('Gói SCORM thiếu imsmanifest.xml ở gốc')

    info = parse_manifest(zf.read(manifest_name))

    storage_prefix = f'scorm/{tenant.id}/{uuid.uuid4().hex}/'
    try:
        for name in names:
            content_type = mimetypes.guess_type(name)[0] or 'application/octet-stream'
            upload_bytes_at_path(f'{storage_prefix}{name}', zf.read(name), content_type)
    except StorageError as exc:
        raise ScormImportError(f'Upload gói SCORM lên kho lưu trữ thất bại: {exc}') from exc

    package, _created = ScormPackage.objects.update_or_create(
        lesson=lesson,
        defaults={
            'tenant': tenant, 'version': info['version'], 'storage_prefix': storage_prefix,
            'launch_path': info['launch_path'], 'title': info['title'], 'uploaded_by': uploaded_by,
        },
    )
    return package
