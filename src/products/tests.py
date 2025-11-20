from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from .models import Category, Subject, Teacher, Product, Pill, PillItem, PurchasedBook
class PurchasedBookTests(APITestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username='student',
			password='pass1234',
			name='Student User'
		)
		self.client.force_authenticate(user=self.user)

		self.category = Category.objects.create(name='Science')
		self.subject = Subject.objects.create(name='Chemistry')
		self.teacher = Teacher.objects.create(name='Dr. Smith', subject=self.subject)
		self.product = Product.objects.create(
			name='Chemistry 101',
			price=150,
			category=self.category,
			subject=self.subject,
			teacher=self.teacher
		)

		self.pill = Pill.objects.create(user=self.user, status='i')
		item = PillItem.objects.create(
			pill=self.pill,
			user=self.user,
			product=self.product,
			status='p'
		)
		self.pill.items.add(item)

		self.pill.status = 'p'
		self.pill.save()

	def test_purchased_book_created_when_pill_paid(self):
		purchased_book = PurchasedBook.objects.filter(user=self.user).first()
		self.assertIsNotNone(purchased_book)
		self.assertEqual(purchased_book.product, self.product)
		self.assertEqual(purchased_book.pill, self.pill)
		self.assertEqual(purchased_book.product_name, self.product.name)

	def test_my_books_endpoint_returns_purchased_books(self):
		url = reverse('products:purchased-books')
		response = self.client.get(url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['count'], 1)
		self.assertEqual(len(response.data['results']), 1)

		payload = response.data['results'][0]
		book = PurchasedBook.objects.get()
		self.assertEqual(payload['book_id'], book.id)
		self.assertEqual(payload['product_id'], self.product.id)
		self.assertEqual(payload['name'], self.product.name)
		self.assertEqual(payload['pill_number'], self.pill.pill_number)
		self.assertEqual(payload['category_name'], self.category.name)

	def test_book_owned_check_endpoint(self):
		url = reverse('products:book-owned-check', args=[self.product.product_number])
		response = self.client.get(url)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertTrue(response.data['owned'])
		self.assertEqual(response.data['product_id'], self.product.id)
		self.assertEqual(response.data['product_number'], self.product.product_number)

		# Another product should return false
		other_product = Product.objects.create(name='Physics 101', price=200)
		url = reverse('products:book-owned-check', args=[other_product.product_number])
		response = self.client.get(url)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertFalse(response.data['owned'])
		self.assertEqual(response.data['product_id'], other_product.id)
		self.assertEqual(response.data['product_number'], other_product.product_number)

	def test_pill_creation_filters_owned_products(self):
		owned_product = Product.objects.create(name='Owned Book', price=100)
		pill = Pill.objects.create(user=self.user, status='p')
		item = PillItem.objects.create(
			pill=pill,
			user=self.user,
			product=owned_product,
			status='p'
		)
		pill.items.add(item)
		PurchasedBook.objects.create(
			user=self.user,
			pill=pill,
			product=owned_product,
			pill_item=item,
			product_name=owned_product.name
		)

		new_product = Product.objects.create(name='New Book', price=120)
		payload = {
			'items': [
				{'product': owned_product.id},
				{'product': new_product.id},
			]
		}

		response = self.client.post(reverse('products:pill-create'), payload, format='json')
		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(len(response.data['items']), 1)
		self.assertEqual(response.data['items'][0]['product']['id'], new_product.id)

	def test_pill_creation_rejects_all_owned_products(self):
		product = Product.objects.create(name='Owned Book', price=100)
		pill = Pill.objects.create(user=self.user, status='p')
		item = PillItem.objects.create(
			pill=pill,
			user=self.user,
			product=product,
			status='p'
		)
		pill.items.add(item)
		PurchasedBook.objects.create(
			user=self.user,
			pill=pill,
			product=product,
			pill_item=item,
			product_name=product.name
		)

		payload = {
			'items': [
				{'product': product.id}
			]
		}

		response = self.client.post(reverse('products:pill-create'), payload, format='json')
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('items', response.data)
		self.assertIn('already owned', response.data['items'][0])

	def test_add_free_book_success(self):
		free_product = Product.objects.create(
			name='Free Book',
			price=0,
			category=self.category,
			subject=self.subject,
			teacher=self.teacher
		)

		url = reverse('products:add-free-book', args=[free_product.product_number])
		response = self.client.post(url)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertTrue(PurchasedBook.objects.filter(user=self.user, product=free_product).exists())
		self.assertEqual(response.data['product_id'], free_product.id)

	def test_add_free_book_requires_free_price(self):
		url = reverse('products:add-free-book', args=[self.product.product_number])
		response = self.client.post(url)
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('not free', response.data['detail'])

	def test_add_free_book_prevents_duplicates(self):
		free_product = Product.objects.create(
			name='Another Free Book',
			price=0,
			category=self.category,
			subject=self.subject,
			teacher=self.teacher
		)

		url = reverse('products:add-free-book', args=[free_product.product_number])
		first_response = self.client.post(url)
		self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)

		second_response = self.client.post(url)
		self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('already exists', second_response.data['detail'])
