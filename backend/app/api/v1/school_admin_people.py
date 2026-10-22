"""School Admin students, parents, teachers and staff (backend/docs/PEOPLE_API_CONTRACT.md).

The older /school-admin/academics/{students,teachers,parents} routes stay in
school_admin_academics.py until the admin build has switched every module.
"""

from __future__ import annotations

from datetime import date as Date
from typing import Annotated, List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, assert_school_permission, require_school_admin
from app.services.v1 import file_storage, rbac
from app.services.v1 import school_people as people
from app.services.v1.records import RecordError

router = APIRouter(prefix="/school-admin", tags=["v1-school-admin-people"])
files_router = APIRouter(prefix="/files", tags=["v1-files"])

Auth = Annotated[AuthContext, Depends(require_school_admin)]
Db = Annotated[Session, Depends(central_db)]
PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=50)]
StatusFilter = Annotated[Optional[str], Query(pattern="^[01]?$")]
RecordStatus = Annotated[int, Field(ge=0, le=1)]


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _blank_to_none(cls, data):
        # Forms send "" for an empty optional field; treat it as missing.
        if isinstance(data, dict):
            return {key: (None if value == "" else value) for key, value in data.items()}
        return data


class GuardianChoice(Body):
    parent_id: Optional[int] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    relationship: Optional[str] = None


class StudentBody(Body):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    dob: Optional[Date] = None
    gender: Optional[str] = None
    admission_no: Optional[str] = None
    admission_date: Optional[Date] = None
    session_year_id: Optional[int] = None
    class_section_id: Optional[int] = None
    roll_number: Optional[int] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    current_address: Optional[str] = None
    permanent_address: Optional[str] = None
    status: RecordStatus = 1


class StudentCreateBody(StudentBody):
    guardian: Optional[GuardianChoice] = None


class StatusBody(Body):
    status: RecordStatus


class GuardianLinkBody(Body):
    parent_id: Optional[int] = None
    relationship: Optional[str] = None
    is_primary: bool = False


class ParentBody(Body):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    current_address: Optional[str] = None
    occupation: Optional[str] = None
    status: RecordStatus = 1


class StudentLink(Body):
    student_id: Optional[int] = None
    relationship: Optional[str] = None


class ParentCreateBody(ParentBody):
    students: List[StudentLink] = []


class EmployeeBody(Body):
    employee_code: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    gender: Optional[str] = None
    dob: Optional[Date] = None
    qualification: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    joining_date: Optional[Date] = None
    employment_type: Optional[str] = None
    current_address: Optional[str] = None
    status: RecordStatus = 1


def _school(auth: AuthContext, db: Session, permission: str) -> int:
    assert_school_permission(auth, db, permission)
    return int(auth.user.school_id)  # type: ignore[arg-type]


def _url_for(request: Request):
    return lambda token: str(request.url_for("download_people_file", token=token))


def _run(action):
    try:
        return action()
    except RecordError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _dump(body: BaseModel) -> dict:
    return body.model_dump()


STUDENTS = rbac.PERM_STUDENTS


# ---------- students ----------


@router.get("/students")
def list_students(
    request: Request,
    auth: Auth,
    db: Db,
    q: str = "",
    status: StatusFilter = None,
    page: PageNo = 1,
    page_size: PageSize = 20,
    session_year_id: Optional[int] = None,
    class_id: Optional[int] = None,
    class_section_id: Optional[int] = None,
    parent_id: Optional[int] = None,
    sort: Optional[str] = None,
    order: Annotated[Optional[str], Query(pattern="^(asc|desc)?$")] = None,
):
    school_id = _school(auth, db, STUDENTS)
    params = {
        "q": q, "status": status, "page": page, "page_size": page_size, "session_year_id": session_year_id,
        "class_id": class_id, "class_section_id": class_section_id, "parent_id": parent_id, "sort": sort, "order": order,
    }
    return _run(lambda: people.list_students(db, school_id, params, _url_for(request)))


@router.get("/students/{student_id}")
def get_student(student_id: int, request: Request, auth: Auth, db: Db):
    school_id = _school(auth, db, STUDENTS)
    return _run(lambda: people.student_profile(db, school_id, student_id, _url_for(request)))


@router.post("/students", status_code=201)
def create_student(body: StudentCreateBody, request: Request, auth: Auth, db: Db):
    school_id = _school(auth, db, STUDENTS)
    return _run(lambda: people.create_student(db, school_id, _dump(body), _url_for(request)))


@router.patch("/students/{student_id}")
def update_student(student_id: int, body: StudentBody, request: Request, auth: Auth, db: Db):
    school_id = _school(auth, db, STUDENTS)
    return _run(lambda: people.update_student(db, school_id, student_id, _dump(body), _url_for(request)))


@router.patch("/students/{student_id}/status")
def set_student_status(student_id: int, body: StatusBody, request: Request, auth: Auth, db: Db):
    school_id = _school(auth, db, STUDENTS)
    return _run(lambda: people.set_student_status(db, school_id, student_id, body.status, _url_for(request)))


@router.post("/students/{student_id}/guardians")
def link_guardian(student_id: int, body: GuardianLinkBody, request: Request, auth: Auth, db: Db):
    school_id = _school(auth, db, STUDENTS)
    return _run(lambda: people.link_guardian(db, school_id, student_id, _dump(body), _url_for(request)))


@router.delete("/students/{student_id}/guardians/{parent_id}")
def unlink_guardian(student_id: int, parent_id: int, request: Request, auth: Auth, db: Db):
    school_id = _school(auth, db, STUDENTS)
    return _run(lambda: people.unlink_guardian(db, school_id, student_id, parent_id, _url_for(request)))


# ---------- parents ----------


@router.get("/parents")
def list_parents(
    auth: Auth,
    db: Db,
    q: str = "",
    status: StatusFilter = None,
    page: PageNo = 1,
    page_size: PageSize = 20,
    email: Optional[str] = None,
    mobile: Optional[str] = None,
):
    school_id = _school(auth, db, STUDENTS)
    params = {"q": q, "status": status, "page": page, "page_size": page_size, "email": email, "mobile": mobile}
    return _run(lambda: people.list_parents(db, school_id, params))


@router.get("/parents/{parent_id}")
def get_parent(parent_id: int, auth: Auth, db: Db):
    school_id = _school(auth, db, STUDENTS)
    return _run(lambda: people.parent_profile(db, school_id, parent_id))


@router.post("/parents", status_code=201)
def create_parent(body: ParentCreateBody, auth: Auth, db: Db):
    school_id = _school(auth, db, STUDENTS)
    return _run(lambda: people.create_parent(db, school_id, _dump(body)))


@router.patch("/parents/{parent_id}")
def update_parent(parent_id: int, body: ParentBody, auth: Auth, db: Db):
    school_id = _school(auth, db, STUDENTS)
    return _run(lambda: people.update_parent(db, school_id, parent_id, _dump(body)))


@router.patch("/parents/{parent_id}/status")
def set_parent_status(parent_id: int, body: StatusBody, auth: Auth, db: Db):
    school_id = _school(auth, db, STUDENTS)
    return _run(lambda: people.set_parent_status(db, school_id, parent_id, body.status))


# ---------- teachers and staff (same handlers, one set of routes per kind) ----------


def _employee_routes(kind: str) -> None:
    permission = rbac.PERM_TEACHERS

    @router.get(f"/{kind}", name=f"list_{kind}")
    def list_employees(
        request: Request,
        auth: Auth,
        db: Db,
        q: str = "",
        status: StatusFilter = None,
        page: PageNo = 1,
        page_size: PageSize = 20,
        department: Optional[str] = None,
        employment_type: Optional[str] = None,
    ):
        school_id = _school(auth, db, permission)
        params = {
            "q": q, "status": status, "page": page, "page_size": page_size,
            "department": department, "employment_type": employment_type,
        }
        return _run(lambda: people.list_employees(db, school_id, kind, params, _url_for(request)))

    # Registered before /{kind}/{user_id} so "departments" is not read as an id.
    @router.get(f"/{kind}/departments", name=f"{kind}_departments")
    def departments(auth: Auth, db: Db):
        school_id = _school(auth, db, permission)
        return _run(lambda: people.list_departments(db, school_id, kind))

    @router.get(f"/{kind}/{{user_id}}", name=f"get_{kind}")
    def get_employee(user_id: int, request: Request, auth: Auth, db: Db):
        school_id = _school(auth, db, permission)
        return _run(lambda: people.employee_profile(db, school_id, kind, user_id, _url_for(request)))

    @router.post(f"/{kind}", status_code=201, name=f"create_{kind}")
    def create_employee(body: EmployeeBody, request: Request, auth: Auth, db: Db):
        school_id = _school(auth, db, permission)
        return _run(lambda: people.create_employee(db, school_id, kind, _dump(body), _url_for(request)))

    @router.patch(f"/{kind}/{{user_id}}", name=f"update_{kind}")
    def update_employee(user_id: int, body: EmployeeBody, request: Request, auth: Auth, db: Db):
        school_id = _school(auth, db, permission)
        return _run(lambda: people.update_employee(db, school_id, kind, user_id, _dump(body), _url_for(request)))

    @router.patch(f"/{kind}/{{user_id}}/status", name=f"set_{kind}_status")
    def set_employee_status(user_id: int, body: StatusBody, request: Request, auth: Auth, db: Db):
        school_id = _school(auth, db, permission)
        return _run(lambda: people.set_employee_status(db, school_id, kind, user_id, body.status, _url_for(request)))


for _kind in people.EMPLOYEE_KINDS:
    _employee_routes(_kind)


# ---------- photos and documents ----------


def _read_upload(file: UploadFile, limit: int) -> bytes:
    # One byte over the limit is enough to reject it; the rest is never read into memory here.
    return file.file.read(limit + 1)


def _upload_routes(owner: str) -> None:
    permission = rbac.PERM_STUDENTS if owner == "students" else rbac.PERM_TEACHERS

    @router.post(f"/{owner}/{{owner_id}}/photo", name=f"{owner}_photo")
    def upload_photo(owner_id: int, request: Request, auth: Auth, db: Db, file: UploadFile = File(...)):
        school_id = _school(auth, db, permission)
        data = _read_upload(file, file_storage.PHOTO_MAX_BYTES)
        return _run(lambda: people.upload_photo(db, school_id, owner, owner_id, data, file.filename, _url_for(request)))

    @router.post(f"/{owner}/{{owner_id}}/documents", status_code=201, name=f"{owner}_document")
    def upload_document(
        owner_id: int,
        request: Request,
        auth: Auth,
        db: Db,
        file: UploadFile = File(...),
        title: str = Form(""),
    ):
        school_id = _school(auth, db, permission)
        data = _read_upload(file, file_storage.DOCUMENT_MAX_BYTES)
        return _run(
            lambda: people.upload_document(db, school_id, owner, owner_id, data, file.filename, title, _url_for(request))
        )

    @router.delete(f"/{owner}/{{owner_id}}/documents/{{document_id}}", name=f"{owner}_delete_document")
    def delete_document(owner_id: int, document_id: int, auth: Auth, db: Db):
        school_id = _school(auth, db, permission)
        return _run(lambda: people.delete_document(db, school_id, owner, owner_id, document_id))


for _owner in people.FILE_OWNERS:
    _upload_routes(_owner)


# ---------- signed downloads ----------


@files_router.get("/{token}", name="download_people_file")
def download_file(token: str) -> Response:
    """Serve a stored file to whoever holds a valid, unexpired signed token."""
    try:
        data = file_storage.unsign(token)
        content = file_storage.get_storage().read(data["k"])
    except file_storage.StorageError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    content_type = data.get("t") or "application/octet-stream"
    disposition = "inline" if content_type in file_storage.INLINE_TYPES else "attachment"
    name = quote(str(data.get("n") or "file"))
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{name}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=300",
        },
    )
