"""School Admin ERP modules 1–5: installments, payment cancel, transport trips/GPS.

Revision ID: 20261029_0041
Revises: 20261028_0040
Create Date: 2026-10-29

Additive schema only. Does not apply automatically — do not run against Neon from this delivery.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261029_0041"
down_revision: Union[str, None] = "20261028_0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fee_installments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("structure_id", sa.Integer(), sa.ForeignKey("fee_structures.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_fee_installments_school_id", "fee_installments", ["school_id"], unique=False)
    op.create_index("ix_fee_installments_structure_id", "fee_installments", ["structure_id"], unique=False)
    op.create_index(
        "ix_fee_installments_school_structure",
        "fee_installments",
        ["school_id", "structure_id"],
        unique=False,
    )

    op.create_table(
        "fee_payment_allocations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("fee_payments.id"), nullable=False),
        sa.Column("installment_id", sa.Integer(), sa.ForeignKey("fee_installments.id"), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_fee_payment_allocations_school_id", "fee_payment_allocations", ["school_id"], unique=False
    )
    op.create_index(
        "ix_fee_payment_allocations_payment_id", "fee_payment_allocations", ["payment_id"], unique=False
    )
    op.create_index(
        "ix_fee_payment_allocations_installment_id",
        "fee_payment_allocations",
        ["installment_id"],
        unique=False,
    )
    op.create_index(
        "ix_fee_payment_allocations_payment",
        "fee_payment_allocations",
        ["school_id", "payment_id"],
        unique=False,
    )
    op.create_index(
        "ix_fee_payment_allocations_installment",
        "fee_payment_allocations",
        ["school_id", "installment_id"],
        unique=False,
    )

    op.add_column("fee_payments", sa.Column("cancelled_at", sa.DateTime(), nullable=True))
    op.add_column("fee_payments", sa.Column("cancel_reason", sa.String(length=512), nullable=True))

    op.add_column(
        "transport_vehicles",
        sa.Column("driver_staff_id", sa.Integer(), sa.ForeignKey("staffs.id"), nullable=True),
    )
    op.add_column(
        "transport_vehicles",
        sa.Column("helper_staff_id", sa.Integer(), sa.ForeignKey("staffs.id"), nullable=True),
    )
    op.create_index(
        "ix_transport_vehicles_driver_staff_id", "transport_vehicles", ["driver_staff_id"], unique=False
    )
    op.create_index(
        "ix_transport_vehicles_helper_staff_id", "transport_vehicles", ["helper_staff_id"], unique=False
    )

    op.create_table(
        "transport_trips",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("route_id", sa.Integer(), sa.ForeignKey("transport_routes.id"), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("transport_vehicles.id"), nullable=False),
        sa.Column("driver_staff_id", sa.Integer(), sa.ForeignKey("staffs.id"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="scheduled"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_transport_trips_school_id", "transport_trips", ["school_id"], unique=False)
    op.create_index("ix_transport_trips_route_id", "transport_trips", ["route_id"], unique=False)
    op.create_index("ix_transport_trips_vehicle_id", "transport_trips", ["vehicle_id"], unique=False)
    op.create_index(
        "ix_transport_trips_driver_staff_id", "transport_trips", ["driver_staff_id"], unique=False
    )
    op.create_index(
        "ix_transport_trips_school_route", "transport_trips", ["school_id", "route_id"], unique=False
    )
    op.create_index(
        "ix_transport_trips_school_status", "transport_trips", ["school_id", "status"], unique=False
    )

    op.create_table(
        "transport_gps_points",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("trip_id", sa.Integer(), sa.ForeignKey("transport_trips.id"), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("transport_vehicles.id"), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("staffs.id"), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_transport_gps_points_school_id", "transport_gps_points", ["school_id"], unique=False)
    op.create_index("ix_transport_gps_points_trip_id", "transport_gps_points", ["trip_id"], unique=False)
    op.create_index("ix_transport_gps_points_vehicle_id", "transport_gps_points", ["vehicle_id"], unique=False)
    op.create_index("ix_transport_gps_points_staff_id", "transport_gps_points", ["staff_id"], unique=False)
    op.create_index(
        "ix_transport_gps_points_trip_recorded",
        "transport_gps_points",
        ["trip_id", "recorded_at"],
        unique=False,
    )
    op.create_index(
        "ix_transport_gps_points_school_trip",
        "transport_gps_points",
        ["school_id", "trip_id"],
        unique=False,
    )

    op.create_table(
        "transport_attendance_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("trip_id", sa.Integer(), sa.ForeignKey("transport_trips.id"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("stop_id", sa.Integer(), sa.ForeignKey("transport_stops.id"), nullable=True),
        sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_transport_attendance_events_school_id",
        "transport_attendance_events",
        ["school_id"],
        unique=False,
    )
    op.create_index(
        "ix_transport_attendance_events_trip_id",
        "transport_attendance_events",
        ["trip_id"],
        unique=False,
    )
    op.create_index(
        "ix_transport_attendance_events_student_id",
        "transport_attendance_events",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        "ix_transport_attendance_events_stop_id",
        "transport_attendance_events",
        ["stop_id"],
        unique=False,
    )
    op.create_index(
        "ix_transport_attendance_school_trip",
        "transport_attendance_events",
        ["school_id", "trip_id"],
        unique=False,
    )
    op.create_index(
        "uq_transport_attendance_trip_student_event_active",
        "transport_attendance_events",
        ["trip_id", "student_id", "event_type"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_transport_attendance_trip_student_event_active",
        table_name="transport_attendance_events",
    )
    op.drop_index("ix_transport_attendance_school_trip", table_name="transport_attendance_events")
    op.drop_index("ix_transport_attendance_events_stop_id", table_name="transport_attendance_events")
    op.drop_index("ix_transport_attendance_events_student_id", table_name="transport_attendance_events")
    op.drop_index("ix_transport_attendance_events_trip_id", table_name="transport_attendance_events")
    op.drop_index("ix_transport_attendance_events_school_id", table_name="transport_attendance_events")
    op.drop_table("transport_attendance_events")

    op.drop_index("ix_transport_gps_points_school_trip", table_name="transport_gps_points")
    op.drop_index("ix_transport_gps_points_trip_recorded", table_name="transport_gps_points")
    op.drop_index("ix_transport_gps_points_staff_id", table_name="transport_gps_points")
    op.drop_index("ix_transport_gps_points_vehicle_id", table_name="transport_gps_points")
    op.drop_index("ix_transport_gps_points_trip_id", table_name="transport_gps_points")
    op.drop_index("ix_transport_gps_points_school_id", table_name="transport_gps_points")
    op.drop_table("transport_gps_points")

    op.drop_index("ix_transport_trips_school_status", table_name="transport_trips")
    op.drop_index("ix_transport_trips_school_route", table_name="transport_trips")
    op.drop_index("ix_transport_trips_driver_staff_id", table_name="transport_trips")
    op.drop_index("ix_transport_trips_vehicle_id", table_name="transport_trips")
    op.drop_index("ix_transport_trips_route_id", table_name="transport_trips")
    op.drop_index("ix_transport_trips_school_id", table_name="transport_trips")
    op.drop_table("transport_trips")

    op.drop_index("ix_transport_vehicles_helper_staff_id", table_name="transport_vehicles")
    op.drop_index("ix_transport_vehicles_driver_staff_id", table_name="transport_vehicles")
    op.drop_column("transport_vehicles", "helper_staff_id")
    op.drop_column("transport_vehicles", "driver_staff_id")

    op.drop_column("fee_payments", "cancel_reason")
    op.drop_column("fee_payments", "cancelled_at")

    op.drop_index("ix_fee_payment_allocations_installment", table_name="fee_payment_allocations")
    op.drop_index("ix_fee_payment_allocations_payment", table_name="fee_payment_allocations")
    op.drop_index("ix_fee_payment_allocations_installment_id", table_name="fee_payment_allocations")
    op.drop_index("ix_fee_payment_allocations_payment_id", table_name="fee_payment_allocations")
    op.drop_index("ix_fee_payment_allocations_school_id", table_name="fee_payment_allocations")
    op.drop_table("fee_payment_allocations")

    op.drop_index("ix_fee_installments_school_structure", table_name="fee_installments")
    op.drop_index("ix_fee_installments_structure_id", table_name="fee_installments")
    op.drop_index("ix_fee_installments_school_id", table_name="fee_installments")
    op.drop_table("fee_installments")
