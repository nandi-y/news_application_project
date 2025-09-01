# news_app/tests/test_api.py
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from news_app.models import Publisher, Article, Newsletter
from unittest.mock import patch

CustomUser = get_user_model()


class ArticleAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create users
        self.reader = CustomUser.objects.create_user(
            username='reader1',
            password='testpass123',
            email='reader@example.com',
            role='reader'
        )
        self.journalist = CustomUser.objects.create_user(
            username='journalist1',
            password='testpass123',
            email='journalist@example.com',
            role='journalist'
        )
        self.editor = CustomUser.objects.create_user(
            username='editor1',
            password='testpass123',
            email='editor@example.com',
            role='editor'
        )

        # Create publisher
        self.publisher = Publisher.objects.create(name='Test Publisher')
        self.publisher.editors.add(self.editor)
        self.publisher.journalists.add(self.journalist)

        # Create articles
        self.published_article1 = Article.objects.create(
            title='Published Article 1',
            content='Published content 1',
            status='published',
            publisher=self.publisher,
            approved_by=self.editor
        )
        self.published_article1.authors.add(self.journalist)

        self.published_article2 = Article.objects.create(
            title='Published Article 2',
            content='Published content 2',
            status='published',
            approved_by=self.editor
        )
        self.published_article2.authors.add(self.journalist)

        # Set up subscriptions
        self.reader.subscribed_publishers.add(self.publisher)
        self.reader.subscribed_journalists.add(self.journalist)

        # Authenticate client
        self.client.force_authenticate(user=self.reader)

    def test_get_articles_by_publisher(self):
        url = reverse('api_articles')
        response = self.client.get(url, {'publisher_id': self.publisher.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Published Article 1')

    def test_get_articles_by_journalist(self):
        url = reverse('api_articles')
        response = self.client.get(url, {'journalist_id': self.journalist.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        titles = [article['title'] for article in response.data]
        self.assertIn('Published Article 1', titles)
        self.assertIn('Published Article 2', titles)

    def test_get_articles_requires_authentication(self):
        self.client.force_authenticate(user=None)
        url = reverse('api_articles')
        response = self.client.get(url, {'publisher_id': self.publisher.id})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_articles_requires_subscription_param(self):
        url = reverse('api_articles')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('news_app.signals.tweepy.Client')
    def test_article_approval_flow(self, mock_twitter):
        # Test API approval flow
        self.client.force_authenticate(user=self.editor)
        url = reverse('article_update', kwargs={'slug': self.published_article1.slug})
        response = self.client.patch(url, {
            'status': 'published',
            'approved_by': self.editor.id
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_twitter.return_value.create_tweet.assert_called_once()


class NewsletterAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create users
        self.reader = CustomUser.objects.create_user(
            username='reader1',
            password='testpass123',
            email='reader@example.com',
            role='reader'
        )
        self.journalist = CustomUser.objects.create_user(
            username='journalist1',
            password='testpass123',
            email='journalist@example.com',
            role='journalist'
        )

        # Create publisher
        self.publisher = Publisher.objects.create(name='Test Publisher')

        # Create newsletters
        self.newsletter1 = Newsletter.objects.create(
            title='Newsletter 1',
            content='Content 1',
            publisher=self.publisher,
            created_by=self.journalist
        )

        self.newsletter2 = Newsletter.objects.create(
            title='Newsletter 2',
            content='Content 2',
            created_by=self.journalist
        )

        # Authenticate client
        self.client.force_authenticate(user=self.reader)

    def test_get_newsletters_by_publisher(self):
        url = reverse('api_newsletters')
        response = self.client.get(url, {'publisher_id': self.publisher.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Newsletter 1')

    def test_get_newsletters_by_journalist(self):
        url = reverse('api_newsletters')
        response = self.client.get(url, {'journalist_id': self.journalist.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        titles = [newsletter['title'] for newsletter in response.data]
        self.assertIn('Newsletter 1', titles)
        self.assertIn('Newsletter 2', titles)

    def test_get_newsletters_requires_authentication(self):
        self.client.force_authenticate(user=None)
        url = reverse('api_newsletters')
        response = self.client.get(url, {'publisher_id': self.publisher.id})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_newsletters_requires_subscription_param(self):
        url = reverse('api_newsletters')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
