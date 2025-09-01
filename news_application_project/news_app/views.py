

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets, permissions
from rest_framework.permissions import IsAuthenticated
from news_app.models import Article, Publisher, Newsletter, CustomUser
from news_app.serializers import ArticleSerializer, NewsletterSerializer, SubscriptionSerializer, PublisherSerializer, CustomUserSerializer
import tweepy
from django.conf import settings
from django.db import connection
from django.contrib import messages
from news_app.forms import CustomUserRegistrationForm


def search(request):
    """Search for articles by title using a query string from GET parameters."""
    query = request.GET.get('q')
    results = Article.objects.filter(title__icontains=query) if query else []
    return render(request, 'news_app/search_results.html', {'results': results, 'query': query})

# Registration view
def register(request):
    """Handle user registration via POST; display registration form on GET."""
    if request.method == 'POST':
        form = CustomUserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, "Registration successful! You can now log in.")
            return redirect('login')
    else:
        form = CustomUserRegistrationForm()
    return render(request, 'news_app/register.html', {'form': form})
    query = request.GET.get('q')
    if query:
        articles = Article.objects.filter(title__icontains=query)
    else:
        articles = Article.objects.none()
    return render(request, 'news_app/search.html', {'articles': articles, 'query': query})


# Regular Django Views


class ArticleListView(ListView):
    """Display a list of articles, filtered by user role if authenticated."""
    model = Article
    template_name = 'news_app/article_list.html'
    context_object_name = 'articles'

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_authenticated:
            if user.role == 'reader':
                queryset = queryset.filter(status='published')
                if user.subscribed_publishers.exists():
                    queryset = queryset.filter(publisher__in=user.subscribed_publishers.all())
                if user.subscribed_journalists.exists():
                    queryset = queryset.filter(authors__in=user.subscribed_journalists.all())
                if not user.subscribed_publishers.exists() and not user.subscribed_journalists.exists():
                    queryset = queryset.filter(status='published')
            elif user.role == 'journalist':
                queryset = queryset.filter(authors=user)
            elif user.role == 'editor':
                queryset = queryset.filter(publisher__in=user.managed_publishers.all())
        else:
            queryset = queryset.filter(status='published')
        return queryset.distinct().order_by('-created_at')


class ArticleDetailView(DetailView):
    model = Article
    template_name = 'news_app/article_detail.html'
    context_object_name = 'article'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'


class ArticleCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Article
    fields = ['title', 'content', 'publisher', 'featured_image']
    template_name = 'news_app/article_form.html'
    permission_required = 'news_app.add_article'

    def form_valid(self, form):
        if not form.instance.publisher:
            messages.error(self.request, "You must be affiliated with a publisher to create an article.")
            return self.form_invalid(form)
        form.instance.status = 'draft'
        response = super().form_valid(form)
        self.object.authors.add(self.request.user)
        return response

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.request.user.role == 'journalist':
            publishers = self.request.user.affiliated_publishers.all()
            form.fields['publisher'].queryset = publishers
            if not publishers.exists():
                form.fields['publisher'].disabled = True
                messages.warning(self.request, "You are not affiliated with any publishers. Contact an editor to be added.")
        return form


class ArticleUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Article
    fields = ['title', 'content', 'publisher', 'featured_image', 'status']
    template_name = 'news_app/article_form.html'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_permission_required(self):
        if self.get_object().status == 'published':
            return ['news_app.change_article', 'news_app.can_publish_article']
        return ['news_app.change_article']

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.request.user.role == 'journalist':
            form.fields['publisher'].queryset = self.request.user.affiliated_publishers.all()
            if self.get_object().status != 'draft':
                form.fields['status'].choices = [('submitted', 'Submitted')]
        elif self.request.user.role == 'editor':
            form.fields['status'].choices = [
                ('submitted', 'Submitted'),
                ('published', 'Published'),
                ('rejected', 'Rejected')
            ]
        return form

    def form_valid(self, form):
        if form.instance.status == 'published' and not form.instance.approved_by:
            form.instance.approved_by = self.request.user
        return super().form_valid(form)


class ArticleDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Article
    template_name = 'news_app/article_confirm_delete.html'
    success_url = reverse_lazy('article_list')
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    permission_required = 'news_app.delete_article'


class ApprovalListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Article
    template_name = 'news_app/approval_page.html'
    context_object_name = 'articles'
    permission_required = 'news_app.can_approve_article'

    def get_queryset(self):
        return Article.objects.filter(
            status='submitted',
            publisher__in=self.request.user.managed_publishers.all()
        ).order_by('-created_at')

    def post(self, request, *args, **kwargs):
        article_id = request.POST.get('article_id')
        action = request.POST.get('action')
        article = get_object_or_404(Article, id=article_id)
        if action == 'approve':
            article.status = 'published'
            article.approved_by = request.user
            article.save()
            messages.success(request, "Article approved and published.")
        elif action == 'reject':
            article.status = 'rejected'
            article.approved_by = request.user
            article.save()
            messages.warning(request, "Article rejected.")
        return redirect('approval_list')


@login_required
def manage_subscriptions(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        publisher_id = request.POST.get('publisher_id')
        journalist_id = request.POST.get('journalist_id')

        if action == 'subscribe':
            if publisher_id:
                publisher = get_object_or_404(Publisher, id=publisher_id)
                request.user.subscribed_publishers.add(publisher)
                messages.success(request, f"Subscribed to publisher {publisher.name}.")
            elif journalist_id:
                journalist = get_object_or_404(CustomUser, id=journalist_id, role='journalist')
                request.user.subscribed_journalists.add(journalist)
                messages.success(request, f"Subscribed to journalist {journalist.username}.")
        elif action == 'unsubscribe':
            if publisher_id:
                publisher = get_object_or_404(Publisher, id=publisher_id)
                request.user.subscribed_publishers.remove(publisher)
                messages.info(request, f"Unsubscribed from publisher {publisher.name}.")
            elif journalist_id:
                journalist = get_object_or_404(CustomUser, id=journalist_id, role='journalist')
                request.user.subscribed_journalists.remove(journalist)
                messages.info(request, f"Unsubscribed from journalist {journalist.username}.")

        return redirect('manage_subscriptions')

    publishers = Publisher.objects.all()
    journalists = CustomUser.objects.filter(role='journalist')
    return render(request, 'news_app/manage_subscriptions.html', {
        'publishers': publishers,
        'journalists': journalists,
    })

# API Views


class ArticleAPIView(APIView):
    """API endpoint for retrieving published articles, filtered by publisher or journalist."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get subscriptions from query params or request data
        serializer = SubscriptionSerializer(data=request.GET)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        articles = Article.objects.filter(status='published')

        if data.get('publisher_id'):
            articles = articles.filter(publisher_id=data['publisher_id'])
        elif data.get('journalist_id'):
            articles = articles.filter(authors__id=data['journalist_id'])

        serializer = ArticleSerializer(articles.distinct().order_by('-created_at'), many=True)
        return Response(serializer.data)


class NewsletterAPIView(APIView):
    """API endpoint for retrieving newsletters, filtered by publisher or journalist."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = SubscriptionSerializer(data=request.GET)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        newsletters = Newsletter.objects.all()

        if data.get('publisher_id'):
            newsletters = newsletters.filter(publisher_id=data['publisher_id'])
        elif data.get('journalist_id'):
            newsletters = newsletters.filter(created_by_id=data['journalist_id'])

        serializer = NewsletterSerializer(newsletters.order_by('-created_at'), many=True)
        return Response(serializer.data)


def test_twitter_connection(request):
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        client = tweepy.Client(bearer_token=settings.TWITTER_BEARER_TOKEN)
        user = client.get_me()
        return JsonResponse({
            'status': 'success',
            'account': user.data
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

# Test view


def test_db(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()
        return JsonResponse({'status': 'success', 'db_version': version[0]})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


class ArticleViewSet(viewsets.ModelViewSet):
    queryset = Article.objects.filter(status='published')
    serializer_class = ArticleSerializer
    permission_classes = [permissions.IsAuthenticated]


class CustomUserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [permissions.IsAdminUser]


class PublisherViewSet(viewsets.ModelViewSet):
    queryset = Publisher.objects.all()
    serializer_class = PublisherSerializer
    permission_classes = [permissions.IsAuthenticated]
