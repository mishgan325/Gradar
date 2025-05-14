import pytest
from django.urls import reverse
from rest_framework import status
from api.models import User
import uuid

@pytest.mark.django_db
class TestUserAPI:
    def test_list_users_student(self, auth_client):
        """Test that a student can only see themselves in the user list"""
        client, user = auth_client(role='student')
        url = reverse('user-list')
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['username'] == user.username

    def test_list_users_teacher(self, auth_client, create_user):
        """Test that a teacher can see all users"""
        # Create some additional users
        student1 = create_user(role='student')
        student2 = create_user(role='student')
        client, teacher = auth_client(role='teacher')
        
        url = reverse('user-list')
        response = client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 3  # teacher + 2 students

    def test_register_user(self, api_client):
        """Test that anyone can register as a student"""
        url = reverse('user-list')
        username = f'newuser_{uuid.uuid4().hex[:8]}'
        data = {
            'username': username,
            'password': 'testpass123',
            'email': f'{username}@example.com',
            'role': 'student'
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['username'] == username
        assert response.data['role'] == 'student'

    def test_register_as_teacher_forbidden(self, api_client):
        """Test that users cannot register as teachers"""
        url = reverse('user-list')
        username = f'newteacher_{uuid.uuid4().hex[:8]}'
        data = {
            'username': username,
            'password': 'testpass123',
            'email': f'{username}@example.com',
            'role': 'teacher'
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_teacher_by_teacher(self, auth_client):
        """Test that teachers can create other teachers"""
        client, _ = auth_client(role='teacher')
        url = reverse('user-list')
        username = f'newteacher_{uuid.uuid4().hex[:8]}'
        data = {
            'username': username,
            'password': 'testpass123',
            'email': f'{username}@example.com',
            'role': 'teacher'
        }
        response = client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['username'] == username
        assert response.data['role'] == 'teacher'

    def test_retrieve_user_detail(self, auth_client, create_user):
        """Test retrieving user details"""
        # Create a student
        student = create_user(role='student')
        # Create a teacher and get their client
        client, teacher = auth_client(role='teacher')
        
        url = reverse('user-detail', args=[student.id])
        response = client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['username'] == student.username

    def test_update_user(self, auth_client):
        """Test updating user details"""
        client, user = auth_client(role='student')
        url = reverse('user-detail', args=[user.id])
        data = {
            'email': f'newemail_{uuid.uuid4().hex[:8]}@example.com',
            'bio': 'New bio'
        }
        response = client.patch(url, data)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['email'] == data['email']
        assert 'bio' in response.data
        assert response.data['bio'] == data['bio']

    def test_delete_user_forbidden(self, auth_client, create_user):
        """Test that students cannot delete users"""
        # Create a student to be deleted
        student_to_delete = create_user(role='student')
        # Create another student who will try to delete
        client, _ = auth_client(role='student')
        
        url = reverse('user-detail', args=[student_to_delete.id])
        response = client.delete(url)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        # Verify user still exists
        assert User.objects.filter(id=student_to_delete.id).exists()

    def test_delete_user_teacher(self, auth_client, create_user):
        """Test that teachers can delete users"""
        # Create a student to be deleted
        student_to_delete = create_user(role='student')
        # Create a teacher
        client, _ = auth_client(role='teacher')
        
        url = reverse('user-detail', args=[student_to_delete.id])
        response = client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        # Verify user was deleted
        assert not User.objects.filter(id=student_to_delete.id).exists() 