from typing import Optional, List, Dict, Any
from datetime import datetime, time

from sqlmodel import SQLModel, Field
from sqlalchemy import JSON, UniqueConstraint


metadata = SQLModel.metadata


# ============================================
# 1. ПОЛЬЗОВАТЕЛИ И РОЛИ
# Связи: Role 1→N User (одна роль — много пользователей)
#        User 1→1 Student/Tutor/Admin (один пользователь — один профиль)
# ============================================

class Role(SQLModel, table=True):
    """Роли пользователей."""
    __tablename__ = "roles"
    id: Optional[int] = Field(default=None, primary_key=True)                    # [_авто_] ID роли
    name: str = Field(max_length=50, unique=True)                                # [обязат] Название: 'student', 'tutor', 'admin'


class User(SQLModel, table=True):
    """Пользователи системы."""
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)                    # [_авто_] ID пользователя
    created_at: Optional[datetime] = Field(default_factory=datetime.now)         # [_авто_] Дата и время создания аккаунта
    refresh_token: Optional[str] = Field(default=None, max_length=500)           # [необяз] Refresh токен

    role_id: int = Field(foreign_key="roles.id")                                 # [обязат] ID роли (внешний ключ на roles)
    username: str = Field(max_length=50, unique=True)                            # [обязат] Логин (уникальный)
    personal_number: str = Field(max_length=50, unique=True)                     # [обязат] Уникальный личный код (буквенно-цифровой)
    password_hash: str = Field(max_length=255)                                   # [обязат] Хеш пароля (bcrypt)
    full_name: str = Field(max_length=255)                                       # [обязат] Полное ФИО
    email: str = Field(max_length=255, unique=True)                              # [обязат] Электронная почта (уникальная)

    gender: Optional[str] = Field(default=None, max_length=20)                   # [необяз] Пол (male/female/other)
    additional_info: Optional[str] = None                                        # [необяз] Дополнительная информация


# ============================================
# 2. ПРОФИЛИ ПОЛЬЗОВАТЕЛЕЙ
# Связи: User 1→1 Admin (один пользователь — один админ)
#        User 1→1 Student (один пользователь — один ученик)
#        Student 1→N Configuration (один ученик — много конфигураций)
#        Student 1→1 StudentSettings (один ученик — одни настройки)
#        User 1→1 Tutor (один пользователь — один репетитор)
#        Tutor 1→N Configuration (один репетитор — много конфигураций)
#        Tutor 1→1 TutorSettings (один репетитор — одни настройки)
#        Tutor 1→N Booking (один репетитор — много броней)
#        Tutor 1→N Lesson (один репетитор — много уроков)
# ============================================

class Admin(SQLModel, table=True):
    """Администраторы."""
    __tablename__ = "admins"
    id: Optional[int] = Field(default=None, primary_key=True)                    # [_авто_] ID администратора
    user_id: int = Field(foreign_key="users.id", unique=True)                    # [обязат] ID пользователя (внешний ключ на users)


class Student(SQLModel, table=True):
    """Ученики."""
    __tablename__ = "students"
    id: Optional[int] = Field(default=None, primary_key=True)                    # [_авто_] ID ученика
    user_id: int = Field(foreign_key="users.id", unique=True)                    # [обязат] ID пользователя (внешний ключ на users)


class Tutor(SQLModel, table=True):
    """Репетиторы."""
    __tablename__ = "tutors"
    id: Optional[int] = Field(default=None, primary_key=True)                    # [_авто_] ID репетитора
    user_id: int = Field(foreign_key="users.id", unique=True)                    # [обязат] ID пользователя (внешний ключ на users)


# ============================================
# 3. НАСТРОЙКИ
# Связи: Student 1→1 StudentSettings
#        Tutor 1→1 TutorSettings
# ============================================

class StudentSettings(SQLModel, table=True):
    """Настройки ученика."""
    __tablename__ = "student_settings"
    id: Optional[int] = Field(default=None, primary_key=True)                    # [_авто_] ID настроек
    student_id: int = Field(foreign_key="students.id", unique=True)              # [обязат] ID ученика (внешний ключ на students)

    status: str = Field(default="ACTIVE", max_length=20)                         # [необяз] Статус активности: active/inactive
    timezone_offset: int = Field(default=0)                                      # [необяз] Часовой пояс (смещение в часах от UTC)
    schedule_view: str = Field(default="INFORMATIVE", max_length=20)             # [необяз] Вид расписания: informative/minimalistic


class TutorSettings(SQLModel, table=True):
    """Настройки репетитора."""
    __tablename__ = "tutor_settings"
    id: Optional[int] = Field(default=None, primary_key=True)                    # [_авто_] ID настроек
    tutor_id: int = Field(foreign_key="tutors.id", unique=True)                  # [обязат] ID репетитора (внешний ключ на tutors)

    hourly_rate: float = Field(default=0.0)                                      # [необяз] Стоимость занятия (руб/час)
    discount: float = Field(default=0.0)                                         # [необяз] Скидка в процентах
    timezone_offset: int = Field(default=0)                                      # [необяз] Часовой пояс (смещение в часах от UTC)
    work_status: str = Field(default="WORKING", max_length=20)                   # [необяз] Статус работы: working/not_working
    schedule_view: str = Field(default="INFORMATIVE", max_length=20)             # [необяз] Вид расписания: informative/minimalistic
    allow_self_booking: bool = Field(default=True)                               # [необяз] Разрешить самостоятельную запись учеников
    booking_lead_time_hours: int = Field(default=24)                             # [необяз] Запись возможна за N часов до начала урока
    cancellation_lead_time_hours: int = Field(default=24)                        # [необяз] Отмена возможна за N часов до начала урока
    notifications_enabled: bool = Field(default=True)                            # [необяз] Включены ли уведомления
    notification_lead_time_hours: int = Field(default=24)                        # [необяз] Уведомление за N часов до начала урока
    default_links: Optional[List[Dict[str, str]]] = Field(default=None, sa_type=JSON)  # [необяз] Ссылки по умолчанию [{"description": "...", "url": "..."}]


# ============================================
# 4. КОНФИГУРАЦИИ (связь ученик-репетитор)
# Связи: Student 1→N Configuration (один ученик — много конфигураций)
#        Tutor 1→N Configuration (один репетитор — много конфигураций)
#        Реализует связь многие-ко-многим между учениками и репетиторами
# ============================================

class Configuration(SQLModel, table=True):
    """Конфигурация связи ученик-репетитор."""
    __tablename__ = "configurations"
    id: Optional[int] = Field(default=None, primary_key=True)                    # [_авто_] ID конфигурации
    student_id: int = Field(foreign_key="students.id")                           # [обязат] ID ученика (внешний ключ на students)
    tutor_id: int = Field(foreign_key="tutors.id")                               # [обязат] ID репетитора (внешний ключ на tutors)

    hourly_rate: float = Field(default=0.0)                                      # [необяз] Стоимость занятия (руб/час)
    allow_self_booking: bool = Field(default=True)                               # [необяз] Разрешить самостоятельную запись ученика
    booking_lead_time_hours: int = Field(default=24)                             # [необяз] Запись возможна за N часов до урока
    cancellation_lead_time_hours: int = Field(default=24)                        # [необяз] Отмена возможна за N часов до урока
    notifications_enabled: bool = Field(default=True)                            # [необяз] Включены ли уведомления
    notification_lead_time_hours: int = Field(default=24)                        # [необяз] Уведомление за N часов до урока
    default_links: Optional[List[Dict[str, str]]] = Field(default=None, sa_type=JSON)  # [необяз] Ссылки для занятий [{"description": "...", "url": "..."}]
    allow_unpaid_lesson: bool = Field(default=False)                             # [необяз] Разрешить вход на урок без оплаты
    student_notes: Optional[str] = None                                          # [необяз] Заметки репетитора об ученике

    class Config:
        __table_args__ = (
            UniqueConstraint("student_id", "tutor_id", name="uq_student_tutor"),
        )


# ============================================
# 5. БРОНИ (ПОВТОРЯЮЩИЕСЯ БЛОКИРОВКИ ВРЕМЕНИ)
# Связи: Tutor 1→N Booking (один репетитор — много броней)
# ============================================

class Booking(SQLModel, table=True):
    """Бронь — повторяющаяся блокировка времени репетитора."""
    __tablename__ = "bookings"
    id: Optional[int] = Field(default=None, primary_key=True)                    # [_авто_] ID брони
    created_at: Optional[datetime] = Field(default_factory=datetime.now)         # [_авто_] Дата и время создания
    updated_at: Optional[datetime] = Field(default_factory=datetime.now)         # [_авто_] Дата и время обновления

    tutor_id: int = Field(foreign_key="tutors.id")                               # [обязат] ID репетитора (внешний ключ на tutors)
    weekday: str = Field(max_length=20)                                          # [обязат] День недели
    start_time: time                                                             # [обязат] Время начала
    end_time: time                                                               # [обязат] Время окончания

    access_rule: str = Field(default="EVERYONE", max_length=20)                  # [необяз] Правило доступа: nobody/all_except/only/everyone
    access_targets: Optional[List[int]] = Field(default=None, sa_type=JSON)      # [необяз] Список ID учеников: для 'only' — разрешённые, для 'all_except' — исключённые
    booking_metadata: Optional[Dict[str, Any]] = Field(default=None, sa_type=JSON)  # [необяз] Дополнительные данные


# ============================================
# 6. УРОКИ
# Связи: Tutor 1→N Lesson (один репетитор — много уроков)
#        Lesson 1→N LessonParticipant (один урок — много участников)
#        Student 1→N LessonParticipant (один ученик — много участий)
# ============================================

class Lesson(SQLModel, table=True):
    """Уроки."""
    __tablename__ = "lessons"
    id: Optional[int] = Field(default=None, primary_key=True)                    # [_авто_] ID урока
    created_at: Optional[datetime] = Field(default_factory=datetime.now)         # [_авто_] Дата и время создания
    updated_at: Optional[datetime] = Field(default_factory=datetime.now)         # [_авто_] Дата и время обновления

    tutor_id: int = Field(foreign_key="tutors.id")                               # [обязат] ID репетитора (внешний ключ на tutors)
    start_time: datetime                                                         # [обязат] Время начала
    end_time: datetime                                                           # [обязат] Время окончания
    created_by_id: int                                                           # [обязат] ID создателя (student.id или tutor.id)

    is_group: bool = Field(default=False)                                        # [необяз] Групповой ли урок
    lesson_settings: Optional[Dict[str, Any]] = Field(default=None, sa_type=JSON)  # [необяз] Настройки урока
    lesson_links: Optional[List[Dict[str, str]]] = Field(default=None, sa_type=JSON)  # [необяз] Ссылки для занятий [{"description": "...", "url": "..."}]
    lesson_metadata: Optional[Dict[str, Any]] = Field(default=None, sa_type=JSON)  # [необяз] Дополнительные данные
    lesson_descriptions: Optional[str] = None                                    # [необяз] Описание урока


class LessonParticipant(SQLModel, table=True):
    """Участники урока."""
    __tablename__ = "lesson_participants"
    id: Optional[int] = Field(default=None, primary_key=True)                    # [_авто_] ID записи
    created_at: Optional[datetime] = Field(default_factory=datetime.now)         # [_авто_] Дата и время создания
    updated_at: Optional[datetime] = Field(default_factory=datetime.now)         # [_авто_] Дата и время обновления

    lesson_id: int = Field(foreign_key="lessons.id")                             # [обязат] ID урока (внешний ключ на lessons)
    student_id: int = Field(foreign_key="students.id")                           # [обязат] ID ученика (внешний ключ на students)

    participant_settings: Optional[Dict[str, Any]] = Field(default=None, sa_type=JSON)  # [необяз] Индивидуальные настройки участника
    participant_metadata: Optional[Dict[str, Any]] = Field(default=None, sa_type=JSON)  # [необяз] Дополнительные данные

    class Config:
        __table_args__ = (
            UniqueConstraint("lesson_id", "student_id", name="uq_lesson_participant"),
        )


# ============================================
# 7. ТЕСТОВЫЕ МОДЕЛИ
# ============================================

class DemoUser(SQLModel, table=True):
    """Тестовый пользователь (для отладки CRUD)."""
    __tablename__ = "demo_users"
    id: Optional[int] = Field(default=None, primary_key=True)                    # [_авто_] ID
    name: str = Field(max_length=255)                                            # [обязат] Имя
    age: int                                                                     # [обязат] Возраст
    email: str = Field(max_length=255, unique=True)                              # [обязат] Электронная почта (уникальная)


class DemoProduct(SQLModel, table=True):
    """Тестовый продукт (для отладки CRUD)."""
    __tablename__ = "demo_products"
    id: Optional[int] = Field(default=None, primary_key=True)                    # [_авто_] ID
    name: str = Field(max_length=255)                                            # [обязат] Название
    price: float                                                                 # [обязат] Цена
    quantity: int                                                                # [обязат] Количество


class model_test(SQLModel, table=True):
    """Тестовая модель для нагрузочных тестов."""
    __tablename__ = "model_test"
    id: Optional[int] = Field(default=None, primary_key=True)                    # [_авто_] ID
    val: int = Field(default=0)                                                  # [необяз] Значение
    name: str = Field(default="")                                                # [необяз] Имя


# ============================================
# 8. АВТОСБОР СХЕМ
# ============================================

def get_all_schemas():
    """Автоматически собирает все SQLModel-таблицы из текущего модуля."""
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