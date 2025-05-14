import pytest
from django.urls import reverse
from rest_framework import status
from api.models import Attendance, Lesson, Course, Group
from django.utils import timezone
import uuid

@pytest.fixture
def setup_attendance_test(auth_client):
    client, student = auth_client(role='student')
    teacher_client, teacher = auth_client(role='teacher')
    
    # Create course
    course_data = {
        'name': f'Test Course {uuid.uuid4().hex}',
        'description': 'Test Description',
        'semester': 'spring',
        'year': 2024
    }
    course = Course.objects.create(**course_data, teacher=teacher)
    
    # Create group and add student
    group = Group.objects.create(name=f'Test Group {uuid.uuid4().hex}', year=2024)
    group.students.add(student)
    course.groups.add(group)
    
    # Create lesson
    lesson = Lesson.objects.create(
        course=course,
        topic='Test Lesson',
        date=timezone.now() + timezone.timedelta(days=1)
    )
    
    return {
        'student_client': client,
        'teacher_client': teacher_client,
        'student': student,
        'teacher': teacher,
        'course': course,
        'lesson': lesson,
        'group': group
    }

@pytest.mark.django_db
class TestAttendanceAPI:
    @pytest.fixture(autouse=True)
    def setup(self, setup_attendance_test):
        self.student_client = setup_attendance_test['student_client']
        self.teacher_client = setup_attendance_test['teacher_client']
        self.student = setup_attendance_test['student']
        self.teacher = setup_attendance_test['teacher']
        self.course = setup_attendance_test['course']
        self.lesson = setup_attendance_test['lesson']
        self.group = setup_attendance_test['group']
        self.url = reverse('attendance-list')

    def test_list_attendance_student(self, auth_client, test_group, create_user):
        """Test that a student can only see their own attendance records"""
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
        lesson_id = response.data['id']

        # Create attendance record
        attendance_data = {
            'lesson_id': lesson_id,
            'student_id': student.id,
            'status': 'present'
        }
        response = teacher_client.post(reverse('attendance-list'), attendance_data)
        assert response.status_code == status.HTTP_201_CREATED

        # Test student can see their attendance
        response = client.get(reverse('attendance-list'))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['status'] == 'present'

    def test_list_attendance_teacher(self, auth_client, test_group):
        """Test that a teacher can see attendance for their courses"""
        client, teacher = auth_client(role='teacher')
        
        # Create a course
        course_data = {
            'title': f'Test Course {uuid.uuid4().hex}',
            'semester': 'spring',
            'year': 2024
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
        lesson_id = response.data['id']

        # Create a student and add them to the course via group
        student_client, student = auth_client(role='student')
        group = test_group

        # Add group to course
        add_group_url = reverse('course-add-group', args=[course_id])
        response = client.post(add_group_url, {'group_id': group['id']})
        assert response.status_code == status.HTTP_200_OK

        # Create attendance record
        attendance_data = {
            'lesson_id': lesson_id,
            'student_id': student.id,
            'status': 'present'
        }
        response = client.post(reverse('attendance-list'), attendance_data)
        assert response.status_code == status.HTTP_201_CREATED

        # Test teacher can see the attendance
        response = client.get(reverse('attendance-list'))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['status'] == 'present'

    def test_create_attendance_student(self, auth_client, test_group):
        """Test that students cannot create attendance records"""
        # Create necessary course and lesson as teacher
        teacher_client, teacher = auth_client(role='teacher')
        course_data = {
            'title': f'Test Course {uuid.uuid4().hex}',
            'semester': 'spring',
            'year': 2024
        }
        response = teacher_client.post(reverse('course-list'), course_data)
        course_id = response.data['id']

        lesson_data = {
            'course_id': course_id,
            'date': (timezone.now() + timezone.timedelta(days=1)).isoformat(),
            'topic': 'Test Lesson'
        }
        response = teacher_client.post(reverse('lesson-list'), lesson_data)
        lesson_id = response.data['id']

        # Try to create attendance as student
        client, student = auth_client(role='student')
        attendance_data = {
            'lesson_id': lesson_id,
            'student_id': student.id,
            'status': 'present'
        }
        response = client.post(reverse('attendance-list'), attendance_data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_attendance_teacher(self, auth_client, test_group):
        """Test that teachers can create attendance records"""
        client, teacher = auth_client(role='teacher')
        
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
        lesson_id = response.data['id']

        # Create a student and add them to the course via group
        student_client, student = auth_client(role='student')
        group = test_group

        # Add group to course
        add_group_url = reverse('course-add-group', args=[course_id])
        response = client.post(add_group_url, {'group_id': group['id']})
        assert response.status_code == status.HTTP_200_OK

        # Create attendance record
        attendance_data = {
            'lesson_id': lesson_id,
            'student_id': student.id,
            'status': 'present'
        }
        response = client.post(reverse('attendance-list'), attendance_data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['status'] == 'present'

    def test_update_attendance_teacher(self, auth_client, test_group):
        """Test that teachers can update attendance records"""
        client, teacher = auth_client(role='teacher')
        
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
        lesson_id = response.data['id']

        # Create a student and add them to the course via group
        student_client, student = auth_client(role='student')
        group = test_group

        # Add group to course
        add_group_url = reverse('course-add-group', args=[course_id])
        response = client.post(add_group_url, {'group_id': group['id']})
        assert response.status_code == status.HTTP_200_OK

        # Create attendance record
        attendance_data = {
            'lesson_id': lesson_id,
            'student_id': student.id,
            'status': 'present'
        }
        response = client.post(reverse('attendance-list'), attendance_data)
        attendance_id = response.data['id']

        # Update attendance
        update_data = {
            'status': 'absent'
        }
        response = client.patch(reverse('attendance-detail', args=[attendance_id]), update_data)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'absent'

    def test_update_attendance_other_teacher(self, auth_client, test_group):
        """Test that teachers cannot update attendance records for other teachers' courses"""
        # First teacher creates course, lesson and attendance
        client1, teacher1 = auth_client(role='teacher')
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

        # Create a student and add them to the course
        student_client, student = auth_client(role='student')
        group = test_group

        # Add group to course
        add_group_url = reverse('course-add-group', args=[course_id])
        response = client1.post(add_group_url, {'group_id': group['id']})
        assert response.status_code == status.HTTP_200_OK

        # Create attendance
        attendance_data = {
            'lesson_id': lesson_id,
            'student_id': student.id,
            'status': 'present'
        }
        response = client1.post(reverse('attendance-list'), attendance_data)
        attendance_id = response.data['id']

        # Second teacher tries to update it
        client2, teacher2 = auth_client(role='teacher')
        update_data = {'status': 'absent'}
        response = client2.patch(reverse('attendance-detail', args=[attendance_id]), update_data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_attendance_teacher(self, auth_client, test_group):
        """Test that teachers can delete attendance records"""
        client, teacher = auth_client(role='teacher')
        
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
        lesson_id = response.data['id']

        # Create a student and add them to the course
        student_client, student = auth_client(role='student')
        group = test_group

        # Add group to course
        add_group_url = reverse('course-add-group', args=[course_id])
        response = client.post(add_group_url, {'group_id': group['id']})
        assert response.status_code == status.HTTP_200_OK

        # Create attendance
        attendance_data = {
            'lesson_id': lesson_id,
            'student_id': student.id,
            'status': 'present'
        }
        response = client.post(reverse('attendance-list'), attendance_data)
        attendance_id = response.data['id']

        # Delete attendance
        response = client.delete(reverse('attendance-detail', args=[attendance_id]))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Attendance.objects.filter(id=attendance_id).exists()

    def test_create_duplicate_attendance(self, auth_client, test_group):
        """Test that duplicate attendance records cannot be created"""
        client, teacher = auth_client(role='teacher')
        
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
        lesson_id = response.data['id']

        # Create a student and add them to the course
        student_client, student = auth_client(role='student')
        group = test_group

        # Add group to course
        add_group_url = reverse('course-add-group', args=[course_id])
        response = client.post(add_group_url, {'group_id': group['id']})
        assert response.status_code == status.HTTP_200_OK

        # Create first attendance record
        attendance_data = {
            'lesson_id': lesson_id,
            'student_id': student.id,
            'status': 'present'
        }
        response = client.post(reverse('attendance-list'), attendance_data)
        assert response.status_code == status.HTTP_201_CREATED

        # Try to create duplicate attendance record
        response = client.post(reverse('attendance-list'), attendance_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_attendance_student_not_in_course(self, auth_client):
        """Test that attendance cannot be created for students not enrolled in the course"""
        client, teacher = auth_client(role='teacher')
        
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
        lesson_id = response.data['id']

        # Create a student but don't add them to the course
        student_client, student = auth_client(role='student')

        # Try to create attendance for student not in course
        attendance_data = {
            'lesson_id': lesson_id,
            'student_id': student.id,
            'status': 'present'
        }
        response = client.post(reverse('attendance-list'), attendance_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_mark_attendance_as_teacher(self, auth_client, create_course, create_group):
        """Test that a teacher can mark attendance"""
        client, student = auth_client(role='student')
        teacher_client, teacher = auth_client(role='teacher')
        course = create_course(teacher=teacher)
        
        # Create a group and add student to it
        group = create_group()
        group.students.add(student)
        course.groups.add(group)
        
        # Create a lesson
        lesson = Lesson.objects.create(
            course=course,
            date=timezone.now() + timezone.timedelta(days=1),
            title='Test Lesson'
        )
        
        url = reverse('attendance-list')
        data = {
            'lesson_id': lesson.id,
            'student_id': student.id,
            'status': 'present'
        }
        response = teacher_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['status'] == 'present'

    def test_mark_attendance_as_student_forbidden(self, auth_client, create_course, create_group):
        """Test that a student cannot mark attendance"""
        client, student = auth_client(role='student')
        teacher_client, teacher = auth_client(role='teacher')
        course = create_course(teacher=teacher)
        
        # Create a group and add student to it
        group = create_group()
        group.students.add(student)
        course.groups.add(group)
        
        # Create a lesson
        lesson = Lesson.objects.create(
            course=course,
            date=timezone.now() + timezone.timedelta(days=1),
            title='Test Lesson'
        )
        
        url = reverse('attendance-list')
        data = {
            'lesson_id': lesson.id,
            'student_id': student.id,
            'status': 'present'
        }
        response = client.post(url, data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_attendance_as_teacher(self, auth_client, create_course, create_group):
        """Test that a teacher can list attendance"""
        client, student = auth_client(role='student')
        teacher_client, teacher = auth_client(role='teacher')
        course = create_course(teacher=teacher)
        
        # Create a group and add student to it
        group = create_group()
        group.students.add(student)
        course.groups.add(group)
        
        # Create a lesson
        lesson = Lesson.objects.create(
            course=course,
            date=timezone.now() + timezone.timedelta(days=1),
            title='Test Lesson'
        )
        
        # Create attendance
        Attendance.objects.create(
            lesson=lesson,
            student=student,
            status='present'
        )
        
        url = reverse('attendance-list')
        response = teacher_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['status'] == 'present'

    def test_list_attendance_as_student(self, auth_client, create_course, create_group):
        """Test that a student can list their own attendance"""
        client, student = auth_client(role='student')
        teacher_client, teacher = auth_client(role='teacher')
        course = create_course(teacher=teacher)
        
        # Create a group and add student to it
        group = create_group()
        group.students.add(student)
        course.groups.add(group)
        
        # Create a lesson
        lesson = Lesson.objects.create(
            course=course,
            date=timezone.now() + timezone.timedelta(days=1),
            title='Test Lesson'
        )
        
        # Create attendance
        Attendance.objects.create(
            lesson=lesson,
            student=student,
            status='present'
        )
        
        url = reverse('attendance-list')
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['status'] == 'present'

    def test_update_attendance(self):
        # Create initial attendance
        attendance = Attendance.objects.create(
            lesson=self.lesson,
            student=self.student,
            status='present'
        )
        
        # Update attendance
        data = {'status': 'absent'}
        url = reverse('attendance-detail', args=[attendance.id])
        response = self.teacher_client.patch(url, data)
        assert response.status_code == status.HTTP_200_OK
        attendance.refresh_from_db()
        assert attendance.status == 'absent'

    def test_bulk_mark_attendance(self, auth_client, create_course, create_lesson):
        client, teacher = auth_client(role='teacher')
        course = create_course(teacher=teacher)
        lesson = create_lesson(course=course)
        student_client1, student1 = auth_client(role='student')
        student_client2, student2 = auth_client(role='student')
        course.students.add(student1, student2)
        
        url = reverse('attendance-bulk-mark')
        data = {
            'lesson': lesson.id,
            'attendance_data': [
                {'student': student1.id, 'status': 'present'},
                {'student': student2.id, 'status': 'absent'}
            ]
        }
        response = client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) == 2
        assert Attendance.objects.filter(lesson=lesson).count() == 2

    def test_create_attendance(self):
        data = {
            'lesson_id': self.lesson.id,
            'student_id': self.student.id,
            'status': 'present'
        }
        response = self.teacher_client.post(self.url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert Attendance.objects.count() == 1
        attendance = Attendance.objects.first()
        assert attendance.status == 'present'

    def test_duplicate_attendance(self):
        # Create initial attendance
        Attendance.objects.create(
            lesson=self.lesson,
            student=self.student,
            status='present'
        )
        
        # Try to create duplicate
        data = {
            'lesson_id': self.lesson.id,
            'student_id': self.student.id,
            'status': 'present'
        }
        response = self.teacher_client.post(self.url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'уже отмечена' in str(response.data['error'])

    def test_student_cannot_create_attendance(self):
        data = {
            'lesson_id': self.lesson.id,
            'student_id': self.student.id,
            'status': 'present'
        }
        response = self.student_client.post(self.url, data)
        assert response.status_code == status.HTTP_403_FORBIDDEN 