import pytest
from django.urls import reverse
from rest_framework import status
from api.models import Group
import uuid

@pytest.mark.django_db
class TestGroupAPI:
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