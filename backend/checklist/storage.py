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


def upload_data_url(data_url, folder, filename_prefix):
    """Giải mã data: URL, nén nếu là ảnh, upload lên Supabase Storage, trả về URL public."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        raise StorageError('Chưa cấu hình SUPABASE_URL / SUPABASE_SERVICE_KEY trong .env')

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
    return _upload_to_supabase(path, raw, mime)


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


def _upload_to_supabase(path, content, content_type):
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


def upload_pdf_bytes(pdf_bytes, folder, filename_prefix):
    path = f'{folder}/{filename_prefix}_{uuid.uuid4().hex}.pdf'
    return _upload_to_supabase(path, pdf_bytes, 'application/pdf')


def delete_by_url(public_url):
    """Xoa 1 file da upload qua public URL (tra ve tu upload_data_url/upload_pdf_bytes).
    Dung khi "xuat lai" 1 phieu - xoa ban cu truoc khi thay bang URL moi. Bo qua loi (khong
    lam gian doan luong chinh neu xoa that bai, vd file da bi xoa tu truoc)."""
    if not public_url or not settings.SUPABASE_URL:
        return
    marker = f'/storage/v1/object/public/{settings.SUPABASE_STORAGE_BUCKET}/'
    idx = public_url.find(marker)
    if idx == -1:
        return
    path = public_url[idx + len(marker):]
    url = f'{settings.SUPABASE_URL}/storage/v1/object/{settings.SUPABASE_STORAGE_BUCKET}/{path}'
    try:
        requests.delete(url, headers={'Authorization': f'Bearer {settings.SUPABASE_SERVICE_KEY}'}, timeout=15)
    except requests.RequestException:
        pass
