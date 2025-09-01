# news_app/urls.py
from django.urls import path, include
from django.contrib.auth import views as auth_views
from news_app import views
from rest_framework import routers

# Create a router and register our viewsets with it.
router = routers.DefaultRouter()
router.register(r'articles', views.ArticleViewSet)
router.register(r'publishers', views.PublisherViewSet)
router.register(r'users', views.CustomUserViewSet)

urlpatterns = [
    path('search/', views.search, name='search'),
    path('', views.ArticleListView.as_view(), name='article_list'),
    path('article/create/', views.ArticleCreateView.as_view(), name='article_create'),
    path('article/<slug:slug>/', views.ArticleDetailView.as_view(), name='article_detail'),
    path('article/<slug:slug>/edit/', views.ArticleUpdateView.as_view(), name='article_edit'),
    path('article/<slug:slug>/delete/', views.ArticleDeleteView.as_view(), name='article_delete'),
    path('approval/', views.ApprovalListView.as_view(), name='approval_list'),
    path('subscriptions/', views.manage_subscriptions, name='manage_subscriptions'),
    path('api/articles/', views.ArticleAPIView.as_view(), name='api_articles'),
    path('api/newsletters/', views.NewsletterAPIView.as_view(), name='api_newsletters'),
    path('api/test-twitter/', views.test_twitter_connection, name='test_twitter'),
    path('api/test-db/', views.test_db, name='test_db'),
    path('api/', include(router.urls)),
    path('login/', auth_views.LoginView.as_view(template_name='news_app/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('register/', views.register, name='register'),
    path('search/', views.search, name='search')
]
