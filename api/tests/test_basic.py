import pytest
from django.urls import reverse
from rest_framework import status

@pytest.mark.django_db
class TestBasicAccess:
    def test_unauthorized_access(self, api_client):
        url = reverse('user-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_authorized_access(self, auth_client):
        client, user = auth_client()
        url = reverse('user-list')
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK 