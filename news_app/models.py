# news_app/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.urls import reverse
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.core.validators import MinLengthValidator, MaxLengthValidator
from django.utils import timezone
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
import uuid

# Custom User Model


class CustomUser(AbstractUser):
    """Custom user model with extended fields and role-based logic."""
    ROLE_CHOICES = (
        ('reader', 'Reader'),
        ('journalist', 'Journalist'),
        ('editor', 'Editor'),
        ('admin', 'Administrator'),
    )
    
    # Enhanced user fields
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='reader')
    bio = models.TextField(max_length=500, blank=True, help_text="Brief description about yourself")
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True)
    website = models.URLField(blank=True)
    location = models.CharField(max_length=100, blank=True)
    is_verified = models.BooleanField(default=False, help_text="Verified journalist/editor")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Reader fields
    subscribed_publishers = models.ManyToManyField('Publisher', blank=True, related_name='subscribers')
    subscribed_journalists = models.ManyToManyField('CustomUser', blank=True, related_name='followers', limit_choices_to={'role': 'journalist'})
    preferred_categories = models.ManyToManyField('Category', blank=True, related_name='preferred_by')
    
    # Journalist fields
    published_articles = models.ManyToManyField('Article', blank=True, related_name='independent_authors')
    published_newsletters = models.ManyToManyField('Newsletter', blank=True, related_name='independent_newsletters')
    
    # Analytics fields
    total_views = models.PositiveIntegerField(default=0)
    total_likes = models.PositiveIntegerField(default=0)

    def save(self, *args, **kwargs):
        # Resize profile image if it exists
        if self.profile_image:
            img = Image.open(self.profile_image)
            if img.height > 300 or img.width > 300:
                output_size = (300, 300)
                img.thumbnail(output_size)
                # Save back to the same file
                img_io = BytesIO()
                img.save(img_io, format='JPEG', quality=85)
                self.profile_image.save(
                    self.profile_image.name,
                    ContentFile(img_io.getvalue()),
                    save=False
                )
        
        super().save(*args, **kwargs)
        
        # Role-specific field management
        if self.role == 'reader':
            self.published_articles.clear()
            self.published_newsletters.clear()
        elif self.role == 'journalist':
            pass  # Journalists can have subscriptions too
        
        # Assign to group
        group, _ = Group.objects.get_or_create(name=self.role.capitalize())
        self.groups.clear()
        self.groups.add(group)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username
    
    @property
    def article_count(self):
        return self.articles.filter(status='published').count()
    
    @property
    def follower_count(self):
        return self.followers.count()


class Category(models.Model):
    """Model representing news categories for better organization."""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#007bff', help_text="Hex color code for the category")
    icon = models.CharField(max_length=50, blank=True, help_text="Font Awesome icon class")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name
    
    @property
    def article_count(self):
        return self.articles.filter(status='published').count()


class Publisher(models.Model):
    name = models.CharField(max_length=100, validators=[MinLengthValidator(2)])
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(validators=[MinLengthValidator(10)])
    editors = models.ManyToManyField(CustomUser, related_name='managed_publishers', limit_choices_to={'role': 'editor'})
    journalists = models.ManyToManyField(CustomUser, related_name='affiliated_publishers', limit_choices_to={'role': 'journalist'})
    logo = models.ImageField(upload_to='publisher_logos/', blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    established_date = models.DateField(blank=True, null=True)
    contact_email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Social media links
    twitter_handle = models.CharField(max_length=50, blank=True)
    facebook_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    
    # Analytics
    total_articles = models.PositiveIntegerField(default=0)
    total_subscribers = models.PositiveIntegerField(default=0)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
    
    @property
    def published_articles_count(self):
        return self.articles.filter(status='published').count()
    
    @property
    def subscriber_count(self):
        return self.subscribers.count()
        return self.name



class Article(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('published', 'Published'),
        ('rejected', 'Rejected'),
        ('archived', 'Archived'),
    )
    
    PRIORITY_CHOICES = (
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('breaking', 'Breaking News'),
    )
    
    # Basic fields
    title = models.CharField(max_length=200, validators=[MinLengthValidator(5)])
    subtitle = models.CharField(max_length=300, blank=True, help_text="Optional subtitle")
    content = models.TextField(validators=[MinLengthValidator(100)])
    excerpt = models.TextField(max_length=500, blank=True, help_text="Brief summary for previews")
    
    # Media
    featured_image = models.ImageField(upload_to='article_images/', blank=True, null=True)
    featured_image_alt = models.CharField(max_length=200, blank=True, help_text="Alt text for accessibility")
    
    # Categorization and relationships
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='articles')
    tags = models.CharField(max_length=500, blank=True, help_text="Comma-separated tags")
    publisher = models.ForeignKey(Publisher, on_delete=models.SET_NULL, null=True, blank=True, related_name='articles')
    authors = models.ManyToManyField(CustomUser, related_name='articles')
    approved_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name='approved_articles', limit_choices_to={'role__in': ['editor', 'admin']})
    
    # Status and metadata
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    
    # SEO fields
    meta_description = models.CharField(max_length=160, blank=True, help_text="SEO meta description")
    meta_keywords = models.CharField(max_length=255, blank=True, help_text="SEO keywords")
    
    # Analytics
    view_count = models.PositiveIntegerField(default=0)
    like_count = models.PositiveIntegerField(default=0)
    share_count = models.PositiveIntegerField(default=0)
    comment_count = models.PositiveIntegerField(default=0)
    
    # Settings
    allow_comments = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text="Feature this article on homepage")
    is_sticky = models.BooleanField(default=False, help_text="Keep at top of listings")
    reading_time = models.PositiveIntegerField(default=0, help_text="Estimated reading time in minutes")

    def save(self, *args, **kwargs):
        # Auto-generate slug if not provided
        if not self.slug and self.title:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Article.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        
        # Auto-generate excerpt if not provided
        if not self.excerpt and self.content:
            # Remove HTML tags and truncate to 200 characters
            import re
            clean_content = re.sub('<[^<]+?>', '', self.content)
            self.excerpt = clean_content[:200] + "..." if len(clean_content) > 200 else clean_content
        
        # Calculate reading time (average 200 words per minute)
        if self.content:
            word_count = len(self.content.split())
            self.reading_time = max(1, round(word_count / 200))
        
        # Set published date when status changes to published
        if self.status == 'published' and not self.published_at:
            from django.utils import timezone
            self.published_at = timezone.now()
        
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-is_sticky', '-created_at']
        permissions = [
            ('can_publish_article', 'Can publish article'),
            ('can_approve_article', 'Can approve article'),
            ('can_feature_article', 'Can feature article'),
        ]
        indexes = [
            models.Index(fields=['status', 'published_at']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['publisher', 'status']),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('article_detail', kwargs={'slug': self.slug})
    
    @property
    def tag_list(self):
        """Convert comma-separated tags to list"""
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
    
    @property
    def is_published(self):
        return self.status == 'published'
    
    @property
    def is_recent(self):
        """Check if article was published in the last 24 hours"""
        if not self.published_at:
            return False
        from django.utils import timezone
        return (timezone.now() - self.published_at).days < 1


class Comment(models.Model):
    """Article comments system"""
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='comments')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    content = models.TextField(validators=[MinLengthValidator(5)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_approved = models.BooleanField(default=True)
    like_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Comment by {self.author.username} on {self.article.title}"
    
    @property
    def is_reply(self):
        return self.parent is not None


class ArticleLike(models.Model):
    """Track article likes"""
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='liked_articles')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('article', 'user')
    
    def __str__(self):
        return f"{self.user.username} likes {self.article.title}"


class ReadingHistory(models.Model):
    """Track user reading history"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='reading_history')
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='readers')
    read_at = models.DateTimeField(auto_now_add=True)
    read_duration = models.PositiveIntegerField(default=0, help_text="Time spent reading in seconds")
    read_percentage = models.PositiveIntegerField(default=0, help_text="Percentage of article read")
    
    class Meta:
        unique_together = ('user', 'article')
        ordering = ['-read_at']
    
    def __str__(self):
        return f"{self.user.username} read {self.article.title}"


class Newsletter(models.Model):
    FREQUENCY_CHOICES = (
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('special', 'Special Edition'),
    )
    
    title = models.CharField(max_length=200, validators=[MinLengthValidator(5)])
    content = models.TextField(validators=[MinLengthValidator(50)])
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='weekly')
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    scheduled_for = models.DateTimeField(null=True, blank=True, help_text="Schedule newsletter for future sending")
    
    # Relationships
    publisher = models.ForeignKey(Publisher, on_delete=models.SET_NULL, null=True, blank=True, related_name='newsletters')
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, 
                                  related_name='created_newsletters', limit_choices_to={'role__in': ['journalist', 'editor']})
    articles = models.ManyToManyField(Article, blank=True, help_text="Featured articles in this newsletter")
    
    # Analytics
    sent_count = models.PositiveIntegerField(default=0)
    open_count = models.PositiveIntegerField(default=0)
    click_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    @property
    def is_sent(self):
        return self.sent_at is not None
    
    @property
    def open_rate(self):
        if self.sent_count == 0:
            return 0
        return round((self.open_count / self.sent_count) * 100, 2)

# Management command for setting up roles and permissions


class Command(BaseCommand):
    help = 'Set up user roles and permissions'

    def handle(self, *args, **options):
        roles = {
            'Reader': [],
            'Journalist': [
                'add_article', 'change_article', 'delete_article',
                'add_newsletter', 'change_newsletter', 'delete_newsletter'
            ],
            'Editor': [
                'change_article', 'delete_article',
                'change_newsletter', 'delete_newsletter',
                'can_publish_article', 'can_approve_article'
            ],
        }
        for role, perms in roles.items():
            group, _ = Group.objects.get_or_create(name=role)
            for perm_codename in perms:
                for model in ['article', 'newsletter']:
                    try:
                        perm = Permission.objects.get(codename=perm_codename, content_type__model=model)
                        group.permissions.add(perm)
                    except Permission.DoesNotExist:
                        continue
            self.stdout.write(self.style.SUCCESS(f'Group {role} set up.'))
