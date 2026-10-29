from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def add_responses(src: str, fn: str, expr: str) -> str:
    pattern = rf"((?:@[^\n]+\n)+)(def {fn}\()"
    m = re.search(pattern, src)
    if not m:
        raise SystemExit(f"missing {fn}")
    decorators = m.group(1)
    if "responses=" in decorators:
        return src
    lines = decorators.rstrip("\n").split("\n")
    last = lines[-1]
    lines[-1] = last[:-1] + f", {expr})"
    new_decorators = "\n".join(lines) + "\n"
    return src[: m.start(1)] + new_decorators + src[m.start(2) :]


settings = ROOT / "app" / "api" / "v1" / "school_admin_settings.py"
st = settings.read_text(encoding="utf-8")
if "school_admin_settings_responses" not in st:
    st = st.replace(
        "from app.api.deps import central_db\n",
        "from app.api.deps import central_db\n"
        "from app.schemas.v1 import school_admin_settings_responses as settings_out\n",
        1,
    )

SETTINGS_MAP = {
    "put_content": "settings_out.json_response(settings_out.ContentPageOut)",
    "put_web_content": "settings_out.json_response(settings_out.ContentPageOut)",
    "create_faq": "settings_out.json_response(settings_out.FaqOut, status_code=201)",
    "patch_faq": "settings_out.json_response(settings_out.FaqOut)",
    "put_leave_settings": "settings_out.json_response(settings_out.LeaveSettingsOut)",
    "create_email_template": "settings_out.json_response(settings_out.EmailTemplateOut, status_code=201)",
    "patch_email_template": "settings_out.json_response(settings_out.EmailTemplateOut)",
    "put_whatsapp_settings": "settings_out.json_response(settings_out.IntegrationSettingsOut)",
    "put_payment_gateway_settings": "settings_out.json_response(settings_out.IntegrationSettingsOut)",
    "put_third_party_integration": "settings_out.json_response(settings_out.IntegrationSettingsOut)",
    "patch_contact_inquiry": "settings_out.json_response(settings_out.ContactInquiryOut)",
}

for fn, expr in SETTINGS_MAP.items():
    st = add_responses(st, fn, expr)
settings.write_text(st, encoding="utf-8")
print("settings wired", len(SETTINGS_MAP))

admin = ROOT / "app" / "api" / "v1" / "school_admin.py"
at = admin.read_text(encoding="utf-8")
if "school_admin_settings_responses" not in at:
    at = at.replace(
        "from app.schemas.v1 import school_admin_core_responses as core_out\n",
        "from app.schemas.v1 import school_admin_core_responses as core_out\n"
        "from app.schemas.v1 import school_admin_settings_responses as settings_out\n",
        1,
    )

ADMIN_MAP = {
    "create_study_material": "settings_out.json_response(settings_out.StudyMaterialOut, status_code=201)",
    "update_study_material": "settings_out.json_response(settings_out.StudyMaterialOut)",
    "create_online_assessment": "settings_out.json_response(settings_out.OnlineAssessmentOut, status_code=201)",
    "update_online_assessment": "settings_out.json_response(settings_out.OnlineAssessmentOut)",
}
for fn, expr in ADMIN_MAP.items():
    at = add_responses(at, fn, expr)
admin.write_text(at, encoding="utf-8")
print("admin wired", len(ADMIN_MAP))
