import pytest
from django.urls import reverse
from rest_framework import status
from api.models import Group
import uuid

@pytest.mark.django_db
class TestGroupAPI:
    @pytest.fixture(autouse=True)
    def setup(self, auth_client):
        self.student_client, self.student = auth_client(role='student')
        self.teacher_client, self.teacher = auth_client(role='teacher')
        self.url = reverse('group-list')

    def test_create_group(self):
        data = {
            'name': 'Test Group',
            'year': 2024
        }
        response = self.teacher_client.post(self.url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert Group.objects.count() == 1
        group = Group.objects.first()
        assert group.name == 'Test Group'
        assert group.year == 2024

    def test_student_cannot_create_group(self):
        data = {
            'name': 'Test Group',
            'year': 2024
        }
        response = self.student_client.post(self.url, data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_groups(self):
        # Create a group
        group = Group.objects.create(name='Test Group', year=2024)
        group.students.add(self.student)
        
        # Test teacher view
        response = self.teacher_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        
        # Test student view
        response = self.student_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_update_group(self):
        # Create a group
        group = Group.objects.create(name='Test Group', year=2024)
        
        data = {'name': 'Updated Group'}
        url = reverse('group-detail', args=[group.id])
        response = self.teacher_client.patch(url, data)
        assert response.status_code == status.HTTP_200_OK
        group.refresh_from_db()
        assert group.name == 'Updated Group'

    def test_add_student_to_group(self):
        # Create a group
        group = Group.objects.create(name='Test Group', year=2024)
        
        data = {'student_ids': [self.student.id]}
        url = reverse('group-detail', args=[group.id])
        response = self.teacher_client.patch(url, data)
        assert response.status_code == status.HTTP_200_OK
        group.refresh_from_db()
        assert group.students.count() == 1
        assert group.students.first() == self.student

    def test_student_single_group_validation(self):
        # Create first group and add student
        group1 = Group.objects.create(name='Test Group 1', year=2024)
        group1.students.add(self.student)
        
        # Try to add student to second group
        group2 = Group.objects.create(name='Test Group 2', year=2024)
        data = {'student_ids': [self.student.id]}
        url = reverse('group-detail', args=[group2.id])
        response = self.teacher_client.patch(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'уже состоит в группе' in str(response.data['error'])

    def test_list_groups_student(self, auth_client):
        """Test that students can only see their own groups"""
        client, user = auth_client(role='student')
        url = reverse('group-list')
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_list_groups_teacher(self, auth_client):
        """Test that teachers can see all groups"""
        client, _ = auth_client(role='teacher')
        url = reverse('group-list')
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_create_group_unauthorized(self, api_client):
        """Test that unauthorized users cannot create groups"""
        url = reverse('group-list')
        data = {'name': 'New Group'}
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_group_student(self, auth_client):
        """Test that students cannot create groups"""
        client, _ = auth_client(role='student')
        url = reverse('group-list')
        data = {
            'name': f'Test Group {uuid.uuid4().hex}',
            'description': 'Test group description'
        }
        response = client.post(url, data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_group_teacher(self, auth_client):
        """Test that teachers can create groups"""
        client, _ = auth_client(role='teacher')
        url = reverse('group-list')
        group_name = f'Test Group {uuid.uuid4().hex}'
        data = {
            'name': group_name,
            'description': 'Test group description'
        }
        response = client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == group_name

    @pytest.fixture
    def test_group(self, auth_client):
        """Create a test group"""
        client, _ = auth_client(role='teacher')
        url = reverse('group-list')
        data = {'name': 'Test Group'}
        response = client.post(url, data)
        return response.data

    def test_retrieve_group(self, auth_client, test_group):
        """Test retrieving group details"""
        client, _ = auth_client(role='teacher')
        url = reverse('group-detail', args=[test_group['id']])
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == test_group['name']

    def test_update_group_teacher(self, auth_client, test_group):
        """Test that teachers can update groups"""
        client, _ = auth_client(role='teacher')
        url = reverse('group-detail', args=[test_group['id']])
        new_name = f'Updated Group {uuid.uuid4().hex}'
        data = {
            'name': new_name,
            'description': 'Updated description'
        }
        response = client.patch(url, data)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == new_name

    def test_update_group_student(self, auth_client, test_group):
        """Test that students cannot update groups"""
        client, _ = auth_client(role='student')
        url = reverse('group-detail', args=[test_group['id']])
        data = {
            'name': 'Updated Group',
            'description': 'Updated description'
        }
        response = client.patch(url, data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_group_teacher(self, auth_client, test_group):
        """Test that teachers can delete groups"""
        client, _ = auth_client(role='teacher')
        url = reverse('group-detail', args=[test_group['id']])
        response = client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        # Verify group was deleted
        assert not Group.objects.filter(id=test_group['id']).exists()

    def test_delete_group_student(self, auth_client, test_group):
        """Test that students cannot delete groups"""
        client, _ = auth_client(role='student')
        url = reverse('group-detail', args=[test_group['id']])
        response = client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        # Verify group still exists
        assert Group.objects.filter(id=test_group['id']).exists()

    def test_add_student_to_group(self, auth_client, test_group, create_user):
        """Test adding a student to a group"""
        client, _ = auth_client(role='teacher')
        student = create_user(role='student')
        url = reverse('group-add-student', args=[test_group['id']])
        data = {'student_id': student.id}
        response = client.post(url, data)
        assert response.status_code == status.HTTP_200_OK
        # Verify student was added to group
        group = Group.objects.get(id=test_group['id'])
        assert student in group.students.all()

    def test_remove_student_from_group(self, auth_client, test_group, create_user):
        """Test removing a student from a group"""
        client, _ = auth_client(role='teacher')
        student = create_user(role='student')
        
        # First add the student to the group
        group = Group.objects.get(id=test_group['id'])
        group.students.add(student)
        
        url = reverse('group-remove-student', args=[test_group['id']])
        data = {'student_id': student.id}
        response = client.post(url, data)
        assert response.status_code == status.HTTP_200_OK
        # Verify student was removed from group
        group.refresh_from_db()
        assert student not in group.students.all()

    def test_create_group_as_teacher(self, auth_client):
        client, teacher = auth_client(role='teacher')
        url = reverse('group-list')
        data = {
            'name': 'Test Group',
            'year': 2024
        }
        response = client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert Group.objects.filter(name='Test Group').exists()

    def test_create_group_as_student_forbidden(self, auth_client):
        client, student = auth_client(role='student')
        url = reverse('group-list')
        data = {
            'name': 'Test Group',
            'year': 2024
        }
        response = client.post(url, data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_group_students(self, auth_client, create_group):
        client, teacher = auth_client(role='teacher')
        student_client1, student1 = auth_client(role='student')
        student_client2, student2 = auth_client(role='student')
        group = create_group()
        group.students.add(student1, student2)
        
        url = reverse('group-students', args=[group.id])
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2
        student_ids = [student['id'] for student in response.data]
        assert student1.id in student_ids
        assert student2.id in student_ids

    def test_bulk_add_students_to_group(self, auth_client, create_group):
        client, teacher = auth_client(role='teacher')
        student_client1, student1 = auth_client(role='student')
        student_client2, student2 = auth_client(role='student')
        group = create_group()
        
        url = reverse('group-bulk-add-students', args=[group.id])
        data = {'student_ids': [student1.id, student2.id]}
        response = client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert student1 in group.students.all()
        assert student2 in group.students.all() 