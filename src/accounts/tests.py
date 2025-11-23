from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User


class DeleteAccountTests(APITestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username='student1',
			password='pass1234',
			name='Student One'
		)
		self.admin = User.objects.create_superuser(
			username='admin',
			password='adminpass',
			email='admin@example.com'
		)
		self.url = reverse('accounts:delete-account')

	def test_authenticated_student_can_delete_account(self):
		self.client.force_authenticate(user=self.user)
		response = self.client.delete(self.url)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertFalse(User.objects.filter(username='student1').exists())

	def test_unauthenticated_request_is_rejected(self):
		response = self.client.delete(self.url)
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_admin_cannot_use_student_delete_endpoint(self):
		self.client.force_authenticate(user=self.admin)
		response = self.client.delete(self.url)
		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
		self.assertTrue(User.objects.filter(username='admin').exists())
