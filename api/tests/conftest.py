import os
import pytest
import django
import uuid

# Ensure Django is configured before importing DRF components
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gradar.test_settings')
django.setup()

from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from api.models import Group

User = get_user_model()

@pytest.fixture(autouse=True)
def clean_database():
    """Clean database before each test"""
    User.objects.all().delete()
    Group.objects.all().delete()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def create_user():
    def make_user(username=None, password='testpass123', role='student', **kwargs):
        if username is None:
            username = f'testuser_{uuid.uuid4().hex}'
        email = kwargs.pop('email', f'{username}@example.com')
        return User.objects.create_user(
            username=username,
            password=password,
            role=role,
            email=email,
            **kwargs
        )
    return make_user

@pytest.fixture
def get_or_create_token():
    def make_token(user):
        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
    return make_token

@pytest.fixture
def auth_client(api_client, create_user, get_or_create_token):
    def get_auth_client(user=None, role='student'):
        if user is None:
            username = f'testuser_{role}_{uuid.uuid4().hex}'
            user = create_user(
                username=username,
                role=role,
                email=f'{username}@example.com'
            )
        token = get_or_create_token(user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token["access"]}')
        return api_client, user
    return get_auth_client

@pytest.fixture
def test_group(auth_client):
    client, teacher = auth_client(role='teacher')
    group_name = f'Test Group {uuid.uuid4().hex}'
    group_data = {
        'name': group_name,
        'description': 'Test group description'
    }
    response = client.post('/api/groups/', group_data)
    assert response.status_code == 201, f"Failed to create test group: {response.json()}"
    return response.json() 