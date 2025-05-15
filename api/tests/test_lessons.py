import pytest
from django.urls import reverse
from rest_framework import status
from api.models import Lesson, Course, Group
from django.utils import timezone
from datetime import datetime, timedelta
import uuid

@pytest.mark.django_db
class TestLessonAPI:
    @pytest.fixture(autouse=True)
    def setup(self, auth_client):
        self.student_client, self.student = auth_client(role='student')
        self.teacher_client, self.teacher = auth_client(role='teacher')
        self.other_teacher_client, self.other_teacher = auth_client(role='teacher')
        
        # Create course
        self.course = Course.objects.create(
            name='Test Course',
            description='Test Description',
            semester='spring',
            year=2024,
            teacher=self.teacher
        )
        
        # Create group and add student
        self.group = Group.objects.create(name=f'Test Group {uuid.uuid4().hex}', year=2024)
        self.group.students.add(self.student)
        self.course.groups.add(self.group)
        
        self.url = reverse('lesson-list')

    def test_create_lesson(self):
        data = {
            'course_id': self.course.id,
            'topic': 'Test Lesson',
            'date': (timezone.now() + timezone.timedelta(days=1)).isoformat()
        }
        response = self.teacher_client.post(self.url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert Lesson.objects.count() == 1
        lesson = Lesson.objects.first()
        assert lesson.topic == 'Test Lesson'
        assert lesson.course == self.course

    def test_student_cannot_create_lesson(self):
        data = {
            'course_id': self.course.id,
            'topic': 'Test Lesson',
            'date': (timezone.now() + timezone.timedelta(days=1)).isoformat()
        }
        response = self.student_client.post(self.url, data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_lessons(self):
        # Create a lesson
        lesson = Lesson.objects.create(
            course=self.course,
            topic='Test Lesson',
            date=timezone.now() + timezone.timedelta(days=1)
        )
        
        # Test teacher view
        response = self.teacher_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['topic'] == 'Test Lesson'
        
        # Test student view
        response = self.student_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['topic'] == 'Test Lesson'

    def test_update_lesson(self):
        # Create a lesson
        lesson = Lesson.objects.create(
            course=self.course,
            topic='Test Lesson',
            date=timezone.now() + timezone.timedelta(days=1)
        )
        
        data = {
            'topic': 'Updated Lesson',
            'course_id': self.course.id,
            'date': (timezone.now() + timezone.timedelta(days=1)).isoformat()
        }
        url = reverse('lesson-detail', args=[lesson.id])
        response = self.teacher_client.patch(url, data)
        assert response.status_code == status.HTTP_200_OK
        lesson.refresh_from_db()
        assert lesson.topic == 'Updated Lesson'

    def test_other_teacher_cannot_update_lesson(self):
        # Create a lesson
        lesson = Lesson.objects.create(
            course=self.course,
            topic='Test Lesson',
            date=timezone.now() + timezone.timedelta(days=1)
        )
        
        # Test that other teacher cannot see the lesson in list
        response = self.other_teacher_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0
        
        # Test that other teacher cannot update the lesson directly
        data = {
            'topic': 'Updated Lesson',
            'course_id': self.course.id,
            'date': (timezone.now() + timezone.timedelta(days=1)).isoformat()
        }
        url = reverse('lesson-detail', args=[lesson.id])
        response = self.other_teacher_client.patch(url, data)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cannot_create_lesson_in_past(self):
        data = {
            'course_id': self.course.id,
            'topic': 'Test Lesson',
            'date': (timezone.now() - timezone.timedelta(days=1)).isoformat()
        }
        response = self.teacher_client.post(self.url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Дата урока не может быть в прошлом' in str(response.data)

    def test_create_lesson_invalid_course(self):
        """Test creating a lesson with invalid course ID"""
        data = {
            'course_id': 99999,
            'topic': 'Test Lesson',
            'date': (timezone.now() + timezone.timedelta(days=1)).isoformat()
        }
        response = self.teacher_client.post(self.url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_delete_lesson(self):
        """Test that teachers can delete their lessons"""
        lesson = Lesson.objects.create(
            course=self.course,
            topic='Test Lesson',
            date=timezone.now() + timezone.timedelta(days=1)
        )
        url = reverse('lesson-detail', args=[lesson.id])
        response = self.teacher_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Lesson.objects.filter(id=lesson.id).exists()

    def test_retrieve_lesson(self):
        """Test retrieving a single lesson"""
        lesson = Lesson.objects.create(
            course=self.course,
            topic='Test Lesson',
            date=timezone.now() + timezone.timedelta(days=1)
        )
        url = reverse('lesson-detail', args=[lesson.id])
        response = self.teacher_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['topic'] == 'Test Lesson'

    def test_student_view_lesson(self):
        """Test that a student can view lessons from their courses"""
        lesson = Lesson.objects.create(
            course=self.course,
            topic='Test Lesson',
            date=timezone.now() + timezone.timedelta(days=1)
        )
        url = reverse('lesson-detail', args=[lesson.id])
        response = self.student_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['topic'] == 'Test Lesson' 