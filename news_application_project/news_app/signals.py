from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
import logging
import tweepy
from .models import Article

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Article)
def handle_article_approval(sender, instance, created, **kwargs):
    if instance.status == 'published' and instance.approved_by:
        subscribers = set()
        if instance.publisher:
            subscribers.update(instance.publisher.subscribers.all())
        for author in instance.authors.all():
            subscribers.update(author.followers.all())
        for subscriber in subscribers:
            if subscriber.email:
                try:
                    send_mail(
                        f"New Article Published: {instance.title}",
                        f"Check out the new article: {instance.title}\n\n{getattr(settings, 'SITE_URL', '')}{instance.get_absolute_url()}",
                        getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                        [subscriber.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    logger.error(f"Failed to send email to {subscriber.email}: {e}")

        twitter_keys = [
            'TWITTER_API_KEY',
            'TWITTER_API_SECRET',
            'TWITTER_ACCESS_TOKEN',
            'TWITTER_ACCESS_TOKEN_SECRET'
        ]
        if all(hasattr(settings, key) for key in twitter_keys):
            try:
                client = tweepy.Client(
                    consumer_key=getattr(settings, 'TWITTER_API_KEY'),
                    consumer_secret=getattr(settings, 'TWITTER_API_SECRET'),
                    access_token=getattr(settings, 'TWITTER_ACCESS_TOKEN'),
                    access_token_secret=getattr(settings, 'TWITTER_ACCESS_TOKEN_SECRET')
                )
                tweet_text = f"New article: {instance.title}\n{getattr(settings, 'SITE_URL', '')}{instance.get_absolute_url()}"
                client.create_tweet(text=tweet_text)
            except Exception as e:
                logger.error(f"Failed to post to Twitter: {e}")
