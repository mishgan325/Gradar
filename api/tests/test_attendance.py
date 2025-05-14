import pytest
from django.urls import reverse
from rest_framework import status
from api.models import Attendance, Lesson, Course, Group, User
from django.utils import timezone
import uuid

@pytest.mark.django_db
class TestAttendanceAPI:
    @pytest.fixture(autouse=True)
    def setup(self, auth_client):
        self.student_client, self.student = auth_client(role='student')
        self.teacher_client, self.teacher = auth_client(role='teacher')
        
        # Create course
        self.course = Course.objects.create(
            name='Test Course',
            description='Test Description',
            semester='spring',
            year=2024,
            teacher=self.teacher
        )
        
        # Create group and add student
        self.group = Group.objects.create(
            name=f'Test Group {uuid.uuid4().hex}',
            year=2024
        )
        self.group.students.add(self.student)
        self.course.groups.add(self.group)
        
        # Create lesson
        self.lesson = Lesson.objects.create(
            course=self.course,
            topic='Test Lesson',
            date=timezone.now() + timezone.timedelta(days=1)
        )
        
        self.url = reverse('attendance-list')

    def test_create_attendance(self):
        """Test creating attendance record"""
        data = {
            'student_id': self.student.id,
            'lesson_id': self.lesson.id,
            'is_present': True
        }
        print(f"\nTest data: {data}")
        print(f"Student exists: {User.objects.filter(id=self.student.id).exists()}")
        print(f"Lesson exists: {self.lesson.id in Lesson.objects.values_list('id', flat=True)}")
        print(f"Student in course groups: {self.student.student_groups.filter(courses=self.lesson.course).exists()}")
        
        response = self.teacher_client.post(self.url, data)
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.data}")
        
        assert response.status_code == status.HTTP_201_CREATED
        assert Attendance.objects.count() == 1
        attendance = Attendance.objects.first()
        assert attendance.student == self.student
        assert attendance.lesson == self.lesson
        assert attendance.is_present is True

    def test_student_cannot_create_attendance(self):
        """Test that students cannot create attendance records"""
        data = {
            'student_id': self.student.id,
            'lesson_id': self.lesson.id,
            'is_present': True
        }
        response = self.student_client.post(self.url, data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_attendance(self):
        """Test listing attendance records"""
        # Create attendance record
        Attendance.objects.create(
            student=self.student,
            lesson=self.lesson,
            is_present=True
        )
        
        # Test teacher view
        response = self.teacher_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        
        # Test student view
        response = self.student_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_update_attendance(self):
        """Test updating attendance record"""
        # Create attendance record
        attendance = Attendance.objects.create(
            student=self.student,
            lesson=self.lesson,
            is_present=True
        )
        
        data = {'is_present': False}
        url = reverse('attendance-detail', args=[attendance.id])
        response = self.teacher_client.patch(url, data)
        assert response.status_code == status.HTTP_200_OK
        attendance.refresh_from_db()
        assert attendance.is_present is False

    def test_student_cannot_update_attendance(self):
        """Test that students cannot update attendance records"""
        attendance = Attendance.objects.create(
            student=self.student,
            lesson=self.lesson,
            is_present=True
        )
        
        data = {'is_present': False}
        url = reverse('attendance-detail', args=[attendance.id])
        response = self.student_client.patch(url, data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_invalid_attendance_data(self):
        """Test that invalid data is rejected"""
        data = {
            'student_id': self.student.id,
            'lesson_id': 999999,  # Non-existent lesson
            'is_present': True
        }
        response = self.teacher_client.post(self.url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_duplicate_attendance(self):
        """Test that duplicate attendance records are rejected"""
        # Create first attendance
        Attendance.objects.create(
            student=self.student,
            lesson=self.lesson,
            is_present=True
        )
        
        # Try to create duplicate
        data = {
            'student_id': self.student.id,
            'lesson_id': self.lesson.id,
            'is_present': False
        }
        response = self.teacher_client.post(self.url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_attendance_student_not_in_course(self, auth_client):
        """Test that attendance can't be created for student not in course"""
        # Create another student not in the course
        other_client, other_student = auth_client(role='student')
        
        data = {
            'student_id': other_student.id,
            'lesson_id': self.lesson.id,
            'is_present': True
        }
        response = self.teacher_client.post(self.url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST 