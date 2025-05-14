import pytest
from django.urls import reverse
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.mark.django_db
class TestAuthentication:
    def test_user_registration(self, api_client):
        url = reverse('user-list')
        data = {
            'username': 'testuser',
            'password': 'testpass123',
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'role': 'student'
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert User.objects.filter(username='testuser').exists()

    def test_teacher_registration_by_teacher(self, auth_client):
        client, teacher = auth_client(role='teacher')
        url = reverse('user-list')
        data = {
            'username': 'newteacher',
            'password': 'testpass123',
            'email': 'newteacher@example.com',
            'role': 'teacher'
        }
        response = client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert User.objects.filter(username='newteacher', role='teacher').exists()

    def test_teacher_registration_by_student_forbidden(self, auth_client):
        client, student = auth_client(role='student')
        url = reverse('user-list')
        data = {
            'username': 'newteacher',
            'password': 'testpass123',
            'email': 'newteacher@example.com',
            'role': 'teacher'
        }
        response = client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_token_obtain(self, create_user, api_client):
        user = create_user(username='testuser', password='testpass123')
        url = reverse('token_obtain_pair')
        data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data

    def test_token_refresh(self, create_user, api_client, get_or_create_token):
        user = create_user(username='testuser', password='testpass123')
        tokens = get_or_create_token(user)
        url = reverse('token_refresh')
        data = {
            'refresh': tokens['refresh']
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data

    def test_invalid_token_refresh(self, api_client):
        url = reverse('token_refresh')
        data = {
            'refresh': 'invalid_token'
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_login_credentials(self, create_user, api_client):
        """Test that invalid login credentials return 401"""
        user = create_user(username='testuser', password='testpass123')
        url = reverse('token_obtain_pair')
        
        # Test with wrong password
        data = {
            'username': 'testuser',
            'password': 'wrongpass'
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Test with non-existent user
        data = {
            'username': 'nonexistent',
            'password': 'testpass123'
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED 