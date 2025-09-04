from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core import mail
from news_app.models import Publisher, Article, Newsletter
from django.db.utils import IntegrityError
from unittest.mock import patch
from django.conf import settings


CustomUser = get_user_model()


class CustomUserModelTest(TestCase):
    def setUp(self):
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

    def test_user_creation(self):
        self.assertEqual(self.reader.role, 'reader')
        self.assertEqual(self.journalist.role, 'journalist')
        self.assertEqual(self.editor.role, 'editor')

    def test_reader_specific_fields(self):
        publisher = Publisher.objects.create(name='Test Publisher')
        self.reader.subscribed_publishers.add(publisher)
        self.assertEqual(self.reader.subscribed_publishers.count(), 1)

        self.reader.subscribed_journalists.add(self.journalist)
        self.assertEqual(self.reader.subscribed_journalists.count(), 1)

    def test_journalist_specific_fields(self):
        article = Article.objects.create(
            title='Test Article',
            content='Test content',
            status='draft'
        )
        self.journalist.published_articles.add(article)
        self.assertEqual(self.journalist.published_articles.count(), 1)

        newsletter = Newsletter.objects.create(
            title='Test Newsletter',
            content='Test content',
            created_by=self.journalist
        )
        self.journalist.published_newsletters.add(newsletter)
        self.assertEqual(self.journalist.published_newsletters.count(), 1)

    def test_role_validation(self):
        with self.assertRaises(IntegrityError):
            CustomUser.objects.create_user(
                username='invalid',
                password='testpass123',
                role='invalid_role'
            )


class PublisherModelTest(TestCase):
    def setUp(self):
        self.editor = CustomUser.objects.create_user(
            username='editor1',
            password='testpass123',
            email='editor@example.com',
            role='editor'
        )
        self.journalist = CustomUser.objects.create_user(
            username='journalist1',
            password='testpass123',
            email='journalist@example.com',
            role='journalist'
        )
        self.publisher = Publisher.objects.create(
            name='Test Publisher',
            description='Test description'
        )

    def test_publisher_creation(self):
        self.assertEqual(str(self.publisher), 'Test Publisher')

    def test_publisher_relationships(self):
        self.publisher.editors.add(self.editor)
        self.publisher.journalists.add(self.journalist)

        self.assertEqual(self.publisher.editors.count(), 1)
        self.assertEqual(self.publisher.journalists.count(), 1)
        self.assertEqual(self.editor.managed_publishers.count(), 1)
        self.assertEqual(self.journalist.affiliated_publishers.count(), 1)


class ArticleModelTest(TestCase):
    def setUp(self):
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
        self.publisher = Publisher.objects.create(name='Test Publisher')
        self.publisher.editors.add(self.editor)

        self.article = Article.objects.create(
            title='Test Article',
            content='Test content',
            status='draft',
            publisher=self.publisher
        )
        self.article.authors.add(self.journalist)

    def test_article_creation(self):
        self.assertEqual(str(self.article), 'Test Article')
        self.assertEqual(self.article.status, 'draft')
        self.assertEqual(self.article.authors.count(), 1)

    def test_article_approval(self):
        self.article.status = 'published'
        self.article.approved_by = self.editor
        self.article.save()

        self.assertEqual(self.article.status, 'published')
        self.assertEqual(self.article.approved_by, self.editor)

    def test_article_slug(self):
        self.assertTrue(self.article.slug)
        self.assertEqual(self.article.slug, 'test-article')


class NewsletterModelTest(TestCase):
    def setUp(self):
        self.journalist = CustomUser.objects.create_user(
            username='journalist1',
            password='testpass123',
            email='journalist@example.com',
            role='journalist'
        )
        self.publisher = Publisher.objects.create(name='Test Publisher')

        self.newsletter = Newsletter.objects.create(
            title='Test Newsletter',
            content='Test content',
            created_by=self.journalist,
            publisher=self.publisher
        )

    def test_newsletter_creation(self):
        self.assertEqual(str(self.newsletter), 'Test Newsletter')
        self.assertEqual(self.newsletter.created_by, self.journalist)
        self.assertEqual(self.newsletter.publisher, self.publisher)


class ArticleSignalTest(TestCase):
    def setUp(self):
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
        self.publisher = Publisher.objects.create(name='Test Publisher')
        self.publisher.editors.add(self.editor)

        self.article = Article.objects.create(
            title='Test Article',
            content='Test content',
            status='submitted',
            publisher=self.publisher
        )
        self.article.authors.add(self.journalist)

        # Set up subscriptions
        self.reader.subscribed_publishers.add(self.publisher)
        self.reader.subscribed_journalists.add(self.journalist)

    def test_email_notifications(self):
        """Test that emails are sent correctly when an article is approved"""
        mail.outbox = []  # Clear test inbox

        # Use locmem backend for testing
        with self.settings(
            EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
            DEFAULT_FROM_EMAIL=settings.DEFAULT_FROM_EMAIL,  # 'webmaster@localhost'
            SITE_URL=settings.SITE_URL  # 'http://127.0.0.1:8000'
        ):
            # Publish the article
            self.article.status = 'published'
            self.article.approved_by = self.editor
            self.article.save()

            # Verify emails were sent
            self.assertEqual(len(mail.outbox), 2)  # One for publisher subscribers, one for journalist subscribers

            # Verify email contents
            for email in mail.outbox:
                self.assertEqual(email.subject, f"New Article Published: {self.article.title}")
                self.assertIn(self.article.title, email.body)
                self.assertIn(settings.SITE_URL, email.body)
                self.assertIn('unsubscribe', email.body.lower())

            # Verify recipients
            recipients = [email.to[0] for email in mail.outbox]
            self.assertIn(self.reader.email, recipients)

    def test_no_emails_on_non_publish(self):
        """Test that no emails are sent when status isn't 'published'"""
        mail.outbox = []  # Clear test inbox
        self.article.status = 'submitted'
        self.article.save()
        self.assertEqual(len(mail.outbox), 0)

    @patch('tweepy.Client')
    def test_twitter_post_on_approval(self, mock_twitter):
        """Test Twitter posting on article approval"""
        # Configure test Twitter credentials
        with self.settings(
            TWITTER_API_KEY=settings.TWITTER_API_KEY,
            TWITTER_API_SECRET=settings.TWITTER_API_SECRET,
            TWITTER_ACCESS_TOKEN=settings.TWITTER_ACCESS_TOKEN,
            TWITTER_ACCESS_TOKEN_SECRET=settings.TWITTER_ACCESS_TOKEN_SECRET,
            SITE_URL=settings.SITE_URL
        ):
            # Publish the article
            self.article.status = 'published'
            self.article.approved_by = self.editor
            self.article.save()

            # Verify Twitter API was called
            mock_twitter.return_value.create_tweet.assert_called_once()
            tweet_text = mock_twitter.return_value.create_tweet.call_args[1]['text']
            self.assertIn(self.article.title, tweet_text)
            self.assertIn(settings.SITE_URL, tweet_text)
