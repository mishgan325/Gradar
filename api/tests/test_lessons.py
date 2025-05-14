import pytest
from django.urls import reverse
from rest_framework import status
from api.models import Lesson, Course, Group
from django.utils import timezone
import uuid

@pytest.mark.django_db
class TestLessonAPI:
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
        
        # Test student view
        response = self.student_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_update_lesson(self):
        # Create a lesson
        lesson = Lesson.objects.create(
            course=self.course,
            topic='Test Lesson',
            date=timezone.now() + timezone.timedelta(days=1)
        )
        
        data = {'topic': 'Updated Lesson'}
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
        
        # Create another teacher
        other_client, other_teacher = auth_client(role='teacher')
        
        data = {'topic': 'Updated Lesson'}
        url = reverse('lesson-detail', args=[lesson.id])
        response = other_client.patch(url, data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_create_lesson_in_past(self):
        data = {
            'course_id': self.course.id,
            'topic': 'Test Lesson',
            'date': (timezone.now() - timezone.timedelta(days=1)).isoformat()
        }
        response = self.teacher_client.post(self.url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'cannot be in the past' in str(response.data['error'])

    def test_list_lessons_student(self, auth_client, test_group, create_user):
        """Test that a student can only see lessons from courses they are enrolled in"""
        # Create a student and add them to a group
        client, student = auth_client(role='student')
        group = test_group
        
        # Create a course and assign the group to it
        teacher_client, teacher = auth_client(role='teacher')
        course_data = {
            'title': f'Test Course {uuid.uuid4().hex}',
            'semester': 'spring',
            'year': 2024,
            'description': 'Test course description'
        }
        response = teacher_client.post(reverse('course-list'), course_data)
        assert response.status_code == status.HTTP_201_CREATED
        course_id = response.data['id']
        
        # Add group to course
        add_group_url = reverse('course-add-group', args=[course_id])
        response = teacher_client.post(add_group_url, {'group_id': group['id']})
        assert response.status_code == status.HTTP_200_OK

        # Create a lesson
        lesson_data = {
            'course_id': course_id,
            'date': (timezone.now() + timezone.timedelta(days=1)).isoformat(),
            'topic': 'Test Lesson'
        }
        response = teacher_client.post(reverse('lesson-list'), lesson_data)
        assert response.status_code == status.HTTP_201_CREATED

        # Test student can see the lesson
        response = client.get(reverse('lesson-list'))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['topic'] == 'Test Lesson'

    def test_list_lessons_teacher(self, auth_client):
        """Test that a teacher can see their lessons"""
        client, teacher = auth_client(role='teacher')
        
        # Create a course
        course_data = {
            'title': f'Test Course {uuid.uuid4().hex}',
            'semester': 'spring',
            'year': 2024,
            'description': 'Test course description'
        }
        response = client.post(reverse('course-list'), course_data)
        assert response.status_code == status.HTTP_201_CREATED
        course_id = response.data['id']

        # Create a lesson
        lesson_data = {
            'course_id': course_id,
            'date': (timezone.now() + timezone.timedelta(days=1)).isoformat(),
            'topic': 'Test Lesson'
        }
        response = client.post(reverse('lesson-list'), lesson_data)
        assert response.status_code == status.HTTP_201_CREATED

        # Test teacher can see their lesson
        response = client.get(reverse('lesson-list'))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['topic'] == 'Test Lesson'

    def test_create_lesson_student(self, auth_client, test_group):
        """Test that students cannot create lessons"""
        # Create a course first
        teacher_client, teacher = auth_client(role='teacher')
        course_data = {
            'title': f'Test Course {uuid.uuid4().hex}',
            'semester': 'spring',
            'year': 2024
        }
        response = teacher_client.post(reverse('course-list'), course_data)
        course_id = response.data['id']

        # Try to create a lesson as student
        client, _ = auth_client(role='student')
        lesson_data = {
            'course_id': course_id,
            'date': (timezone.now() + timezone.timedelta(days=1)).isoformat(),
            'topic': 'Test Lesson'
        }
        response = client.post(reverse('lesson-list'), lesson_data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_lesson_teacher(self, auth_client):
        """Test that teachers can create lessons"""
        client, _ = auth_client(role='teacher')
        
        # Create a course
        course_data = {
            'title': f'Test Course {uuid.uuid4().hex}',
            'semester': 'spring',
            'year': 2024
        }
        response = client.post(reverse('course-list'), course_data)
        course_id = response.data['id']

        # Create a lesson
        lesson_data = {
            'course_id': course_id,
            'date': (timezone.now() + timezone.timedelta(days=1)).isoformat(),
            'topic': 'Test Lesson'
        }
        response = client.post(reverse('lesson-list'), lesson_data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['topic'] == lesson_data['topic']

    def test_update_lesson_teacher(self, auth_client):
        """Test that teachers can update their lessons"""
        client, _ = auth_client(role='teacher')
        
        # Create a course
        course_data = {
            'title': f'Test Course {uuid.uuid4().hex}',
            'semester': 'spring',
            'year': 2024
        }
        response = client.post(reverse('course-list'), course_data)
        course_id = response.data['id']

        # Create a lesson
        lesson_data = {
            'course_id': course_id,
            'date': (timezone.now() + timezone.timedelta(days=1)).isoformat(),
            'topic': 'Test Lesson'
        }
        response = client.post(reverse('lesson-list'), lesson_data)
        assert response.status_code == status.HTTP_201_CREATED
        lesson_id = response.data['id']

        # Update the lesson
        update_data = {
            'topic': 'Updated Lesson'
        }
        response = client.patch(reverse('lesson-detail', args=[lesson_id]), update_data)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['topic'] == update_data['topic']

    def test_update_lesson_other_teacher(self, auth_client):
        """Test that teachers cannot update other teachers' lessons"""
        # First teacher creates a course and lesson
        client1, _ = auth_client(role='teacher')
        course_data = {
            'title': f'Test Course {uuid.uuid4().hex}',
            'semester': 'spring',
            'year': 2024
        }
        response = client1.post(reverse('course-list'), course_data)
        course_id = response.data['id']

        lesson_data = {
            'course_id': course_id,
            'date': (timezone.now() + timezone.timedelta(days=1)).isoformat(),
            'topic': 'Test Lesson'
        }
        response = client1.post(reverse('lesson-list'), lesson_data)
        lesson_id = response.data['id']

        # Second teacher tries to update it
        client2, _ = auth_client(role='teacher')
        update_data = {'topic': 'Updated Lesson'}
        response = client2.patch(reverse('lesson-detail', args=[lesson_id]), update_data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_lesson_teacher(self, auth_client):
        """Test that teachers can delete their lessons"""
        client, _ = auth_client(role='teacher')
        
        # Create a course
        course_data = {
            'title': f'Test Course {uuid.uuid4().hex}',
            'semester': 'spring',
            'year': 2024
        }
        response = client.post(reverse('course-list'), course_data)
        course_id = response.data['id']

        # Create a lesson
        lesson_data = {
            'course_id': course_id,
            'date': (timezone.now() + timezone.timedelta(days=1)).isoformat(),
            'topic': 'Test Lesson'
        }
        response = client.post(reverse('lesson-list'), lesson_data)
        assert response.status_code == status.HTTP_201_CREATED
        lesson_id = response.data['id']

        # Delete the lesson
        response = client.delete(reverse('lesson-detail', args=[lesson_id]))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Lesson.objects.filter(id=lesson_id).exists()

    def test_create_lesson_invalid_course(self, auth_client):
        """Test creating a lesson with invalid course ID"""
        client, _ = auth_client(role='teacher')
        
        lesson_data = {
            'course_id': 999999,  # Non-existent course ID
            'date': (datetime.now() + timedelta(days=1)).isoformat(),
            'topic': 'Test Lesson'
        }
        response = client.post(reverse('lesson-list'), lesson_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_lesson_past_date(self, auth_client):
        """Test creating a lesson with a past date"""
        client, _ = auth_client(role='teacher')
        
        # Create a course
        course_data = {
            'title': f'Test Course {uuid.uuid4().hex}',
            'semester': 'spring',
            'year': 2024
        }
        response = client.post(reverse('course-list'), course_data)
        course_id = response.data['id']

        # Try to create a lesson with past date
        lesson_data = {
            'course_id': course_id,
            'date': (datetime.now() - timedelta(days=1)).isoformat(),
            'topic': 'Test Lesson'
        }
        response = client.post(reverse('lesson-list'), lesson_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_lesson_as_teacher(self, auth_client, create_course):
        client, teacher = auth_client(role='teacher')
        course = create_course(teacher=teacher)
        url = reverse('lesson-list')
        data = {
            'title': 'Test Lesson',
            'description': 'Test Description',
            'course': course.id,
            'date': (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
            'start_time': '10:00:00',
            'end_time': '11:00:00'
        }
        response = client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert Lesson.objects.filter(title='Test Lesson').exists()

    def test_create_lesson_as_student_forbidden(self, auth_client, create_course):
        client, student = auth_client(role='student')
        teacher_client, teacher = auth_client(role='teacher')
        course = create_course(teacher=teacher)
        url = reverse('lesson-list')
        data = {
            'title': 'Test Lesson',
            'description': 'Test Description',
            'course': course.id,
            'date': (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
            'start_time': '10:00:00',
            'end_time': '11:00:00'
        }
        response = client.post(url, data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_lessons(self, auth_client, create_course, create_lesson):
        client, teacher = auth_client(role='teacher')
        course = create_course(teacher=teacher)
        lesson = create_lesson(course=course)
        url = reverse('lesson-list')
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['title'] == lesson.title

    def test_retrieve_lesson(self, auth_client, create_course, create_lesson):
        client, teacher = auth_client(role='teacher')
        course = create_course(teacher=teacher)
        lesson = create_lesson(course=course)
        url = reverse('lesson-detail', args=[lesson.id])
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == lesson.title

    def test_update_lesson(self, auth_client, create_course, create_lesson):
        client, teacher = auth_client(role='teacher')
        course = create_course(teacher=teacher)
        lesson = create_lesson(course=course)
        url = reverse('lesson-detail', args=[lesson.id])
        data = {
            'title': 'Updated Lesson',
            'description': 'Updated Description',
            'course': course.id,
            'date': (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
            'start_time': '10:00:00',
            'end_time': '11:00:00'
        }
        response = client.put(url, data)
        assert response.status_code == status.HTTP_200_OK
        assert Lesson.objects.get(id=lesson.id).title == 'Updated Lesson'

    def test_delete_lesson(self, auth_client, create_course, create_lesson):
        client, teacher = auth_client(role='teacher')
        course = create_course(teacher=teacher)
        lesson = create_lesson(course=course)
        url = reverse('lesson-detail', args=[lesson.id])
        response = client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Lesson.objects.filter(id=lesson.id).exists()

    def test_student_view_lesson(self, auth_client, create_course, create_lesson):
        client, student = auth_client(role='student')
        teacher_client, teacher = auth_client(role='teacher')
        course = create_course(teacher=teacher)
        course.students.add(student)
        lesson = create_lesson(course=course)
        url = reverse('lesson-detail', args=[lesson.id])
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == lesson.title 