from typing import Optional, List, Dict, Any
from datetime import datetime, time

from sqlmodel import SQLModel, Field
from sqlalchemy import JSON, UniqueConstraint

metadata = SQLModel.metadata


class Role(SQLModel, table=True):
    __tablename__ = "roles"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=50, unique=True)


class User(SQLModel, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    refresh_token: Optional[str] = Field(default=None, max_length=500)
    role_id: int = Field(foreign_key="roles.id")
    username: str = Field(max_length=50, unique=True)
    personal_number: str = Field(max_length=50, unique=True)
    password_hash: str = Field(max_length=255)
    full_name: str = Field(max_length=255)
    email: str = Field(max_length=255, unique=True)
    gender: Optional[str] = Field(default=None, max_length=20)
    additional_info: Optional[str] = None


class Admin(SQLModel, table=True):
    __tablename__ = "admins"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True)


class Student(SQLModel, table=True):
    __tablename__ = "students"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True)


class Tutor(SQLModel, table=True):
    __tablename__ = "tutors"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True)


class StudentSettings(SQLModel, table=True):
    __tablename__ = "student_settings"
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="students.id", unique=True)
    status: str = Field(default="ACTIVE", max_length=20)
    timezone_offset: int = Field(default=0)
    schedule_view: str = Field(default="INFORMATIVE", max_length=20)


class TutorSettings(SQLModel, table=True):
    __tablename__ = "tutor_settings"
    id: Optional[int] = Field(default=None, primary_key=True)
    tutor_id: int = Field(foreign_key="tutors.id", unique=True)
    hourly_rate: float = Field(default=0.0)
    discount: float = Field(default=0.0)
    timezone_offset: int = Field(default=0)
    work_status: str = Field(default="WORKING", max_length=20)
    schedule_view: str = Field(default="INFORMATIVE", max_length=20)
    allow_self_booking: bool = Field(default=True)
    booking_lead_time_hours: int = Field(default=24)
    cancellation_lead_time_hours: int = Field(default=24)
    notifications_enabled: bool = Field(default=True)
    notification_lead_time_hours: int = Field(default=24)
    default_links: Optional[List[Dict[str, str]]] = Field(default=None, sa_type=JSON)


class Configuration(SQLModel, table=True):
    __tablename__ = "configurations"
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="students.id")
    tutor_id: int = Field(foreign_key="tutors.id")
    hourly_rate: float = Field(default=0.0)
    allow_self_booking: bool = Field(default=True)
    booking_lead_time_hours: int = Field(default=24)
    cancellation_lead_time_hours: int = Field(default=24)
    notifications_enabled: bool = Field(default=True)
    notification_lead_time_hours: int = Field(default=24)
    default_links: Optional[List[Dict[str, str]]] = Field(default=None, sa_type=JSON)
    allow_unpaid_lesson: bool = Field(default=False)
    student_notes: Optional[str] = None

    class Config:
        __table_args__ = (
            UniqueConstraint("student_id", "tutor_id", name="uq_student_tutor"),
        )


class Booking(SQLModel, table=True):
    __tablename__ = "bookings"
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = Field(default_factory=datetime.now)
    tutor_id: int = Field(foreign_key="tutors.id")
    weekday: str = Field(max_length=20)
    start_time: time
    end_time: time
    access_rule: str = Field(default="EVERYONE", max_length=20)
    access_targets: Optional[List[int]] = Field(default=None, sa_type=JSON)
    booking_metadata: Optional[Dict[str, Any]] = Field(default=None, sa_type=JSON)


class Lesson(SQLModel, table=True):
    __tablename__ = "lessons"
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = Field(default_factory=datetime.now)
    tutor_id: int = Field(foreign_key="tutors.id")
    start_time: datetime
    end_time: datetime
    created_by_id: int
    is_group: bool = Field(default=False)
    lesson_settings: Optional[Dict[str, Any]] = Field(default=None, sa_type=JSON)
    lesson_links: Optional[List[Dict[str, str]]] = Field(default=None, sa_type=JSON)
    lesson_metadata: Optional[Dict[str, Any]] = Field(default=None, sa_type=JSON)
    lesson_descriptions: Optional[str] = None


class LessonParticipant(SQLModel, table=True):
    __tablename__ = "lesson_participants"
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = Field(default_factory=datetime.now)
    lesson_id: int = Field(foreign_key="lessons.id")
    student_id: int = Field(foreign_key="students.id")
    participant_settings: Optional[Dict[str, Any]] = Field(default=None, sa_type=JSON)
    participant_metadata: Optional[Dict[str, Any]] = Field(default=None, sa_type=JSON)

    class Config:
        __table_args__ = (
            UniqueConstraint("lesson_id", "student_id", name="uq_lesson_participant"),
        )


class DemoUser(SQLModel, table=True):
    __tablename__ = "demo_users"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    age: int
    email: str = Field(max_length=255, unique=True)


class DemoProduct(SQLModel, table=True):
    __tablename__ = "demo_products"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    price: float
    quantity: int


class model_test(SQLModel, table=True):
    __tablename__ = "model_test"
    id: Optional[int] = Field(default=None, primary_key=True)
    val: int = Field(default=0)
    name: str = Field(default="")


def get_all_schemas():
    import sys
    module = sys.modules[__name__]
    schemas = {}
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if (
            isinstance(attr, type) and
            issubclass(attr, SQLModel) and
            attr != SQLModel and
            hasattr(attr, '__table__')
        ):
            schemas[attr.__tablename__] = attr
    return schemas
