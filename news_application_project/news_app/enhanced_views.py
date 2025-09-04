# Enhanced views for the news application
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Count, Avg
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from news_app.models import (Article, Publisher, Newsletter, CustomUser, 
                           Category, Comment, ArticleLike, ReadingHistory)
from news_app.serializers import (ArticleSerializer, NewsletterSerializer, 
                                SubscriptionSerializer, PublisherSerializer, 
                                CustomUserSerializer)
from news_app.forms import CustomUserRegistrationForm, ArticleForm, CommentForm
import json
from datetime import datetime, timedelta

class EnhancedArticleListView(ListView):
    """
    Enhanced article list view for displaying articles with filtering, search, and pagination.
    """
    model = Article
    template_name = 'news_app/enhanced_article_list.html'
    context_object_name = 'articles'
    paginate_by = 12

    def get_queryset(self):
        queryset = Article.objects.select_related('publisher', 'category')
        queryset = queryset.prefetch_related('authors', 'likes')
        
        user = self.request.user
        search_query = self.request.GET.get('search', '')
        category_filter = self.request.GET.get('category', '')
        sort_by = self.request.GET.get('sort', '-published_at')
        
        # Apply user-specific filtering
        if user.is_authenticated:
            if user.role == 'reader':
                queryset = queryset.filter(status='published')
                # Show personalized feed based on subscriptions
                if user.subscribed_publishers.exists() or user.subscribed_journalists.exists():
                    publisher_articles = Q(publisher__in=user.subscribed_publishers.all())
                    journalist_articles = Q(authors__in=user.subscribed_journalists.all())
                    queryset = queryset.filter(publisher_articles | journalist_articles)
            elif user.role == 'journalist':
                # Show own articles and published articles
                queryset = queryset.filter(Q(authors=user) | Q(status='published'))
            elif user.role == 'editor':
                # Show articles from managed publishers
                queryset = queryset.filter(
                    Q(publisher__in=user.managed_publishers.all()) | 
                    Q(status='published')
                )
        else:
            queryset = queryset.filter(status='published')
        
        # Apply search filter
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(content__icontains=search_query) |
                Q(excerpt__icontains=search_query) |
                Q(tags__icontains=search_query)
            )
        
        # Apply category filter
        if category_filter:
            queryset = queryset.filter(category__slug=category_filter)
        
        # Apply sorting
        if sort_by == 'popular':
            queryset = queryset.annotate(
                popularity_score=Count('likes') + Count('comments') + models.F('view_count') / 10
            ).order_by('-popularity_score', '-published_at')
        elif sort_by == 'trending':
            # Articles with high engagement in the last 7 days
            week_ago = timezone.now() - timedelta(days=7)
            queryset = queryset.filter(published_at__gte=week_ago).annotate(
                trend_score=Count('likes') + Count('comments') * 2
            ).order_by('-trend_score', '-published_at')
        else:
            queryset = queryset.order_by(sort_by)
        
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.filter(is_active=True)
        context['current_category'] = self.request.GET.get('category', '')
        context['search_query'] = self.request.GET.get('search', '')
        context['current_sort'] = self.request.GET.get('sort', '-published_at')
        
        # Featured articles
        context['featured_articles'] = Article.objects.filter(
            is_featured=True, 
            status='published'
        ).order_by('-published_at')[:3]
        
        # Breaking news
        context['breaking_news'] = Article.objects.filter(
            priority='breaking',
            status='published'
        ).order_by('-published_at')[:5]
        
        return context


class EnhancedArticleDetailView(DetailView):
    """Enhanced article detail with comments, likes, and reading tracking"""
    model = Article
    template_name = 'news_app/enhanced_article_detail.html'
    context_object_name = 'article'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        """
        Returns a queryset of articles filtered by search, category, and sorted by published date.
        """
        return Article.objects.select_related('publisher', 'category').prefetch_related(
            'authors', 'comments__author', 'likes__user'
        )

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        article = self.object
        
        # Increment view count
        article.view_count += 1
        article.save(update_fields=['view_count'])
        
        # Track reading history for authenticated users
        if request.user.is_authenticated:
            ReadingHistory.objects.get_or_create(
                user=request.user,
                article=article,
                defaults={'read_at': timezone.now()}
            )
        
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        article = self.object
        user = self.request.user
        
        # Comments with replies
        comments = article.comments.filter(
            parent=None, 
            is_approved=True
        ).select_related('author').prefetch_related('replies__author')
        context['comments'] = comments
        context['comment_form'] = CommentForm()
        
        # Check if user has liked this article
        if user.is_authenticated:
            context['has_liked'] = ArticleLike.objects.filter(
                article=article, 
                user=user
            ).exists()
        
        # Related articles
        related_articles = Article.objects.filter(
            category=article.category,
            status='published'
        ).exclude(id=article.id)[:4]
        context['related_articles'] = related_articles
        
        # More from same author
        if article.authors.exists():
            main_author = article.authors.first()
            context['more_from_author'] = Article.objects.filter(
                authors=main_author,
                status='published'
            ).exclude(id=article.id)[:3]
        
        return context


@login_required
def like_article(request, slug):
    """
    Handles AJAX requests to like or unlike an article specified by slug.
    """
    if request.method == 'POST':
        article = get_object_or_404(Article, slug=slug)
        like, created = ArticleLike.objects.get_or_create(
            article=article,
            user=request.user
        )
        
        if not created:
            # Unlike the article
            like.delete()
            liked = False
            article.like_count = max(0, article.like_count - 1)
        else:
            # Like the article
            liked = True
            article.like_count += 1
        
        article.save(update_fields=['like_count'])
        
        return JsonResponse({
            'liked': liked,
            'like_count': article.like_count
        })
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)


@login_required
def add_comment(request, slug):
    """Add comment to article"""
    if request.method == 'POST':
        article = get_object_or_404(Article, slug=slug)
        form = CommentForm(request.POST)
        
        if form.is_valid():
            comment = form.save(commit=False)
            comment.article = article
            comment.author = request.user
            
            # Handle reply to another comment
            parent_id = request.POST.get('parent_id')
            if parent_id:
                comment.parent = get_object_or_404(Comment, id=parent_id)
            
            comment.save()
            
            # Update article comment count
            article.comment_count += 1
            article.save(update_fields=['comment_count'])
            
            messages.success(request, 'Comment added successfully!')
        else:
            messages.error(request, 'Please correct the errors in your comment.')
    
    return redirect('article_detail', slug=slug)


class EnhancedArticleCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Enhanced article creation with rich text editor and better validation"""
    model = Article
    form_class = ArticleForm
    template_name = 'news_app/enhanced_article_form.html'
    permission_required = 'news_app.add_article'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.status = 'draft'
        response = super().form_valid(form)
        self.object.authors.add(self.request.user)
        messages.success(self.request, 'Article created successfully!')
        return response


class CategoryListView(ListView):
    """List articles by category"""
    model = Article
    template_name = 'news_app/category_list.html'
    context_object_name = 'articles'
    paginate_by = 10

    def get_queryset(self):
        self.category = get_object_or_404(Category, slug=self.kwargs['category_slug'])
        return Article.objects.filter(
            category=self.category,
            status='published'
        ).select_related('publisher').prefetch_related('authors').order_by('-published_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = self.category
        return context


class SearchView(ListView):
    """Advanced search functionality"""
    model = Article
    template_name = 'news_app/search_results.html'
    context_object_name = 'articles'
    paginate_by = 10

    def get_queryset(self):
        query = self.request.GET.get('q', '')
        if not query:
            return Article.objects.none()
        
        # Advanced search across multiple fields
        articles = Article.objects.filter(
            Q(title__icontains=query) |
            Q(content__icontains=query) |
            Q(excerpt__icontains=query) |
            Q(tags__icontains=query) |
            Q(authors__first_name__icontains=query) |
            Q(authors__last_name__icontains=query) |
            Q(publisher__name__icontains=query),
            status='published'
        ).distinct().select_related('publisher', 'category').prefetch_related('authors')
        
        return articles.order_by('-published_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['total_results'] = self.get_queryset().count()
        return context


@login_required
def dashboard(request):
    """User dashboard with personalized content"""
    user = request.user
    context = {
        'user': user,
    }
    
    if user.role == 'reader':
        # Reading statistics
        context.update({
            'articles_read': ReadingHistory.objects.filter(user=user).count(),
            'liked_articles': ArticleLike.objects.filter(user=user).count(),
            'subscribed_publishers': user.subscribed_publishers.count(),
            'subscribed_journalists': user.subscribed_journalists.count(),
            'recent_articles': Article.objects.filter(
                Q(publisher__in=user.subscribed_publishers.all()) |
                Q(authors__in=user.subscribed_journalists.all()),
                status='published'
            ).distinct()[:5],
            'reading_history': ReadingHistory.objects.filter(user=user)[:10],
        })
    
    elif user.role == 'journalist':
        # Writing statistics
        user_articles = Article.objects.filter(authors=user)
        context.update({
            'total_articles': user_articles.count(),
            'published_articles': user_articles.filter(status='published').count(),
            'draft_articles': user_articles.filter(status='draft').count(),
            'pending_articles': user_articles.filter(status='submitted').count(),
            'total_views': sum(article.view_count for article in user_articles),
            'total_likes': sum(article.like_count for article in user_articles),
            'recent_articles': user_articles.order_by('-created_at')[:5],
        })
    
    elif user.role == 'editor':
        # Editorial statistics
        managed_publishers = user.managed_publishers.all()
        pending_approval = Article.objects.filter(
            publisher__in=managed_publishers,
            status='submitted'
        )
        context.update({
            'managed_publishers': managed_publishers.count(),
            'pending_approval': pending_approval.count(),
            'approved_this_month': Article.objects.filter(
                approved_by=user,
                approved_at__gte=timezone.now().replace(day=1)
            ).count(),
            'pending_articles': pending_approval[:10],
        })
    
    return render(request, 'news_app/dashboard.html', context)


# API Views for modern frontend integration
class EnhancedArticleAPIView(APIView):
    """Enhanced API for articles with filtering and pagination"""
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get(self, request):
        queryset = Article.objects.filter(status='published')
        
        # Filtering
        category = request.GET.get('category')
        if category:
            queryset = queryset.filter(category__slug=category)
        
        search = request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(content__icontains=search)
            )
        
        # Pagination
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        start = (page - 1) * page_size
        end = start + page_size
        
        articles = queryset[start:end]
        serializer = ArticleSerializer(articles, many=True)
        
        return Response({
            'articles': serializer.data,
            'total': queryset.count(),
            'page': page,
            'page_size': page_size
        })


def analytics_data(request):
    """Provide analytics data for charts and graphs"""
    if not request.user.is_authenticated or request.user.role not in ['editor', 'admin']:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    # Article publication trends
    thirty_days_ago = timezone.now() - timedelta(days=30)
    daily_articles = Article.objects.filter(
        published_at__gte=thirty_days_ago,
        status='published'
    ).extra({
        'day': 'date(published_at)'
    }).values('day').annotate(
        count=Count('id')
    ).order_by('day')
    
    # Category distribution
    category_data = Category.objects.annotate(
        article_count=Count('articles', filter=Q(articles__status='published'))
    ).values('name', 'article_count')
    
    # Top authors
    top_authors = CustomUser.objects.filter(
        role='journalist'
    ).annotate(
        article_count=Count('articles', filter=Q(articles__status='published')),
        total_views=models.Sum('articles__view_count'),
        total_likes=models.Sum('articles__like_count')
    ).order_by('-article_count')[:10]
    
    return JsonResponse({
        'daily_articles': list(daily_articles),
        'category_distribution': list(category_data),
        'top_authors': [{
            'username': author.username,
            'article_count': author.article_count,
            'total_views': author.total_views or 0,
            'total_likes': author.total_likes or 0
        } for author in top_authors]
    })
