import io
import zipfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import RequestFactory, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import Tenant, User
from cls_sync.models import CourseResult
from employees.models import Employee
from integration.models import OfflineConfirmation, XapiStatement

from .models import Course, CourseModule, Enrollment, Lesson, LessonProgress, ScormPackage, ScormTracking
from .scorm import ScormImportError, parse_manifest


class CourseAdminApiTests(TestCase):
    """Tao/sua khoa hoc - chi Admin duoc ghi, moi role dang nhap doc duoc."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.trainer = User.objects.create_user(username='trainer1', password='x', tenant=self.tenant, role='trainer')
        self.client = APIClient()

    def test_admin_can_create_course(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('course-list'), {'title': 'An toàn vệ sinh thực phẩm'})
        self.assertEqual(resp.status_code, 201)
        course = Course.objects.get(id=resp.data['id'])
        self.assertEqual(course.tenant_id, self.tenant.id)
        self.assertEqual(course.created_by_id, self.admin.id)
        self.assertEqual(course.status, Course.Status.DRAFT)

    def test_non_admin_cannot_create_course(self):
        self.client.force_authenticate(self.trainer)
        resp = self.client.post(reverse('course-list'), {'title': 'X'})
        self.assertEqual(resp.status_code, 403)

    def test_non_admin_can_read_courses(self):
        Course.objects.create(tenant=self.tenant, title='Khóa demo')
        self.client.force_authenticate(self.trainer)
        resp = self.client.get(reverse('course-list'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    def test_other_tenant_course_not_visible(self):
        other_tenant = Tenant.objects.create(name='Other Tenant')
        Course.objects.create(tenant=other_tenant, title='Khóa tenant khác')
        self.client.force_authenticate(self.admin)
        resp = self.client.get(reverse('course-list'))
        self.assertEqual(resp.data['count'], 0)


class ReorderApiTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.course = Course.objects.create(tenant=self.tenant, title='Khóa demo')
        self.m1 = CourseModule.objects.create(tenant=self.tenant, course=self.course, title='Chương 1', order=0)
        self.m2 = CourseModule.objects.create(tenant=self.tenant, course=self.course, title='Chương 2', order=1)
        self.client = APIClient()

    def test_reorder_modules(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('course-reorder'), {
            'model': 'module',
            'items': [{'id': self.m1.id, 'order': 1}, {'id': self.m2.id, 'order': 0}],
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.m1.refresh_from_db()
        self.m2.refresh_from_db()
        self.assertEqual(self.m1.order, 1)
        self.assertEqual(self.m2.order, 0)

    def test_reorder_requires_admin(self):
        trainer = User.objects.create_user(username='trainer1', password='x', tenant=self.tenant, role='trainer')
        self.client.force_authenticate(trainer)
        resp = self.client.post(reverse('course-reorder'), {
            'model': 'module', 'items': [{'id': self.m1.id, 'order': 1}],
        }, format='json')
        self.assertEqual(resp.status_code, 403)


class CourseAssignApiTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.course = Course.objects.create(tenant=self.tenant, title='Khóa demo')
        self.e1 = Employee.objects.create(tenant=self.tenant, code='NV1', name='NV1', position='Phục vụ')
        self.e2 = Employee.objects.create(tenant=self.tenant, code='NV2', name='NV2', position='Thu ngân')
        self.client = APIClient()

    def test_assign_by_employee_ids(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            reverse('course-assign', args=[self.course.id]), {'employee_ids': [self.e1.id, self.e2.id]},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['created'], 2)
        self.assertEqual(Enrollment.objects.filter(course=self.course).count(), 2)

    def test_assign_skips_already_enrolled(self):
        Enrollment.objects.create(tenant=self.tenant, course=self.course, employee=self.e1)
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            reverse('course-assign', args=[self.course.id]), {'employee_ids': [self.e1.id, self.e2.id]},
            format='json',
        )
        self.assertEqual(resp.data['created'], 1)
        self.assertEqual(Enrollment.objects.filter(course=self.course).count(), 2)

    def test_assign_by_position_filter(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            reverse('course-assign', args=[self.course.id]), {'position': 'Phục vụ'}, format='json',
        )
        self.assertEqual(resp.data['created'], 1)
        self.assertTrue(Enrollment.objects.filter(course=self.course, employee=self.e1).exists())
        self.assertFalse(Enrollment.objects.filter(course=self.course, employee=self.e2).exists())

    def test_assign_requires_admin(self):
        trainer = User.objects.create_user(username='trainer1', password='x', tenant=self.tenant, role='trainer')
        self.client.force_authenticate(trainer)
        resp = self.client.post(
            reverse('course-assign', args=[self.course.id]), {'employee_ids': [self.e1.id]}, format='json',
        )
        self.assertEqual(resp.status_code, 403)


class LearnerFlowApiTests(TestCase):
    """Smoke test cuoi bai: tao 1 khoa 1 chuong 2 bai -> gan 1 nhan su -> hoc -> danh dau hoan
    thanh -> khoa hien 100% (dung nghiem thu muc 4 cua prompt)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.course = Course.objects.create(tenant=self.tenant, title='Khóa demo', status=Course.Status.PUBLISHED)
        self.module = CourseModule.objects.create(tenant=self.tenant, course=self.course, title='Chương 1', order=0)
        self.lesson1 = Lesson.objects.create(
            tenant=self.tenant, module=self.module, title='Bài 1', type=Lesson.Type.TEXT,
            complete_rule=Lesson.CompleteRule.MARK, order=0,
        )
        self.lesson2 = Lesson.objects.create(
            tenant=self.tenant, module=self.module, title='Bài 2', type=Lesson.Type.VIDEO_YOUTUBE,
            complete_rule=Lesson.CompleteRule.WATCH_PCT, pass_watch_pct=80, order=1,
        )

        self.learner_user = User.objects.create_user(
            username='nv1', password='x', tenant=self.tenant, role=User.Role.EMPLOYEE,
        )
        self.employee = Employee.objects.create(
            tenant=self.tenant, code='NV1', name='NV1', user=self.learner_user,
        )
        Enrollment.objects.create(tenant=self.tenant, course=self.course, employee=self.employee)

        self.client = APIClient()

    def test_my_courses_lists_enrollment_with_zero_progress(self):
        self.client.force_authenticate(self.learner_user)
        resp = self.client.get(reverse('course-my'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['course_id'], self.course.id)
        self.assertEqual(resp.data[0]['progress_percent'], 0)
        self.assertEqual(resp.data[0]['status'], Enrollment.Status.ASSIGNED)

    def test_my_course_detail_returns_module_tree(self):
        self.client.force_authenticate(self.learner_user)
        resp = self.client.get(reverse('course-my-detail', args=[self.course.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['modules']), 1)
        self.assertEqual(len(resp.data['modules'][0]['lessons']), 2)

    def test_my_course_detail_404_when_not_enrolled(self):
        other_course = Course.objects.create(tenant=self.tenant, title='Khóa khác')
        self.client.force_authenticate(self.learner_user)
        resp = self.client.get(reverse('course-my-detail', args=[other_course.id]))
        self.assertEqual(resp.status_code, 404)

    def test_mark_done_progresses_enrollment_to_in_progress(self):
        self.client.force_authenticate(self.learner_user)
        resp = self.client.post(reverse('course-progress'), {'lesson': self.lesson1.id, 'mark_done': True}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], LessonProgress.Status.DONE)

        enrollment = Enrollment.objects.get(course=self.course, employee=self.employee)
        self.assertEqual(enrollment.status, Enrollment.Status.IN_PROGRESS)

    def test_watch_pct_below_threshold_stays_in_progress(self):
        self.client.force_authenticate(self.learner_user)
        resp = self.client.post(
            reverse('course-progress'), {'lesson': self.lesson2.id, 'watched_pct': 50}, format='json',
        )
        self.assertEqual(resp.data['status'], LessonProgress.Status.IN_PROGRESS)

    def test_watch_pct_meets_threshold_marks_done(self):
        self.client.force_authenticate(self.learner_user)
        resp = self.client.post(
            reverse('course-progress'), {'lesson': self.lesson2.id, 'watched_pct': 85}, format='json',
        )
        self.assertEqual(resp.data['status'], LessonProgress.Status.DONE)

    def test_completing_all_lessons_marks_enrollment_completed_and_course_100_percent(self):
        self.client.force_authenticate(self.learner_user)
        self.client.post(reverse('course-progress'), {'lesson': self.lesson1.id, 'mark_done': True}, format='json')
        self.client.post(reverse('course-progress'), {'lesson': self.lesson2.id, 'watched_pct': 100}, format='json')

        enrollment = Enrollment.objects.get(course=self.course, employee=self.employee)
        self.assertEqual(enrollment.status, Enrollment.Status.COMPLETED)

        resp = self.client.get(reverse('course-my'))
        self.assertEqual(resp.data[0]['progress_percent'], 100)
        self.assertEqual(resp.data[0]['status'], Enrollment.Status.COMPLETED)

    def test_progress_rejects_lesson_not_in_own_enrollment(self):
        other_employee = Employee.objects.create(tenant=self.tenant, code='NV2', name='NV2')
        other_user = User.objects.create_user(
            username='nv2', password='x', tenant=self.tenant, role=User.Role.EMPLOYEE,
        )
        other_employee.user = other_user
        other_employee.save(update_fields=['user'])
        self.client.force_authenticate(other_user)
        resp = self.client.post(reverse('course-progress'), {'lesson': self.lesson1.id, 'mark_done': True}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_account_without_employee_link_gets_403(self):
        staff_only = User.objects.create_user(
            username='staffonly', password='x', tenant=self.tenant, role=User.Role.EMPLOYEE,
        )
        self.client.force_authenticate(staff_only)
        resp = self.client.get(reverse('course-my'))
        self.assertEqual(resp.status_code, 403)


class EmployeeLearnerScopeApiTests(TestCase):
    """role='employee' chi duoc goi /api/courses/ (+ /api/auth/me) - khong doc duoc du lieu
    quan tri noi bo qua app khac (vd danh sach nhan su)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.learner_user = User.objects.create_user(
            username='nv1', password='x', tenant=self.tenant, role=User.Role.EMPLOYEE,
        )
        self.client = APIClient()

    def test_employee_role_blocked_from_employees_endpoint(self):
        self.client.force_authenticate(self.learner_user)
        resp = self.client.get(reverse('employee-list'))
        self.assertEqual(resp.status_code, 403)

    def test_employee_role_can_call_courses_endpoint(self):
        self.client.force_authenticate(self.learner_user)
        resp = self.client.get(reverse('course-my'))
        # 403 vi chua lien ket Employee, nhung KHONG bi EmployeeLearnerScope chan truoc do
        # (neu bi chan se cung la 403 nhung tu permission khac - kiem tra qua detail message).
        self.assertEqual(resp.status_code, 403)
        self.assertIn('hồ sơ nhân sự', resp.data['detail'])

    def test_staff_roles_unaffected(self):
        admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.client.force_authenticate(admin)
        resp = self.client.get(reverse('employee-list'))
        self.assertEqual(resp.status_code, 200)


class EmployeeCreateLoginApiTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.employee = Employee.objects.create(tenant=self.tenant, code='AM001', name='Nguyễn Văn A')
        self.client = APIClient()

    def test_admin_creates_login_for_employee(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('employee-create-login', args=[self.employee.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['username'], 'am001')
        self.assertTrue(resp.data['password'])

        self.employee.refresh_from_db()
        self.assertIsNotNone(self.employee.user)
        self.assertEqual(self.employee.user.role, User.Role.EMPLOYEE)
        self.assertEqual(self.employee.user.tenant_id, self.tenant.id)

    def test_cannot_create_login_twice(self):
        self.client.force_authenticate(self.admin)
        self.client.post(reverse('employee-create-login', args=[self.employee.id]))
        resp = self.client.post(reverse('employee-create-login', args=[self.employee.id]))
        self.assertEqual(resp.status_code, 400)

    def test_username_collision_gets_suffix(self):
        User.objects.create_user(username='am001', password='x', tenant=self.tenant, role='trainer')
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('employee-create-login', args=[self.employee.id]))
        self.assertEqual(resp.data['username'], 'am0012')

    def test_non_admin_cannot_create_login(self):
        trainer = User.objects.create_user(username='trainer1', password='x', tenant=self.tenant, role='trainer')
        self.client.force_authenticate(trainer)
        resp = self.client.post(reverse('employee-create-login', args=[self.employee.id]))
        self.assertEqual(resp.status_code, 403)


class OfflineConfirmApiTests(TestCase):
    """Dot 3 phan B: xac nhan hoan thanh HO (khong qua player) - moi vai tro dao tao duoc,
    hoc vien (role=employee) khong duoc; ghi audit OfflineConfirmation day du."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.trainer = User.objects.create_user(username='trainer1', password='x', tenant=self.tenant, role='trainer')
        self.course = Course.objects.create(tenant=self.tenant, title='Khóa demo', sync_course_code='HOINHAP_X')
        self.module = CourseModule.objects.create(tenant=self.tenant, course=self.course, title='Chương 1')
        self.lesson1 = Lesson.objects.create(tenant=self.tenant, module=self.module, title='Bài 1', order=0)
        self.lesson2 = Lesson.objects.create(tenant=self.tenant, module=self.module, title='Bài 2', order=1)
        self.employee = Employee.objects.create(tenant=self.tenant, code='NV1', name='NV1')
        self.client = APIClient()

    def test_trainer_confirms_single_lesson_offline(self):
        self.client.force_authenticate(self.trainer)
        resp = self.client.post(reverse('course-offline-confirm'), {
            'employee': self.employee.id, 'target_type': 'lesson', 'target_id': self.lesson1.id,
            'method': 'kem_tai_cho', 'note': 'Kèm tại chỗ ca sáng',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        enrollment = Enrollment.objects.get(course=self.course, employee=self.employee)
        progress = LessonProgress.objects.get(enrollment=enrollment, lesson=self.lesson1)
        self.assertEqual(progress.status, LessonProgress.Status.DONE)
        self.assertTrue(progress.completed_offline)

        confirmation = OfflineConfirmation.objects.get(employee=self.employee, target_id=self.lesson1.id)
        self.assertEqual(confirmation.confirmed_by, self.trainer)
        self.assertEqual(confirmation.method, 'kem_tai_cho')
        self.assertEqual(confirmation.note, 'Kèm tại chỗ ca sáng')
        self.assertIsNotNone(confirmation.confirmed_at)

    def test_confirm_whole_course_marks_all_lessons_and_completes_enrollment(self):
        self.client.force_authenticate(self.trainer)
        resp = self.client.post(reverse('course-offline-confirm'), {
            'employee': self.employee.id, 'target_type': 'course', 'target_id': self.course.id,
            'method': 'checklist_giay',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], Enrollment.Status.COMPLETED)

        enrollment = Enrollment.objects.get(course=self.course, employee=self.employee)
        self.assertEqual(enrollment.progresses.filter(completed_offline=True).count(), 2)
        self.assertEqual(OfflineConfirmation.objects.filter(employee=self.employee).count(), 2)

        # Dot 3 phan A: hoan thanh (du la offline) van chay dong bo ho so vi da gan sync_course_code.
        result = CourseResult.objects.get(employee=self.employee, course_name='HOINHAP_X')
        self.assertEqual(result.status, 'Đạt')

    def test_employee_role_cannot_confirm_offline(self):
        learner_user = User.objects.create_user(
            username='nv1', password='x', tenant=self.tenant, role=User.Role.EMPLOYEE,
        )
        self.client.force_authenticate(learner_user)
        resp = self.client.post(reverse('course-offline-confirm'), {
            'employee': self.employee.id, 'target_type': 'lesson', 'target_id': self.lesson1.id,
        }, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_offline_report_counts_online_vs_offline(self):
        enrollment = Enrollment.objects.create(tenant=self.tenant, course=self.course, employee=self.employee)
        LessonProgress.objects.create(
            tenant=self.tenant, enrollment=enrollment, lesson=self.lesson1,
            status=LessonProgress.Status.DONE, completed_offline=False,
        )
        LessonProgress.objects.create(
            tenant=self.tenant, enrollment=enrollment, lesson=self.lesson2,
            status=LessonProgress.Status.DONE, completed_offline=True,
        )
        admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.client.force_authenticate(admin)
        resp = self.client.get(reverse('course-offline-report', args=[self.course.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, {'total_done': 2, 'offline': 1, 'online': 1, 'offline_percent': 50})


class XapiHookTests(TestCase):
    """Dot 3 phan C: cac moc hoc (xem/hoan thanh bai, hoan thanh khoa) phai sinh XapiStatement
    dung verb/object."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.course = Course.objects.create(tenant=self.tenant, title='Khóa demo', status=Course.Status.PUBLISHED)
        self.module = CourseModule.objects.create(tenant=self.tenant, course=self.course, title='Chương 1')
        self.lesson = Lesson.objects.create(
            tenant=self.tenant, module=self.module, title='Bài 1', complete_rule=Lesson.CompleteRule.MARK,
        )
        self.learner_user = User.objects.create_user(
            username='nv1', password='x', tenant=self.tenant, role=User.Role.EMPLOYEE,
        )
        self.employee = Employee.objects.create(tenant=self.tenant, code='NV1', name='NV1', user=self.learner_user)
        Enrollment.objects.create(tenant=self.tenant, course=self.course, employee=self.employee)
        self.client = APIClient()

    def test_first_touch_logs_viewed_then_mark_done_logs_completed(self):
        self.client.force_authenticate(self.learner_user)
        self.client.post(reverse('course-progress'), {'lesson': self.lesson.id, 'watched_pct': 10}, format='json')
        self.assertTrue(
            XapiStatement.objects.filter(
                employee=self.employee, verb='viewed', object_type='lesson', object_id=self.lesson.id,
            ).exists()
        )

        self.client.post(reverse('course-progress'), {'lesson': self.lesson.id, 'mark_done': True}, format='json')
        self.assertTrue(
            XapiStatement.objects.filter(
                employee=self.employee, verb='completed', object_type='lesson', object_id=self.lesson.id,
            ).exists()
        )
        self.assertTrue(
            XapiStatement.objects.filter(
                employee=self.employee, verb='completed', object_type='course', object_id=self.course.id,
            ).exists()
        )


# ==================================================================== Dot 4: SCORM

MANIFEST_SCORM_12 = '''<?xml version="1.0" standalone="no" ?>
<manifest identifier="TEST_COURSE" version="1"
    xmlns="http://www.imsglobal.org/xsd/imscp_rootv1p1p2"
    xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2">
  <metadata>
    <schema>ADL SCORM</schema>
    <schemaversion>1.2</schemaversion>
  </metadata>
  <organizations default="ORG1">
    <organization identifier="ORG1">
      <title>Bai kiem tra SCORM</title>
      <item identifier="ITEM1" identifierref="RES1">
        <title>Bai kiem tra SCORM</title>
      </item>
    </organization>
  </organizations>
  <resources>
    <resource identifier="RES1" type="webcontent" adlcp:scormtype="sco" href="index.html">
      <file href="index.html" />
    </resource>
  </resources>
</manifest>
'''

MANIFEST_SCORM_2004 = '''<?xml version="1.0" standalone="no" ?>
<manifest identifier="TEST_COURSE_2004" version="1"
    xmlns="http://www.imsglobal.org/xsd/imscp_v1p1"
    xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_v1p3">
  <metadata>
    <schema>ADL SCORM</schema>
    <schemaversion>2004 3rd Edition</schemaversion>
  </metadata>
  <organizations default="ORG1">
    <organization identifier="ORG1">
      <title>Bai kiem tra SCORM 2004</title>
      <item identifier="ITEM1" identifierref="RES1">
        <title>Bai kiem tra SCORM 2004</title>
      </item>
    </organization>
  </organizations>
  <resources>
    <resource identifier="RES1" type="webcontent" adlcp:scormType="sco" href="story.html">
      <file href="story.html" />
    </resource>
  </resources>
</manifest>
'''

# SCO toi thieu: goi LMSInitialize/LMSSetValue('cmi.core.lesson_status','completed')/LMSCommit/
# LMSFinish dung y nghiem thu cua prompt Dot 4 (khong chay duoc trong Django test - chi de gioi
# thieu noi dung file, phan cham diem thuc su test qua ScormCommitView voi payload gia lap dung
# hinh dang CommitObject cua scorm-again).
INDEX_HTML_12 = '''<!DOCTYPE html>
<html><body><script>
function findAPI(win) {
  var attempts = 0;
  while (!win.API && win.parent && win.parent != win && attempts < 10) {
    attempts++;
    win = win.parent;
  }
  return win.API;
}
var api = findAPI(window);
if (api) {
  api.LMSInitialize("");
  api.LMSSetValue("cmi.core.lesson_status", "completed");
  api.LMSCommit("");
  api.LMSFinish("");
}
</script></body></html>
'''


def _build_zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    buf.seek(0)
    return buf


def _minimal_scorm12_zip():
    return _build_zip({'imsmanifest.xml': MANIFEST_SCORM_12, 'index.html': INDEX_HTML_12})


class ParseManifestTests(TestCase):
    """Test A (Dot 4): parse imsmanifest.xml dung phien ban + file khoi chay, cho ca 2 bien
    the thuoc tinh scormtype/scormType cua SCORM 1.2 va 2004."""

    def test_parses_scorm_12(self):
        info = parse_manifest(MANIFEST_SCORM_12.encode('utf-8'))
        self.assertEqual(info['version'], ScormPackage.Version.SCORM_12)
        self.assertEqual(info['launch_path'], 'index.html')
        self.assertEqual(info['title'], 'Bai kiem tra SCORM')

    def test_parses_scorm_2004(self):
        info = parse_manifest(MANIFEST_SCORM_2004.encode('utf-8'))
        self.assertEqual(info['version'], ScormPackage.Version.SCORM_2004)
        self.assertEqual(info['launch_path'], 'story.html')

    def test_missing_resource_raises(self):
        bad_xml = b'<manifest><organizations/></manifest>'
        with self.assertRaises(ScormImportError):
            parse_manifest(bad_xml)

    def test_invalid_xml_raises(self):
        with self.assertRaises(ScormImportError):
            parse_manifest(b'not xml at all <<<')


class ScormUploadApiTests(TestCase):
    """Test A (Dot 4): upload goi SCORM - parse dung + zip-slip bi chan - chi Admin."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.course = Course.objects.create(tenant=self.tenant, title='Khóa SCORM', status=Course.Status.PUBLISHED)
        self.module = CourseModule.objects.create(tenant=self.tenant, course=self.course, title='Chương 1')
        self.lesson = Lesson.objects.create(
            tenant=self.tenant, module=self.module, title='Bài SCORM', type=Lesson.Type.SCORM, order=0,
        )
        self.learner_user = User.objects.create_user(
            username='nv1', password='x', tenant=self.tenant, role=User.Role.EMPLOYEE,
        )
        self.client = APIClient()

    @patch('courses.scorm.upload_bytes_at_path', return_value='https://pub-x.r2.dev/scorm/x')
    def test_admin_uploads_scorm_12_package(self, mock_upload):
        self.client.force_authenticate(self.admin)
        zip_file = SimpleUploadedFile('pkg.zip', _minimal_scorm12_zip().getvalue(), content_type='application/zip')
        resp = self.client.post(
            reverse('scorm-upload'), {'lesson': self.lesson.id, 'file': zip_file}, format='multipart',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['version'], 'scorm_12')
        self.assertEqual(resp.data['launch_path'], 'index.html')
        self.assertTrue(ScormPackage.objects.filter(lesson=self.lesson).exists())
        # 2 file trong goi (manifest + index.html) -> upload_bytes_at_path goi 2 lan.
        self.assertEqual(mock_upload.call_count, 2)

    def test_non_admin_cannot_upload(self):
        self.client.force_authenticate(self.learner_user)
        zip_file = SimpleUploadedFile('pkg.zip', _minimal_scorm12_zip().getvalue(), content_type='application/zip')
        resp = self.client.post(
            reverse('scorm-upload'), {'lesson': self.lesson.id, 'file': zip_file}, format='multipart',
        )
        self.assertEqual(resp.status_code, 403)

    def test_missing_file_rejected(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('scorm-upload'), {'lesson': self.lesson.id}, format='multipart')
        self.assertEqual(resp.status_code, 400)

    def test_missing_manifest_rejected(self):
        self.client.force_authenticate(self.admin)
        buf = _build_zip({'index.html': INDEX_HTML_12})
        zip_file = SimpleUploadedFile('pkg.zip', buf.getvalue(), content_type='application/zip')
        resp = self.client.post(
            reverse('scorm-upload'), {'lesson': self.lesson.id, 'file': zip_file}, format='multipart',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('imsmanifest.xml', resp.data['detail'])

    @patch('courses.scorm.upload_bytes_at_path')
    def test_zip_slip_rejected(self, mock_upload):
        """Test bao mat zip-slip (bat buoc theo nghiem thu Dot 4) - duong dan chua '..' phai bi
        loai, KHONG duoc upload bat cu file nao trong goi."""
        self.client.force_authenticate(self.admin)
        buf = _build_zip({
            'imsmanifest.xml': MANIFEST_SCORM_12,
            '../../evil.html': '<html>pwned</html>',
        })
        zip_file = SimpleUploadedFile('pkg.zip', buf.getvalue(), content_type='application/zip')
        resp = self.client.post(
            reverse('scorm-upload'), {'lesson': self.lesson.id, 'file': zip_file}, format='multipart',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('không an toàn', resp.data['detail'])
        mock_upload.assert_not_called()
        self.assertFalse(ScormPackage.objects.filter(lesson=self.lesson).exists())

    def test_bad_zip_file_rejected(self):
        self.client.force_authenticate(self.admin)
        zip_file = SimpleUploadedFile('pkg.zip', b'not a zip', content_type='application/zip')
        resp = self.client.post(
            reverse('scorm-upload'), {'lesson': self.lesson.id, 'file': zip_file}, format='multipart',
        )
        self.assertEqual(resp.status_code, 400)


class ScormRuntimeApiTests(TestCase):
    """Test A/B (Dot 4): resume (state) + commit -> hoan thanh -> tai dung dung luong hien co
    (Enrollment->completed, on_course_completed: dong bo ho so + chung chi)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.course = Course.objects.create(
            tenant=self.tenant, title='Khóa SCORM', status=Course.Status.PUBLISHED,
        )
        self.module = CourseModule.objects.create(tenant=self.tenant, course=self.course, title='Chương 1')
        self.lesson = Lesson.objects.create(
            tenant=self.tenant, module=self.module, title='Bài SCORM', type=Lesson.Type.SCORM, order=0,
        )
        self.learner_user = User.objects.create_user(
            username='nv1', password='x', tenant=self.tenant, role=User.Role.EMPLOYEE,
        )
        self.employee = Employee.objects.create(tenant=self.tenant, code='NV1', name='NV1', user=self.learner_user)
        Enrollment.objects.create(tenant=self.tenant, course=self.course, employee=self.employee)
        self.client = APIClient()

    def _make_package(self, version=ScormPackage.Version.SCORM_12):
        return ScormPackage.objects.create(
            tenant=self.tenant, lesson=self.lesson, version=version,
            storage_prefix=f'scorm/{self.tenant.id}/testpkg/', launch_path='index.html',
            title='Bài SCORM', uploaded_by=self.admin,
        )

    def _start_progress(self):
        self.client.force_authenticate(self.learner_user)
        resp = self.client.post(reverse('course-progress'), {'lesson': self.lesson.id}, format='json')
        self.assertEqual(resp.status_code, 200)
        return resp.data['id']

    def test_state_empty_before_any_commit(self):
        self._make_package()
        progress_id = self._start_progress()
        resp = self.client.get(reverse('scorm-state', args=[progress_id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['cmi_json'], {})

    def test_resume_returns_saved_cmi(self):
        self._make_package()
        progress_id = self._start_progress()
        self.client.post(reverse('scorm-commit', args=[progress_id]), {
            'completionStatus': 'incomplete',
            'runtimeData': {'cmi': {'core': {'lesson_location': 'page3'}}},
        }, format='json')

        resp = self.client.get(reverse('scorm-state', args=[progress_id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['cmi_json'], {'cmi': {'core': {'lesson_location': 'page3'}}})
        self.assertEqual(resp.data['lesson_status'], 'incomplete')

        progress = LessonProgress.objects.get(pk=progress_id)
        self.assertEqual(progress.status, LessonProgress.Status.IN_PROGRESS)  # chua hoan thanh

    def test_commit_completed_marks_done_and_completes_course(self):
        self._make_package()
        progress_id = self._start_progress()
        resp = self.client.post(reverse('scorm-commit', args=[progress_id]), {
            'completionStatus': 'completed', 'successStatus': 'unknown',
            'score': {'raw': 80, 'min': 0, 'max': 100},
            'runtimeData': {'cmi': {'core': {'lesson_status': 'completed'}}},
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        progress = LessonProgress.objects.get(pk=progress_id)
        self.assertEqual(progress.status, LessonProgress.Status.DONE)
        self.assertIsNotNone(progress.completed_at)

        tracking = ScormTracking.objects.get(lesson_progress=progress)
        self.assertEqual(tracking.lesson_status, 'completed')
        self.assertEqual(float(tracking.score_raw), 80.0)

        # Chi 1 bai trong khoa -> hoan thanh bai nay = hoan thanh ca khoa (tai dung
        # _advance_enrollment_status co san, khong viet lai).
        enrollment = Enrollment.objects.get(course=self.course, employee=self.employee)
        self.assertEqual(enrollment.status, Enrollment.Status.COMPLETED)

    def test_commit_passed_success_status_also_completes(self):
        """SCORM 2004: successStatus='passed' cung phai duoc coi la hoan thanh, du
        completionStatus chua phai 'completed' (dung mapping cua prompt)."""
        self._make_package(version=ScormPackage.Version.SCORM_2004)
        progress_id = self._start_progress()
        self.client.post(reverse('scorm-commit', args=[progress_id]), {
            'completionStatus': 'incomplete', 'successStatus': 'passed',
            'score': {'scaled': 0.9}, 'runtimeData': {},
        }, format='json')
        progress = LessonProgress.objects.get(pk=progress_id)
        self.assertEqual(progress.status, LessonProgress.Status.DONE)

    @patch('integration.services.upload_pdf_bytes', return_value='https://pub-x.r2.dev/certificates/x.pdf')
    def test_commit_completed_triggers_course_completion_hook_and_certificate(self, _mock_upload_pdf):
        """Dot 4 nghiem thu: 'neu la bai cuoi thi Enrollment=completed va hook chay (chung chi
        khoa duoc cap)' - xac nhan CourseResult dong bo (Dot 3 phan A) + CertificateIssued
        duoc tao (Dot 3 phan D), TAT CA qua dung on_course_completed co san, khong viet lai."""
        from cls_sync.models import CourseResult
        from integration.models import CertificateIssued, CertificateTemplate

        self.course.sync_course_code = 'SCORM_TEST_COURSE'
        self.course.save()
        CertificateTemplate.objects.create(tenant=self.tenant, type='hoc', name='Mẫu', active=True)

        self._make_package()
        progress_id = self._start_progress()
        self.client.post(reverse('scorm-commit', args=[progress_id]), {
            'completionStatus': 'completed', 'score': {'raw': 100}, 'runtimeData': {},
        }, format='json')

        self.assertTrue(
            CourseResult.objects.filter(
                employee=self.employee, course_name='SCORM_TEST_COURSE', status='Đạt', source='internal_lms',
            ).exists()
        )
        self.assertTrue(CertificateIssued.objects.filter(employee=self.employee, ref_type='course').exists())

    def test_cannot_access_other_employee_progress(self):
        self._make_package()
        progress_id = self._start_progress()

        other_user = User.objects.create_user(
            username='nv2', password='x', tenant=self.tenant, role=User.Role.EMPLOYEE,
        )
        Employee.objects.create(tenant=self.tenant, code='NV2', name='NV2', user=other_user)

        self.client.force_authenticate(other_user)
        state_resp = self.client.get(reverse('scorm-state', args=[progress_id]))
        self.assertEqual(state_resp.status_code, 404)
        commit_resp = self.client.post(
            reverse('scorm-commit', args=[progress_id]), {'completionStatus': 'completed'}, format='json',
        )
        self.assertEqual(commit_resp.status_code, 404)


class ScormSameOriginApiTests(TestCase):
    """Test C (Dot 4): trang phat + noi dung SCORM khong duoc gan X-Frame-Options (nguoc lai
    se bi trinh duyet chan khi React nhung vao iframe - day la yeu cau 'same-origin' cot loi
    cua tinh nang) + phong ho zip-slip lan 2 o tang serve noi dung."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.course = Course.objects.create(tenant=self.tenant, title='Khóa SCORM')
        self.module = CourseModule.objects.create(tenant=self.tenant, course=self.course, title='Chương 1')
        self.lesson = Lesson.objects.create(
            tenant=self.tenant, module=self.module, title='Bài SCORM', type=Lesson.Type.SCORM, order=0,
        )
        self.learner_user = User.objects.create_user(
            username='nv1', password='x', tenant=self.tenant, role=User.Role.EMPLOYEE,
        )
        self.employee = Employee.objects.create(tenant=self.tenant, code='NV1', name='NV1', user=self.learner_user)
        Enrollment.objects.create(tenant=self.tenant, course=self.course, employee=self.employee)
        self.package = ScormPackage.objects.create(
            tenant=self.tenant, lesson=self.lesson, version=ScormPackage.Version.SCORM_12,
            storage_prefix=f'scorm/{self.tenant.id}/testpkg/', launch_path='index.html',
            title='Bài SCORM', uploaded_by=self.admin,
        )
        self.client = APIClient()

    def test_player_view_has_no_x_frame_options_header(self):
        self.client.force_authenticate(self.learner_user)
        progress_resp = self.client.post(reverse('course-progress'), {'lesson': self.lesson.id}, format='json')
        resp = self.client.get(reverse('scorm-player', args=[self.package.id]), {'progress': progress_resp.data['id']})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('X-Frame-Options', resp)
        self.assertIn(b'Scorm12API', resp.content)
        self.assertEqual(resp['Content-Type'].split(';')[0], 'text/html')

    def test_player_requires_progress_param(self):
        resp = self.client.get(reverse('scorm-player', args=[self.package.id]))
        self.assertEqual(resp.status_code, 400)

    @patch('courses.views.requests.get')
    def test_content_view_streams_file_without_x_frame_options(self, mock_get):
        mock_resp = mock_get.return_value
        mock_resp.status_code = 200
        mock_resp.content = b'<html>hello</html>'
        mock_resp.headers = {'Content-Type': 'text/html'}

        resp = self.client.get(reverse('scorm-content', args=[self.package.id, 'index.html']))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('X-Frame-Options', resp)
        self.assertEqual(resp.content, b'<html>hello</html>')

    def test_content_view_rejects_dotdot_path(self):
        """Phong ho zip-slip lan 2 o tang SERVE (ngoai lan chan luc UPLOAD) - path chua '..'
        khong duoc doc tu R2 du storage_prefix hop le."""
        from courses.views import scorm_content

        factory = RequestFactory()
        request = factory.get(f'/api/courses/scorm/{self.package.id}/content/../secret.txt')
        with self.assertRaises(Http404):
            scorm_content(request, self.package.id, '../secret.txt')
