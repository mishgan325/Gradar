import pytest
from django.urls import reverse
from rest_framework import status
from api.models import Course, Group
import uuid

@pytest.mark.django_db
class TestCourseAPI:
    @pytest.fixture(autouse=True)
    def setup(self, auth_client):
        self.student_client, self.student = auth_client(role='student')
        self.teacher_client, self.teacher = auth_client(role='teacher')
        self.url = reverse('course-list')

    def test_create_course(self):
        data = {
            'name': 'Test Course',
            'description': 'Test Description',
            'semester': 'spring',
            'year': 2024
        }
        response = self.teacher_client.post(self.url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert Course.objects.count() == 1
        course = Course.objects.first()
        assert course.name == 'Test Course'
        assert course.teacher == self.teacher

    def test_student_cannot_create_course(self):
        data = {
            'name': 'Test Course',
            'description': 'Test Description',
            'semester': 'spring',
            'year': 2024
        }
        response = self.student_client.post(self.url, data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_courses(self):
        # Create a course
        course = Course.objects.create(
            name='Test Course',
            description='Test Description',
            semester='spring',
            year=2024,
            teacher=self.teacher
        )
        
        # Create a group and add student to it
        group = Group.objects.create(name=f'Test Group {uuid.uuid4().hex}', year=2024)
        group.students.add(self.student)
        course.groups.add(group)
        
        # Test teacher view
        response = self.teacher_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        
        # Test student view
        response = self.student_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_update_course(self):
        # Create a course
        course = Course.objects.create(
            name='Test Course',
            description='Test Description',
            semester='spring',
            year=2024,
            teacher=self.teacher
        )
        
        data = {'name': 'Updated Course'}
        url = reverse('course-detail', args=[course.id])
        response = self.teacher_client.patch(url, data)
        assert response.status_code == status.HTTP_200_OK
        course.refresh_from_db()
        assert course.name == 'Updated Course'

    def test_other_teacher_cannot_update_course(self, auth_client):
        """Test that teachers cannot update other teachers' courses"""
        # First teacher creates a course
        client1, teacher1 = auth_client(role='teacher')
        course_data = {
            'name': f'Test Course {uuid.uuid4().hex}',
            'description': 'Test Description',
            'semester': 'spring',
            'year': 2024
        }
        response = client1.post(reverse('course-list'), course_data)
        assert response.status_code == status.HTTP_201_CREATED
        course_id = response.data['id']
        
        # Verify the course was created with correct data
        assert response.data['name'] == course_data['name']
        assert response.data['description'] == course_data['description']
        assert response.data['semester'] == course_data['semester']
        assert response.data['year'] == course_data['year']

        # Second teacher tries to update it
        client2, teacher2 = auth_client(role='teacher')
        update_data = {
            'name': 'Updated Course',
            'description': 'Updated Description',
            'semester': 'autumn'
        }
        response = client2.patch(reverse('course-detail', args=[course_id]), update_data)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Verify the course was not updated
        response = client1.get(reverse('course-detail', args=[course_id]))
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == course_data['name']
        assert response.data['description'] == course_data['description']
        assert response.data['semester'] == course_data['semester']

    def test_add_group_to_course(self):
        # Create a course
        course = Course.objects.create(
            name='Test Course',
            description='Test Description',
            semester='spring',
            year=2024,
            teacher=self.teacher
        )
        
        # Create a group
        group = Group.objects.create(name=f'Test Group {uuid.uuid4().hex}', year=2024)
        
        url = reverse('course-add-group', args=[course.id])
        response = self.teacher_client.post(url, {'group_id': group.id})
        assert response.status_code == status.HTTP_200_OK
        course.refresh_from_db()
        assert group in course.groups.all()

    def test_list_courses_student(self, auth_client, test_group):
        """Test that a student can only see courses they are enrolled in"""
        # Create a student and add them to a group
        client, student = auth_client(role='student')
        
        # Create a course and assign the group to it
        teacher_client, teacher = auth_client(role='teacher')
        course_data = {
            'name': f'Test Course {uuid.uuid4().hex}',
            'semester': 'spring',
            'year': 2024,
            'description': 'Test course description'
        }
        response = teacher_client.post(reverse('course-list'), course_data)
        assert response.status_code == status.HTTP_201_CREATED
        course_id = response.data['id']
        
        # Add student to group and group to course
        group = Group.objects.get(id=test_group['id'])
        group.students.add(student)
        course = Course.objects.get(id=course_id)
        course.groups.add(group)

        # Test student can see the course
        response = client.get(reverse('course-list'))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['name'] == course_data['name']

    def test_list_courses_teacher(self, auth_client):
        """Test that a teacher can see their courses"""
        client, teacher = auth_client(role='teacher')
        
        # Create a course
        course_data = {
            'name': f'Test Course {uuid.uuid4().hex}',
            'semester': 'spring',
            'year': 2024,
            'description': 'Test course description'
        }
        response = client.post(reverse('course-list'), course_data)
        assert response.status_code == status.HTTP_201_CREATED

        # Test teacher can see their course
        response = client.get(reverse('course-list'))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['name'] == course_data['name']

    def test_create_course_teacher(self, auth_client):
        """Test that teachers can create courses"""
        client, _ = auth_client(role='teacher')
        course_data = {
            'name': f'Test Course {uuid.uuid4().hex}',
            'semester': 'spring',
            'year': 2024,
            'description': 'Test course description'
        }
        response = client.post(reverse('course-list'), course_data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == course_data['name']
        assert response.data['semester'] == course_data['semester']
        assert response.data['year'] == course_data['year']

    def test_update_course_teacher(self, auth_client):
        """Test that teachers can update their courses"""
        client, teacher = auth_client(role='teacher')
        
        # Create a course
        course_data = {
            'name': f'Test Course {uuid.uuid4().hex}',
            'semester': 'spring',
            'year': 2024,
            'description': 'Test course description'
        }
        response = client.post(reverse('course-list'), course_data)
        print(f"\nCreate response: {response.data}")  # Debug print
        assert response.status_code == status.HTTP_201_CREATED
        course_id = response.data['id']

        # Update the course
        update_data = {
            'name': f'Updated Course {uuid.uuid4().hex}',
            'semester': 'autumn',
            'year': 2024,
            'description': 'Updated description'
        }
        print(f"\nUpdate data: {update_data}")  # Debug print
        response = client.patch(reverse('course-detail', args=[course_id]), update_data)
        print(f"\nUpdate response: {response.data}")  # Debug print
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == update_data['name']
        assert response.data['semester'] == update_data['semester']
        assert response.data['year'] == update_data['year']

    def test_delete_course_teacher(self, auth_client):
        """Test that teachers can delete their courses"""
        client, teacher = auth_client(role='teacher')
        
        # Create a course
        course_data = {
            'name': f'Test Course {uuid.uuid4().hex}',
            'semester': 'spring',
            'year': 2024,
            'description': 'Test Description'
        }
        response = client.post(reverse('course-list'), course_data)
        assert response.status_code == status.HTTP_201_CREATED
        course_id = response.data['id']

        # Delete the course
        response = client.delete(reverse('course-detail', args=[course_id]))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Course.objects.filter(id=course_id).exists()

    def test_add_nonexistent_group_to_course(self, auth_client):
        """Test adding a nonexistent group to a course"""
        client, teacher = auth_client(role='teacher')
        
        # Create a course
        course_data = {
            'name': f'Test Course {uuid.uuid4().hex}',
            'semester': 'spring',
            'year': 2024,
            'description': 'Test Description'
        }
        response = client.post(reverse('course-list'), course_data)
        assert response.status_code == status.HTTP_201_CREATED
        course_id = response.data['id']

        # Try to add nonexistent group
        url = reverse('course-add-group', args=[course_id])
        response = client.post(url, {'group_id': 999999})
        print(f"\nResponse data: {response.data}")  # Debug print
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Группа с ID 999999 не найдена" in str(response.data['error'])

    def test_create_course_as_teacher(self, auth_client):
        client, teacher = auth_client(role='teacher')
        url = reverse('course-list')
        data = {
            'name': 'Test Course',
            'description': 'Test Description',
            'semester': 'spring',
            'year': 2024
        }
        response = client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_course_as_student_forbidden(self, auth_client):
        client, student = auth_client(role='student')
        url = reverse('course-list')
        data = {
            'name': 'Test Course',
            'description': 'Test Description'
        }
        response = client.post(url, data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_retrieve_course(self, auth_client, create_course):
        client, teacher = auth_client(role='teacher')
        course = create_course(teacher=teacher)
        url = reverse('course-detail', args=[course.id])
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == course.name

    def test_delete_course(self, auth_client, create_course):
        client, teacher = auth_client(role='teacher')
        course = create_course(teacher=teacher)
        url = reverse('course-detail', args=[course.id])
        response = client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Course.objects.filter(id=course.id).exists()

    def test_student_enrollment(self, auth_client, create_course, create_group):
        """Test that a student can be enrolled in a course through a group"""
        client, student = auth_client(role='student')
        teacher_client, teacher = auth_client(role='teacher')
        course = create_course(teacher=teacher)
        
        # Create a group and add student to it
        group = create_group()
        group.students.add(student)
        
        # Add group to course
        url = reverse('course-add-group', args=[course.id])
        response = teacher_client.post(url, {'group_id': group.id})
        assert response.status_code == status.HTTP_200_OK
        assert group.id in [g['id'] for g in response.data['groups']]
        assert student in group.students.all()

    def test_student_unenrollment(self, auth_client, create_course, create_group):
        """Test that a student can be unenrolled from a course by removing from group"""
        client, student = auth_client(role='student')
        teacher_client, teacher = auth_client(role='teacher')
        course = create_course(teacher=teacher)
        
        # Create a group, add student and connect to course
        group = create_group()
        group.students.add(student)
        course.groups.add(group)
        
        # Remove student from group
        group.students.remove(student)
        assert student not in group.students.all()
        # Student should no longer have access to course through this group
        assert not student.student_groups.filter(courses=course).exists() 