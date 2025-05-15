import os
import pytest
import django
from django.core.management import call_command
import uuid

# Configure Django settings before any other imports
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gradar.test_settings')
django.setup()

# Now we can import Django and DRF related modules
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from api.models import Group, Course, Lesson, Attendance, Grade
from datetime import datetime, timedelta

User = get_user_model()

@pytest.fixture(autouse=True)
def clean_database(db):
    """Clean database before each test"""
    # Delete related records first
    Grade.objects.all().delete()
    Attendance.objects.all().delete()
    Lesson.objects.all().delete()
    Course.objects.all().delete()
    Group.objects.all().delete()
    User.objects.all().delete()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def create_user():
    def make_user(username=None, password='testpass123', role='student', **kwargs):
        if username is None:
            username = f'testuser_{role}_{uuid.uuid4().hex}'
        if 'email' not in kwargs:
            kwargs['email'] = f'{username}_{uuid.uuid4().hex}@example.com'
        return User.objects.create_user(
            username=username,
            password=password,
            role=role,
            **kwargs
        )
    return make_user

@pytest.fixture
def get_or_create_token():
    def get_token(user):
        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
    return get_token

@pytest.fixture
def auth_client(api_client, create_user, get_or_create_token):
    def get_client(role='student'):
        user = create_user(
            role=role,
            first_name=f'Test {role.capitalize()}',
            last_name='User'
        )
        tokens = get_or_create_token(user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
        return client, user
    return get_client

@pytest.fixture
def create_course():
    def make_course(teacher, name='Test Course', semester='spring', year=2024):
        return Course.objects.create(
            name=name,
            description='Test course description',
            teacher=teacher,
            semester=semester,
            year=year
        )
    return make_course

@pytest.fixture
def create_lesson():
    def make_lesson(course, topic='Test Lesson', date=None):
        if date is None:
            date = datetime.now() + timedelta(days=1)
        return Lesson.objects.create(
            course=course,
            topic=topic,
            date=date
        )
    return make_lesson

@pytest.fixture
def create_grade():
    def make_grade(lesson, student, value=85, comment='Test comment'):
        return Grade.objects.create(
            lesson=lesson,
            student=student,
            value=value,
            comment=comment
        )
    return make_grade

@pytest.fixture
def create_group():
    def make_group(name='Test Group', year=2024):
        return Group.objects.create(
            name=name,
            year=year
        )
    return make_group

@pytest.fixture
def create_attendance():
    def make_attendance(lesson, student, status='present'):
        return Attendance.objects.create(
            lesson=lesson,
            student=student,
            status=status
        )
    return make_attendance

@pytest.fixture
def test_group(create_group, create_user):
    group = create_group()
    student = create_user(username='test_student', role='student')
    group.students.add(student)
    return {
        'id': group.id,
        'name': group.name,
        'year': group.year,
        'student': student
    } 