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
            'student_id': self.student.id,
            'value': 5
        }
        response = self.teacher_client.post(self.url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

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

    def test_other_teacher_cannot_update_grade(self, auth_client):
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
            'student_id': self.student.id,
            'value': 6  # Invalid value (should be 1-5)
        }
        response = self.teacher_client.post(self.url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Поле 'lesson_id' обязательно" in str(response.data)

    def test_list_grades_student(self, auth_client, test_group, create_user):
        """Test that a student can only see their own grades"""
        # Create a student and add them to a group
        client, student = auth_client(role='student')
        group = Group.objects.create(name=f'Test Group {uuid.uuid4().hex}', year=2024)
        group.students.add(student)
        
        # Create a course and assign the group to it
        teacher_client, teacher = auth_client(role='teacher')
        course_data = {
            'name': f'Test Course {uuid.uuid4().hex}',
            'description': 'Test course description',
            'semester': 'spring',
            'year': 2024,
            'teacher': teacher
        }
        course = Course.objects.create(**course_data)
        course.groups.add(group)
        
        # Create a lesson
        lesson = Lesson.objects.create(
            course=course,
            topic='Test Lesson',
            date=timezone.now() + timezone.timedelta(days=1)
        )

        # Create grade
        grade_data = {
            'lesson_id': lesson.id,
            'student_id': student.id,
            'value': 85,
            'comment': 'Good work'
        }
        Grade.objects.create(
            lesson=lesson,
            student=student,
            value=85,
            comment='Good work'
        )

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
            'name': f'Test Course {uuid.uuid4().hex}',
            'description': 'Test course description',
            'semester': 'spring',
            'year': 2024,
            'teacher': teacher
        }
        course = Course.objects.create(**course_data)

        # Create a lesson
        lesson = Lesson.objects.create(
            course=course,
            topic='Test Lesson',
            date=timezone.now() + timezone.timedelta(days=1)
        )

        # Create a student and add them to a group
        student_client, student = auth_client(role='student')
        group = Group.objects.create(name=f'Test Group {uuid.uuid4().hex}', year=2024)
        group.students.add(student)
        course.groups.add(group)

        # Create grade
        Grade.objects.create(
            lesson=lesson,
            student=student,
            value=90,
            comment='Excellent work'
        )

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
        course = Course.objects.create(
            name=f'Test Course {uuid.uuid4().hex}',
            description='Test course description',
            semester='spring',
            year=2024,
            teacher=teacher
        )

        # Create a lesson
        lesson = Lesson.objects.create(
            course=course,
            topic='Test Lesson',
            date=timezone.now() + timezone.timedelta(days=1)
        )

        # Try to create grade as student
        client, student = auth_client(role='student')
        group = Group.objects.create(name=f'Test Group {uuid.uuid4().hex}', year=2024)
        group.students.add(student)
        course.groups.add(group)

        grade_data = {
            'lesson_id': lesson.id,
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
        course = Course.objects.create(
            name=f'Test Course {uuid.uuid4().hex}',
            description='Test course description',
            semester='spring',
            year=2024,
            teacher=teacher
        )

        # Create a lesson
        lesson = Lesson.objects.create(
            course=course,
            topic='Test Lesson',
            date=timezone.now() + timezone.timedelta(days=1)
        )

        # Create a student and add them to a group
        student_client, student = auth_client(role='student')
        group = Group.objects.create(name=f'Test Group {uuid.uuid4().hex}', year=2024)
        group.students.add(student)
        course.groups.add(group)

        # Create grade
        grade_data = {
            'lesson_id': lesson.id,
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
        course = Course.objects.create(
            name=f'Test Course {uuid.uuid4().hex}',
            description='Test course description',
            semester='spring',
            year=2024,
            teacher=teacher
        )

        # Create a lesson
        lesson = Lesson.objects.create(
            course=course,
            topic='Test Lesson',
            date=timezone.now() + timezone.timedelta(days=1)
        )

        # Create a student and add them to a group
        student_client, student = auth_client(role='student')
        group = Group.objects.create(name=f'Test Group {uuid.uuid4().hex}', year=2024)
        group.students.add(student)
        course.groups.add(group)

        # Create grade
        grade = Grade.objects.create(
            lesson=lesson,
            student=student,
            value=85,
            comment='Good work'
        )

        # Update grade
        update_data = {
            'value': 90,
            'comment': 'Updated: Excellent work'
        }
        response = client.patch(reverse('grade-detail', args=[grade.id]), update_data)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['value'] == 90
        assert response.data['comment'] == 'Updated: Excellent work'

    def test_update_grade_other_teacher(self, auth_client):
        """Test that teachers cannot update grades for other teachers' courses"""
        # First teacher creates course, lesson and grade
        client1, teacher1 = auth_client(role='teacher')
        course = Course.objects.create(
            name=f'Test Course {uuid.uuid4().hex}',
            description='Test course description',
            semester='spring',
            year=2024,
            teacher=teacher1
        )

        # Create a lesson
        lesson = Lesson.objects.create(
            course=course,
            topic='Test Lesson',
            date=timezone.now() + timezone.timedelta(days=1)
        )

        # Create a student and add them to a group
        student_client, student = auth_client(role='student')
        group = Group.objects.create(name=f'Test Group {uuid.uuid4().hex}', year=2024)
        group.students.add(student)
        course.groups.add(group)

        # Create grade
        grade = Grade.objects.create(
            lesson=lesson,
            student=student,
            value=85,
            comment='Good work'
        )

        # Second teacher tries to update it
        client2, teacher2 = auth_client(role='teacher')
        update_data = {
            'value': 70,
            'comment': 'Changed by other teacher'
        }
        response = client2.patch(reverse('grade-detail', args=[grade.id]), update_data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_grade_teacher(self, auth_client):
        """Test that teachers can delete grades"""
        client, teacher = auth_client(role='teacher')
        
        # Create a course
        course = Course.objects.create(
            name=f'Test Course {uuid.uuid4().hex}',
            description='Test course description',
            semester='spring',
            year=2024,
            teacher=teacher
        )

        # Create a lesson
        lesson = Lesson.objects.create(
            course=course,
            topic='Test Lesson',
            date=timezone.now() + timezone.timedelta(days=1)
        )

        # Create a student and add them to a group
        student_client, student = auth_client(role='student')
        group = Group.objects.create(name=f'Test Group {uuid.uuid4().hex}', year=2024)
        group.students.add(student)
        course.groups.add(group)

        # Create grade
        grade = Grade.objects.create(
            lesson=lesson,
            student=student,
            value=85,
            comment='Good work'
        )

        # Delete grade
        response = client.delete(reverse('grade-detail', args=[grade.id]))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Grade.objects.filter(id=grade.id).exists()

    def test_create_invalid_grade_value(self, auth_client):
        """Test that invalid grade values are rejected"""
        client, teacher = auth_client(role='teacher')
        
        # Create a course
        course = Course.objects.create(
            name=f'Test Course {uuid.uuid4().hex}',
            description='Test course description',
            semester='spring',
            year=2024,
            teacher=teacher
        )

        # Create a lesson
        lesson = Lesson.objects.create(
            course=course,
            topic='Test Lesson',
            date=timezone.now() + timezone.timedelta(days=1)
        )

        # Create a student and add them to a group
        student_client, student = auth_client(role='student')
        group = Group.objects.create(name=f'Test Group {uuid.uuid4().hex}', year=2024)
        group.students.add(student)
        course.groups.add(group)

        # Try to create grade with invalid value
        grade_data = {
            'lesson_id': lesson.id,
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
        course = Course.objects.create(
            name=f'Test Course {uuid.uuid4().hex}',
            description='Test course description',
            semester='spring',
            year=2024,
            teacher=teacher
        )

        # Create a lesson
        lesson = Lesson.objects.create(
            course=course,
            topic='Test Lesson',
            date=timezone.now() + timezone.timedelta(days=1)
        )

        # Create a student but don't add them to the course
        student_client, student = auth_client(role='student')

        # Try to create grade for student not in course
        grade_data = {
            'lesson_id': lesson.id,
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

    def test_bulk_assign_grades(self, auth_client):
        """Test bulk assigning grades to multiple students"""
        # Create teacher and students
        teacher_client, teacher = auth_client(role='teacher')
        student1_client, student1 = auth_client(role='student')
        student2_client, student2 = auth_client(role='student')

        # Create course and group
        course = Course.objects.create(
            name=f'Test Course {uuid.uuid4().hex}',
            description='Test course description',
            semester='spring',
            year=2024,
            teacher=teacher
        )
        group = Group.objects.create(name=f'Test Group {uuid.uuid4().hex}', year=2024)
        group.students.add(student1, student2)
        course.groups.add(group)

        # Create lesson
        lesson = Lesson.objects.create(
            course=course,
            topic='Test Lesson',
            date=timezone.now() + timezone.timedelta(days=1)
        )

        # Bulk assign grades
        data = [
            {'student_id': student1.id, 'value': 85},
            {'student_id': student2.id, 'value': 90}
        ]
        response = teacher_client.post(f'/api/lessons/{lesson.id}/bulk_grades/', data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) == 2

    def test_get_student_course_grades(self, auth_client):
        """Test retrieving all grades for a student in a course"""
        # Create teacher and student
        teacher_client, teacher = auth_client(role='teacher')
        student_client, student = auth_client(role='student')

        # Create course and group
        course = Course.objects.create(
            name=f'Test Course {uuid.uuid4().hex}',
            description='Test course description',
            semester='spring',
            year=2024,
            teacher=teacher
        )
        group = Group.objects.create(name=f'Test Group {uuid.uuid4().hex}', year=2024)
        group.students.add(student)
        course.groups.add(group)

        # Create lessons and grades
        lesson1 = Lesson.objects.create(
            course=course,
            topic='Test Lesson 1',
            date=timezone.now() + timezone.timedelta(days=1)
        )
        lesson2 = Lesson.objects.create(
            course=course,
            topic='Test Lesson 2',
            date=timezone.now() + timezone.timedelta(days=2)
        )
        
        Grade.objects.create(lesson=lesson1, student=student, value=85)
        Grade.objects.create(lesson=lesson2, student=student, value=90)

        # Get grades
        response = student_client.get(f'/api/courses/{course.id}/my-grades/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2
        assert response.data[0]['value'] in [85, 90]
        assert response.data[1]['value'] in [85, 90] 