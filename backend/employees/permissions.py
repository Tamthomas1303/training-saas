"""
Port EmployeeService.gs::canTrainPosition (AppsScript Ver 2.0).

Ai duoc DAO TAO vi tri nao:
  - Admin: moi vi tri (gop luon vai tro "Training"/Phong Dao tao cua ban cu -
    he thong nay khong co role rieng cho Phong Dao tao, dung Admin thay the).
  - AM: chi Quan ly nha hang (QLNH)   -  KCS: chi Bep truong
  - BQL: moi vi tri TRU QLNH & Bep truong (gom Giam sat, Bep pho, NV)
  - Trainer: chi nhan vien thuong (khong phai cap quan ly)

Luu y: ban goc con co logic phan vung FOH/BOH cho BQL theo "chuc danh" (job_title) khi
vi tri khong phai QLNH/Bep truong (vd BQL chi duoc dao tao dung khu vuc minh phu trach).
He thong nay chua co du du lieu anh xa chuc danh -> khu vuc day du, nen BQL duoc phep
dao tao moi vi tri (tru QLNH/Bep truong) - dung hanh vi fallback "chua gan chuc danh"
cua ban goc.
"""


def _normalize_key(value):
    return (value or '').strip().lower()


def can_train_position(user, job_position):
    role = (user.role or '').lower()
    p = _normalize_key(job_position)
    is_ql = 'quan ly' in p
    is_bt = 'bep truong' in p
    is_gs = 'giam sat' in p
    is_bp = 'bep pho' in p

    if role == 'admin':
        return True
    if role == 'am':
        return is_ql
    if role == 'kcs':
        return is_bt
    if role == 'bql':
        return not (is_ql or is_bt)
    if role == 'trainer':
        return not (is_ql or is_bt or is_gs or is_bp)
    return False


# Vai tro co quyen danh gia nhan su - port Constants.gs::ROLES_CAN_EVALUATE.
# Ban goc co them "Training" (Phong Dao tao) - gop vao Admin nhu tren.
ROLES_CAN_EVALUATE = {'admin', 'om', 'am', 'kcs', 'bql'}


def can_evaluate(user):
    return (user.role or '').lower() in ROLES_CAN_EVALUATE
