import base64
import re
import uuid
from io import BytesIO

import requests
from django.conf import settings
from PIL import Image

DATA_URL_RE = re.compile(r'^data:(?P<mime>[^;]+);base64,(?P<b64>.+)$', re.DOTALL)

MAX_IMAGE_DIMENSION = 1024
JPEG_QUALITY = 85


class StorageError(Exception):
    pass


def is_data_url(value):
    return bool(value) and value.startswith('data:')


def _backend():
    """Chọn nơi lưu file: 'r2' (mặc định) hoặc 'supabase' (giữ để dự phòng/rollback)."""
    return (getattr(settings, 'STORAGE_BACKEND', 'r2') or 'r2').lower()


def upload_data_url(data_url, folder, filename_prefix):
    """Giải mã data: URL, nén nếu là ảnh, upload lên kho lưu trữ đang chọn, trả về URL public."""
    match = DATA_URL_RE.match(data_url)
    if not match:
        raise StorageError('Dữ liệu ảnh không hợp lệ (cần dạng data:<mime>;base64,...)')

    mime = match.group('mime')
    raw = base64.b64decode(match.group('b64'))

    if mime.startswith('image/'):
        raw, mime = _compress_image(raw)
        ext = 'jpg'
    elif mime == 'application/pdf':
        ext = 'pdf'
    else:
        raise StorageError(f'Định dạng tệp không được hỗ trợ: {mime}')

    path = f'{folder}/{filename_prefix}_{uuid.uuid4().hex}.{ext}'
    return _upload(path, raw, mime)


def upload_pdf_bytes(pdf_bytes, folder, filename_prefix):
    path = f'{folder}/{filename_prefix}_{uuid.uuid4().hex}.pdf'
    return _upload(path, pdf_bytes, 'application/pdf')


def _compress_image(raw_bytes, max_dimension=MAX_IMAGE_DIMENSION, quality=JPEG_QUALITY):
    image = Image.open(BytesIO(raw_bytes))
    if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
        # Anh ky ten thuong la PNG nen trong suot - ghep len nen trang truoc khi luu JPEG
        image = image.convert('RGBA')
        background = Image.new('RGB', image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[-1])
        image = background
    else:
        image = image.convert('RGB')
    image.thumbnail((max_dimension, max_dimension))
    buf = BytesIO()
    image.save(buf, format='JPEG', quality=quality)
    return buf.getvalue(), 'image/jpeg'


# ------------------------- Dispatch -------------------------
def _upload(path, content, content_type):
    if _backend() == 'supabase':
        return _upload_to_supabase(path, content, content_type)
    return _upload_to_r2(path, content, content_type)


# ------------------------- Cloudflare R2 (S3) -------------------------
def _r2_client():
    if not (settings.R2_ACCOUNT_ID and settings.R2_ACCESS_KEY_ID and settings.R2_SECRET_ACCESS_KEY and settings.R2_BUCKET):
        raise StorageError('Chưa cấu hình R2_* trong .env')
    import boto3  # import lazy: chỉ cần khi dùng R2
    from botocore.config import Config
    return boto3.client(
        's3',
        endpoint_url=f'https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name='auto',
        config=Config(signature_version='s3v4'),
    )


def _upload_to_r2(path, content, content_type):
    if not settings.R2_PUBLIC_BASE_URL:
        raise StorageError('Chưa cấu hình R2_PUBLIC_BASE_URL trong .env')
    try:
        _r2_client().put_object(Bucket=settings.R2_BUCKET, Key=path, Body=content, ContentType=content_type)
    except StorageError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise StorageError(f'Upload R2 thất bại: {exc}')
    return f'{settings.R2_PUBLIC_BASE_URL.rstrip("/")}/{path}'


def _delete_from_r2(public_url):
    base = (getattr(settings, 'R2_PUBLIC_BASE_URL', '') or '').rstrip('/')
    if not base or not public_url.startswith(base):
        return False
    key = public_url[len(base) + 1:]
    try:
        _r2_client().delete_object(Bucket=settings.R2_BUCKET, Key=key)
    except Exception:  # noqa: BLE001
        pass
    return True


# ------------------------- Supabase Storage (giữ để dự phòng) -------------------------
def _upload_to_supabase(path, content, content_type):
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        raise StorageError('Chưa cấu hình SUPABASE_URL / SUPABASE_SERVICE_KEY trong .env')
    url = f'{settings.SUPABASE_URL}/storage/v1/object/{settings.SUPABASE_STORAGE_BUCKET}/{path}'
    resp = requests.post(
        url,
        headers={
            'Authorization': f'Bearer {settings.SUPABASE_SERVICE_KEY}',
            'Content-Type': content_type,
        },
        data=content,
        timeout=30,
    )
    if not resp.ok:
        raise StorageError(f'Upload Supabase Storage thất bại ({resp.status_code}): {resp.text}')
    return f'{settings.SUPABASE_URL}/storage/v1/object/public/{settings.SUPABASE_STORAGE_BUCKET}/{path}'


def _delete_from_supabase(public_url):
    if not settings.SUPABASE_URL:
        return False
    marker = f'/storage/v1/object/public/{settings.SUPABASE_STORAGE_BUCKET}/'
    idx = public_url.find(marker)
    if idx == -1:
        return False
    path = public_url[idx + len(marker):]
    url = f'{settings.SUPABASE_URL}/storage/v1/object/{settings.SUPABASE_STORAGE_BUCKET}/{path}'
    try:
        requests.delete(url, headers={'Authorization': f'Bearer {settings.SUPABASE_SERVICE_KEY}'}, timeout=15)
    except requests.RequestException:
        pass
    return True


def delete_by_url(public_url):
    """Xoá 1 file đã upload (tự nhận nguồn R2 hay Supabase theo URL). Bỏ qua lỗi để không gián đoạn
    luồng chính (vd file đã bị xoá từ trước)."""
    if not public_url:
        return
    if _delete_from_r2(public_url):
        return
    _delete_from_supabase(public_url)
