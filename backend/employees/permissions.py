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


# Vai tro "toan he thong" (moi nha hang) - port Constants.gs::ROLES_GLOBAL.
ROLES_GLOBAL = {'admin', 'om', 'bod', 'am'}


def get_restaurant_scope(user):
    """Pham vi nha hang user duoc thao tac. Port AuthService.gs::getScope.

    Admin/OM/BOD/AM: toan he thong. KCS: theo bang UserRestaurantAssignment ("phan vung",
    port DB_AreaAssignment - co the phu trach nhieu nha hang), fallback ve User.restaurant
    neu chua duoc "phan vung" lan nao. BQL/Trainer: dung 1 nha hang gan tren User.restaurant.
    Neu chua gan nha hang nao, coi nhu chua duoc cap quyen o dau ca.
    """
    role = (user.role or '').lower()
    if role in ROLES_GLOBAL:
        return {'all': True, 'restaurant_ids': []}
    if role == 'kcs':
        ids = list(user.restaurant_assignments.values_list('restaurant_id', flat=True))
        if not ids and user.restaurant_id:
            ids = [user.restaurant_id]
        return {'all': False, 'restaurant_ids': ids}
    return {'all': False, 'restaurant_ids': [user.restaurant_id] if user.restaurant_id else []}


def can_access_restaurant(user, restaurant_id):
    scope = get_restaurant_scope(user)
    if scope['all']:
        return True
    return restaurant_id is not None and int(restaurant_id) in scope['restaurant_ids']
