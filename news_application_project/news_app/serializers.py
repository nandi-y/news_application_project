from rest_framework import serializers
from news_app.models import Article, Publisher, Newsletter, CustomUser


class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'role']


class PublisherSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publisher
        fields = ['id', 'name', 'description', 'website']


class ArticleSerializer(serializers.ModelSerializer):
    authors = CustomUserSerializer(many=True, read_only=True)
    publisher = PublisherSerializer(read_only=True)
    approved_by = CustomUserSerializer(read_only=True)

    class Meta:
        model = Article
        fields = [
            'id', 'title', 'slug', 'content', 'status', 'created_at', 'updated_at',
            'publisher', 'authors', 'approved_by', 'featured_image'
        ]


class NewsletterSerializer(serializers.ModelSerializer):
    publisher = PublisherSerializer(read_only=True)
    created_by = CustomUserSerializer(read_only=True)

    class Meta:
        model = Newsletter
        fields = [
            'id', 'title', 'content', 'created_at', 'sent_at', 'publisher', 'created_by'
        ]


class SubscriptionSerializer(serializers.Serializer):
    publisher_id = serializers.IntegerField(required=False)
    journalist_id = serializers.IntegerField(required=False)

    def validate(self, data):
        if not data.get('publisher_id') and not data.get('journalist_id'):
            raise serializers.ValidationError("Either publisher_id or journalist_id must be provided.")
        return data
