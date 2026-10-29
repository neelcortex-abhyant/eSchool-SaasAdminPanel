from pathlib import Path

p = Path("app/api/v1/school_admin.py")
t = p.read_text(encoding="utf-8")
replacements = [
    (
        '@router.patch("/students/{student_id}/status", responses=core_out.json_response(core_out.StatusOut))',
        '@router.patch("/students/{student_id}/status", responses=core_out.json_response(core_out.StudentOut))',
    ),
    (
        '@router.patch("/parents/{parent_id}/status", responses=core_out.json_response(core_out.StatusOut))',
        '@router.patch("/parents/{parent_id}/status", responses=core_out.json_response(core_out.ParentOut))',
    ),
    (
        '@router.patch("/teachers/{teacher_id}/status", responses=core_out.json_response(core_out.StatusOut))',
        '@router.patch("/teachers/{teacher_id}/status", responses=core_out.json_response(core_out.TeacherOut))',
    ),
    (
        '@router.patch("/staff/{staff_id}/status", responses=core_out.json_response(core_out.StatusOut))',
        '@router.patch("/staff/{staff_id}/status", responses=core_out.json_response(core_out.StaffOut))',
    ),
]
for a, b in replacements:
    if a in t:
        t = t.replace(a, b)
        print("fixed", a.split("/status")[0])
    elif b in t:
        print("already", b.split("/status")[0])
    else:
        print("MISSING", a)
p.write_text(t, encoding="utf-8")
print("StatusOut remaining", t.count("StatusOut"))
