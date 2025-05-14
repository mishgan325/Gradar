import pytest
from django.urls import reverse
from rest_framework import status
from api.models import Grade, Lesson, Course, Group
from django.utils import timezone
import uuid

@pytest.mark.django_db
class TestGradeAPI:
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
        
        # Create lesson
        self.lesson = Lesson.objects.create(
            course=self.course,
            topic='Test Lesson',
            date=timezone.now() + timezone.timedelta(days=1)
        )
        
        self.url = reverse('grade-list')

    def test_create_grade(self):
        data = {
            'lesson_id': self.lesson.id,
            'student_id': self.student.id,
            'value': 5
        }
        response = self.teacher_client.post(self.url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert Grade.objects.count() == 1
        grade = Grade.objects.first()
        assert grade.value == 5
        assert grade.student == self.student

    def test_student_cannot_create_grade(self):
        data = {
            'lesson_id': self.lesson.id,
            'student_id': self.student.id,
            'value': 5
        }
        response = self.student_client.post(self.url, data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_grades(self):
        # Create a grade
        Grade.objects.create(
            lesson=self.lesson,
            student=self.student,
            value=5
        )
        
        # Test teacher view
        response = self.teacher_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        
        # Test student view
        response = self.student_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_update_grade(self):
        # Create a grade
        grade = Grade.objects.create(
            lesson=self.lesson,
            student=self.student,
            value=4
        )
        
        data = {'value': 5}
        url = reverse('grade-detail', args=[grade.id])
        response = self.teacher_client.patch(url, data)
        assert response.status_code == status.HTTP_200_OK
        grade.refresh_from_db()
        assert grade.value == 5

    def test_other_teacher_cannot_update_grade(self):
        # Create a grade
        grade = Grade.objects.create(
            lesson=self.lesson,
            student=self.student,
            value=4
        )
        
        # Create another teacher
        other_client, other_teacher = auth_client(role='teacher')
        
        data = {'value': 5}
        url = reverse('grade-detail', args=[grade.id])
        response = other_client.patch(url, data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_invalid_grade_value(self):
        data = {
            'lesson_id': self.lesson.id,
            'student_id': self.student.id,
            'value': 6  # Invalid value (should be 1-5)
        }
        response = self.teacher_client.post(self.url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Invalid grade value' in str(response.data['error'])

    def test_list_grades_student(self, auth_client, test_group, create_user):
        """Test that a student can only see their own grades"""
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

        # Create grade
        grade_data = {
            'lesson_id': lesson_id,
            'student_id': student.id,
            'value': 85,
            'comment': 'Good work'
        }
        response = teacher_client.post(reverse('grade-list'), grade_data)
        assert response.status_code == status.HTTP_201_CREATED

        # Test student can see their grade
        response = client.get(reverse('grade-list'))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['value'] == 85
        assert response.data[0]['comment'] == 'Good work'

    def test_list_grades_teacher(self, auth_client, test_group):
        """Test that a teacher can see grades for their courses"""
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

        # Create grade
        grade_data = {
            'lesson_id': lesson_id,
            'student_id': student.id,
            'value': 90,
            'comment': 'Excellent work'
        }
        response = client.post(reverse('grade-list'), grade_data)
        assert response.status_code == status.HTTP_201_CREATED

        # Test teacher can see the grade
        response = client.get(reverse('grade-list'))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['value'] == 90
        assert response.data[0]['comment'] == 'Excellent work'

    def test_create_grade_student(self, auth_client, test_group):
        """Test that students cannot create grades"""
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

        # Try to create grade as student
        client, student = auth_client(role='student')
        grade_data = {
            'lesson_id': lesson_id,
            'student_id': student.id,
            'value': 100,
            'comment': 'Self-grading'
        }
        response = client.post(reverse('grade-list'), grade_data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_grade_teacher(self, auth_client, test_group):
        """Test that teachers can create grades"""
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

        # Create grade
        grade_data = {
            'lesson_id': lesson_id,
            'student_id': student.id,
            'value': 95,
            'comment': 'Great performance'
        }
        response = client.post(reverse('grade-list'), grade_data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['value'] == 95
        assert response.data['comment'] == 'Great performance'

    def test_update_grade_teacher(self, auth_client, test_group):
        """Test that teachers can update grades"""
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

        # Create grade
        grade_data = {
            'lesson_id': lesson_id,
            'student_id': student.id,
            'value': 85,
            'comment': 'Good work'
        }
        response = client.post(reverse('grade-list'), grade_data)
        grade_id = response.data['id']

        # Update grade
        update_data = {
            'value': 90,
            'comment': 'Updated: Excellent work'
        }
        response = client.patch(reverse('grade-detail', args=[grade_id]), update_data)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['value'] == 90
        assert response.data['comment'] == 'Updated: Excellent work'

    def test_update_grade_other_teacher(self, auth_client, test_group):
        """Test that teachers cannot update grades for other teachers' courses"""
        # First teacher creates course, lesson and grade
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

        # Create grade
        grade_data = {
            'lesson_id': lesson_id,
            'student_id': student.id,
            'value': 85,
            'comment': 'Good work'
        }
        response = client1.post(reverse('grade-list'), grade_data)
        grade_id = response.data['id']

        # Second teacher tries to update it
        client2, teacher2 = auth_client(role='teacher')
        update_data = {
            'value': 70,
            'comment': 'Changed by other teacher'
        }
        response = client2.patch(reverse('grade-detail', args=[grade_id]), update_data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_grade_teacher(self, auth_client, test_group):
        """Test that teachers can delete grades"""
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

        # Create grade
        grade_data = {
            'lesson_id': lesson_id,
            'student_id': student.id,
            'value': 85,
            'comment': 'Good work'
        }
        response = client.post(reverse('grade-list'), grade_data)
        grade_id = response.data['id']

        # Delete grade
        response = client.delete(reverse('grade-detail', args=[grade_id]))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Grade.objects.filter(id=grade_id).exists()

    def test_create_invalid_grade_value(self, auth_client, test_group):
        """Test that invalid grade values are rejected"""
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

        # Try to create grade with invalid value
        grade_data = {
            'lesson_id': lesson_id,
            'student_id': student.id,
            'value': 101,  # Value > 100
            'comment': 'Invalid grade'
        }
        response = client.post(reverse('grade-list'), grade_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        grade_data['value'] = -1  # Value < 0
        response = client.post(reverse('grade-list'), grade_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_grade_student_not_in_course(self, auth_client):
        """Test that grades cannot be created for students not enrolled in the course"""
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

        # Try to create grade for student not in course
        grade_data = {
            'lesson_id': lesson_id,
            'student_id': student.id,
            'value': 85,
            'comment': 'Grade for non-enrolled student'
        }
        response = client.post(reverse('grade-list'), grade_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_assign_grade_as_teacher(self, auth_client, create_course, create_group):
        """Test that a teacher can assign grades"""
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
            topic='Test Lesson'
        )
        
        url = reverse('grade-list')
        data = {
            'lesson_id': lesson.id,
            'student_id': student.id,
            'value': 85,
            'comment': 'Good work'
        }
        response = teacher_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['value'] == 85

    def test_assign_grade_as_student_forbidden(self, auth_client, create_course, create_group):
        """Test that a student cannot assign grades"""
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
            topic='Test Lesson'
        )
        
        url = reverse('grade-list')
        data = {
            'lesson_id': lesson.id,
            'student_id': student.id,
            'value': 85,
            'comment': 'Good work'
        }
        response = client.post(url, data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_grades_as_teacher(self, auth_client, create_course, create_group):
        """Test that a teacher can list grades"""
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
            topic='Test Lesson'
        )
        
        # Create grade
        Grade.objects.create(
            lesson=lesson,
            student=student,
            value=85,
            comment='Good work'
        )
        
        url = reverse('grade-list')
        response = teacher_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['value'] == 85

    def test_list_grades_as_student(self, auth_client, create_course, create_group):
        """Test that a student can list their own grades"""
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
            topic='Test Lesson'
        )
        
        # Create grade
        Grade.objects.create(
            lesson=lesson,
            student=student,
            value=85,
            comment='Good work'
        )
        
        url = reverse('grade-list')
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['value'] == 85

    def test_update_grade(self, auth_client, create_course, create_group):
        """Test updating a grade"""
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
            topic='Test Lesson'
        )
        
        # Create grade
        grade = Grade.objects.create(
            lesson=lesson,
            student=student,
            value=85,
            comment='Good work'
        )
        
        url = reverse('grade-detail', args=[grade.id])
        data = {'value': 90, 'comment': 'Excellent work'}
        response = teacher_client.patch(url, data)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['value'] == 90
        assert response.data['comment'] == 'Excellent work'

    def test_bulk_assign_grades(self, auth_client, create_course, create_lesson):
        client, teacher = auth_client(role='teacher')
        course = create_course(teacher=teacher)
        lesson = create_lesson(course=course)
        student_client1, student1 = auth_client(role='student')
        student_client2, student2 = auth_client(role='student')
        course.students.add(student1, student2)
        
        url = reverse('grade-bulk-create')
        data = {
            'lesson': lesson.id,
            'grades': [
                {'student': student1.id, 'value': 85, 'comment': 'Good'},
                {'student': student2.id, 'value': 90, 'comment': 'Excellent'}
            ]
        }
        response = client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) == 2
        assert Grade.objects.filter(lesson=lesson).count() == 2

    def test_get_student_course_grades(self, auth_client, create_course, create_lesson, create_grade):
        client, student = auth_client(role='student')
        teacher_client, teacher = auth_client(role='teacher')
        course = create_course(teacher=teacher)
        lesson1 = create_lesson(course=course)
        lesson2 = create_lesson(course=course)
        course.students.add(student)
        grade1 = create_grade(lesson=lesson1, student=student, value=85)
        grade2 = create_grade(lesson=lesson2, student=student, value=90)
        
        url = reverse('grade-course-summary', args=[course.id])
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['grades']) == 2
        assert response.data['average'] == 87.5 