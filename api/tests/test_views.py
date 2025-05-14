import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from ..models import Course, Group, Lesson, Attendance, Grade
from datetime import datetime, timedelta

User = get_user_model()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def teacher():
    return User.objects.create_user(
        username='teacher',
        email='teacher@example.com',
        password='testpass123',
        role='teacher',
        first_name='Test',
        last_name='Teacher'
    )

@pytest.fixture
def student1():
    return User.objects.create_user(
        username='student1',
        email='student1@example.com',
        password='testpass123',
        role='student',
        first_name='Test',
        last_name='Student1'
    )

@pytest.fixture
def student2():
    return User.objects.create_user(
        username='student2',
        email='student2@example.com',
        password='testpass123',
        role='student',
        first_name='Test',
        last_name='Student2'
    )

@pytest.fixture
def group(teacher):
    return Group.objects.create(name='Test Group')

@pytest.fixture
def course(teacher, group):
    course = Course.objects.create(
        title='Test Course',
        description='Test Description',
        teacher=teacher,
        semester='fall',
        year=2024
    )
    course.groups.add(group)
    return course

@pytest.fixture
def lesson(course):
    return Lesson.objects.create(
        course=course,
        date=datetime.now() + timedelta(days=1),
        topic='Test Topic'
    )

@pytest.mark.django_db
class TestGroupEndpoints:
    def test_create_group(self, api_client, teacher):
        api_client.force_authenticate(user=teacher)
        url = reverse('group-list')
        data = {
            'name': 'New Group',
            'student_ids': []
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'New Group'

    def test_add_student_to_group(self, api_client, teacher, group, student1):
        api_client.force_authenticate(user=teacher)
        url = reverse('group-detail', kwargs={'pk': group.id})
        data = {
            'name': group.name,
            'student_ids': [student1.id]
        }
        response = api_client.put(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert student1.id in [s['id'] for s in response.data['students']]

    def test_student_single_group_validation(self, api_client, teacher, group, student1):
        # Создаем вторую группу и пытаемся добавить студента в обе группы
        api_client.force_authenticate(user=teacher)
        group.students.add(student1)
        
        url = reverse('group-list')
        data = {
            'name': 'Second Group',
            'student_ids': [student1.id]
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'уже состоит в группе' in str(response.data['error'])

@pytest.mark.django_db
class TestCourseEndpoints:
    def test_create_course(self, api_client, teacher):
        api_client.force_authenticate(user=teacher)
        url = reverse('course-list')
        data = {
            'title': 'New Course',
            'description': 'Course Description',
            'semester': 'fall',
            'year': 2024
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == 'New Course'

    def test_add_group_to_course(self, api_client, teacher, course, group):
        api_client.force_authenticate(user=teacher)
        url = reverse('course-add-group', kwargs={'pk': course.id})
        data = {'group_id': group.id}
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert group.id in [g['id'] for g in response.data['groups']]

@pytest.mark.django_db
class TestLessonEndpoints:
    def test_create_lesson(self, api_client, teacher, course):
        api_client.force_authenticate(user=teacher)
        url = reverse('lesson-list')
        data = {
            'course_id': course.id,
            'date': (datetime.now() + timedelta(days=1)).isoformat(),
            'topic': 'Test Lesson'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['topic'] == 'Test Lesson'

    def test_unauthorized_create_lesson(self, api_client, student1, course):
        api_client.force_authenticate(user=student1)
        url = reverse('lesson-list')
        data = {
            'course_id': course.id,
            'date': (datetime.now() + timedelta(days=1)).isoformat(),
            'topic': 'Test Lesson'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.django_db
class TestAttendanceEndpoints:
    def test_create_attendance(self, api_client, teacher, lesson, student1, group):
        api_client.force_authenticate(user=teacher)
        group.students.add(student1)
        
        url = reverse('attendance-list')
        data = {
            'lesson_id': lesson.id,
            'student_id': student1.id,
            'is_present': True
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['is_present'] is True

    def test_duplicate_attendance(self, api_client, teacher, lesson, student1, group):
        api_client.force_authenticate(user=teacher)
        group.students.add(student1)
        
        # Создаем первую отметку посещаемости
        Attendance.objects.create(lesson=lesson, student=student1, is_present=True)
        
        # Пытаемся создать вторую отметку
        url = reverse('attendance-list')
        data = {
            'lesson_id': lesson.id,
            'student_id': student1.id,
            'is_present': True
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'уже отмечена' in str(response.data['error'])

    def test_attendance_student_not_in_course(self, api_client, teacher, lesson, student1):
        api_client.force_authenticate(user=teacher)
        
        url = reverse('attendance-list')
        data = {
            'lesson_id': lesson.id,
            'student_id': student1.id,
            'is_present': True
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'не записан на этот курс' in str(response.data['error'])

@pytest.mark.django_db
class TestGradeEndpoints:
    def test_create_grade(self, api_client, teacher, lesson, student1, group):
        api_client.force_authenticate(user=teacher)
        group.students.add(student1)
        
        url = reverse('grade-list')
        data = {
            'lesson': lesson.id,
            'student': student1.id,
            'value': 85,
            'comment': 'Good work'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['value'] == 85

    def test_invalid_grade_value(self, api_client, teacher, lesson, student1, group):
        api_client.force_authenticate(user=teacher)
        group.students.add(student1)
        
        url = reverse('grade-list')
        data = {
            'lesson': lesson.id,
            'student': student1.id,
            'value': 101,  # Значение больше 100
            'comment': 'Invalid grade'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_student_view_own_grades(self, api_client, student1, lesson, group):
        api_client.force_authenticate(user=student1)
        group.students.add(student1)
        
        # Создаем оценку для студента
        Grade.objects.create(lesson=lesson, student=student1, value=90)
        
        url = reverse('grade-my-grades')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['value'] == 90 