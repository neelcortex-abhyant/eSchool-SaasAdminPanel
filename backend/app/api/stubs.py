"""Auto-generated contract stubs for Phases 5–7.

Each stub returns a Laravel-shaped error envelope marking the route as not yet ported.
Do not canary these paths until implementation + golden fixtures pass.
Regenerate: python3 contract-tests/scripts/generate_stubs.py (embedded in Phase execution).
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.responses import fail

router = APIRouter()


def _stub(request: Request):
    return fail(
        f"Route not yet ported: {request.method} {request.url.path}",
        code=501,
        details="contract-stub",
    )

@router.post('/certificate/assign')
async def stub_post_api_certificate_assign(request: Request):
    return _stub(request)

@router.post('/certificate/generate')
async def stub_post_api_certificate_generate(request: Request):
    return _stub(request)

@router.post('/class-section/teachers')
async def stub_post_api_class_section_teachers(request: Request):
    return _stub(request)

@router.post('/create-transportation-expense')
async def stub_post_api_create_transportation_expense(request: Request):
    return _stub(request)

@router.get('/driver-helpr/dashboard')
async def stub_get_api_driver_helpr_dashboard(request: Request):
    return _stub(request)

@router.get('/driver-helpr/get-trips')
async def stub_get_api_driver_helpr_get_trips(request: Request):
    return _stub(request)

@router.get('/driver-helpr/get-vehicle-details')
async def stub_get_api_driver_helpr_get_vehicle_details(request: Request):
    return _stub(request)

@router.post('/driver-helpr/trip/start-end')
async def stub_post_api_driver_helpr_trip_start_end(request: Request):
    return _stub(request)

@router.get('/get-image')
async def stub_get_api_get_image(request: Request):
    return _stub(request)

@router.get('/get-transportation-expense')
async def stub_get_api_get_transportation_expense(request: Request):
    return _stub(request)

@router.post('/get-vehicle-assignment-status')
async def stub_post_api_get_vehicle_assignment_status(request: Request):
    return _stub(request)

@router.get('/leave-settings')
async def stub_get_api_leave_settings(request: Request):
    return _stub(request)

@router.get('/message')
async def stub_get_api_message(request: Request):
    return _stub(request)

@router.post('/message')
async def stub_post_api_message(request: Request):
    return _stub(request)

@router.get('/parent/assignments')
async def stub_get_api_parent_assignments(request: Request):
    return _stub(request)

@router.get('/parent/diary-categories')
async def stub_get_api_parent_diary_categories(request: Request):
    return _stub(request)

@router.get('/parent/exam-marks')
async def stub_get_api_parent_exam_marks(request: Request):
    return _stub(request)

@router.get('/parent/fees')
async def stub_get_api_parent_fees(request: Request):
    return _stub(request)

@router.post('/parent/fees/compulsory/pay')
async def stub_post_api_parent_fees_compulsory_pay(request: Request):
    return _stub(request)

@router.get('/parent/fees/fees-transactions')
async def stub_get_api_parent_fees_fees_transactions(request: Request):
    return _stub(request)

@router.post('/parent/fees/manual/compulsory/pay')
async def stub_post_api_parent_fees_manual_compulsory_pay(request: Request):
    return _stub(request)

@router.post('/parent/fees/manual/optional/pay')
async def stub_post_api_parent_fees_manual_optional_pay(request: Request):
    return _stub(request)

@router.post('/parent/fees/optional/pay')
async def stub_post_api_parent_fees_optional_pay(request: Request):
    return _stub(request)

@router.get('/parent/fees/receipt')
async def stub_get_api_parent_fees_receipt(request: Request):
    return _stub(request)

@router.get('/parent/fees/transaction-receipt')
async def stub_get_api_parent_fees_transaction_receipt(request: Request):
    return _stub(request)

@router.get('/parent/get-assignments-report')
async def stub_get_api_parent_get_assignments_report(request: Request):
    return _stub(request)

@router.get('/parent/get-child-profile-data')
async def stub_get_api_parent_get_child_profile_data(request: Request):
    return _stub(request)

@router.get('/parent/get-exam-details')
async def stub_get_api_parent_get_exam_details(request: Request):
    return _stub(request)

@router.get('/parent/get-online-exam-list')
async def stub_get_api_parent_get_online_exam_list(request: Request):
    return _stub(request)

@router.get('/parent/get-online-exam-report')
async def stub_get_api_parent_get_online_exam_report(request: Request):
    return _stub(request)

@router.get('/parent/get-online-exam-result')
async def stub_get_api_parent_get_online_exam_result(request: Request):
    return _stub(request)

@router.get('/parent/get-online-exam-result-list')
async def stub_get_api_parent_get_online_exam_result_list(request: Request):
    return _stub(request)

@router.get('/parent/lesson-topics')
async def stub_get_api_parent_lesson_topics(request: Request):
    return _stub(request)

@router.get('/parent/lessons')
async def stub_get_api_parent_lessons(request: Request):
    return _stub(request)

@router.get('/parent/sliders')
async def stub_get_api_parent_sliders(request: Request):
    return _stub(request)

@router.get('/parent/student/leave')
async def stub_get_api_parent_student_leave(request: Request):
    return _stub(request)

@router.post('/parent/student/leave')
async def stub_post_api_parent_student_leave(request: Request):
    return _stub(request)

@router.post('/parent/student/leave/cancel')
async def stub_post_api_parent_student_leave_cancel(request: Request):
    return _stub(request)

@router.get('/parent/timetable')
async def stub_get_api_parent_timetable(request: Request):
    return _stub(request)

@router.get('/payment-confirmation')
async def stub_get_api_payment_confirmation(request: Request):
    return _stub(request)

@router.get('/payment-transactions')
async def stub_get_api_payment_transactions(request: Request):
    return _stub(request)

@router.get('/semester')
async def stub_get_api_semester(request: Request):
    return _stub(request)

@router.get('/staff-leaves-details')
async def stub_get_api_staff_leaves_details(request: Request):
    return _stub(request)

@router.get('/staff/allowances-deductions')
async def stub_get_api_staff_allowances_deductions(request: Request):
    return _stub(request)

@router.get('/staff/attendance')
async def stub_get_api_staff_attendance(request: Request):
    return _stub(request)

@router.get('/staff/class-timetable')
async def stub_get_api_staff_class_timetable(request: Request):
    return _stub(request)

@router.post('/staff/delete-announcement')
async def stub_post_api_staff_delete_announcement(request: Request):
    return _stub(request)

@router.get('/staff/fees-paid-list')
async def stub_get_api_staff_fees_paid_list(request: Request):
    return _stub(request)

@router.get('/staff/get-announcement')
async def stub_get_api_staff_get_announcement(request: Request):
    return _stub(request)

@router.get('/staff/get-fees')
async def stub_get_api_staff_get_fees(request: Request):
    return _stub(request)

@router.get('/staff/id-card')
async def stub_get_api_staff_id_card(request: Request):
    return _stub(request)

@router.post('/staff/leave-approve')
async def stub_post_api_staff_leave_approve(request: Request):
    return _stub(request)

@router.get('/staff/leave-request')
async def stub_get_api_staff_leave_request(request: Request):
    return _stub(request)

@router.get('/staff/my-payroll')
async def stub_get_api_staff_my_payroll(request: Request):
    return _stub(request)

@router.post('/staff/notification')
async def stub_post_api_staff_notification(request: Request):
    return _stub(request)

@router.post('/staff/notification-delete')
async def stub_post_api_staff_notification_delete(request: Request):
    return _stub(request)

@router.post('/staff/payroll-create')
async def stub_post_api_staff_payroll_create(request: Request):
    return _stub(request)

@router.get('/staff/payroll-slip')
async def stub_get_api_staff_payroll_slip(request: Request):
    return _stub(request)

@router.get('/staff/payroll-staff-list')
async def stub_get_api_staff_payroll_staff_list(request: Request):
    return _stub(request)

@router.get('/staff/payroll-year')
async def stub_get_api_staff_payroll_year(request: Request):
    return _stub(request)

@router.get('/staff/qr-attendance/config')
async def stub_get_api_staff_qr_attendance_config(request: Request):
    return _stub(request)

@router.get('/staff/qr-attendance/my-attendance')
async def stub_get_api_staff_qr_attendance_my_attendance(request: Request):
    return _stub(request)

@router.post('/staff/qr-attendance/punch')
async def stub_post_api_staff_qr_attendance_punch(request: Request):
    return _stub(request)

@router.get('/staff/qr-attendance/punches')
async def stub_get_api_staff_qr_attendance_punches(request: Request):
    return _stub(request)

@router.get('/staff/qr-attendance/today')
async def stub_get_api_staff_qr_attendance_today(request: Request):
    return _stub(request)

@router.get('/staff/roles')
async def stub_get_api_staff_roles(request: Request):
    return _stub(request)

@router.post('/staff/send-announcement')
async def stub_post_api_staff_send_announcement(request: Request):
    return _stub(request)

@router.get('/staff/staff-attendance')
async def stub_get_api_staff_staff_attendance(request: Request):
    return _stub(request)

@router.post('/staff/staff-attendance-store')
async def stub_post_api_staff_staff_attendance_store(request: Request):
    return _stub(request)

@router.get('/staff/staffs')
async def stub_get_api_staff_staffs(request: Request):
    return _stub(request)

@router.get('/staff/student-fees-receipt')
async def stub_get_api_staff_student_fees_receipt(request: Request):
    return _stub(request)

@router.get('/staff/student-leave')
async def stub_get_api_staff_student_leave(request: Request):
    return _stub(request)

@router.post('/staff/student-leave/update-status')
async def stub_post_api_staff_student_leave_update_status(request: Request):
    return _stub(request)

@router.get('/staff/student-offline-exam-result')
async def stub_get_api_staff_student_offline_exam_result(request: Request):
    return _stub(request)

@router.get('/staff/student/attendance')
async def stub_get_api_staff_student_attendance(request: Request):
    return _stub(request)

@router.get('/staff/tasks')
async def stub_get_api_staff_tasks(request: Request):
    return _stub(request)

@router.post('/staff/tasks')
async def stub_post_api_staff_tasks(request: Request):
    return _stub(request)

@router.post('/staff/tasks/delete')
async def stub_post_api_staff_tasks_delete(request: Request):
    return _stub(request)

@router.post('/staff/tasks/status')
async def stub_post_api_staff_tasks_status(request: Request):
    return _stub(request)

@router.post('/staff/tasks/update')
async def stub_post_api_staff_tasks_update(request: Request):
    return _stub(request)

@router.get('/staff/teacher-timetable')
async def stub_get_api_staff_teacher_timetable(request: Request):
    return _stub(request)

@router.post('/staff/update-announcement')
async def stub_post_api_staff_update_announcement(request: Request):
    return _stub(request)

@router.get('/staff/users')
async def stub_get_api_staff_users(request: Request):
    return _stub(request)

@router.get('/staff/users-role-wise')
async def stub_get_api_staff_users_role_wise(request: Request):
    return _stub(request)

@router.get('/student-exan-result-pdf')
async def stub_get_api_student_exan_result_pdf(request: Request):
    return _stub(request)

@router.get('/student/class-subjects')
async def stub_get_api_student_class_subjects(request: Request):
    return _stub(request)

@router.post('/student/delete-assignment-submission')
async def stub_post_api_student_delete_assignment_submission(request: Request):
    return _stub(request)

@router.get('/student/diary-categories')
async def stub_get_api_student_diary_categories(request: Request):
    return _stub(request)

@router.get('/student/exam-marks')
async def stub_get_api_student_exam_marks(request: Request):
    return _stub(request)

@router.post('/student/forgot-password')
async def stub_post_api_student_forgot_password(request: Request):
    return _stub(request)

@router.get('/student/get-assignments-report')
async def stub_get_api_student_get_assignments_report(request: Request):
    return _stub(request)

@router.get('/student/get-exam-details')
async def stub_get_api_student_get_exam_details(request: Request):
    return _stub(request)

@router.get('/student/get-online-exam-list')
async def stub_get_api_student_get_online_exam_list(request: Request):
    return _stub(request)

@router.get('/student/get-online-exam-questions')
async def stub_get_api_student_get_online_exam_questions(request: Request):
    return _stub(request)

@router.get('/student/get-online-exam-report')
async def stub_get_api_student_get_online_exam_report(request: Request):
    return _stub(request)

@router.get('/student/get-online-exam-result')
async def stub_get_api_student_get_online_exam_result(request: Request):
    return _stub(request)

@router.get('/student/get-online-exam-result-list')
async def stub_get_api_student_get_online_exam_result_list(request: Request):
    return _stub(request)

@router.get('/student/id-card')
async def stub_get_api_student_id_card(request: Request):
    return _stub(request)

@router.get('/student/lesson-topics')
async def stub_get_api_student_lesson_topics(request: Request):
    return _stub(request)

@router.get('/student/lessons')
async def stub_get_api_student_lessons(request: Request):
    return _stub(request)

@router.get('/student/report')
async def stub_get_api_student_report(request: Request):
    return _stub(request)

@router.post('/student/select-subjects')
async def stub_post_api_student_select_subjects(request: Request):
    return _stub(request)

@router.get('/student/sliders')
async def stub_get_api_student_sliders(request: Request):
    return _stub(request)

@router.post('/student/submit-assignment')
async def stub_post_api_student_submit_assignment(request: Request):
    return _stub(request)

@router.post('/student/submit-online-exam-answers')
async def stub_post_api_student_submit_online_exam_answers(request: Request):
    return _stub(request)

@router.get('/student/transportation/live-tracking')
async def stub_get_api_student_transportation_live_tracking(request: Request):
    return _stub(request)

@router.get('/student/web-sliders')
async def stub_get_api_student_web_sliders(request: Request):
    return _stub(request)

@router.post('/subscription/webhook/razorpay')
async def stub_post_api_subscription_webhook_razorpay(request: Request):
    return _stub(request)

@router.post('/subscription/webhook/stripe')
async def stub_post_api_subscription_webhook_stripe(request: Request):
    return _stub(request)

@router.get('/system-settings')
async def stub_get_api_system_settings(request: Request):
    return _stub(request)

@router.post('/teacher/class-detail')
async def stub_post_api_teacher_class_detail(request: Request):
    return _stub(request)

@router.post('/teacher/create-assignment')
async def stub_post_api_teacher_create_assignment(request: Request):
    return _stub(request)

@router.post('/teacher/create-diary')
async def stub_post_api_teacher_create_diary(request: Request):
    return _stub(request)

@router.post('/teacher/create-diary-category')
async def stub_post_api_teacher_create_diary_category(request: Request):
    return _stub(request)

@router.post('/teacher/create-lesson')
async def stub_post_api_teacher_create_lesson(request: Request):
    return _stub(request)

@router.post('/teacher/create-topic')
async def stub_post_api_teacher_create_topic(request: Request):
    return _stub(request)

@router.post('/teacher/delete-announcement')
async def stub_post_api_teacher_delete_announcement(request: Request):
    return _stub(request)

@router.post('/teacher/delete-assignment')
async def stub_post_api_teacher_delete_assignment(request: Request):
    return _stub(request)

@router.post('/teacher/delete-diary')
async def stub_post_api_teacher_delete_diary(request: Request):
    return _stub(request)

@router.post('/teacher/delete-diary-category')
async def stub_post_api_teacher_delete_diary_category(request: Request):
    return _stub(request)

@router.post('/teacher/delete-file')
async def stub_post_api_teacher_delete_file(request: Request):
    return _stub(request)

@router.post('/teacher/delete-lesson')
async def stub_post_api_teacher_delete_lesson(request: Request):
    return _stub(request)

@router.post('/teacher/delete-topic')
async def stub_post_api_teacher_delete_topic(request: Request):
    return _stub(request)

@router.get('/teacher/diary-categories')
async def stub_get_api_teacher_diary_categories(request: Request):
    return _stub(request)

@router.get('/teacher/get-announcement')
async def stub_get_api_teacher_get_announcement(request: Request):
    return _stub(request)

@router.get('/teacher/get-assignment')
async def stub_get_api_teacher_get_assignment(request: Request):
    return _stub(request)

@router.get('/teacher/get-assignment-submission')
async def stub_get_api_teacher_get_assignment_submission(request: Request):
    return _stub(request)

@router.get('/teacher/get-attendance')
async def stub_get_api_teacher_get_attendance(request: Request):
    return _stub(request)

@router.get('/teacher/get-exam-list')
async def stub_get_api_teacher_get_exam_list(request: Request):
    return _stub(request)

@router.get('/teacher/get-lesson')
async def stub_get_api_teacher_get_lesson(request: Request):
    return _stub(request)

@router.get('/teacher/get-topic')
async def stub_get_api_teacher_get_topic(request: Request):
    return _stub(request)

@router.post('/teacher/online-classes')
async def stub_post_api_teacher_online_classes(request: Request):
    return _stub(request)

@router.post('/teacher/online-classes/delete')
async def stub_post_api_teacher_online_classes_delete(request: Request):
    return _stub(request)

@router.get('/teacher/online-classes/periods')
async def stub_get_api_teacher_online_classes_periods(request: Request):
    return _stub(request)

@router.get('/teacher/online-classes/subject-classes')
async def stub_get_api_teacher_online_classes_subject_classes(request: Request):
    return _stub(request)

@router.post('/teacher/online-classes/update')
async def stub_post_api_teacher_online_classes_update(request: Request):
    return _stub(request)

@router.post('/teacher/send-announcement')
async def stub_post_api_teacher_send_announcement(request: Request):
    return _stub(request)

@router.get('/teacher/student-list')
async def stub_get_api_teacher_student_list(request: Request):
    return _stub(request)

@router.get('/teacher/subjects')
async def stub_get_api_teacher_subjects(request: Request):
    return _stub(request)

@router.post('/teacher/submit-attendance')
async def stub_post_api_teacher_submit_attendance(request: Request):
    return _stub(request)

@router.post('/teacher/submit-exam-marks/subject')
async def stub_post_api_teacher_submit_exam_marks_subject(request: Request):
    return _stub(request)

@router.get('/teacher/teacher_timetable')
async def stub_get_api_teacher_teacher_timetable(request: Request):
    return _stub(request)

@router.post('/teacher/update-announcement')
async def stub_post_api_teacher_update_announcement(request: Request):
    return _stub(request)

@router.post('/teacher/update-assignment')
async def stub_post_api_teacher_update_assignment(request: Request):
    return _stub(request)

@router.post('/teacher/update-assignment-submission')
async def stub_post_api_teacher_update_assignment_submission(request: Request):
    return _stub(request)

@router.post('/teacher/update-diary-category')
async def stub_post_api_teacher_update_diary_category(request: Request):
    return _stub(request)

@router.post('/teacher/update-file')
async def stub_post_api_teacher_update_file(request: Request):
    return _stub(request)

@router.post('/teacher/update-lesson')
async def stub_post_api_teacher_update_lesson(request: Request):
    return _stub(request)

@router.post('/teacher/update-topic')
async def stub_post_api_teacher_update_topic(request: Request):
    return _stub(request)

@router.get('/teachers')
async def stub_get_api_teachers(request: Request):
    return _stub(request)

@router.post('/transport/attendance/create')
async def stub_post_api_transport_attendance_create(request: Request):
    return _stub(request)

@router.post('/transport/dashboard')
async def stub_post_api_transport_dashboard(request: Request):
    return _stub(request)

@router.get('/transport/expense/categories/list')
async def stub_get_api_transport_expense_categories_list(request: Request):
    return _stub(request)

@router.post('/transport/plans/current')
async def stub_post_api_transport_plans_current(request: Request):
    return _stub(request)

@router.post('/transport/receipt')
async def stub_post_api_transport_receipt(request: Request):
    return _stub(request)

@router.post('/transport/requests')
async def stub_post_api_transport_requests(request: Request):
    return _stub(request)

@router.post('/transport/routes/stops')
async def stub_post_api_transport_routes_stops(request: Request):
    return _stub(request)

@router.post('/transport/store-trip-reports')
async def stub_post_api_transport_store_trip_reports(request: Request):
    return _stub(request)

@router.post('/transport/user/attendance-list')
async def stub_post_api_transport_user_attendance_list(request: Request):
    return _stub(request)

@router.post('/transportation-payments')
async def stub_post_api_transportation_payments(request: Request):
    return _stub(request)

@router.post('/transportation/live-route')
async def stub_post_api_transportation_live_route(request: Request):
    return _stub(request)

@router.post('/transportation/live-tracking/link')
async def stub_post_api_transportation_live_tracking_link(request: Request):
    return _stub(request)

@router.get('/transportation/live-tracking/session')
async def stub_get_api_transportation_live_tracking_session(request: Request):
    return _stub(request)

@router.post('/transportation/trip/location')
async def stub_post_api_transportation_trip_location(request: Request):
    return _stub(request)

@router.post('/update-profile')
async def stub_post_api_update_profile(request: Request):
    return _stub(request)

@router.get('/users')
async def stub_get_api_users(request: Request):
    return _stub(request)

@router.post('/users-by-role')
async def stub_post_api_users_by_role(request: Request):
    return _stub(request)

@router.get('/users/chat/history')
async def stub_get_api_users_chat_history(request: Request):
    return _stub(request)

@router.get('/whatsapp/webhook/{schoolCode}')
async def stub_get_api_whatsapp_webhook__schoolCode_(request: Request):
    return _stub(request)

@router.post('/whatsapp/webhook/{schoolCode}')
async def stub_post_api_whatsapp_webhook__schoolCode_(request: Request):
    return _stub(request)
