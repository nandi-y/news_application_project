from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from news_app.models import Publisher, Article
from django.contrib.messages import get_messages


CustomUser = get_user_model()


class ArticleViewsTest(TestCase):
    def setUp(self):
        self.client = Client()

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
        self.draft_article = Article.objects.create(
            title='Draft Article',
            content='Draft content',
            status='draft',
            publisher=self.publisher
        )
        self.draft_article.authors.add(self.journalist)

        self.published_article = Article.objects.create(
            title='Published Article',
            content='Published content',
            status='published',
            publisher=self.publisher,
            approved_by=self.editor
        )
        self.published_article.authors.add(self.journalist)

        self.submitted_article = Article.objects.create(
            title='Submitted Article',
            content='Submitted content',
            status='submitted',
            publisher=self.publisher
        )
        self.submitted_article.authors.add(self.journalist)

    def test_article_list_view_unauthenticated(self):
        response = self.client.get(reverse('article_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Published Article')
        self.assertNotContains(response, 'Draft Article')
        self.assertNotContains(response, 'Submitted Article')

    def test_article_list_view_reader(self):
        self.client.login(username='reader1', password='testpass123')
        response = self.client.get(reverse('article_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Published Article')
        self.assertNotContains(response, 'Draft Article')
        self.assertNotContains(response, 'Submitted Article')

    def test_article_list_view_journalist(self):
        self.client.login(username='journalist1', password='testpass123')
        response = self.client.get(reverse('article_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Published Article')
        self.assertContains(response, 'Draft Article')
        self.assertContains(response, 'Submitted Article')

    def test_article_list_view_editor(self):
        self.client.login(username='editor1', password='testpass123')
        response = self.client.get(reverse('article_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Published Article')
        self.assertContains(response, 'Draft Article')
        self.assertContains(response, 'Submitted Article')

    def test_article_detail_view(self):
        response = self.client.get(reverse('article_detail', kwargs={'slug': self.published_article.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Published Article')

    def test_article_create_view_journalist(self):
        self.client.login(username='journalist1', password='testpass123')
        response = self.client.get(reverse('article_create'))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(reverse('article_create'), {
            'title': 'New Article',
            'content': 'New content',
            'publisher': self.publisher.id
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Article.objects.filter(title='New Article').exists())

    def test_article_update_view_journalist(self):
        self.client.login(username='journalist1', password='testpass123')
        response = self.client.get(reverse('article_update', kwargs={'slug': self.draft_article.slug}))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(reverse('article_update', kwargs={'slug': self.draft_article.slug}), {
            'title': 'Updated Draft Article',
            'content': 'Updated content',
            'publisher': self.publisher.id,
            'status': 'submitted'
        })
        self.assertEqual(response.status_code, 302)
        self.draft_article.refresh_from_db()
        self.assertEqual(self.draft_article.title, 'Updated Draft Article')
        self.assertEqual(self.draft_article.status, 'submitted')

    def test_approval_list_view_editor(self):
        self.client.login(username='editor1', password='testpass123')
        response = self.client.get(reverse('approval_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Submitted Article')
        self.assertNotContains(response, 'Draft Article')
        self.assertNotContains(response, 'Published Article')

    def test_manage_subscriptions_view_reader(self):
        self.client.login(username='reader1', password='testpass123')
        response = self.client.get(reverse('manage_subscriptions'))
        self.assertEqual(response.status_code, 200)

        # Test subscribing to publisher
        response = self.client.post(reverse('manage_subscriptions'), {
            'action': 'subscribe',
            'publisher_id': self.publisher.id
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.publisher in self.reader.subscribed_publishers.all())

        # Test unsubscribing from publisher
        response = self.client.post(reverse('manage_subscriptions'), {
            'action': 'unsubscribe',
            'publisher_id': self.publisher.id
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.publisher in self.reader.subscribed_publishers.all())
 
    def test_article_create_permission_denied(self):
        # Reader should not be able to create articles
        self.client.login(username='reader1', password='testpass123')
        response = self.client.get(reverse('article_create'))
        self.assertEqual(response.status_code, 403)

    def test_article_update_permission_denied(self):
        # Reader should not be able to update articles
        article = Article.objects.create(title='Test', content='...', publisher=self.publisher, status='draft')
        article.authors.add(self.journalist)
        self.client.login(username='reader1', password='testpass123')
        response = self.client.get(reverse('article_edit', args=[article.slug]))
        self.assertEqual(response.status_code, 403)

    def test_subscription_feedback_message(self):
        self.client.login(username='reader1', password='testpass123')
        publisher_id = self.publisher.id
        response = self.client.post(reverse('manage_subscriptions'), {'action': 'subscribe', 'publisher_id': publisher_id})
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertTrue(any('subscribed' in msg.lower() for msg in messages))

    def test_api_articles_invalid_params(self):
        self.client.login(username='reader1', password='testpass123')
        response = self.client.get(reverse('api_articles'), {'invalid_param': 123})
        self.assertEqual(response.status_code, 400)
        self.assertIn('must be provided', response.json().get('detail', ''))

    def test_article_approval_workflow(self):
        self.client.login(username='editor1', password='testpass123')
        article = Article.objects.create(title='To Approve', content='...', publisher=self.publisher, status='submitted')
        response = self.client.post(reverse('approval_list'), {'article_id': article.id, 'action': 'approve'}, follow=True)
        article.refresh_from_db()
        self.assertEqual(response.status_code, 200)  # Should be 200 after redirect with follow=True
        self.assertEqual(article.status, 'published')
        self.assertEqual(article.approved_by, self.editor)
        # Check for feedback message if you use messages
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertTrue(any('approved' in msg.lower() or 'published' in msg.lower() for msg in messages))


class ApprovalFlowTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.editor = CustomUser.objects.create_user(
            username='editor1', password='testpass123', role='editor'
        )
        self.journalist = CustomUser.objects.create_user(
            username='journalist1', password='testpass123', role='journalist'
        )
        self.article = Article.objects.create(
            title='Test Article', content='Content', status='submitted'
        )
        self.article.authors.add(self.journalist)

    def test_approval_workflow(self):
        self.client.login(username='editor1', password='testpass123')
        response = self.client.post(reverse('approval_list'), {
            'article_id': self.article.id,
            'action': 'approve'
        })
        self.assertEqual(response.status_code, 302)
        self.article.refresh_from_db()
        self.assertEqual(self.article.status, 'published')
