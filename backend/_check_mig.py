from sqlalchemy import create_engine, text
from app.core.db_urls import get_neon_database_url

engine = create_engine(get_neon_database_url())
with engine.connect() as c:
    ver = c.execute(text("select version_num from alembic_version")).fetchall()
    print("alembic_version", ver)
    tables = c.execute(
        text(
            """
      select table_name from information_schema.tables
      where table_schema='public' and table_name in (
        'leave_types','salary_structures','salary_structure_lines','salary_assignments',
        'messaging_policies','message_conversations','conversation_messages','conversation_reads',
        'payroll_audit_events'
      ) order by 1
    """
        )
    ).fetchall()
    print("tables", [r[0] for r in tables])
    cols = c.execute(
        text(
            """
      select table_name, column_name from information_schema.columns
      where table_schema='public' and (
        (table_name='leaves' and column_name='leave_type_id') or
        (table_name='announcements' and column_name in ('status','audience_json','publish_at','published_at','deleted_at')) or
        (table_name='certificate_issues' and column_name in ('staff_id','verification_token','status','revoked_at','pdf_storage_key')) or
        (table_name='notifications' and column_name in ('audience_json','delivery')) or
        (table_name='payroll_runs' and column_name in ('processed_at','idempotency_key')) or
        (table_name='payroll_items' and column_name in ('breakdown_json','payslip_ref','status'))
      ) order by 1,2
    """
        )
    ).fetchall()
    print("cols", cols)
    types = c.execute(
        text(
            """
      select n.nspname, t.typname from pg_type t
      join pg_namespace n on n.oid=t.typnamespace
      where t.typname in ('leave_types','salary_structures','message_conversations')
    """
        )
    ).fetchall()
    print("pg_types", types)
